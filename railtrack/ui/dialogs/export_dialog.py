"""Export dialog with format selection and options."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class ExportDialog(QDialog):
    """Dialog for exporting alignment data with format options."""

    FORMATS = [
        ("CSV - Tabela elementów", "csv", "CSV (*.csv)"),
        ("XLSX - Arkusz z raportem", "xlsx", "Excel (*.xlsx)"),
        ("DXF - Geometria osi", "dxf", "DXF (*.dxf)"),
        ("LandXML 1.2", "landxml", "LandXML (*.xml)"),
        ("HTML - Raport walidacji", "html", "HTML (*.html)"),
    ]

    def __init__(self, parent=None, alignment_name: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Eksport danych")
        self.resize(500, 300)
        self.setModal(True)

        self._export_format: str = ""
        self._export_path: str = ""

        layout = QVBoxLayout(self)

        # Format selection
        form = QFormLayout()
        self.format_combo = QComboBox()
        for label, _, _ in self.FORMATS:
            self.format_combo.addItem(label)
        form.addRow("Format:", self.format_combo)

        # File path
        file_layout = QHBoxLayout()
        self.file_edit = QLineEdit()
        file_layout.addWidget(self.file_edit)
        browse_btn = QPushButton("Przeglądaj...")
        browse_btn.clicked.connect(self._browse)
        file_layout.addWidget(browse_btn)
        form.addRow("Plik:", file_layout)

        # Options
        self.include_validation = QCheckBox("Dołącz wyniki walidacji (XLSX/HTML)")
        self.include_validation.setChecked(True)
        form.addRow(self.include_validation)

        self.chainage_labels = QCheckBox("Etykiety kilometrażu (DXF)")
        self.chainage_labels.setChecked(True)
        form.addRow(self.chainage_labels)

        layout.addLayout(form)

        # Info
        info = QLabel(
            "CSV/XLSX: tabela elementów geometrii poziomej\n"
            "DXF: oś toru z rzeczywistą geometrią (LINE/ARC/POLYLINE)\n"
            "LandXML: pełna geometria zgodna ze standardem 1.2\n"
            "HTML: raport walidacji z kolorami"
        )
        info.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(info)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        export_btn = QPushButton("Eksportuj")
        export_btn.clicked.connect(self._do_export)
        btn_layout.addWidget(export_btn)
        cancel_btn = QPushButton("Anuluj")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        if alignment_name:
            default_name = alignment_name.replace(" ", "_")
            self.file_edit.setText(default_name)

    def _browse(self):
        idx = self.format_combo.currentIndex()
        _, _, filt = self.FORMATS[idx]
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz jako", self.file_edit.text(), filt)
        if path:
            self.file_edit.setText(path)

    def _do_export(self):
        path = self.file_edit.text()
        if not path:
            QMessageBox.warning(self, "Błąd", "Podaj ścieżkę pliku")
            return
        idx = self.format_combo.currentIndex()
        _, fmt, _ = self.FORMATS[idx]
        # Ensure correct extension
        ext_map = {"csv": ".csv", "xlsx": ".xlsx", "dxf": ".dxf", "landxml": ".xml", "html": ".html"}
        expected_ext = ext_map.get(fmt, "")
        if expected_ext and not path.lower().endswith(expected_ext):
            path += expected_ext
        self._export_format = fmt
        self._export_path = path
        self.accept()

    @property
    def export_format(self) -> str:
        return self._export_format

    @property
    def export_path(self) -> str:
        return self._export_path

    @property
    def should_include_validation(self) -> bool:
        return self.include_validation.isChecked()
