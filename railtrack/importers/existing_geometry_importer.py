"""Importer for existing track geometry from surveyed point data.

Converts a polyline of surveyed points into alignment elements
(straights, circular arcs) by fitting geometric primitives to
the point cloud.

The algorithm:
1. Compute cumulative chainage and azimuths at each point.
2. Compute curvature at each point via 3-point circle fitting.
3. Segment the polyline by curvature: near-zero = straight, constant = arc.
4. Fit geometric elements to each segment.
5. Build an alignment with tangency-enforced elements.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from railtrack.domain.alignment import Alignment, ExistingTrackGeometry
from railtrack.domain.horizontal import (
    CircularArc,
    CurveDirection,
    HorizontalElementUnion,
    Straight,
    TransitionCurve,
)
from railtrack.domain.primitives import Point2D, Point3D, azimuth_from_dx_dy
from railtrack.geometry_engine.horizontal_engine import propagate_geometry


@dataclass
class _SegmentClassification:
    """Internal classification of a polyline segment."""
    start_idx: int
    end_idx: int
    segment_type: str  # "straight", "arc", "transition"
    radius: float      # inf for straight
    direction: CurveDirection | None


def import_existing_geometry(
    points: list[Point3D] | list[Point2D],
    name: str = "Imported",
    curvature_threshold: float = 1e-4,
    min_segment_points: int = 3,
    smoothing_window: int = 5,
) -> Alignment:
    """Convert surveyed points into an alignment with fitted elements.

    Args:
        points: Ordered list of survey points along the track centerline.
        name: Name for the resulting alignment.
        curvature_threshold: Below this curvature (1/m), segment is treated as straight.
        min_segment_points: Minimum number of points to form a segment.
        smoothing_window: Window size for curvature smoothing.

    Returns:
        Alignment with fitted horizontal elements.
    """
    if len(points) < 3:
        raise ValueError("Need at least 3 points to reconstruct geometry")

    pts_2d = _to_point2d_list(points)
    n = len(pts_2d)

    # Step 1: Compute chainages
    chainages = _compute_chainages(pts_2d)

    # Step 2: Compute curvature at each interior point
    curvatures = _compute_curvatures(pts_2d, smoothing_window)

    # Step 3: Classify segments
    segments = _classify_segments(curvatures, curvature_threshold, min_segment_points)

    # Step 4: Fit elements to segments
    elements = _fit_elements(pts_2d, chainages, segments)

    # Step 5: Propagate geometry for tangency
    if elements:
        elements = propagate_geometry(elements)

    alignment = Alignment(name=name)
    alignment.horizontal_elements = elements
    return alignment


def import_from_existing_track(
    existing: ExistingTrackGeometry,
    curvature_threshold: float = 1e-4,
    min_segment_points: int = 3,
) -> Alignment:
    """Convert an ExistingTrackGeometry object into a fitted alignment."""
    return import_existing_geometry(
        points=existing.points,
        name=existing.name,
        curvature_threshold=curvature_threshold,
        min_segment_points=min_segment_points,
    )


def _to_point2d_list(points: list) -> list[Point2D]:
    result = []
    for p in points:
        if isinstance(p, Point3D):
            result.append(p.to_2d())
        elif isinstance(p, Point2D):
            result.append(p)
        else:
            result.append(Point2D(float(p[0]), float(p[1])))
    return result


def _compute_chainages(pts: list[Point2D]) -> list[float]:
    chainages = [0.0]
    for i in range(1, len(pts)):
        chainages.append(chainages[-1] + pts[i - 1].distance_to(pts[i]))
    return chainages


def _compute_curvatures(pts: list[Point2D], window: int) -> list[float]:
    """Compute curvature at each point using 3-point circle fitting.

    Returns curvature with sign: positive = right turn, negative = left turn.
    Endpoints get the curvature of their nearest interior point.
    """
    n = len(pts)
    raw_curvatures = [0.0] * n

    for i in range(1, n - 1):
        raw_curvatures[i] = _curvature_3pt(pts[i - 1], pts[i], pts[i + 1])

    raw_curvatures[0] = raw_curvatures[1] if n > 1 else 0.0
    raw_curvatures[-1] = raw_curvatures[-2] if n > 1 else 0.0

    # Smooth curvatures
    if window > 1 and n > window:
        smoothed = list(raw_curvatures)
        half = window // 2
        for i in range(half, n - half):
            smoothed[i] = sum(raw_curvatures[i - half:i + half + 1]) / window
        return smoothed

    return raw_curvatures


def _curvature_3pt(p1: Point2D, p2: Point2D, p3: Point2D) -> float:
    """Compute signed curvature from 3 points using the Menger curvature formula.

    Sign convention: positive = clockwise (right turn in survey coords).
    """
    ax, ay = p1.x, p1.y
    bx, by = p2.x, p2.y
    cx, cy = p3.x, p3.y

    # Twice the signed area of the triangle
    twice_area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

    # Side lengths
    ab = math.hypot(bx - ax, by - ay)
    bc = math.hypot(cx - bx, cy - by)
    ca = math.hypot(ax - cx, ay - cy)

    denom = ab * bc * ca
    if denom < 1e-12:
        return 0.0

    # Curvature = 2 * area / (|AB| * |BC| * |CA|)
    # Sign follows the cross product (negative = right turn in math coords,
    # but in survey coords with x=east, y=north, we negate)
    return -2.0 * twice_area / denom


def _classify_segments(
    curvatures: list[float],
    threshold: float,
    min_points: int,
) -> list[_SegmentClassification]:
    """Classify consecutive points into straight/arc segments based on curvature."""
    n = len(curvatures)
    if n < 2:
        return []

    segments: list[_SegmentClassification] = []
    i = 0

    while i < n:
        if abs(curvatures[i]) < threshold:
            # Straight segment
            j = i
            while j < n and abs(curvatures[j]) < threshold:
                j += 1
            if j - i >= min_points:
                segments.append(_SegmentClassification(
                    start_idx=i, end_idx=j - 1,
                    segment_type="straight", radius=math.inf, direction=None,
                ))
            i = j
        else:
            # Curved segment - determine sign consistency
            sign = 1 if curvatures[i] > 0 else -1
            j = i
            curvature_sum = 0.0
            count = 0
            while j < n and abs(curvatures[j]) >= threshold * 0.5:
                # Allow some tolerance in sign (noisy data)
                if count > 2 and curvatures[j] * sign < -threshold:
                    break
                curvature_sum += curvatures[j]
                count += 1
                j += 1

            if j - i >= min_points:
                avg_curv = curvature_sum / max(count, 1)
                radius = abs(1.0 / avg_curv) if abs(avg_curv) > 1e-10 else math.inf
                direction = CurveDirection.RIGHT if avg_curv > 0 else CurveDirection.LEFT
                segments.append(_SegmentClassification(
                    start_idx=i, end_idx=j - 1,
                    segment_type="arc", radius=radius, direction=direction,
                ))
            i = j

    return segments


def _fit_elements(
    pts: list[Point2D],
    chainages: list[float],
    segments: list[_SegmentClassification],
) -> list[HorizontalElementUnion]:
    """Fit geometric elements to classified segments."""
    elements: list[HorizontalElementUnion] = []

    for seg in segments:
        start_pt = pts[seg.start_idx]
        end_pt = pts[seg.end_idx]
        start_ch = chainages[seg.start_idx]
        end_ch = chainages[seg.end_idx]
        length = end_ch - start_ch

        if length < 1e-6:
            continue

        # Compute azimuth from first two points of segment
        if seg.end_idx > seg.start_idx:
            p0 = pts[seg.start_idx]
            p1 = pts[min(seg.start_idx + 1, seg.end_idx)]
            dx = p1.x - p0.x
            dy = p1.y - p0.y
            azimuth = azimuth_from_dx_dy(dx, dy)
        else:
            azimuth = 0.0

        if seg.segment_type == "straight":
            elements.append(Straight(
                start_chainage=start_ch,
                length=length,
                start_point=start_pt,
                start_azimuth=azimuth,
            ))
        elif seg.segment_type == "arc" and seg.direction is not None:
            # Refine radius by least-squares circle fit
            seg_pts = pts[seg.start_idx:seg.end_idx + 1]
            refined_radius = _fit_circle_radius(seg_pts)
            if refined_radius is not None and refined_radius > 1.0:
                radius = refined_radius
            else:
                radius = seg.radius

            elements.append(CircularArc(
                start_chainage=start_ch,
                length=length,
                start_point=start_pt,
                start_azimuth=azimuth,
                radius=radius,
                direction=seg.direction,
            ))

    return elements


def _fit_circle_radius(pts: list[Point2D]) -> float | None:
    """Fit a circle to points using algebraic least-squares method.

    Returns the radius of the best-fit circle, or None if fitting fails.
    """
    n = len(pts)
    if n < 3:
        return None

    # Set up the least-squares system: (x-a)^2 + (y-b)^2 = r^2
    # Linearized: 2*a*x + 2*b*y + c = x^2 + y^2  where c = r^2 - a^2 - b^2
    xs = np.array([p.x for p in pts])
    ys = np.array([p.y for p in pts])

    A = np.column_stack([2 * xs, 2 * ys, np.ones(n)])
    b = xs ** 2 + ys ** 2

    try:
        result, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
        a, b_val, c = result
        radius = math.sqrt(c + a ** 2 + b_val ** 2)
        if radius > 1e6:  # Essentially straight
            return None
        return radius
    except (np.linalg.LinAlgError, ValueError):
        return None
