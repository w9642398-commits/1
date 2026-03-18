"""Plan (horizontal) view using pyqtgraph for fast rendering."""
from __future__ import annotations

import math

from PySide6.QtWidgets import QVBoxLayout, QWidget

try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False

from railtrack.domain.alignment import Alignment
from railtrack.domain.horizontal import CircularArc, Straight, TransitionCurve
from railtrack.geometry_engine.horizontal_engine import compute_points_along


class PlanView(QWidget):
    """Interactive plan view of horizontal alignment."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if HAS_PYQTGRAPH:
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.setAspectLocked(True)
            self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
            self.plot_widget.setLabel("bottom", "Easting [m]")
            self.plot_widget.setLabel("left", "Northing [m]")
            layout.addWidget(self.plot_widget)
        else:
            from PySide6.QtWidgets import QLabel
            layout.addWidget(QLabel("pyqtgraph nie jest zainstalowany - widok planu niedostępny"))
            self.plot_widget = None

    def set_alignment(self, alignment: Alignment):
        if not self.plot_widget:
            return
        self.plot_widget.clear()

        if not alignment.horizontal_elements:
            return

        # Draw each element with distinct color
        colors = {
            "straight": (100, 200, 100),    # green
            "circular_arc": (200, 100, 100), # red
            "transition_curve": (100, 100, 200),  # blue
        }

        for elem in alignment.horizontal_elements:
            etype = elem.element_type.value
            color = colors.get(etype, (200, 200, 200))

            if isinstance(elem, Straight):
                sp, ep = elem.start_point, elem.end_point
                self.plot_widget.plot(
                    [sp.x, ep.x], [sp.y, ep.y],
                    pen=pg.mkPen(color=color, width=2),
                )
            else:
                # Arc or transition: discretize
                n = max(20, int(elem.length / 2.0))
                xs, ys = [], []
                for j in range(n + 1):
                    ch = elem.start_chainage + elem.length * j / n
                    p = elem.point_at(ch)
                    xs.append(p.x)
                    ys.append(p.y)
                self.plot_widget.plot(xs, ys, pen=pg.mkPen(color=color, width=2))

        # Start/end markers
        if alignment.horizontal_elements:
            sp = alignment.horizontal_elements[0].start_point
            ep = alignment.horizontal_elements[-1].end_point
            self.plot_widget.plot([sp.x], [sp.y], pen=None, symbol="o", symbolSize=8, symbolBrush="g")
            self.plot_widget.plot([ep.x], [ep.y], pen=None, symbol="s", symbolSize=8, symbolBrush="r")
