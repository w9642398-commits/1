"""Horizontal geometry computation engine.

Handles:
- Building horizontal alignment from element definitions
- Tangency checks and enforcement
- Chainage propagation
- Coordinate computation
- Geometry rebuilding after element changes
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from railtrack.domain.horizontal import (
    CircularArc,
    CurveDirection,
    HorizontalElementUnion,
    Straight,
    TransitionCurve,
)
from railtrack.domain.primitives import Point2D, normalize_angle


TANGENCY_TOLERANCE = 1e-4  # metres for position
AZIMUTH_TOLERANCE = 1e-6   # radians for azimuth


@dataclass
class TangencyError:
    """Describes a tangency break between two consecutive elements."""
    index: int
    position_gap: float
    azimuth_gap: float

    @property
    def is_position_break(self) -> bool:
        return self.position_gap > TANGENCY_TOLERANCE

    @property
    def is_azimuth_break(self) -> bool:
        return self.azimuth_gap > AZIMUTH_TOLERANCE


def check_tangency(
    elements: list[HorizontalElementUnion],
) -> list[TangencyError]:
    """Check tangency between consecutive elements."""
    errors: list[TangencyError] = []
    for i in range(len(elements) - 1):
        e1 = elements[i]
        e2 = elements[i + 1]
        pos_gap = e1.end_point.distance_to(e2.start_point)
        az_diff = abs(normalize_angle(e1.end_azimuth) - normalize_angle(e2.start_azimuth))
        az_gap = min(az_diff, 2 * math.pi - az_diff)
        if pos_gap > TANGENCY_TOLERANCE or az_gap > AZIMUTH_TOLERANCE:
            errors.append(TangencyError(i, pos_gap, az_gap))
    return errors


def check_chainage_continuity(
    elements: list[HorizontalElementUnion],
    tolerance: float = 1e-6,
) -> list[tuple[int, float]]:
    """Check that chainage is continuous (no gaps/overlaps).

    Returns list of (index, gap) where gap = next.start - prev.end.
    """
    issues = []
    for i in range(len(elements) - 1):
        gap = elements[i + 1].start_chainage - elements[i].end_chainage
        if abs(gap) > tolerance:
            issues.append((i, gap))
    return issues


def propagate_geometry(
    elements: list[HorizontalElementUnion],
) -> list[HorizontalElementUnion]:
    """Rebuild element chain ensuring tangent continuity.

    Takes the first element as fixed and propagates start_point,
    start_azimuth, and start_chainage through the chain.
    Each element's length, radius, direction etc. are preserved.
    """
    if not elements:
        return []

    result: list[HorizontalElementUnion] = [elements[0]]
    for i in range(1, len(elements)):
        prev = result[-1]
        elem = elements[i]
        new_start_chainage = prev.end_chainage
        new_start_point = prev.end_point
        new_start_azimuth = prev.end_azimuth

        if isinstance(elem, Straight):
            result.append(Straight(
                start_chainage=new_start_chainage,
                length=elem.length,
                start_point=new_start_point,
                start_azimuth=new_start_azimuth,
            ))
        elif isinstance(elem, CircularArc):
            result.append(CircularArc(
                start_chainage=new_start_chainage,
                length=elem.length,
                start_point=new_start_point,
                start_azimuth=new_start_azimuth,
                radius=elem.radius,
                direction=elem.direction,
            ))
        elif isinstance(elem, TransitionCurve):
            result.append(TransitionCurve(
                start_chainage=new_start_chainage,
                length=elem.length,
                start_point=new_start_point,
                start_azimuth=new_start_azimuth,
                radius_start=elem.radius_start,
                radius_end=elem.radius_end,
                direction=elem.direction,
            ))
    return result


def compute_points_along(
    elements: list[HorizontalElementUnion],
    interval: float = 10.0,
) -> list[tuple[float, Point2D]]:
    """Compute points at regular intervals along the alignment."""
    points = []
    if not elements:
        return points

    ch_start = elements[0].start_chainage
    ch_end = elements[-1].end_chainage
    ch = ch_start

    while ch <= ch_end + 1e-9:
        for elem in elements:
            if elem.chainage_range.contains(ch):
                points.append((ch, elem.point_at(ch)))
                break
        ch += interval

    # Always include the very end
    if points and abs(points[-1][0] - ch_end) > 1e-6:
        for elem in elements:
            if elem.chainage_range.contains(ch_end):
                points.append((ch_end, elem.point_at(ch_end)))
                break

    return points


def minimize_elements(
    elements: list[HorizontalElementUnion],
    position_tolerance: float = 1e-3,
    azimuth_tolerance: float = 1e-4,
    radius_tolerance: float = 0.1,
) -> list[HorizontalElementUnion]:
    """Minimize the number of elements by merging adjacent compatible ones.

    Merges:
    - Adjacent straights with same azimuth → single longer straight
    - Adjacent circular arcs with same radius and direction → single longer arc
    - Zero-length elements → removed

    Preserves tangency. Does NOT merge transition curves (clothoids), as their
    curvature function depends on position within the element.

    Returns a new propagated element list.
    """
    if len(elements) <= 1:
        return list(elements)

    merged: list[HorizontalElementUnion] = []
    i = 0

    while i < len(elements):
        elem = elements[i]

        # Skip zero-length elements
        if elem.length < 1e-9:
            i += 1
            continue

        # Try to merge with subsequent elements
        if isinstance(elem, Straight):
            combined_length = elem.length
            j = i + 1
            while j < len(elements):
                nxt = elements[j]
                if not isinstance(nxt, Straight):
                    break
                if nxt.length < 1e-9:
                    j += 1
                    continue
                # Check azimuth compatibility
                az_diff = abs(normalize_angle(elem.start_azimuth) - normalize_angle(nxt.start_azimuth))
                az_gap = min(az_diff, 2 * math.pi - az_diff)
                if az_gap > azimuth_tolerance:
                    break
                combined_length += nxt.length
                j += 1
            merged.append(Straight(
                start_chainage=elem.start_chainage,
                length=combined_length,
                start_point=elem.start_point,
                start_azimuth=elem.start_azimuth,
            ))
            i = j

        elif isinstance(elem, CircularArc):
            combined_length = elem.length
            j = i + 1
            while j < len(elements):
                nxt = elements[j]
                if not isinstance(nxt, CircularArc):
                    break
                if nxt.length < 1e-9:
                    j += 1
                    continue
                # Check radius and direction compatibility
                if nxt.direction != elem.direction:
                    break
                if abs(nxt.radius - elem.radius) > radius_tolerance:
                    break
                combined_length += nxt.length
                j += 1
            merged.append(CircularArc(
                start_chainage=elem.start_chainage,
                length=combined_length,
                start_point=elem.start_point,
                start_azimuth=elem.start_azimuth,
                radius=elem.radius,
                direction=elem.direction,
            ))
            i = j

        else:
            # Transition curves - cannot merge
            merged.append(elem)
            i += 1

    # Re-propagate to fix chainage and coordinates
    return propagate_geometry(merged)


def build_straight_curve_straight(
    start_point: Point2D,
    start_azimuth: float,
    start_chainage: float,
    straight1_length: float,
    transition1_length: float,
    arc_radius: float,
    arc_length: float,
    direction: CurveDirection,
    transition2_length: float,
    straight2_length: float,
) -> list[HorizontalElementUnion]:
    """Build a standard S-T-C-T-S (straight-transition-curve-transition-straight)
    element sequence and propagate geometry.

    This is the most common pattern in railway alignment design.
    """
    elements: list[HorizontalElementUnion] = []

    # Straight 1
    if straight1_length > 0:
        elements.append(Straight(
            start_chainage=start_chainage,
            length=straight1_length,
            start_point=start_point,
            start_azimuth=start_azimuth,
        ))

    # Transition 1 (entry spiral)
    if transition1_length > 0:
        elements.append(TransitionCurve(
            start_chainage=0,  # will be fixed by propagation
            length=transition1_length,
            start_point=Point2D(0, 0),
            start_azimuth=0,
            radius_start=math.inf,
            radius_end=arc_radius,
            direction=direction,
        ))

    # Circular arc
    if arc_length > 0:
        elements.append(CircularArc(
            start_chainage=0,
            length=arc_length,
            start_point=Point2D(0, 0),
            start_azimuth=0,
            radius=arc_radius,
            direction=direction,
        ))

    # Transition 2 (exit spiral)
    if transition2_length > 0:
        elements.append(TransitionCurve(
            start_chainage=0,
            length=transition2_length,
            start_point=Point2D(0, 0),
            start_azimuth=0,
            radius_start=arc_radius,
            radius_end=math.inf,
            direction=direction,
        ))

    # Straight 2
    if straight2_length > 0:
        elements.append(Straight(
            start_chainage=0,
            length=straight2_length,
            start_point=Point2D(0, 0),
            start_azimuth=0,
        ))

    return propagate_geometry(elements)
