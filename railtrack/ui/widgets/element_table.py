"""Element table widget for displaying and editing alignment elements."""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QPushButton,
    QComboBox,
)

from railtrack.domain.alignment import Alignment
from railtrack.domain.horizontal import (
    CircularArc,
    CurveDirection,
    HorizontalElementUnion,
    Straight,
    TransitionCurve,
)
from railtrack.domain.primitives import Point2D


class ElementTable(QWidget):
    element_changed = Signal()
    element_selected = Signal(int)  # emitted with element index when row is selected

    COLUMNS = [
        "Typ", "Km pocz.", "Km końc.", "Długość",
        "X pocz.", "Y pocz.", "X końc.", "Y końc.",
        "Az pocz. (°)", "Az końc. (°)", "Promień", "Kierunek",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("+ Dodaj element")
        self.add_btn.clicked.connect(self._add_element)
        self.remove_btn = QPushButton("- Usuń")
        self.remove_btn.clicked.connect(self._remove_element)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Prosta", "Łuk kołowy", "Krzywa przejściowa"])
        toolbar.addWidget(self.type_combo)
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.remove_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)

        self._alignment: Alignment | None = None

    def set_alignment(self, alignment: Alignment):
        self._alignment = alignment
        self._refresh()

    def _refresh(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if not self._alignment:
            self.table.blockSignals(False)
            return

        for i, elem in enumerate(self._alignment.horizontal_elements):
            self.table.insertRow(i)
            etype = elem.element_type.value
            radius_str = ""
            direction_str = ""

            if isinstance(elem, CircularArc):
                radius_str = f"{elem.radius:.2f}"
                direction_str = elem.direction.value
            elif isinstance(elem, TransitionCurve):
                rs = "∞" if math.isinf(elem.radius_start) else f"{elem.radius_start:.2f}"
                re = "∞" if math.isinf(elem.radius_end) else f"{elem.radius_end:.2f}"
                radius_str = f"{rs} → {re}"
                direction_str = elem.direction.value

            values = [
                etype,
                f"{elem.start_chainage:.3f}",
                f"{elem.end_chainage:.3f}",
                f"{elem.length:.3f}",
                f"{elem.start_point.x:.3f}",
                f"{elem.start_point.y:.3f}",
                f"{elem.end_point.x:.3f}",
                f"{elem.end_point.y:.3f}",
                f"{math.degrees(elem.start_azimuth):.4f}",
                f"{math.degrees(elem.end_azimuth):.4f}",
                radius_str,
                direction_str,
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                # Make computed columns read-only
                if col in (1, 2, 4, 5, 6, 7, 8, 9):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i, col, item)

        self.table.blockSignals(False)

    def _add_element(self):
        if not self._alignment:
            return
        idx = self.type_combo.currentIndex()
        elems = self._alignment.horizontal_elements

        # Determine start parameters from last element
        if elems:
            last = elems[-1]
            ch = last.end_chainage
            pt = last.end_point
            az = last.end_azimuth
        else:
            ch = 0.0
            pt = Point2D(0.0, 0.0)
            az = 0.0

        if idx == 0:  # Straight
            elems.append(Straight(ch, 100.0, pt, az))
        elif idx == 1:  # Arc
            elems.append(CircularArc(ch, 100.0, pt, az, 500.0, CurveDirection.RIGHT))
        elif idx == 2:  # Transition
            elems.append(TransitionCurve(ch, 60.0, pt, az, math.inf, 500.0, CurveDirection.RIGHT))

        self._refresh()
        self.element_changed.emit()

    def _remove_element(self):
        if not self._alignment:
            return
        rows = set(idx.row() for idx in self.table.selectedIndexes())
        if not rows:
            return
        for row in sorted(rows, reverse=True):
            if row < len(self._alignment.horizontal_elements):
                self._alignment.horizontal_elements.pop(row)
        self._refresh()
        self.element_changed.emit()

    def _on_selection_changed(self):
        rows = set(idx.row() for idx in self.table.selectedIndexes())
        if len(rows) == 1:
            self.element_selected.emit(next(iter(rows)))

    def select_row(self, index: int):
        """Programmatically select a row (e.g. from plan view click)."""
        if 0 <= index < self.table.rowCount():
            self.table.blockSignals(True)
            self.table.selectRow(index)
            self.table.blockSignals(False)
