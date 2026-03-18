"""Turnout catalog selection dialog."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from railtrack.domain.turnout import Turnout, TurnoutHand
from railtrack.domain.turnout_library import TURNOUT_LIBRARY, TurnoutCatalogEntry


class TurnoutCatalogDialog(QDialog):
    """Dialog for selecting a turnout from the catalog and placing it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Katalog rozjazdów")
        self.resize(800, 500)
        self.setModal(True)

        self._created_turnout: Turnout | None = None
        self._entries = TURNOUT_LIBRARY.all()

        layout = QVBoxLayout(self)

        # Filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Typ szyny:"))
        self.rail_filter = QComboBox()
        self.rail_filter.addItems(["Wszystkie", "S49", "49E1", "60E1"])
        self.rail_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.rail_filter)

        filter_layout.addWidget(QLabel("Typ rozjazdu:"))
        self.type_filter = QComboBox()
        self.type_filter.addItems(["Wszystkie", "Zwyczajny", "Symetryczny", "Krzywoliniowy"])
        self.type_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.type_filter)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Catalog table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Opis", "Szyna", "Krzyżownica", "R [m]",
            "Długość [m]", "V przejazd", "V zwrotnica",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        # Placement parameters
        place_layout = QFormLayout()
        self.chainage_spin = QDoubleSpinBox()
        self.chainage_spin.setRange(0, 999999)
        self.chainage_spin.setDecimals(3)
        self.chainage_spin.setSuffix(" m")
        place_layout.addRow("Kilometraż:", self.chainage_spin)

        self.hand_combo = QComboBox()
        self.hand_combo.addItems(["Prawy", "Lewy"])
        place_layout.addRow("Ręka:", self.hand_combo)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("(automatycznie z katalogu)")
        place_layout.addRow("Nazwa:", self.name_edit)
        layout.addLayout(place_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        insert_btn = QPushButton("Wstaw rozjazd")
        insert_btn.clicked.connect(self._do_insert)
        btn_layout.addWidget(insert_btn)
        cancel_btn = QPushButton("Anuluj")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self._populate_table(self._entries)

    def _apply_filter(self):
        entries = TURNOUT_LIBRARY.all()

        rail = self.rail_filter.currentText()
        if rail != "Wszystkie":
            entries = [e for e in entries if e.rail_type == rail]

        type_text = self.type_filter.currentText()
        type_map = {"Zwyczajny": "simple", "Symetryczny": "symmetric", "Krzywoliniowy": "curved"}
        if type_text in type_map:
            entries = [e for e in entries if e.turnout_type.value == type_map[type_text]]

        self._entries = entries
        self._populate_table(entries)

    def _populate_table(self, entries: list[TurnoutCatalogEntry]):
        self.table.setRowCount(len(entries))
        for i, e in enumerate(entries):
            self.table.setItem(i, 0, QTableWidgetItem(e.catalog_id))
            self.table.setItem(i, 1, QTableWidgetItem(e.description))
            self.table.setItem(i, 2, QTableWidgetItem(e.rail_type))
            self.table.setItem(i, 3, QTableWidgetItem(f"1:{e.frog_ratio}"))
            self.table.setItem(i, 4, QTableWidgetItem(f"{e.curve_radius:.0f}"))
            self.table.setItem(i, 5, QTableWidgetItem(f"{e.total_length:.3f}"))
            self.table.setItem(i, 6, QTableWidgetItem(f"{e.speed_through:.0f} km/h"))
            self.table.setItem(i, 7, QTableWidgetItem(f"{e.speed_diverging:.0f} km/h"))

    def _do_insert(self):
        rows = set(idx.row() for idx in self.table.selectedIndexes())
        if not rows:
            return
        row = next(iter(rows))
        if row >= len(self._entries):
            return

        entry = self._entries[row]
        hand = TurnoutHand.RIGHT if self.hand_combo.currentIndex() == 0 else TurnoutHand.LEFT
        chainage = self.chainage_spin.value()
        name = self.name_edit.text().strip()

        self._created_turnout = entry.create_turnout(chainage, hand, name)
        self.accept()

    @property
    def created_turnout(self) -> Turnout | None:
        return self._created_turnout
