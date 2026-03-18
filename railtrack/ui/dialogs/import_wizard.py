"""Import wizard dialog for CSV, XLSX, and LandXML files."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QHeaderView,
    QAbstractItemView,
)

from railtrack.domain.alignment import Alignment
from railtrack.domain.primitives import Point2D
from railtrack.importers.csv_importer import import_horizontal_elements, import_survey_points
from railtrack.importers.landxml_importer import import_landxml
from railtrack.importers.xlsx_importer import import_horizontal_elements_xlsx, import_survey_points_xlsx


class ImportWizard(QDialog):
    """Multi-step import wizard with file selection, format config, and preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import danych")
        self.resize(700, 500)
        self.setModal(True)

        self._imported_alignment: Alignment | None = None
        self._imported_points: list | None = None

        layout = QVBoxLayout(self)

        # Format selection
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "CSV/TXT - Elementy geometrii",
            "CSV/TXT - Punkty pomiarowe",
            "XLSX - Elementy geometrii",
            "XLSX - Punkty pomiarowe",
            "LandXML 1.2",
            "CSV/TXT - Rekonstrukcja geometrii z punktów",
        ])
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        format_layout.addWidget(self.format_combo)
        layout.addLayout(format_layout)

        # File selection
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Plik:"))
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        file_layout.addWidget(self.file_edit)
        browse_btn = QPushButton("Przeglądaj...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)

        # Options stack
        self.options_stack = QStackedWidget()
        layout.addWidget(self.options_stack)

        # CSV options
        csv_options = QWidget()
        csv_layout = QFormLayout(csv_options)
        self.csv_delimiter = QComboBox()
        self.csv_delimiter.addItems([",", ";", "\\t (tabulator)", "spacja"])
        csv_layout.addRow("Separator:", self.csv_delimiter)
        self.csv_skip_header = QCheckBox("Pomiń nagłówek")
        self.csv_skip_header.setChecked(True)
        csv_layout.addRow(self.csv_skip_header)
        self.csv_x_col = QSpinBox()
        self.csv_x_col.setValue(0)
        csv_layout.addRow("Kolumna X:", self.csv_x_col)
        self.csv_y_col = QSpinBox()
        self.csv_y_col.setValue(1)
        csv_layout.addRow("Kolumna Y:", self.csv_y_col)
        self.csv_z_col = QSpinBox()
        self.csv_z_col.setValue(2)
        csv_layout.addRow("Kolumna Z:", self.csv_z_col)
        self.options_stack.addWidget(csv_options)

        # XLSX options
        xlsx_options = QWidget()
        xlsx_layout = QFormLayout(xlsx_options)
        self.xlsx_sheet = QLineEdit("Sheet1")
        xlsx_layout.addRow("Arkusz:", self.xlsx_sheet)
        self.options_stack.addWidget(xlsx_options)

        # LandXML options (minimal)
        landxml_options = QWidget()
        landxml_layout = QFormLayout(landxml_options)
        landxml_layout.addRow(QLabel("LandXML 1.2 - automatyczne rozpoznanie geometrii"))
        self.options_stack.addWidget(landxml_options)

        # Preview table
        layout.addWidget(QLabel("Podgląd:"))
        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(200)
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.preview_table)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        preview_btn = QPushButton("Podgląd")
        preview_btn.clicked.connect(self._preview)
        btn_layout.addWidget(preview_btn)
        import_btn = QPushButton("Importuj")
        import_btn.clicked.connect(self._do_import)
        btn_layout.addWidget(import_btn)
        cancel_btn = QPushButton("Anuluj")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self._on_format_changed(0)

    def _on_format_changed(self, idx: int):
        if idx in (0, 1, 5):  # CSV (including geometry reconstruction)
            self.options_stack.setCurrentIndex(0)
        elif idx in (2, 3):  # XLSX
            self.options_stack.setCurrentIndex(1)
        else:  # LandXML
            self.options_stack.setCurrentIndex(2)

    def _browse_file(self):
        idx = self.format_combo.currentIndex()
        if idx in (0, 1, 5):
            filt = "CSV/TXT (*.csv *.txt);;Wszystkie (*)"
        elif idx in (2, 3):
            filt = "Excel (*.xlsx *.xls);;Wszystkie (*)"
        else:
            filt = "LandXML (*.xml);;Wszystkie (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Wybierz plik", "", filt)
        if path:
            self.file_edit.setText(path)

    def _get_delimiter(self) -> str:
        idx = self.csv_delimiter.currentIndex()
        return [",", ";", "\t", " "][idx]

    def _preview(self):
        path = self.file_edit.text()
        if not path:
            QMessageBox.warning(self, "Błąd", "Wybierz plik do importu")
            return
        try:
            self._show_file_preview(path)
        except Exception as e:
            QMessageBox.warning(self, "Błąd podglądu", str(e))

    def _show_file_preview(self, path: str):
        """Show first 10 rows of the file in the preview table."""
        self.preview_table.clear()
        self.preview_table.setRowCount(0)
        idx = self.format_combo.currentIndex()
        if idx in (0, 1):
            delim = self._get_delimiter()
            with open(path, "r", encoding="utf-8") as f:
                lines = [f.readline().strip() for _ in range(10)]
            lines = [l for l in lines if l]
            if not lines:
                return
            cols = max(len(l.split(delim)) for l in lines)
            self.preview_table.setColumnCount(cols)
            self.preview_table.setRowCount(len(lines))
            for r, line in enumerate(lines):
                for c, val in enumerate(line.split(delim)):
                    self.preview_table.setItem(r, c, QTableWidgetItem(val.strip()))
        elif idx in (2, 3):
            try:
                import pandas as pd
                df = pd.read_excel(path, sheet_name=self.xlsx_sheet.text(), nrows=10)
                self.preview_table.setColumnCount(len(df.columns))
                self.preview_table.setHorizontalHeaderLabels([str(c) for c in df.columns])
                self.preview_table.setRowCount(len(df))
                for r in range(len(df)):
                    for c in range(len(df.columns)):
                        self.preview_table.setItem(r, c, QTableWidgetItem(str(df.iloc[r, c])))
            except Exception as e:
                QMessageBox.warning(self, "Błąd", f"Nie można odczytać XLSX:\n{e}")

    def _do_import(self):
        path = self.file_edit.text()
        if not path:
            QMessageBox.warning(self, "Błąd", "Wybierz plik do importu")
            return
        idx = self.format_combo.currentIndex()
        try:
            if idx == 0:  # CSV elements
                elems = import_horizontal_elements(
                    path, delimiter=self._get_delimiter(),
                    skip_header=self.csv_skip_header.isChecked(),
                )
                al = Alignment(name=Path(path).stem)
                al.horizontal_elements = elems
                self._imported_alignment = al
            elif idx == 1:  # CSV survey points
                pts = import_survey_points(
                    path, delimiter=self._get_delimiter(),
                    skip_header=self.csv_skip_header.isChecked(),
                    x_col=self.csv_x_col.value(),
                    y_col=self.csv_y_col.value(),
                    z_col=self.csv_z_col.value(),
                )
                self._imported_points = pts
            elif idx == 2:  # XLSX elements
                elems = import_horizontal_elements_xlsx(
                    path, sheet_name=self.xlsx_sheet.text(),
                )
                al = Alignment(name=Path(path).stem)
                al.horizontal_elements = elems
                self._imported_alignment = al
            elif idx == 3:  # XLSX survey points
                pts = import_survey_points_xlsx(
                    path, sheet_name=self.xlsx_sheet.text(),
                )
                self._imported_points = pts
            elif idx == 4:  # LandXML
                alignments = import_landxml(path)
                if alignments:
                    self._imported_alignment = alignments[0]
                else:
                    QMessageBox.warning(self, "Brak danych", "Plik nie zawiera geometrii osi")
                    return
            elif idx == 5:  # CSV geometry reconstruction from points
                from railtrack.importers.existing_geometry_importer import import_existing_geometry
                pts = import_survey_points(
                    path, delimiter=self._get_delimiter(),
                    skip_header=self.csv_skip_header.isChecked(),
                    x_col=self.csv_x_col.value(),
                    y_col=self.csv_y_col.value(),
                    z_col=self.csv_z_col.value(),
                )
                if len(pts) < 3:
                    QMessageBox.warning(self, "Za mało punktów", "Potrzeba minimum 3 punktów do rekonstrukcji")
                    return
                al = import_existing_geometry(pts, name=Path(path).stem)
                self._imported_alignment = al

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Błąd importu", str(e))

    @property
    def imported_alignment(self) -> Alignment | None:
        return self._imported_alignment

    @property
    def imported_points(self) -> list | None:
        return self._imported_points
