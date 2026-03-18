"""Profile (vertical) view using pyqtgraph."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False

from railtrack.domain.alignment import Alignment
from railtrack.geometry_engine.cant_engine import compute_cant_profile
from railtrack.geometry_engine.vertical_engine import compute_elevation_profile


class ProfileView(QWidget):
    """Vertical profile and cant diagram."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if HAS_PYQTGRAPH:
            self.plot_widget = pg.GraphicsLayoutWidget()
            layout.addWidget(self.plot_widget)

            self.elev_plot = self.plot_widget.addPlot(row=0, col=0, title="Profil pionowy")
            self.elev_plot.showGrid(x=True, y=True, alpha=0.3)
            self.elev_plot.setLabel("bottom", "Kilometraż [m]")
            self.elev_plot.setLabel("left", "Rzędna [m]")

            self.cant_plot = self.plot_widget.addPlot(row=1, col=0, title="Przechyłka")
            self.cant_plot.showGrid(x=True, y=True, alpha=0.3)
            self.cant_plot.setLabel("bottom", "Kilometraż [m]")
            self.cant_plot.setLabel("left", "Przechyłka [mm]")
        else:
            from PySide6.QtWidgets import QLabel
            layout.addWidget(QLabel("pyqtgraph nie jest zainstalowany - widok profilu niedostępny"))
            self.plot_widget = None

    def set_alignment(self, alignment: Alignment):
        if not self.plot_widget:
            return

        self.elev_plot.clear()
        self.cant_plot.clear()

        # Elevation profile
        if alignment.vertical_elements:
            elev_data = compute_elevation_profile(alignment.vertical_elements, interval=5.0)
            if elev_data:
                chs = [p[0] for p in elev_data]
                elevs = [p[1] for p in elev_data]
                self.elev_plot.plot(chs, elevs, pen=pg.mkPen(color=(50, 150, 50), width=2))

        # Cant profile
        if alignment.cant_elements:
            cant_data = compute_cant_profile(alignment.cant_elements, interval=5.0)
            if cant_data:
                chs = [p[0] for p in cant_data]
                cants = [p[1] * 1000.0 for p in cant_data]  # convert to mm
                self.cant_plot.plot(chs, cants, pen=pg.mkPen(color=(150, 50, 150), width=2))
