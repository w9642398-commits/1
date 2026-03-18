"""Validation issues panel."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QLabel,
)

from railtrack.domain.validation_types import Severity, ValidationIssue


_SEVERITY_COLORS = {
    Severity.ERROR: QColor(255, 200, 200),
    Severity.WARNING: QColor(255, 255, 200),
    Severity.INFO: QColor(200, 225, 255),
}


class ValidationPanel(QWidget):
    COLUMNS = ["Ważność", "Kod", "Tytuł", "Opis", "Kilometraż", "Oczekiwane", "Rzeczywiste", "Sugestia"]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.summary_label = QLabel("Brak wyników walidacji")
        layout.addWidget(self.summary_label)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

    def set_issues(self, issues: list[ValidationIssue]):
        self.table.setRowCount(0)
        n_err = sum(1 for i in issues if i.severity == Severity.ERROR)
        n_warn = sum(1 for i in issues if i.severity == Severity.WARNING)
        n_info = sum(1 for i in issues if i.severity == Severity.INFO)
        self.summary_label.setText(
            f"Wynik: {n_err} błędów, {n_warn} ostrzeżeń, {n_info} informacji"
        )

        for row_idx, issue in enumerate(issues):
            self.table.insertRow(row_idx)
            values = [
                issue.severity.value.upper(),
                issue.code,
                issue.title,
                issue.message,
                issue.chainage_display,
                issue.expected_value,
                issue.actual_value,
                issue.suggestion,
            ]
            bg = _SEVERITY_COLORS.get(issue.severity)
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                if bg:
                    item.setBackground(bg)
                self.table.setItem(row_idx, col, item)
