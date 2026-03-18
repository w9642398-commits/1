"""Snap engine for CAD-like snapping to geometric features."""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto

from railtrack.domain.alignment import Alignment
from railtrack.domain.horizontal import CircularArc, Straight, TransitionCurve
from railtrack.domain.primitives import Point2D


class SnapType(Enum):
    NONE = auto()
    GRID = auto()
    ENDPOINT = auto()
    MIDPOINT = auto()
    CENTER = auto()
    NEAREST = auto()
    TANGENT = auto()
    PERPENDICULAR = auto()
    INTERSECTION = auto()


@dataclass
class SnapResult:
    """Result of a snap operation."""
    point: Point2D
    snap_type: SnapType
    element_index: int = -1
    distance: float = 0.0


class SnapEngine:
    """Provides snap-to-grid and snap-to-geometry functionality."""

    def __init__(self):
        self.enabled = True
        self.grid_enabled = True
        self.endpoint_enabled = True
        self.midpoint_enabled = True
        self.center_enabled = True
        self.nearest_enabled = True
        self.tangent_enabled = True
        self.perpendicular_enabled = True

        self.grid_size = 10.0  # metres
        self.snap_radius = 15.0  # pixels (will be converted to world coords)

        self._alignment: Alignment | None = None

    def set_alignment(self, alignment: Alignment | None) -> None:
        self._alignment = alignment

    def snap(self, world_point: Point2D, pixel_to_world_scale: float = 1.0) -> SnapResult:
        """Find the best snap point near the given world coordinate.

        pixel_to_world_scale: how many world units per pixel (for threshold).
        """
        if not self.enabled:
            return SnapResult(world_point, SnapType.NONE)

        threshold = self.snap_radius * pixel_to_world_scale
        best = SnapResult(world_point, SnapType.NONE, distance=float("inf"))

        if self._alignment and self._alignment.horizontal_elements:
            # Endpoint snap
            if self.endpoint_enabled:
                for i, elem in enumerate(self._alignment.horizontal_elements):
                    for pt in (elem.start_point, elem.end_point):
                        d = world_point.distance_to(pt)
                        if d < threshold and d < best.distance:
                            best = SnapResult(pt, SnapType.ENDPOINT, i, d)

            # Midpoint snap
            if self.midpoint_enabled:
                for i, elem in enumerate(self._alignment.horizontal_elements):
                    mid_ch = elem.start_chainage + elem.length / 2
                    mid_pt = elem.point_at(mid_ch)
                    d = world_point.distance_to(mid_pt)
                    if d < threshold and d < best.distance:
                        best = SnapResult(mid_pt, SnapType.MIDPOINT, i, d)

            # Center snap (for arcs)
            if self.center_enabled:
                for i, elem in enumerate(self._alignment.horizontal_elements):
                    if isinstance(elem, CircularArc):
                        c = elem.center
                        d = world_point.distance_to(c)
                        if d < threshold and d < best.distance:
                            best = SnapResult(c, SnapType.CENTER, i, d)

            # Nearest on element snap
            if self.nearest_enabled:
                for i, elem in enumerate(self._alignment.horizontal_elements):
                    nearest = self._nearest_point_on_element(elem, world_point)
                    d = world_point.distance_to(nearest)
                    if d < threshold and d < best.distance:
                        best = SnapResult(nearest, SnapType.NEAREST, i, d)

        # Grid snap (lowest priority)
        if self.grid_enabled and best.snap_type == SnapType.NONE:
            gx = round(world_point.x / self.grid_size) * self.grid_size
            gy = round(world_point.y / self.grid_size) * self.grid_size
            grid_pt = Point2D(gx, gy)
            d = world_point.distance_to(grid_pt)
            if d < threshold:
                best = SnapResult(grid_pt, SnapType.GRID, -1, d)

        if best.snap_type == SnapType.NONE:
            best.point = world_point
            best.distance = 0.0

        return best

    def _nearest_point_on_element(self, elem, world_point: Point2D) -> Point2D:
        """Find nearest point on element by sampling."""
        best_pt = elem.start_point
        best_d = world_point.distance_to(best_pt)
        n = max(10, int(elem.length / 5.0))
        for i in range(n + 1):
            ch = elem.start_chainage + elem.length * i / n
            pt = elem.point_at(ch)
            d = world_point.distance_to(pt)
            if d < best_d:
                best_d = d
                best_pt = pt
        return best_pt

    def get_snap_indicator_text(self, snap_type: SnapType) -> str:
        labels = {
            SnapType.NONE: "",
            SnapType.GRID: "Siatka",
            SnapType.ENDPOINT: "Punkt końcowy",
            SnapType.MIDPOINT: "Środek",
            SnapType.CENTER: "Środek łuku",
            SnapType.NEAREST: "Najbliższy",
            SnapType.TANGENT: "Styczna",
            SnapType.PERPENDICULAR: "Prostopadła",
            SnapType.INTERSECTION: "Przecięcie",
        }
        return labels.get(snap_type, "")
