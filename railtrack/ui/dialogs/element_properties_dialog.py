"""Dialog for editing element properties."""
from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QVBoxLayout,
    QDoubleSpinBox, QComboBox, QGroupBox, QLabel, QLineEdit,
)

from railtrack.domain.horizontal import (
    CircularArc, CurveDirection, HorizontalElementUnion, Straight, TransitionCurve,
)
from railtrack.domain.primitives import Point2D
from railtrack.domain.vertical import VerticalCurve, VerticalGrade


class HorizontalElementDialog(QDialog):
    """Dialog for editing horizontal element properties."""

    def __init__(self, element: HorizontalElementUnion, parent=None):
        super().__init__(parent)
        self._element = element
        self._result_element: HorizontalElementUnion | None = None

        self.setWindowTitle("Właściwości elementu")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Element info
        info_group = QGroupBox("Informacje")
        info_layout = QFormLayout(info_group)

        etype = element.element_type.value
        type_labels = {
            "straight": "Prosta",
            "circular_arc": "Łuk kołowy",
            "transition_curve": "Krzywa przejściowa",
        }
        info_layout.addRow("Typ:", QLabel(type_labels.get(etype, etype)))
        info_layout.addRow("Km pocz.:", QLabel(f"{element.start_chainage:.3f} m"))
        info_layout.addRow("Km końc.:", QLabel(f"{element.end_chainage:.3f} m"))
        info_layout.addRow("Punkt pocz.:",
                          QLabel(f"({element.start_point.x:.3f}, {element.start_point.y:.3f})"))
        info_layout.addRow("Punkt końc.:",
                          QLabel(f"({element.end_point.x:.3f}, {element.end_point.y:.3f})"))
        info_layout.addRow("Azymut pocz.:",
                          QLabel(f"{math.degrees(element.start_azimuth):.4f}°"))
        info_layout.addRow("Azymut końc.:",
                          QLabel(f"{math.degrees(element.end_azimuth):.4f}°"))
        layout.addWidget(info_group)

        # Editable parameters
        edit_group = QGroupBox("Parametry")
        edit_layout = QFormLayout(edit_group)

        self.length_spin = QDoubleSpinBox()
        self.length_spin.setRange(0.1, 100000)
        self.length_spin.setDecimals(3)
        self.length_spin.setSuffix(" m")
        self.length_spin.setValue(element.length)
        edit_layout.addRow("Długość:", self.length_spin)

        self.azimuth_spin = QDoubleSpinBox()
        self.azimuth_spin.setRange(0, 360)
        self.azimuth_spin.setDecimals(4)
        self.azimuth_spin.setSuffix("°")
        self.azimuth_spin.setValue(math.degrees(element.start_azimuth))
        edit_layout.addRow("Azymut:", self.azimuth_spin)

        self.start_x_spin = QDoubleSpinBox()
        self.start_x_spin.setRange(-1e9, 1e9)
        self.start_x_spin.setDecimals(3)
        self.start_x_spin.setSuffix(" m")
        self.start_x_spin.setValue(element.start_point.x)
        edit_layout.addRow("X początkowe:", self.start_x_spin)

        self.start_y_spin = QDoubleSpinBox()
        self.start_y_spin.setRange(-1e9, 1e9)
        self.start_y_spin.setDecimals(3)
        self.start_y_spin.setSuffix(" m")
        self.start_y_spin.setValue(element.start_point.y)
        edit_layout.addRow("Y początkowe:", self.start_y_spin)

        # Arc-specific
        self.radius_spin = None
        self.direction_combo = None
        if isinstance(element, CircularArc):
            self.radius_spin = QDoubleSpinBox()
            self.radius_spin.setRange(1, 100000)
            self.radius_spin.setDecimals(2)
            self.radius_spin.setSuffix(" m")
            self.radius_spin.setValue(element.radius)
            edit_layout.addRow("Promień:", self.radius_spin)

            self.direction_combo = QComboBox()
            self.direction_combo.addItems(["Prawo", "Lewo"])
            self.direction_combo.setCurrentIndex(
                0 if element.direction == CurveDirection.RIGHT else 1
            )
            edit_layout.addRow("Kierunek:", self.direction_combo)

        # Transition-specific
        self.radius_start_spin = None
        self.radius_end_spin = None
        self.trans_direction_combo = None
        if isinstance(element, TransitionCurve):
            self.radius_start_spin = QDoubleSpinBox()
            self.radius_start_spin.setRange(0, 100000)
            self.radius_start_spin.setDecimals(2)
            self.radius_start_spin.setSuffix(" m")
            self.radius_start_spin.setSpecialValueText("∞")
            self.radius_start_spin.setValue(
                0 if math.isinf(element.radius_start) else element.radius_start
            )
            edit_layout.addRow("R początkowy:", self.radius_start_spin)

            self.radius_end_spin = QDoubleSpinBox()
            self.radius_end_spin.setRange(0, 100000)
            self.radius_end_spin.setDecimals(2)
            self.radius_end_spin.setSuffix(" m")
            self.radius_end_spin.setSpecialValueText("∞")
            self.radius_end_spin.setValue(
                0 if math.isinf(element.radius_end) else element.radius_end
            )
            edit_layout.addRow("R końcowy:", self.radius_end_spin)

            self.trans_direction_combo = QComboBox()
            self.trans_direction_combo.addItems(["Prawo", "Lewo"])
            self.trans_direction_combo.setCurrentIndex(
                0 if element.direction == CurveDirection.RIGHT else 1
            )
            edit_layout.addRow("Kierunek:", self.trans_direction_combo)

        layout.addWidget(edit_group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        pt = Point2D(self.start_x_spin.value(), self.start_y_spin.value())
        az = math.radians(self.azimuth_spin.value())
        length = self.length_spin.value()

        if isinstance(self._element, Straight):
            self._result_element = Straight(
                self._element.start_chainage, length, pt, az,
            )
        elif isinstance(self._element, CircularArc):
            direction = CurveDirection.RIGHT if self.direction_combo.currentIndex() == 0 else CurveDirection.LEFT
            self._result_element = CircularArc(
                self._element.start_chainage, length, pt, az,
                self.radius_spin.value(), direction,
            )
        elif isinstance(self._element, TransitionCurve):
            direction = CurveDirection.RIGHT if self.trans_direction_combo.currentIndex() == 0 else CurveDirection.LEFT
            rs = self.radius_start_spin.value()
            re = self.radius_end_spin.value()
            self._result_element = TransitionCurve(
                self._element.start_chainage, length, pt, az,
                math.inf if rs == 0 else rs,
                math.inf if re == 0 else re,
                direction,
            )
        self.accept()

    @property
    def result_element(self) -> HorizontalElementUnion | None:
        return self._result_element


class VerticalElementDialog(QDialog):
    """Dialog for editing vertical element properties."""

    def __init__(self, element=None, chainage: float = 0.0,
                 elevation: float = 0.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Element pionowy")
        self.setMinimumWidth(350)

        self._result = None
        is_new = element is None

        layout = QVBoxLayout(self)

        # Type selection (for new elements)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Spadek stały", "Krzywa pionowa"])
        if element and isinstance(element, VerticalCurve):
            self.type_combo.setCurrentIndex(1)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self.type_combo)

        form = QFormLayout()

        self.chainage_spin = QDoubleSpinBox()
        self.chainage_spin.setRange(-1e6, 1e6)
        self.chainage_spin.setDecimals(3)
        self.chainage_spin.setSuffix(" m")
        self.chainage_spin.setValue(chainage if is_new else element.start_chainage)
        form.addRow("Km pocz.:", self.chainage_spin)

        self.length_spin = QDoubleSpinBox()
        self.length_spin.setRange(0.1, 100000)
        self.length_spin.setDecimals(3)
        self.length_spin.setSuffix(" m")
        self.length_spin.setValue(100.0 if is_new else element.length)
        form.addRow("Długość:", self.length_spin)

        self.elevation_spin = QDoubleSpinBox()
        self.elevation_spin.setRange(-1000, 10000)
        self.elevation_spin.setDecimals(3)
        self.elevation_spin.setSuffix(" m")
        elev_val = elevation if is_new else element.start_elevation
        self.elevation_spin.setValue(elev_val)
        form.addRow("Rzędna pocz.:", self.elevation_spin)

        self.gradient_spin = QDoubleSpinBox()
        self.gradient_spin.setRange(-100, 100)
        self.gradient_spin.setDecimals(2)
        self.gradient_spin.setSuffix(" ‰")
        if not is_new and isinstance(element, VerticalGrade):
            self.gradient_spin.setValue(element.gradient * 1000)
        elif not is_new and isinstance(element, VerticalCurve):
            self.gradient_spin.setValue(element.gradient_in * 1000)
        form.addRow("Spadek/Gradient wej.:", self.gradient_spin)

        self.gradient_out_spin = QDoubleSpinBox()
        self.gradient_out_spin.setRange(-100, 100)
        self.gradient_out_spin.setDecimals(2)
        self.gradient_out_spin.setSuffix(" ‰")
        if not is_new and isinstance(element, VerticalCurve):
            self.gradient_out_spin.setValue(element.gradient_out * 1000)
        form.addRow("Gradient wyj.:", self.gradient_out_spin)

        layout.addLayout(form)

        self._on_type_changed(self.type_combo.currentIndex())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_type_changed(self, idx: int) -> None:
        is_curve = idx == 1
        self.gradient_out_spin.setEnabled(is_curve)

    def _accept(self) -> None:
        ch = self.chainage_spin.value()
        length = self.length_spin.value()
        elev = self.elevation_spin.value()
        grad = self.gradient_spin.value() / 1000.0

        if self.type_combo.currentIndex() == 0:
            self._result = VerticalGrade(ch, length, elev, grad)
        else:
            grad_out = self.gradient_out_spin.value() / 1000.0
            self._result = VerticalCurve(ch, length, elev, grad, grad_out)
        self.accept()

    @property
    def result_element(self):
        return self._result


class CoordinateInputDialog(QDialog):
    """Dialog for precise coordinate input."""

    def __init__(self, parent=None, current_x: float = 0.0, current_y: float = 0.0):
        super().__init__(parent)
        self.setWindowTitle("Wprowadź współrzędne")
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(-1e9, 1e9)
        self.x_spin.setDecimals(3)
        self.x_spin.setSuffix(" m")
        self.x_spin.setValue(current_x)
        form.addRow("X (Easting):", self.x_spin)

        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(-1e9, 1e9)
        self.y_spin.setDecimals(3)
        self.y_spin.setSuffix(" m")
        self.y_spin.setValue(current_y)
        form.addRow("Y (Northing):", self.y_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def point(self) -> Point2D:
        return Point2D(self.x_spin.value(), self.y_spin.value())


class SCSParametersDialog(QDialog):
    """Dialog for S-T-C-T-S sequence parameters."""

    def __init__(self, parent=None, direction: CurveDirection = CurveDirection.RIGHT):
        super().__init__(parent)
        self.setWindowTitle("Parametry S-T-C-T-S")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.straight1_spin = QDoubleSpinBox()
        self.straight1_spin.setRange(0, 100000)
        self.straight1_spin.setDecimals(1)
        self.straight1_spin.setSuffix(" m")
        self.straight1_spin.setValue(100.0)
        form.addRow("Prosta 1:", self.straight1_spin)

        self.transition1_spin = QDoubleSpinBox()
        self.transition1_spin.setRange(0, 10000)
        self.transition1_spin.setDecimals(1)
        self.transition1_spin.setSuffix(" m")
        self.transition1_spin.setValue(60.0)
        form.addRow("Klotoida 1:", self.transition1_spin)

        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(50, 100000)
        self.radius_spin.setDecimals(1)
        self.radius_spin.setSuffix(" m")
        self.radius_spin.setValue(500.0)
        form.addRow("Promień łuku:", self.radius_spin)

        self.arc_length_spin = QDoubleSpinBox()
        self.arc_length_spin.setRange(1, 100000)
        self.arc_length_spin.setDecimals(1)
        self.arc_length_spin.setSuffix(" m")
        self.arc_length_spin.setValue(200.0)
        form.addRow("Długość łuku:", self.arc_length_spin)

        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["Prawo", "Lewo"])
        self.direction_combo.setCurrentIndex(
            0 if direction == CurveDirection.RIGHT else 1
        )
        form.addRow("Kierunek:", self.direction_combo)

        self.transition2_spin = QDoubleSpinBox()
        self.transition2_spin.setRange(0, 10000)
        self.transition2_spin.setDecimals(1)
        self.transition2_spin.setSuffix(" m")
        self.transition2_spin.setValue(60.0)
        form.addRow("Klotoida 2:", self.transition2_spin)

        self.straight2_spin = QDoubleSpinBox()
        self.straight2_spin.setRange(0, 100000)
        self.straight2_spin.setDecimals(1)
        self.straight2_spin.setSuffix(" m")
        self.straight2_spin.setValue(100.0)
        form.addRow("Prosta 2:", self.straight2_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def params(self) -> dict:
        return {
            "straight1_length": self.straight1_spin.value(),
            "transition1_length": self.transition1_spin.value(),
            "arc_radius": self.radius_spin.value(),
            "arc_length": self.arc_length_spin.value(),
            "direction": CurveDirection.RIGHT if self.direction_combo.currentIndex() == 0 else CurveDirection.LEFT,
            "transition2_length": self.transition2_spin.value(),
            "straight2_length": self.straight2_spin.value(),
        }
