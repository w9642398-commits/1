"""Interactive CAD tools for plan view drawing and editing."""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from enum import Enum, auto

from PySide6.QtCore import QObject, Signal

from railtrack.domain.alignment import Alignment
from railtrack.domain.horizontal import (
    CircularArc, CurveDirection, HorizontalElementUnion, Straight, TransitionCurve,
)
from railtrack.domain.primitives import Point2D, azimuth_from_dx_dy
from railtrack.ui.cad.snap_engine import SnapEngine, SnapResult, SnapType


class ToolType(Enum):
    SELECT = auto()
    PAN = auto()
    DRAW_STRAIGHT = auto()
    DRAW_ARC = auto()
    DRAW_TRANSITION = auto()
    DRAW_SCS = auto()  # straight-transition-curve-transition-straight
    MEASURE_DISTANCE = auto()
    MEASURE_ANGLE = auto()
    MOVE_POINT = auto()
    ADJUST_RADIUS = auto()
    SPLIT_ELEMENT = auto()
    EXTEND_ELEMENT = auto()
    INSERT_PI = auto()  # Point of Intersection method


class BaseTool(ABC):
    """Base class for all CAD tools."""

    def __init__(self, tool_type: ToolType):
        self.tool_type = tool_type
        self._active = False

    def activate(self) -> None:
        self._active = True

    def deactivate(self) -> None:
        self._active = False
        self.reset()

    @abstractmethod
    def reset(self) -> None: ...

    @abstractmethod
    def on_mouse_press(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        """Handle mouse press. Returns action dict or None."""
        ...

    @abstractmethod
    def on_mouse_move(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        """Handle mouse move. Returns preview dict or None."""
        ...

    @abstractmethod
    def on_mouse_release(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        """Handle mouse release. Returns action dict or None."""
        ...

    def on_key_press(self, key: int) -> dict | None:
        """Handle key press. Returns action dict or None."""
        return None

    @property
    def cursor_text(self) -> str:
        return ""

    @property
    def status_text(self) -> str:
        return ""


class SelectTool(BaseTool):
    """Selection and basic interaction tool."""

    def __init__(self):
        super().__init__(ToolType.SELECT)
        self._drag_start: Point2D | None = None
        self._dragging = False
        self._drag_element_index: int = -1
        self._drag_handle: str = ""  # "start", "end", "radius"
        self._rubber_band_start: Point2D | None = None

    def reset(self) -> None:
        self._drag_start = None
        self._dragging = False
        self._drag_element_index = -1
        self._drag_handle = ""
        self._rubber_band_start = None

    def on_mouse_press(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        if snap.snap_type == SnapType.ENDPOINT and snap.element_index >= 0:
            self._drag_start = world_pt
            self._drag_element_index = snap.element_index
            elem_pt = snap.point
            return {"type": "select", "index": snap.element_index}

        # Check if clicking near a handle
        return {"type": "pick", "point": world_pt}

    def on_mouse_move(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        if self._drag_start and self._drag_element_index >= 0:
            self._dragging = True
            return {
                "type": "drag_preview",
                "index": self._drag_element_index,
                "from": self._drag_start,
                "to": snap.point if snap.snap_type != SnapType.NONE else world_pt,
            }
        if self._rubber_band_start:
            return {
                "type": "rubber_band",
                "start": self._rubber_band_start,
                "end": world_pt,
            }
        return {"type": "hover", "point": world_pt, "snap": snap}

    def on_mouse_release(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        result = None
        if self._dragging and self._drag_element_index >= 0:
            target = snap.point if snap.snap_type != SnapType.NONE else world_pt
            result = {
                "type": "move_element",
                "index": self._drag_element_index,
                "from": self._drag_start,
                "to": target,
            }
        self.reset()
        return result

    @property
    def status_text(self) -> str:
        if self._dragging:
            return "Przeciąganie elementu..."
        return "Wybierz: klik = zaznacz, przeciągnij punkt = przesuń"


class DrawStraightTool(BaseTool):
    """Draw straight (tangent) elements by clicking start/end points."""

    def __init__(self):
        super().__init__(ToolType.DRAW_STRAIGHT)
        self._start_point: Point2D | None = None
        self._preview_end: Point2D | None = None

    def reset(self) -> None:
        self._start_point = None
        self._preview_end = None

    def on_mouse_press(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        pt = snap.point if snap.snap_type != SnapType.NONE else world_pt
        if self._start_point is None:
            self._start_point = pt
            return {"type": "draw_started", "point": pt}
        else:
            end_pt = pt
            dx = end_pt.x - self._start_point.x
            dy = end_pt.y - self._start_point.y
            length = math.hypot(dx, dy)
            if length < 0.01:
                return None
            azimuth = azimuth_from_dx_dy(dx, dy)
            result = {
                "type": "add_straight",
                "start": self._start_point,
                "end": end_pt,
                "length": length,
                "azimuth": azimuth,
            }
            self._start_point = end_pt  # chain next straight
            return result

    def on_mouse_move(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        pt = snap.point if snap.snap_type != SnapType.NONE else world_pt
        self._preview_end = pt
        if self._start_point:
            dx = pt.x - self._start_point.x
            dy = pt.y - self._start_point.y
            length = math.hypot(dx, dy)
            azimuth = azimuth_from_dx_dy(dx, dy) if length > 0.01 else 0.0
            return {
                "type": "preview_line",
                "start": self._start_point,
                "end": pt,
                "length": length,
                "azimuth": math.degrees(azimuth),
            }
        return {"type": "hover", "point": pt, "snap": snap}

    def on_mouse_release(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        return None

    def on_key_press(self, key: int) -> dict | None:
        from PySide6.QtCore import Qt
        if key == Qt.Key.Key_Escape:
            self.reset()
            return {"type": "cancel_draw"}
        return None

    @property
    def status_text(self) -> str:
        if self._start_point is None:
            return "Prosta: klik = punkt początkowy"
        return "Prosta: klik = punkt końcowy, Esc = anuluj"


class DrawArcTool(BaseTool):
    """Draw circular arc by 3-point method or start+radius+direction."""

    def __init__(self):
        super().__init__(ToolType.DRAW_ARC)
        self._points: list[Point2D] = []
        self._preview_pt: Point2D | None = None
        self._radius: float = 500.0
        self._direction: CurveDirection = CurveDirection.RIGHT

    def reset(self) -> None:
        self._points.clear()
        self._preview_pt = None

    def set_radius(self, radius: float) -> None:
        self._radius = radius

    def set_direction(self, direction: CurveDirection) -> None:
        self._direction = direction

    def on_mouse_press(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        pt = snap.point if snap.snap_type != SnapType.NONE else world_pt
        self._points.append(pt)

        if len(self._points) == 1:
            return {"type": "draw_started", "point": pt}
        elif len(self._points) == 2:
            return {"type": "arc_midpoint", "point": pt}
        elif len(self._points) >= 3:
            result = self._compute_arc_from_3_points()
            self._points.clear()
            return result
        return None

    def on_mouse_move(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        pt = snap.point if snap.snap_type != SnapType.NONE else world_pt
        self._preview_pt = pt
        if len(self._points) == 1:
            return {
                "type": "preview_line",
                "start": self._points[0],
                "end": pt,
            }
        elif len(self._points) == 2:
            return {
                "type": "preview_arc_3pt",
                "p1": self._points[0],
                "p2": self._points[1],
                "p3": pt,
            }
        return {"type": "hover", "point": pt, "snap": snap}

    def on_mouse_release(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        return None

    def _compute_arc_from_3_points(self) -> dict | None:
        """Compute arc passing through 3 points."""
        p1, p2, p3 = self._points[0], self._points[1], self._points[2]
        # Find circumscribed circle
        ax, ay = p1.x, p1.y
        bx, by = p2.x, p2.y
        cx, cy = p3.x, p3.y

        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if abs(d) < 1e-10:
            return None  # Collinear points

        ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) +
              (cx * cx + cy * cy) * (ay - by)) / d
        uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) +
              (cx * cx + cy * cy) * (bx - ax)) / d

        center = Point2D(ux, uy)
        radius = center.distance_to(p1)

        # Determine direction (CW or CCW)
        cross = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        direction = CurveDirection.RIGHT if cross < 0 else CurveDirection.LEFT

        # Compute arc length
        a1 = math.atan2(p1.y - uy, p1.x - ux)
        a3 = math.atan2(p3.y - uy, p3.x - ux)
        if direction == CurveDirection.RIGHT:
            sweep = a1 - a3
            if sweep < 0:
                sweep += 2 * math.pi
        else:
            sweep = a3 - a1
            if sweep < 0:
                sweep += 2 * math.pi

        arc_length = radius * sweep
        azimuth = azimuth_from_dx_dy(p2.x - p1.x, p2.y - p1.y)

        return {
            "type": "add_arc_3pt",
            "p1": p1, "p2": p2, "p3": p3,
            "center": center,
            "radius": radius,
            "direction": direction,
            "arc_length": arc_length,
            "start_azimuth": azimuth,
        }

    def on_key_press(self, key: int) -> dict | None:
        from PySide6.QtCore import Qt
        if key == Qt.Key.Key_Escape:
            self.reset()
            return {"type": "cancel_draw"}
        return None

    @property
    def status_text(self) -> str:
        n = len(self._points)
        if n == 0:
            return "Łuk 3-pkt: klik = punkt początkowy"
        elif n == 1:
            return "Łuk 3-pkt: klik = punkt środkowy łuku"
        elif n == 2:
            return "Łuk 3-pkt: klik = punkt końcowy"
        return ""


class DrawTransitionTool(BaseTool):
    """Draw transition curve (clothoid) by specifying start, end, and radius."""

    def __init__(self):
        super().__init__(ToolType.DRAW_TRANSITION)
        self._start_point: Point2D | None = None
        self._radius_start: float = math.inf
        self._radius_end: float = 500.0
        self._direction: CurveDirection = CurveDirection.RIGHT

    def reset(self) -> None:
        self._start_point = None

    def set_params(self, radius_start: float, radius_end: float,
                   direction: CurveDirection) -> None:
        self._radius_start = radius_start
        self._radius_end = radius_end
        self._direction = direction

    def on_mouse_press(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        pt = snap.point if snap.snap_type != SnapType.NONE else world_pt
        if self._start_point is None:
            self._start_point = pt
            return {"type": "draw_started", "point": pt}
        else:
            dx = pt.x - self._start_point.x
            dy = pt.y - self._start_point.y
            length = math.hypot(dx, dy)
            if length < 0.01:
                return None
            azimuth = azimuth_from_dx_dy(dx, dy)
            result = {
                "type": "add_transition",
                "start": self._start_point,
                "end": pt,
                "length": length,
                "azimuth": azimuth,
                "radius_start": self._radius_start,
                "radius_end": self._radius_end,
                "direction": self._direction,
            }
            self._start_point = pt
            return result

    def on_mouse_move(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        pt = snap.point if snap.snap_type != SnapType.NONE else world_pt
        if self._start_point:
            dx = pt.x - self._start_point.x
            dy = pt.y - self._start_point.y
            length = math.hypot(dx, dy)
            return {
                "type": "preview_transition",
                "start": self._start_point,
                "end": pt,
                "length": length,
            }
        return {"type": "hover", "point": pt, "snap": snap}

    def on_mouse_release(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        return None

    def on_key_press(self, key: int) -> dict | None:
        from PySide6.QtCore import Qt
        if key == Qt.Key.Key_Escape:
            self.reset()
            return {"type": "cancel_draw"}
        return None

    @property
    def status_text(self) -> str:
        if self._start_point is None:
            return "Klotoida: klik = punkt początkowy"
        return "Klotoida: klik = punkt końcowy, Esc = anuluj"


class DrawSCSTool(BaseTool):
    """Draw full S-T-C-T-S sequence interactively.

    1. Click start point
    2. Click direction point (defines initial azimuth)
    3. Click curve area (defines direction of turn and general shape)
    4. Specify parameters in popup
    """

    def __init__(self):
        super().__init__(ToolType.DRAW_SCS)
        self._points: list[Point2D] = []

    def reset(self) -> None:
        self._points.clear()

    def on_mouse_press(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        pt = snap.point if snap.snap_type != SnapType.NONE else world_pt
        self._points.append(pt)

        if len(self._points) == 1:
            return {"type": "draw_started", "point": pt}
        elif len(self._points) == 2:
            return {"type": "scs_direction", "start": self._points[0], "end": pt}
        elif len(self._points) >= 3:
            # Determine curve direction from 3rd click
            p1, p2, p3 = self._points[0], self._points[1], self._points[2]
            cross = (p2.x - p1.x) * (p3.y - p1.y) - (p2.y - p1.y) * (p3.x - p1.x)
            direction = CurveDirection.LEFT if cross > 0 else CurveDirection.RIGHT

            dx = p2.x - p1.x
            dy = p2.y - p1.y
            azimuth = azimuth_from_dx_dy(dx, dy)
            straight1_len = p1.distance_to(p2)

            result = {
                "type": "add_scs",
                "start": p1,
                "azimuth": azimuth,
                "straight1_length": straight1_len,
                "direction": direction,
                "curve_point": p3,
            }
            self._points.clear()
            return result

    def on_mouse_move(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        pt = snap.point if snap.snap_type != SnapType.NONE else world_pt
        n = len(self._points)
        if n == 1:
            return {"type": "preview_line", "start": self._points[0], "end": pt}
        elif n == 2:
            cross = ((self._points[1].x - self._points[0].x) * (pt.y - self._points[0].y) -
                     (self._points[1].y - self._points[0].y) * (pt.x - self._points[0].x))
            side = "LEWO" if cross > 0 else "PRAWO"
            return {
                "type": "preview_scs",
                "start": self._points[0],
                "through": self._points[1],
                "end": pt,
                "side": side,
            }
        return {"type": "hover", "point": pt, "snap": snap}

    def on_mouse_release(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        return None

    def on_key_press(self, key: int) -> dict | None:
        from PySide6.QtCore import Qt
        if key == Qt.Key.Key_Escape:
            self.reset()
            return {"type": "cancel_draw"}
        return None

    @property
    def status_text(self) -> str:
        n = len(self._points)
        if n == 0:
            return "SCS: klik = punkt początkowy"
        elif n == 1:
            return "SCS: klik = punkt kierunkowy (azymut)"
        elif n == 2:
            return "SCS: klik = strona łuku (lewo/prawo)"
        return ""


class MeasureDistanceTool(BaseTool):
    """Measure distance between two points."""

    def __init__(self):
        super().__init__(ToolType.MEASURE_DISTANCE)
        self._start: Point2D | None = None
        self._measurements: list[tuple[Point2D, Point2D, float]] = []

    def reset(self) -> None:
        self._start = None
        self._measurements.clear()

    def on_mouse_press(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        pt = snap.point if snap.snap_type != SnapType.NONE else world_pt
        if self._start is None:
            self._start = pt
            return {"type": "measure_start", "point": pt}
        else:
            dist = self._start.distance_to(pt)
            dx = pt.x - self._start.x
            dy = pt.y - self._start.y
            azimuth = azimuth_from_dx_dy(dx, dy) if dist > 0.01 else 0.0
            self._measurements.append((self._start, pt, dist))
            result = {
                "type": "measure_result",
                "start": self._start,
                "end": pt,
                "distance": dist,
                "azimuth": math.degrees(azimuth),
                "dx": dx,
                "dy": dy,
            }
            self._start = pt  # chain measurements
            return result

    def on_mouse_move(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        pt = snap.point if snap.snap_type != SnapType.NONE else world_pt
        if self._start:
            dist = self._start.distance_to(pt)
            dx = pt.x - self._start.x
            dy = pt.y - self._start.y
            azimuth = azimuth_from_dx_dy(dx, dy) if dist > 0.01 else 0.0
            return {
                "type": "preview_measure",
                "start": self._start,
                "end": pt,
                "distance": dist,
                "azimuth": math.degrees(azimuth),
            }
        return {"type": "hover", "point": pt, "snap": snap}

    def on_mouse_release(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        return None

    def on_key_press(self, key: int) -> dict | None:
        from PySide6.QtCore import Qt
        if key == Qt.Key.Key_Escape:
            self.reset()
            return {"type": "cancel_measure"}
        return None

    @property
    def status_text(self) -> str:
        if self._start is None:
            return "Pomiar: klik = punkt początkowy"
        return "Pomiar: klik = punkt końcowy, Esc = anuluj"


class MeasureAngleTool(BaseTool):
    """Measure angle between three points."""

    def __init__(self):
        super().__init__(ToolType.MEASURE_ANGLE)
        self._points: list[Point2D] = []

    def reset(self) -> None:
        self._points.clear()

    def on_mouse_press(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        pt = snap.point if snap.snap_type != SnapType.NONE else world_pt
        self._points.append(pt)

        if len(self._points) == 3:
            p1, vertex, p3 = self._points
            a1 = math.atan2(p1.y - vertex.y, p1.x - vertex.x)
            a2 = math.atan2(p3.y - vertex.y, p3.x - vertex.x)
            angle = abs(a2 - a1)
            if angle > math.pi:
                angle = 2 * math.pi - angle
            result = {
                "type": "angle_result",
                "p1": p1, "vertex": vertex, "p3": p3,
                "angle_rad": angle,
                "angle_deg": math.degrees(angle),
            }
            self._points.clear()
            return result
        return {"type": "angle_point", "index": len(self._points), "point": pt}

    def on_mouse_move(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        pt = snap.point if snap.snap_type != SnapType.NONE else world_pt
        if self._points:
            return {
                "type": "preview_angle",
                "points": list(self._points) + [pt],
            }
        return {"type": "hover", "point": pt, "snap": snap}

    def on_mouse_release(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        return None

    def on_key_press(self, key: int) -> dict | None:
        from PySide6.QtCore import Qt
        if key == Qt.Key.Key_Escape:
            self.reset()
            return {"type": "cancel_measure"}
        return None

    @property
    def status_text(self) -> str:
        n = len(self._points)
        if n == 0:
            return "Kąt: klik = pierwszy punkt"
        elif n == 1:
            return "Kąt: klik = wierzchołek"
        elif n == 2:
            return "Kąt: klik = trzeci punkt"
        return ""


class InsertPITool(BaseTool):
    """Insert Point of Intersection - common civil engineering method.

    User clicks consecutive PIs, and the tool automatically creates
    tangent-curve-tangent sequences.
    """

    def __init__(self):
        super().__init__(ToolType.INSERT_PI)
        self._points: list[Point2D] = []
        self._default_radius: float = 500.0
        self._default_transition_length: float = 60.0

    def reset(self) -> None:
        self._points.clear()

    def set_defaults(self, radius: float, transition_length: float) -> None:
        self._default_radius = radius
        self._default_transition_length = transition_length

    def on_mouse_press(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        pt = snap.point if snap.snap_type != SnapType.NONE else world_pt
        self._points.append(pt)

        if len(self._points) >= 3:
            result = {
                "type": "add_pi_sequence",
                "points": list(self._points),
                "radius": self._default_radius,
                "transition_length": self._default_transition_length,
            }
            return result

        return {"type": "pi_point", "index": len(self._points), "point": pt}

    def on_mouse_move(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        pt = snap.point if snap.snap_type != SnapType.NONE else world_pt
        if self._points:
            return {
                "type": "preview_pi",
                "points": list(self._points) + [pt],
            }
        return {"type": "hover", "point": pt, "snap": snap}

    def on_mouse_release(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        return None

    def on_key_press(self, key: int) -> dict | None:
        from PySide6.QtCore import Qt
        if key == Qt.Key.Key_Escape:
            self.reset()
            return {"type": "cancel_draw"}
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            if len(self._points) >= 2:
                result = {
                    "type": "finish_pi_sequence",
                    "points": list(self._points),
                    "radius": self._default_radius,
                    "transition_length": self._default_transition_length,
                }
                self._points.clear()
                return result
        return None

    @property
    def status_text(self) -> str:
        n = len(self._points)
        if n == 0:
            return "PI: klik = punkt początkowy"
        elif n == 1:
            return "PI: klik = punkt przecięcia (PI)"
        else:
            return f"PI: klik = następny PI, Enter = zakończ ({n} pkt)"


class SplitElementTool(BaseTool):
    """Split element at clicked chainage."""

    def __init__(self):
        super().__init__(ToolType.SPLIT_ELEMENT)

    def reset(self) -> None:
        pass

    def on_mouse_press(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        if snap.snap_type == SnapType.NEAREST and snap.element_index >= 0:
            return {
                "type": "split_element",
                "index": snap.element_index,
                "point": snap.point,
            }
        return None

    def on_mouse_move(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        return {"type": "hover", "point": world_pt, "snap": snap}

    def on_mouse_release(self, world_pt: Point2D, snap: SnapResult) -> dict | None:
        return None

    @property
    def status_text(self) -> str:
        return "Podział: klik na elemencie = podziel w tym punkcie"
