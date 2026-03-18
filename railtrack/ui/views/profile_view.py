"""Interactive profile (vertical) view with editing capabilities.

Provides interactive editing of vertical alignment and cant diagram.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QVBoxLayout, QWidget, QHBoxLayout, QLabel

try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False

from railtrack.domain.alignment import Alignment
from railtrack.domain.vertical import VerticalCurve, VerticalGrade
from railtrack.domain.cant import CantSegment, CantRamp
from railtrack.domain.primitives import Point2D
from railtrack.geometry_engine.cant_engine import compute_cant_profile
from railtrack.geometry_engine.vertical_engine import compute_elevation_profile


_GRADE_COLOR = (50, 180, 50)
_CURVE_COLOR = (200, 150, 50)
_CANT_COLOR = (150, 50, 150)
_CANT_RAMP_COLOR = (180, 100, 180)
_HANDLE_COLOR = (255, 200, 50)
_PREVIEW_COLOR = (200, 200, 200, 120)
_CROSSHAIR_COLOR = (80, 80, 80, 100)


class ProfileCoordBar(QWidget):
    """Status bar for profile view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(12)

        self.ch_label = QLabel("Km: 0.000")
        self.ch_label.setStyleSheet("color: #aaa; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.ch_label)

        self.elev_label = QLabel("Z: 0.000 m")
        self.elev_label.setStyleSheet("color: #6c6; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.elev_label)

        self.grad_label = QLabel("")
        self.grad_label.setStyleSheet("color: #cc6; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.grad_label)

        self.cant_label = QLabel("")
        self.cant_label.setStyleSheet("color: #c6c; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.cant_label)

        self.tool_label = QLabel("")
        self.tool_label.setStyleSheet("color: #8af; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.tool_label)

        layout.addStretch()


class ProfileView(QWidget):
    """Interactive vertical profile and cant diagram."""

    element_added = Signal(dict)
    element_modified = Signal(dict)
    element_removed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._alignment: Alignment | None = None
        self._elev_items: list = []
        self._cant_items: list = []
        self._handle_items: list = []
        self._preview_items: list = []
        self._selected_v_index: int = -1
        self._selected_c_index: int = -1
        self._dragging: bool = False
        self._drag_target: str = ""  # "grade", "curve", "cant"
        self._drag_index: int = -1
        self._drag_start_y: float = 0.0

        if HAS_PYQTGRAPH:
            self.plot_widget = pg.GraphicsLayoutWidget()
            self.plot_widget.setBackground((25, 25, 30))
            layout.addWidget(self.plot_widget)

            # Elevation profile plot
            self.elev_plot = self.plot_widget.addPlot(row=0, col=0, title="Profil pionowy")
            self.elev_plot.showGrid(x=True, y=True, alpha=0.3)
            self.elev_plot.setLabel("bottom", "Kilometraż [m]")
            self.elev_plot.setLabel("left", "Rzędna [m]")

            # Gradient diagram
            self.grad_plot = self.plot_widget.addPlot(row=1, col=0, title="Pochylenie [‰]")
            self.grad_plot.showGrid(x=True, y=True, alpha=0.3)
            self.grad_plot.setLabel("bottom", "Kilometraż [m]")
            self.grad_plot.setLabel("left", "i [‰]")
            self.grad_plot.setMaximumHeight(120)

            # Link X axes
            self.grad_plot.setXLink(self.elev_plot)

            # Cant profile plot
            self.cant_plot = self.plot_widget.addPlot(row=2, col=0, title="Przechyłka [mm]")
            self.cant_plot.showGrid(x=True, y=True, alpha=0.3)
            self.cant_plot.setLabel("bottom", "Kilometraż [m]")
            self.cant_plot.setLabel("left", "D [mm]")
            self.cant_plot.setMaximumHeight(120)
            self.cant_plot.setXLink(self.elev_plot)

            # Crosshair on elevation plot
            self._crosshair_v = pg.InfiniteLine(angle=90, pen=pg.mkPen(_CROSSHAIR_COLOR, width=1))
            self.elev_plot.addItem(self._crosshair_v)

            # Mouse events
            self.elev_plot.scene().sigMouseMoved.connect(self._on_elev_mouse_moved)
            self.elev_plot.scene().sigMouseClicked.connect(self._on_elev_mouse_clicked)
            self.cant_plot.scene().sigMouseClicked.connect(self._on_cant_mouse_clicked)

        else:
            from PySide6.QtWidgets import QLabel as QL
            layout.addWidget(QL("pyqtgraph nie jest zainstalowany"))
            self.plot_widget = None

        # Coordinate bar
        self.coord_bar = ProfileCoordBar()
        layout.addWidget(self.coord_bar)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_alignment(self, alignment: Alignment) -> None:
        self._alignment = alignment
        self._selected_v_index = -1
        self._selected_c_index = -1
        self._redraw()

    def _redraw(self) -> None:
        if not self.plot_widget:
            return

        self.elev_plot.clear()
        self.grad_plot.clear()
        self.cant_plot.clear()
        self._elev_items.clear()
        self._cant_items.clear()
        self._handle_items.clear()
        self._preview_items.clear()

        # Re-add crosshair
        self._crosshair_v = pg.InfiniteLine(angle=90, pen=pg.mkPen(_CROSSHAIR_COLOR, width=1))
        self.elev_plot.addItem(self._crosshair_v)

        if not self._alignment:
            return

        # --- Elevation Profile ---
        if self._alignment.vertical_elements:
            for i, elem in enumerate(self._alignment.vertical_elements):
                color = _CURVE_COLOR if isinstance(elem, VerticalCurve) else _GRADE_COLOR
                width = 3 if i == self._selected_v_index else 2

                n = max(20, int(elem.length / 2.0))
                chs, elevs = [], []
                for j in range(n + 1):
                    ch = elem.start_chainage + elem.length * j / n
                    chs.append(ch)
                    elevs.append(elem.elevation_at(ch))

                item = self.elev_plot.plot(chs, elevs, pen=pg.mkPen(color=color, width=width))
                self._elev_items.append(item)

                # Handles at boundaries
                sp_x = elem.start_chainage
                sp_y = elem.elevation_at(sp_x)
                ep_x = elem.end_chainage
                ep_y = elem.elevation_at(ep_x)

                handle_s = self.elev_plot.plot(
                    [sp_x], [sp_y], pen=None,
                    symbol="d", symbolSize=8,
                    symbolBrush=pg.mkBrush(_HANDLE_COLOR),
                    symbolPen=pg.mkPen((200, 150, 0), width=1),
                )
                self._handle_items.append(handle_s)

                # Gradient label
                if isinstance(elem, VerticalGrade):
                    grad_permille = elem.gradient * 1000
                    mid_ch = (sp_x + ep_x) / 2
                    mid_el = (sp_y + ep_y) / 2
                    text = pg.TextItem(
                        f"{grad_permille:+.1f}‰", color=_GRADE_COLOR, anchor=(0.5, 1),
                    )
                    text.setPos(mid_ch, mid_el)
                    font = QFont("monospace", 8)
                    text.setFont(font)
                    self.elev_plot.addItem(text)
                elif isinstance(elem, VerticalCurve):
                    mid_ch = (sp_x + ep_x) / 2
                    mid_el = elem.elevation_at(mid_ch)
                    r_text = f"R={elem.radius:.0f}" if not math.isinf(elem.radius) else ""
                    text = pg.TextItem(r_text, color=_CURVE_COLOR, anchor=(0.5, 1))
                    text.setPos(mid_ch, mid_el)
                    font = QFont("monospace", 8)
                    text.setFont(font)
                    self.elev_plot.addItem(text)

            # Gradient diagram
            for elem in self._alignment.vertical_elements:
                n = max(10, int(elem.length / 5.0))
                chs, grads = [], []
                for j in range(n + 1):
                    ch = elem.start_chainage + elem.length * j / n
                    chs.append(ch)
                    grads.append(elem.gradient_at(ch) * 1000)  # to permille
                color = _CURVE_COLOR if isinstance(elem, VerticalCurve) else _GRADE_COLOR
                self.grad_plot.plot(chs, grads, pen=pg.mkPen(color=color, width=2))

            # Zero line
            if self._alignment.vertical_elements:
                ch_s = self._alignment.vertical_elements[0].start_chainage
                ch_e = self._alignment.vertical_elements[-1].end_chainage
                self.grad_plot.plot(
                    [ch_s, ch_e], [0, 0],
                    pen=pg.mkPen(color=(100, 100, 100, 80), width=1, style=Qt.PenStyle.DashLine),
                )

        # --- Cant Profile ---
        if self._alignment.cant_elements:
            for i, elem in enumerate(self._alignment.cant_elements):
                color = _CANT_RAMP_COLOR if isinstance(elem, CantRamp) else _CANT_COLOR
                width = 3 if i == self._selected_c_index else 2

                n = max(10, int(elem.length / 2.0))
                chs, cants = [], []
                for j in range(n + 1):
                    ch = elem.start_chainage + elem.length * j / n
                    chs.append(ch)
                    cants.append(elem.cant_at(ch) * 1000)  # to mm
                item = self.cant_plot.plot(chs, cants, pen=pg.mkPen(color=color, width=width))
                self._cant_items.append(item)

                # Handle at start
                sp_x = elem.start_chainage
                sp_y = elem.cant_at(sp_x) * 1000
                handle = self.cant_plot.plot(
                    [sp_x], [sp_y], pen=None,
                    symbol="d", symbolSize=8,
                    symbolBrush=pg.mkBrush(_HANDLE_COLOR),
                )
                self._handle_items.append(handle)

            # Zero line
            if self._alignment.cant_elements:
                ch_s = self._alignment.cant_elements[0].start_chainage
                ch_e = self._alignment.cant_elements[-1].end_chainage
                self.cant_plot.plot(
                    [ch_s, ch_e], [0, 0],
                    pen=pg.mkPen(color=(100, 100, 100, 80), width=1, style=Qt.PenStyle.DashLine),
                )

    # --- Mouse Handlers ---
    def _on_elev_mouse_moved(self, pos) -> None:
        if not self.plot_widget or not self._alignment:
            return
        mouse_point = self.elev_plot.vb.mapSceneToView(pos)
        ch = mouse_point.x()
        self._crosshair_v.setPos(ch)

        self.coord_bar.ch_label.setText(f"Km: {ch / 1000:.3f}")

        # Show elevation at cursor
        elev = self._alignment.elevation_at(ch)
        if elev is not None:
            self.coord_bar.elev_label.setText(f"Z: {elev:.3f} m")

        # Show gradient
        for elem in self._alignment.vertical_elements:
            if elem.chainage_range.contains(ch):
                grad = elem.gradient_at(ch) * 1000
                self.coord_bar.grad_label.setText(f"i: {grad:+.2f}‰")
                break

        # Show cant
        cant = self._alignment.cant_at(ch)
        if cant is not None:
            self.coord_bar.cant_label.setText(f"D: {cant * 1000:.1f} mm")

    def _on_elev_mouse_clicked(self, event) -> None:
        if not self.plot_widget or not self._alignment:
            return

        pos = event.scenePos()
        mouse_point = self.elev_plot.vb.mapSceneToView(pos)
        ch = mouse_point.x()
        elev = mouse_point.y()

        if event.button() == Qt.MouseButton.LeftButton:
            # Find nearest vertical element
            best_idx = -1
            best_dist = float("inf")
            for i, elem in enumerate(self._alignment.vertical_elements):
                if elem.chainage_range.contains(ch):
                    d = abs(elem.elevation_at(ch) - elev)
                    if d < best_dist:
                        best_dist = d
                        best_idx = i

            if best_idx >= 0:
                # Check reasonable threshold
                view_range = self.elev_plot.vb.viewRange()
                y_span = abs(view_range[1][1] - view_range[1][0])
                if best_dist < y_span * 0.05:
                    self._selected_v_index = best_idx
                    self._redraw()
                    return

            # Double-click to add new grade/curve point
            if event.double():
                self.element_added.emit({
                    "type": "add_vertical_point",
                    "chainage": ch,
                    "elevation": elev,
                })

        elif event.button() == Qt.MouseButton.RightButton:
            if self._selected_v_index >= 0:
                self._selected_v_index = -1
                self._redraw()

    def _on_cant_mouse_clicked(self, event) -> None:
        if not self.plot_widget or not self._alignment:
            return
        pos = event.scenePos()
        mouse_point = self.cant_plot.vb.mapSceneToView(pos)
        ch = mouse_point.x()
        cant_mm = mouse_point.y()

        if event.button() == Qt.MouseButton.LeftButton:
            best_idx = -1
            best_dist = float("inf")
            for i, elem in enumerate(self._alignment.cant_elements):
                if elem.chainage_range.contains(ch):
                    d = abs(elem.cant_at(ch) * 1000 - cant_mm)
                    if d < best_dist:
                        best_dist = d
                        best_idx = i

            if best_idx >= 0:
                view_range = self.cant_plot.vb.viewRange()
                y_span = abs(view_range[1][1] - view_range[1][0])
                if best_dist < y_span * 0.1:
                    self._selected_c_index = best_idx
                    self._redraw()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete:
            if self._selected_v_index >= 0:
                self.element_removed.emit(self._selected_v_index)
                self._selected_v_index = -1
            elif self._selected_c_index >= 0:
                self._selected_c_index = -1
        elif event.key() == Qt.Key.Key_Escape:
            self._selected_v_index = -1
            self._selected_c_index = -1
            self._redraw()
        super().keyPressEvent(event)
