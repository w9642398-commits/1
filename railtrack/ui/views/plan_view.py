"""Plan (horizontal) view using pyqtgraph for fast rendering."""
from __future__ import annotations

import math

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False

from railtrack.domain.alignment import Alignment
from railtrack.domain.horizontal import CircularArc, Straight, TransitionCurve
from railtrack.domain.primitives import Point2D
from railtrack.geometry_engine.horizontal_engine import compute_points_along


# Element type colors
_COLORS = {
    "straight": (100, 200, 100),       # green
    "circular_arc": (200, 100, 100),    # red
    "transition_curve": (100, 100, 200),  # blue
}
_HIGHLIGHT_COLOR = (255, 255, 50)  # yellow highlight


class PlanView(QWidget):
    """Interactive plan view of horizontal alignment."""

    element_clicked = Signal(int)  # emitted with element index

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._alignment: Alignment | None = None
        self._element_items: list = []  # list of plot items per element
        self._highlight_item = None

        if HAS_PYQTGRAPH:
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.setAspectLocked(True)
            self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
            self.plot_widget.setLabel("bottom", "Easting [m]")
            self.plot_widget.setLabel("left", "Northing [m]")
            self.plot_widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)
            layout.addWidget(self.plot_widget)
        else:
            from PySide6.QtWidgets import QLabel
            layout.addWidget(QLabel("pyqtgraph nie jest zainstalowany - widok planu niedostępny"))
            self.plot_widget = None

    def set_alignment(self, alignment: Alignment):
        self._alignment = alignment
        self._element_items.clear()
        self._highlight_item = None

        if not self.plot_widget:
            return
        self.plot_widget.clear()

        if not alignment.horizontal_elements:
            return

        for elem in alignment.horizontal_elements:
            etype = elem.element_type.value
            color = _COLORS.get(etype, (200, 200, 200))

            if isinstance(elem, Straight):
                sp, ep = elem.start_point, elem.end_point
                item = self.plot_widget.plot(
                    [sp.x, ep.x], [sp.y, ep.y],
                    pen=pg.mkPen(color=color, width=2),
                )
            else:
                n = max(20, int(elem.length / 2.0))
                xs, ys = [], []
                for j in range(n + 1):
                    ch = elem.start_chainage + elem.length * j / n
                    p = elem.point_at(ch)
                    xs.append(p.x)
                    ys.append(p.y)
                item = self.plot_widget.plot(xs, ys, pen=pg.mkPen(color=color, width=2))

            self._element_items.append(item)

        # Start/end markers
        if alignment.horizontal_elements:
            sp = alignment.horizontal_elements[0].start_point
            ep = alignment.horizontal_elements[-1].end_point
            self.plot_widget.plot([sp.x], [sp.y], pen=None, symbol="o", symbolSize=8, symbolBrush="g")
            self.plot_widget.plot([ep.x], [ep.y], pen=None, symbol="s", symbolSize=8, symbolBrush="r")

    def highlight_element(self, index: int):
        """Highlight a specific element by index."""
        if not self.plot_widget or not self._alignment:
            return

        # Remove previous highlight
        if self._highlight_item is not None:
            self.plot_widget.removeItem(self._highlight_item)
            self._highlight_item = None

        if index < 0 or index >= len(self._alignment.horizontal_elements):
            return

        elem = self._alignment.horizontal_elements[index]
        if isinstance(elem, Straight):
            sp, ep = elem.start_point, elem.end_point
            self._highlight_item = self.plot_widget.plot(
                [sp.x, ep.x], [sp.y, ep.y],
                pen=pg.mkPen(color=_HIGHLIGHT_COLOR, width=5),
            )
        else:
            n = max(20, int(elem.length / 2.0))
            xs, ys = [], []
            for j in range(n + 1):
                ch = elem.start_chainage + elem.length * j / n
                p = elem.point_at(ch)
                xs.append(p.x)
                ys.append(p.y)
            self._highlight_item = self.plot_widget.plot(
                xs, ys, pen=pg.mkPen(color=_HIGHLIGHT_COLOR, width=5),
            )

    def _on_mouse_clicked(self, event):
        """Find the closest element to the click point and emit element_clicked."""
        if not self._alignment or not self._alignment.horizontal_elements:
            return
        if not self.plot_widget:
            return

        pos = event.scenePos()
        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
        click_x, click_y = mouse_point.x(), mouse_point.y()
        click_pt = Point2D(click_x, click_y)

        best_idx = -1
        best_dist = float("inf")

        for i, elem in enumerate(self._alignment.horizontal_elements):
            # Sample a few points along the element to find min distance
            for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
                ch = elem.start_chainage + elem.length * frac
                p = elem.point_at(ch)
                d = click_pt.distance_to(p)
                if d < best_dist:
                    best_dist = d
                    best_idx = i

        if best_idx >= 0:
            # Threshold: only select if close enough (relative to view extent)
            view_range = self.plot_widget.plotItem.vb.viewRange()
            x_span = abs(view_range[0][1] - view_range[0][0])
            threshold = x_span * 0.05  # 5% of view width
            if best_dist < threshold:
                self.highlight_element(best_idx)
                self.element_clicked.emit(best_idx)
