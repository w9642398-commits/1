"""Interactive CAD plan view with drawing, editing, snapping, and measurement tools.

Provides Civil3D-like interactive editing of horizontal railway alignment geometry.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QPen, QBrush, QFont, QCursor, QKeyEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget, QHBoxLayout, QLabel

try:
    import pyqtgraph as pg
    from pyqtgraph import PlotDataItem, ScatterPlotItem, TextItem, InfiniteLine
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False

from railtrack.domain.alignment import Alignment
from railtrack.domain.horizontal import (
    CircularArc, CurveDirection, HorizontalElementUnion, Straight, TransitionCurve,
)
from railtrack.domain.primitives import Point2D, azimuth_from_dx_dy
from railtrack.geometry_engine.horizontal_engine import compute_points_along, propagate_geometry
from railtrack.ui.cad.snap_engine import SnapEngine, SnapResult, SnapType
from railtrack.ui.cad.tools import (
    BaseTool, DrawArcTool, DrawSCSTool, DrawStraightTool, DrawTransitionTool,
    InsertPITool, MeasureAngleTool, MeasureDistanceTool, SelectTool,
    SplitElementTool, ToolType,
)
from railtrack.ui.cad.layers import LayerManager


# Element type colors
_COLORS = {
    "straight": (100, 200, 100),        # green
    "circular_arc": (200, 100, 100),     # red
    "transition_curve": (100, 100, 200), # blue
}
_HIGHLIGHT_COLOR = (255, 255, 50)    # yellow highlight
_HANDLE_COLOR = (255, 200, 50)       # orange handles
_SNAP_COLOR = (255, 165, 0)          # snap indicator
_PREVIEW_COLOR = (200, 200, 200, 120)  # ghost preview
_MEASURE_COLOR = (0, 255, 255)       # cyan measurement
_VALIDATION_ERROR_COLOR = (255, 50, 50)
_CONSTRUCTION_COLOR = (128, 128, 128, 100)
_GRID_MINOR_COLOR = (50, 50, 50, 40)
_CHAINAGE_COLOR = (180, 180, 180, 150)


class CoordinateBar(QWidget):
    """Status bar showing cursor coordinates, snap info, and tool status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(12)

        self.coord_label = QLabel("X: 0.000  Y: 0.000")
        self.coord_label.setStyleSheet("color: #aaa; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.coord_label)

        self.snap_label = QLabel("")
        self.snap_label.setStyleSheet("color: #ffa500; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.snap_label)

        self.tool_label = QLabel("")
        self.tool_label.setStyleSheet("color: #8af; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.tool_label)

        self.measure_label = QLabel("")
        self.measure_label.setStyleSheet("color: #0ff; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.measure_label)

        layout.addStretch()

    def update_coords(self, x: float, y: float) -> None:
        self.coord_label.setText(f"X: {x:.3f}  Y: {y:.3f}")

    def update_snap(self, text: str) -> None:
        self.snap_label.setText(text)

    def update_tool(self, text: str) -> None:
        self.tool_label.setText(text)

    def update_measure(self, text: str) -> None:
        self.measure_label.setText(text)


class PlanView(QWidget):
    """Interactive CAD plan view of horizontal alignment."""

    element_clicked = Signal(int)
    element_modified = Signal()
    tool_action = Signal(dict)
    coordinates_changed = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._alignment: Alignment | None = None
        self._element_items: list = []
        self._highlight_item = None
        self._handle_items: list = []
        self._preview_items: list = []
        self._measurement_items: list = []
        self._snap_indicator = None
        self._chainage_items: list = []
        self._validation_items: list = []
        self._construction_items: list = []
        self._selected_indices: set[int] = set()

        # CAD systems
        self.snap_engine = SnapEngine()
        self.layer_manager = LayerManager()
        self._current_tool: BaseTool = SelectTool()
        self._current_tool.activate()

        # State
        self._show_handles = True
        self._show_chainage_labels = True
        self._chainage_label_interval = 100.0
        self._show_tangent_lines = False
        self._last_snap: SnapResult | None = None
        self._mouse_world_pt: Point2D = Point2D(0, 0)

        if HAS_PYQTGRAPH:
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.setAspectLocked(True)
            self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
            self.plot_widget.setLabel("bottom", "Easting [m]")
            self.plot_widget.setLabel("left", "Northing [m]")
            self.plot_widget.setBackground((25, 25, 30))

            # Mouse tracking
            self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)
            self.plot_widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)

            # Crosshair cursor
            self._crosshair_v = pg.InfiniteLine(angle=90, pen=pg.mkPen((80, 80, 80, 100), width=1))
            self._crosshair_h = pg.InfiniteLine(angle=0, pen=pg.mkPen((80, 80, 80, 100), width=1))
            self.plot_widget.addItem(self._crosshair_v)
            self.plot_widget.addItem(self._crosshair_h)

            layout.addWidget(self.plot_widget)
        else:
            from PySide6.QtWidgets import QLabel as QL
            layout.addWidget(QL("pyqtgraph nie jest zainstalowany"))
            self.plot_widget = None

        # Coordinate bar
        self.coord_bar = CoordinateBar()
        layout.addWidget(self.coord_bar)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # --- Tool Management ---
    def set_tool(self, tool: BaseTool) -> None:
        if self._current_tool:
            self._current_tool.deactivate()
        self._current_tool = tool
        self._current_tool.activate()
        self._clear_previews()
        self.coord_bar.update_tool(tool.status_text)

    def get_current_tool(self) -> BaseTool:
        return self._current_tool

    # --- Alignment Data ---
    def set_alignment(self, alignment: Alignment) -> None:
        self._alignment = alignment
        self.snap_engine.set_alignment(alignment)
        self._selected_indices.clear()
        self._redraw()

    def _redraw(self) -> None:
        """Full redraw of all geometry."""
        if not self.plot_widget:
            return

        self._element_items.clear()
        self._highlight_item = None
        self._clear_handles()
        self._clear_previews()
        self._clear_chainage_labels()
        self._clear_measurements()
        self._clear_validation()
        self._clear_construction()

        self.plot_widget.clear()

        # Re-add crosshair
        self.plot_widget.addItem(self._crosshair_v)
        self.plot_widget.addItem(self._crosshair_h)

        if not self._alignment or not self._alignment.horizontal_elements:
            return

        # Draw elements
        for i, elem in enumerate(self._alignment.horizontal_elements):
            etype = elem.element_type.value
            color = _COLORS.get(etype, (200, 200, 200))
            width = 3 if i in self._selected_indices else 2

            if isinstance(elem, Straight):
                sp, ep = elem.start_point, elem.end_point
                item = self.plot_widget.plot(
                    [sp.x, ep.x], [sp.y, ep.y],
                    pen=pg.mkPen(color=color, width=width),
                )
            else:
                n = max(30, int(elem.length / 1.5))
                xs, ys = [], []
                for j in range(n + 1):
                    ch = elem.start_chainage + elem.length * j / n
                    p = elem.point_at(ch)
                    xs.append(p.x)
                    ys.append(p.y)
                item = self.plot_widget.plot(xs, ys, pen=pg.mkPen(color=color, width=width))

            self._element_items.append(item)

        # Highlighted elements
        for idx in self._selected_indices:
            self._draw_highlight(idx)

        # Start/end markers
        if self._alignment.horizontal_elements:
            sp = self._alignment.horizontal_elements[0].start_point
            ep = self._alignment.horizontal_elements[-1].end_point
            self.plot_widget.plot([sp.x], [sp.y], pen=None, symbol="o",
                                 symbolSize=10, symbolBrush=(0, 200, 0))
            self.plot_widget.plot([ep.x], [ep.y], pen=None, symbol="s",
                                 symbolSize=10, symbolBrush=(200, 0, 0))

        # Handles
        if self._show_handles and self.layer_manager.is_visible(LayerManager.LAYER_HANDLES):
            self._draw_handles()

        # Chainage labels
        if self._show_chainage_labels and self.layer_manager.is_visible(LayerManager.LAYER_CHAINAGE):
            self._draw_chainage_labels()

        # Tangent construction lines
        if self._show_tangent_lines and self.layer_manager.is_visible(LayerManager.LAYER_CONSTRUCTION):
            self._draw_tangent_lines()

    # --- Drawing Helpers ---
    def _draw_highlight(self, index: int) -> None:
        if not self._alignment or index < 0 or index >= len(self._alignment.horizontal_elements):
            return
        elem = self._alignment.horizontal_elements[index]
        if isinstance(elem, Straight):
            sp, ep = elem.start_point, elem.end_point
            item = self.plot_widget.plot(
                [sp.x, ep.x], [sp.y, ep.y],
                pen=pg.mkPen(color=_HIGHLIGHT_COLOR, width=5),
            )
        else:
            n = max(30, int(elem.length / 1.5))
            xs, ys = [], []
            for j in range(n + 1):
                ch = elem.start_chainage + elem.length * j / n
                p = elem.point_at(ch)
                xs.append(p.x)
                ys.append(p.y)
            item = self.plot_widget.plot(xs, ys, pen=pg.mkPen(color=_HIGHLIGHT_COLOR, width=5))

    def _draw_handles(self) -> None:
        """Draw interactive handles at element endpoints."""
        if not self._alignment:
            return
        handle_xs, handle_ys = [], []
        seen = set()
        for elem in self._alignment.horizontal_elements:
            for pt in (elem.start_point, elem.end_point):
                key = (round(pt.x, 6), round(pt.y, 6))
                if key not in seen:
                    seen.add(key)
                    handle_xs.append(pt.x)
                    handle_ys.append(pt.y)

        if handle_xs:
            item = self.plot_widget.plot(
                handle_xs, handle_ys, pen=None,
                symbol="d", symbolSize=8,
                symbolBrush=pg.mkBrush(_HANDLE_COLOR),
                symbolPen=pg.mkPen((200, 150, 0), width=1),
            )
            self._handle_items.append(item)

        # Draw arc center markers
        for elem in self._alignment.horizontal_elements:
            if isinstance(elem, CircularArc):
                c = elem.center
                item = self.plot_widget.plot(
                    [c.x], [c.y], pen=None,
                    symbol="+", symbolSize=10,
                    symbolPen=pg.mkPen((200, 100, 100, 150), width=1),
                )
                self._handle_items.append(item)

    def _draw_chainage_labels(self) -> None:
        """Draw chainage labels along the alignment."""
        if not self._alignment or not self._alignment.horizontal_elements:
            return

        ch_start = self._alignment.horizontal_elements[0].start_chainage
        ch_end = self._alignment.horizontal_elements[-1].end_chainage
        interval = self._chainage_label_interval

        ch = math.ceil(ch_start / interval) * interval
        while ch <= ch_end:
            pt = self._alignment.point_at(ch)
            az = self._alignment.azimuth_at(ch)
            if pt and az is not None:
                # Draw tick perpendicular to alignment
                perp = az + math.pi / 2
                tick_len = 3.0
                tx1 = pt.x + tick_len * math.sin(perp)
                ty1 = pt.y + tick_len * math.cos(perp)
                tx2 = pt.x - tick_len * math.sin(perp)
                ty2 = pt.y - tick_len * math.cos(perp)
                tick = self.plot_widget.plot(
                    [tx1, tx2], [ty1, ty2],
                    pen=pg.mkPen(color=_CHAINAGE_COLOR, width=1),
                )
                self._chainage_items.append(tick)

                # Label
                km = ch / 1000.0
                text = pg.TextItem(f"{km:.3f}", color=_CHAINAGE_COLOR, anchor=(0, 1))
                text.setPos(tx1, ty1)
                font = QFont("monospace", 7)
                text.setFont(font)
                self.plot_widget.addItem(text)
                self._chainage_items.append(text)

            ch += interval

    def _draw_tangent_lines(self) -> None:
        """Draw construction lines showing tangent directions at element boundaries."""
        if not self._alignment:
            return
        for elem in self._alignment.horizontal_elements:
            sp = elem.start_point
            az = elem.start_azimuth
            ext = 20.0
            ex = sp.x + ext * math.sin(az)
            ey = sp.y + ext * math.cos(az)
            bx = sp.x - ext * math.sin(az)
            by = sp.y - ext * math.cos(az)
            item = self.plot_widget.plot(
                [bx, ex], [by, ey],
                pen=pg.mkPen(color=_CONSTRUCTION_COLOR, width=1, style=Qt.PenStyle.DashLine),
            )
            self._construction_items.append(item)

    def _clear_handles(self) -> None:
        for item in self._handle_items:
            if self.plot_widget:
                self.plot_widget.removeItem(item)
        self._handle_items.clear()

    def _clear_previews(self) -> None:
        for item in self._preview_items:
            if self.plot_widget:
                self.plot_widget.removeItem(item)
        self._preview_items.clear()

    def _clear_chainage_labels(self) -> None:
        for item in self._chainage_items:
            if self.plot_widget:
                self.plot_widget.removeItem(item)
        self._chainage_items.clear()

    def _clear_measurements(self) -> None:
        for item in self._measurement_items:
            if self.plot_widget:
                self.plot_widget.removeItem(item)
        self._measurement_items.clear()

    def _clear_validation(self) -> None:
        for item in self._validation_items:
            if self.plot_widget:
                self.plot_widget.removeItem(item)
        self._validation_items.clear()

    def _clear_construction(self) -> None:
        for item in self._construction_items:
            if self.plot_widget:
                self.plot_widget.removeItem(item)
        self._construction_items.clear()

    # --- Snap Indicator ---
    def _draw_snap_indicator(self, snap: SnapResult) -> None:
        if self._snap_indicator and self.plot_widget:
            self.plot_widget.removeItem(self._snap_indicator)
            self._snap_indicator = None

        if snap.snap_type == SnapType.NONE or not self.plot_widget:
            return

        symbol_map = {
            SnapType.ENDPOINT: "s",
            SnapType.MIDPOINT: "t",
            SnapType.CENTER: "+",
            SnapType.NEAREST: "x",
            SnapType.GRID: "o",
            SnapType.TANGENT: "d",
            SnapType.PERPENDICULAR: "d",
        }
        symbol = symbol_map.get(snap.snap_type, "o")
        self._snap_indicator = self.plot_widget.plot(
            [snap.point.x], [snap.point.y], pen=None,
            symbol=symbol, symbolSize=14,
            symbolBrush=pg.mkBrush(*_SNAP_COLOR, 100),
            symbolPen=pg.mkPen(_SNAP_COLOR, width=2),
        )

    # --- Preview Drawing ---
    def _draw_preview_line(self, start: Point2D, end: Point2D,
                           color=_PREVIEW_COLOR, width=2) -> None:
        item = self.plot_widget.plot(
            [start.x, end.x], [start.y, end.y],
            pen=pg.mkPen(color=color, width=width, style=Qt.PenStyle.DashLine),
        )
        self._preview_items.append(item)

        # Distance label
        dist = start.distance_to(end)
        mid_x = (start.x + end.x) / 2
        mid_y = (start.y + end.y) / 2
        text = pg.TextItem(f"{dist:.2f} m", color=(200, 200, 200), anchor=(0.5, 1))
        text.setPos(mid_x, mid_y)
        font = QFont("monospace", 8)
        text.setFont(font)
        self.plot_widget.addItem(text)
        self._preview_items.append(text)

    def _draw_preview_arc(self, p1: Point2D, p2: Point2D, p3: Point2D) -> None:
        """Draw preview arc through 3 points."""
        # Compute circumscribed circle
        ax, ay = p1.x, p1.y
        bx, by = p2.x, p2.y
        cx, cy = p3.x, p3.y
        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if abs(d) < 1e-10:
            self._draw_preview_line(p1, p3)
            return

        ux = ((ax*ax + ay*ay) * (by - cy) + (bx*bx + by*by) * (cy - ay) +
              (cx*cx + cy*cy) * (ay - by)) / d
        uy = ((ax*ax + ay*ay) * (cx - bx) + (bx*bx + by*by) * (ax - cx) +
              (cx*cx + cy*cy) * (bx - ax)) / d
        center = Point2D(ux, uy)
        radius = center.distance_to(p1)

        # Draw arc through sampling
        a1 = math.atan2(p1.y - uy, p1.x - ux)
        a3 = math.atan2(p3.y - uy, p3.x - ux)
        a2 = math.atan2(p2.y - uy, p2.x - ux)

        # Determine sweep direction
        cross = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        n = 50
        xs, ys = [], []
        if cross < 0:
            sweep = a1 - a3
            if sweep < 0:
                sweep += 2 * math.pi
            for i in range(n + 1):
                a = a1 - sweep * i / n
                xs.append(ux + radius * math.cos(a))
                ys.append(uy + radius * math.sin(a))
        else:
            sweep = a3 - a1
            if sweep < 0:
                sweep += 2 * math.pi
            for i in range(n + 1):
                a = a1 + sweep * i / n
                xs.append(ux + radius * math.cos(a))
                ys.append(uy + radius * math.sin(a))

        item = self.plot_widget.plot(
            xs, ys,
            pen=pg.mkPen(color=_PREVIEW_COLOR, width=2, style=Qt.PenStyle.DashLine),
        )
        self._preview_items.append(item)

        # Radius label
        text = pg.TextItem(f"R={radius:.1f} m", color=(200, 200, 200), anchor=(0, 1))
        text.setPos(ux, uy)
        font = QFont("monospace", 8)
        text.setFont(font)
        self.plot_widget.addItem(text)
        self._preview_items.append(text)

    def _draw_measurement_line(self, start: Point2D, end: Point2D,
                                distance: float, azimuth: float) -> None:
        """Draw permanent measurement annotation."""
        item = self.plot_widget.plot(
            [start.x, end.x], [start.y, end.y],
            pen=pg.mkPen(color=_MEASURE_COLOR, width=1, style=Qt.PenStyle.DashDotLine),
        )
        self._measurement_items.append(item)

        mid_x = (start.x + end.x) / 2
        mid_y = (start.y + end.y) / 2
        text = pg.TextItem(
            f"{distance:.3f} m\nAz: {azimuth:.2f}°",
            color=_MEASURE_COLOR, anchor=(0.5, 1),
        )
        text.setPos(mid_x, mid_y)
        font = QFont("monospace", 9)
        text.setFont(font)
        self.plot_widget.addItem(text)
        self._measurement_items.append(text)

        # Endpoints
        for pt in (start, end):
            marker = self.plot_widget.plot(
                [pt.x], [pt.y], pen=None,
                symbol="x", symbolSize=8,
                symbolPen=pg.mkPen(_MEASURE_COLOR, width=2),
            )
            self._measurement_items.append(marker)

    # --- Validation Overlay ---
    def show_validation_issues(self, issues) -> None:
        """Show validation issues as overlays on the plan view."""
        self._clear_validation()
        if not self._alignment or not self.plot_widget:
            return

        for issue in issues:
            if issue.chainage is not None:
                pt = self._alignment.point_at(issue.chainage)
                if pt:
                    severity_color = (255, 50, 50) if issue.severity.value == "error" else (255, 200, 50)
                    symbol = "x" if issue.severity.value == "error" else "t1"
                    marker = self.plot_widget.plot(
                        [pt.x], [pt.y], pen=None,
                        symbol=symbol, symbolSize=12,
                        symbolBrush=pg.mkBrush(*severity_color, 150),
                        symbolPen=pg.mkPen(severity_color, width=2),
                    )
                    self._validation_items.append(marker)

                    text = pg.TextItem(
                        issue.title[:30], color=severity_color, anchor=(0, 1),
                    )
                    text.setPos(pt.x, pt.y)
                    font = QFont("monospace", 7)
                    text.setFont(font)
                    self.plot_widget.addItem(text)
                    self._validation_items.append(text)

    # --- Mouse Event Handlers ---
    def _on_mouse_moved(self, pos) -> None:
        if not self.plot_widget:
            return

        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
        world_pt = Point2D(mouse_point.x(), mouse_point.y())
        self._mouse_world_pt = world_pt

        # Update crosshair
        self._crosshair_v.setPos(mouse_point.x())
        self._crosshair_h.setPos(mouse_point.y())

        # Update coordinate bar
        self.coord_bar.update_coords(mouse_point.x(), mouse_point.y())
        self.coordinates_changed.emit(mouse_point.x(), mouse_point.y())

        # Snap
        view_range = self.plot_widget.plotItem.vb.viewRange()
        x_span = abs(view_range[0][1] - view_range[0][0])
        pixel_scale = x_span / max(self.plot_widget.width(), 1)
        snap = self.snap_engine.snap(world_pt, pixel_scale)
        self._last_snap = snap

        # Show snap indicator
        self._draw_snap_indicator(snap)
        snap_text = self.snap_engine.get_snap_indicator_text(snap.snap_type)
        self.coord_bar.update_snap(snap_text)

        # Forward to tool
        if self._current_tool:
            self._clear_previews()
            result = self._current_tool.on_mouse_move(world_pt, snap)
            if result:
                self._handle_tool_result(result)

    def _on_mouse_clicked(self, event) -> None:
        if not self.plot_widget or not self._current_tool:
            return

        if event.button() == Qt.MouseButton.RightButton:
            self._handle_right_click(event)
            return

        pos = event.scenePos()
        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
        world_pt = Point2D(mouse_point.x(), mouse_point.y())

        snap = self._last_snap or SnapResult(world_pt, SnapType.NONE)

        result = self._current_tool.on_mouse_press(world_pt, snap)
        if result:
            self._handle_tool_result(result)
            self.tool_action.emit(result)

        self.coord_bar.update_tool(self._current_tool.status_text)

    def _handle_right_click(self, event) -> None:
        """Handle right-click context menu."""
        if self._current_tool and self._current_tool.tool_type != ToolType.SELECT:
            self._current_tool.deactivate()
            self._current_tool = SelectTool()
            self._current_tool.activate()
            self._clear_previews()
            self.coord_bar.update_tool(self._current_tool.status_text)

    # --- Tool Result Processing ---
    def _handle_tool_result(self, result: dict) -> None:
        """Process tool action results for visual feedback."""
        if not self.plot_widget or not result:
            return

        rtype = result.get("type", "")

        if rtype == "preview_line":
            self._draw_preview_line(result["start"], result["end"])
            dist = result.get("length", result["start"].distance_to(result["end"]))
            az = result.get("azimuth", 0)
            self.coord_bar.update_measure(f"L={dist:.2f} m  Az={az:.2f}°")

        elif rtype == "preview_arc_3pt":
            self._draw_preview_arc(result["p1"], result["p2"], result["p3"])

        elif rtype == "preview_transition":
            self._draw_preview_line(result["start"], result["end"],
                                   color=(100, 100, 200, 120))
            self.coord_bar.update_measure(f"L={result['length']:.2f} m")

        elif rtype == "preview_measure":
            self._draw_preview_line(result["start"], result["end"],
                                   color=_MEASURE_COLOR, width=1)
            self.coord_bar.update_measure(
                f"D={result['distance']:.3f} m  Az={result['azimuth']:.2f}°"
            )

        elif rtype == "measure_result":
            self._draw_measurement_line(
                result["start"], result["end"],
                result["distance"], result["azimuth"],
            )
            self.coord_bar.update_measure(
                f"D={result['distance']:.3f} m  "
                f"dX={result['dx']:.3f}  dY={result['dy']:.3f}  "
                f"Az={result['azimuth']:.2f}°"
            )

        elif rtype == "preview_pi":
            pts = result["points"]
            for i in range(len(pts) - 1):
                self._draw_preview_line(pts[i], pts[i + 1],
                                       color=(200, 200, 100, 120))
            # Draw PI markers
            for pt in pts[1:-1]:
                marker = self.plot_widget.plot(
                    [pt.x], [pt.y], pen=None,
                    symbol="t", symbolSize=10,
                    symbolBrush=pg.mkBrush(200, 200, 100, 150),
                )
                self._preview_items.append(marker)

        elif rtype == "preview_scs":
            self._draw_preview_line(result["start"], result["through"])
            # Show side indicator
            text = pg.TextItem(
                result.get("side", ""), color=(200, 200, 100),
                anchor=(0.5, 0.5),
            )
            text.setPos(result["end"].x, result["end"].y)
            self.plot_widget.addItem(text)
            self._preview_items.append(text)

        elif rtype == "preview_angle":
            pts = result["points"]
            for i in range(len(pts) - 1):
                self._draw_preview_line(pts[i], pts[i + 1],
                                       color=_MEASURE_COLOR, width=1)

        elif rtype == "angle_result":
            self.coord_bar.update_measure(
                f"Kąt: {result['angle_deg']:.4f}° ({result['angle_rad']:.6f} rad)"
            )

        elif rtype == "hover":
            snap = result.get("snap")
            if snap and snap.snap_type != SnapType.NONE:
                pass  # snap indicator already drawn
            self.coord_bar.update_measure("")

        elif rtype == "select":
            idx = result.get("index", -1)
            if idx >= 0:
                self._selected_indices = {idx}
                self._redraw()
                self.element_clicked.emit(idx)

        elif rtype == "pick":
            # Try to find element near click
            pt = result["point"]
            idx = self._find_nearest_element(pt)
            if idx >= 0:
                self._selected_indices = {idx}
                self._redraw()
                self.element_clicked.emit(idx)
            else:
                self._selected_indices.clear()
                self._redraw()

        elif rtype in ("cancel_draw", "cancel_measure"):
            self._clear_previews()
            self._clear_measurements()
            self.coord_bar.update_measure("")

        elif rtype == "rubber_band":
            start, end = result["start"], result["end"]
            xs = [start.x, end.x, end.x, start.x, start.x]
            ys = [start.y, start.y, end.y, end.y, start.y]
            item = self.plot_widget.plot(
                xs, ys,
                pen=pg.mkPen(color=(100, 150, 255, 100), width=1, style=Qt.PenStyle.DashLine),
            )
            self._preview_items.append(item)

    def _find_nearest_element(self, world_pt: Point2D) -> int:
        """Find nearest element to a world point."""
        if not self._alignment or not self._alignment.horizontal_elements:
            return -1

        best_idx = -1
        best_dist = float("inf")

        for i, elem in enumerate(self._alignment.horizontal_elements):
            n = max(5, int(elem.length / 5.0))
            for j in range(n + 1):
                ch = elem.start_chainage + elem.length * j / n
                p = elem.point_at(ch)
                d = world_pt.distance_to(p)
                if d < best_dist:
                    best_dist = d
                    best_idx = i

        if best_idx >= 0 and self.plot_widget:
            view_range = self.plot_widget.plotItem.vb.viewRange()
            x_span = abs(view_range[0][1] - view_range[0][0])
            threshold = x_span * 0.03
            if best_dist > threshold:
                return -1

        return best_idx

    # --- Public Methods ---
    def highlight_element(self, index: int) -> None:
        self._selected_indices = {index} if index >= 0 else set()
        self._redraw()

    def select_elements(self, indices: set[int]) -> None:
        self._selected_indices = indices
        self._redraw()

    def zoom_to_fit(self) -> None:
        if self.plot_widget and self._alignment and self._alignment.horizontal_elements:
            self.plot_widget.autoRange()

    def zoom_to_element(self, index: int) -> None:
        if not self.plot_widget or not self._alignment:
            return
        if index < 0 or index >= len(self._alignment.horizontal_elements):
            return
        elem = self._alignment.horizontal_elements[index]
        sp = elem.start_point
        ep = elem.end_point
        margin = max(elem.length * 0.2, 20)
        x_min = min(sp.x, ep.x) - margin
        x_max = max(sp.x, ep.x) + margin
        y_min = min(sp.y, ep.y) - margin
        y_max = max(sp.y, ep.y) + margin
        self.plot_widget.setRange(xRange=(x_min, x_max), yRange=(y_min, y_max))

    def clear_measurements(self) -> None:
        self._clear_measurements()

    def set_chainage_interval(self, interval: float) -> None:
        self._chainage_label_interval = interval
        self._redraw()

    def toggle_handles(self, show: bool) -> None:
        self._show_handles = show
        self._redraw()

    def toggle_chainage_labels(self, show: bool) -> None:
        self._show_chainage_labels = show
        self._redraw()

    def toggle_tangent_lines(self, show: bool) -> None:
        self._show_tangent_lines = show
        self._redraw()

    # --- Keyboard ---
    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()

        # Forward to current tool
        if self._current_tool:
            result = self._current_tool.on_key_press(key)
            if result:
                self._handle_tool_result(result)
                self.tool_action.emit(result)
                self.coord_bar.update_tool(self._current_tool.status_text)
                return

        # Global shortcuts
        if key == Qt.Key.Key_F:
            self.zoom_to_fit()
        elif key == Qt.Key.Key_Delete:
            if self._selected_indices:
                self.tool_action.emit({
                    "type": "delete_elements",
                    "indices": list(self._selected_indices),
                })
        elif key == Qt.Key.Key_Escape:
            self._selected_indices.clear()
            self._clear_previews()
            self._clear_measurements()
            self._redraw()

        super().keyPressEvent(event)
