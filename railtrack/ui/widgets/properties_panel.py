"""Properties / design criteria panel."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
    QGroupBox,
)

from railtrack.domain.alignment import Alignment, DesignCriteria


class PropertiesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Alignment info
        self.info_group = QGroupBox("Oś")
        info_layout = QFormLayout()
        self.lbl_name = QLabel("-")
        self.lbl_length = QLabel("-")
        self.lbl_h_count = QLabel("-")
        self.lbl_v_count = QLabel("-")
        self.lbl_start_ch = QLabel("-")
        self.lbl_end_ch = QLabel("-")
        info_layout.addRow("Nazwa:", self.lbl_name)
        info_layout.addRow("Długość:", self.lbl_length)
        info_layout.addRow("Elem. poziomych:", self.lbl_h_count)
        info_layout.addRow("Elem. pionowych:", self.lbl_v_count)
        info_layout.addRow("Km pocz.:", self.lbl_start_ch)
        info_layout.addRow("Km końc.:", self.lbl_end_ch)
        self.info_group.setLayout(info_layout)
        layout.addWidget(self.info_group)

        # Design criteria
        self.criteria_group = QGroupBox("Kryteria projektowe")
        criteria_layout = QFormLayout()
        self.lbl_speed = QLabel("-")
        self.lbl_gauge = QLabel("-")
        self.lbl_min_r = QLabel("-")
        self.lbl_max_cant = QLabel("-")
        self.lbl_max_grad = QLabel("-")
        criteria_layout.addRow("V_max:", self.lbl_speed)
        criteria_layout.addRow("Rozstaw:", self.lbl_gauge)
        criteria_layout.addRow("R_min:", self.lbl_min_r)
        criteria_layout.addRow("D_max:", self.lbl_max_cant)
        criteria_layout.addRow("i_max:", self.lbl_max_grad)
        self.criteria_group.setLayout(criteria_layout)
        layout.addWidget(self.criteria_group)

        layout.addStretch()

    def set_alignment(self, alignment: Alignment, criteria: DesignCriteria | None = None):
        self.lbl_name.setText(alignment.name)
        self.lbl_length.setText(f"{alignment.total_length:.3f} m")
        self.lbl_h_count.setText(str(len(alignment.horizontal_elements)))
        self.lbl_v_count.setText(str(len(alignment.vertical_elements)))
        self.lbl_start_ch.setText(f"{alignment.start_chainage:.3f}")
        self.lbl_end_ch.setText(f"{alignment.end_chainage:.3f}")

        if criteria:
            self.lbl_speed.setText(f"{criteria.max_speed_kmh} km/h")
            self.lbl_gauge.setText(f"{criteria.gauge} m")
            self.lbl_min_r.setText(f"{criteria.min_radius} m")
            self.lbl_max_cant.setText(f"{criteria.max_cant * 1000:.0f} mm")
            self.lbl_max_grad.setText(f"{criteria.max_gradient * 1000:.1f} ‰")
