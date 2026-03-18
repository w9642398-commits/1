"""Main application window."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from railtrack.application.project_manager import ProjectManager
from railtrack.domain.alignment import Alignment
from railtrack.ui.dialogs.export_dialog import ExportDialog
from railtrack.ui.dialogs.import_wizard import ImportWizard
from railtrack.ui.views.plan_view import PlanView
from railtrack.ui.views.profile_view import ProfileView
from railtrack.ui.widgets.element_table import ElementTable
from railtrack.ui.widgets.project_tree import ProjectTree
from railtrack.ui.widgets.properties_panel import PropertiesPanel
from railtrack.ui.widgets.validation_panel import ValidationPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RailTrack - Railway Geometry Design")
        self.resize(1400, 900)

        self.pm = ProjectManager()
        self._current_alignment: Alignment | None = None

        self._setup_menus()
        self._setup_ui()
        self._setup_statusbar()

        # Start with a new default project
        self._new_project()

    # ---- Menus ----
    def _setup_menus(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("&Projekt")
        file_menu.addAction("Nowy projekt", self._new_project, "Ctrl+N")
        file_menu.addAction("Otwórz...", self._open_project, "Ctrl+O")
        file_menu.addAction("Zapisz", self._save_project, "Ctrl+S")
        file_menu.addAction("Zapisz jako...", self._save_project_as, "Ctrl+Shift+S")
        file_menu.addSeparator()
        file_menu.addAction("Wyjście", self.close, "Ctrl+Q")

        align_menu = mb.addMenu("&Oś")
        align_menu.addAction("Dodaj oś", self._add_alignment)
        align_menu.addAction("Przelicz geometrię", self._recalculate, "F5")
        align_menu.addAction("Generuj przechyłki", self._generate_cant)
        align_menu.addAction("Minimalizuj elementy", self._minimize_elements)
        align_menu.addSeparator()
        align_menu.addAction("Wstaw rozjazd z katalogu...", self._insert_turnout_from_catalog)

        import_menu = mb.addMenu("&Import")
        import_menu.addAction("Kreator importu...", self._open_import_wizard, "Ctrl+I")

        export_menu = mb.addMenu("&Eksport")
        export_menu.addAction("Eksport z opcjami...", self._open_export_dialog, "Ctrl+E")
        export_menu.addSeparator()
        export_menu.addAction("CSV...", self._export_csv)
        export_menu.addAction("XLSX...", self._export_xlsx)
        export_menu.addAction("DXF...", self._export_dxf)
        export_menu.addAction("LandXML...", self._export_landxml)
        export_menu.addAction("Raport HTML...", self._export_html)

        valid_menu = mb.addMenu("&Walidacja")
        valid_menu.addAction("Sprawdź aktywną oś", self._validate_current, "F6")
        valid_menu.addAction("Sprawdź cały projekt", self._validate_all)

    # ---- UI Layout ----
    def _setup_ui(self):
        # Project tree (left dock)
        self.project_tree = ProjectTree()
        self.project_tree.alignment_selected.connect(self._on_alignment_selected)
        dock_tree = QDockWidget("Projekt", self)
        dock_tree.setWidget(self.project_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock_tree)

        # Properties panel (right dock)
        self.properties_panel = PropertiesPanel()
        dock_props = QDockWidget("Właściwości", self)
        dock_props.setWidget(self.properties_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_props)

        # Central area: tabs for plan/profile + element table
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Tabs: Plan / Profile
        self.tabs = QTabWidget()
        self.plan_view = PlanView()
        self.profile_view = ProfileView()
        self.tabs.addTab(self.plan_view, "Plan")
        self.tabs.addTab(self.profile_view, "Profil")
        splitter.addWidget(self.tabs)

        # Element table
        self.element_table = ElementTable()
        self.element_table.element_changed.connect(self._on_element_changed)
        self.element_table.element_selected.connect(self._on_element_selected_in_table)
        splitter.addWidget(self.element_table)

        splitter.setSizes([500, 200])
        layout.addWidget(splitter)
        self.setCentralWidget(central)

        # Validation panel (bottom dock)
        self.validation_panel = ValidationPanel()
        dock_valid = QDockWidget("Walidacja", self)
        dock_valid.setWidget(self.validation_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock_valid)

        # Connect plan view element selection back to table
        self.plan_view.element_clicked.connect(self._on_element_selected_in_view)

    def _setup_statusbar(self):
        self.statusBar().showMessage("Gotowy")

    # ---- Project operations ----
    def _new_project(self):
        self.pm.new_project("Nowy projekt")
        alignment = self.pm.add_alignment("Oś 1")
        self._current_alignment = alignment
        self._refresh_all()
        self.statusBar().showMessage("Nowy projekt utworzony")

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Otwórz projekt", "", "RailTrack JSON (*.rtk.json);;Wszystkie (*)"
        )
        if path:
            try:
                self.pm.load_project(path)
                if self.pm.project and self.pm.project.alignments:
                    self._current_alignment = self.pm.project.alignments[0]
                self._refresh_all()
                self.statusBar().showMessage(f"Otwarto: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Błąd", f"Nie można otworzyć pliku:\n{e}")

    def _save_project(self):
        if self.pm._file_path:
            self.pm.save_project(self.pm._file_path)
            self.statusBar().showMessage(f"Zapisano: {self.pm._file_path}")
        else:
            self._save_project_as()

    def _save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Zapisz projekt", "", "RailTrack JSON (*.rtk.json)"
        )
        if path:
            if not path.endswith(".rtk.json"):
                path += ".rtk.json"
            self.pm.save_project(path)
            self.statusBar().showMessage(f"Zapisano: {path}")

    def _add_alignment(self):
        if self.pm.project is None:
            return
        n = len(self.pm.project.alignments) + 1
        alignment = self.pm.add_alignment(f"Oś {n}")
        self._current_alignment = alignment
        self._refresh_all()

    # ---- Element operations ----
    def _minimize_elements(self):
        if self._current_alignment:
            before = len(self._current_alignment.horizontal_elements)
            self.pm.minimize_elements(self._current_alignment)
            after = len(self._current_alignment.horizontal_elements)
            self._refresh_views()
            self.statusBar().showMessage(
                f"Minimalizacja: {before} → {after} elementów"
            )

    def _insert_turnout_from_catalog(self):
        if not self._current_alignment:
            QMessageBox.warning(self, "Brak osi", "Nie ma aktywnej osi")
            return
        from railtrack.ui.dialogs.turnout_dialog import TurnoutCatalogDialog
        dlg = TurnoutCatalogDialog(self)
        if dlg.exec() == TurnoutCatalogDialog.DialogCode.Accepted and dlg.created_turnout:
            self._current_alignment.turnouts.append(dlg.created_turnout)
            self._refresh_all()
            self.statusBar().showMessage(
                f"Wstawiono rozjazd: {dlg.created_turnout.name}"
            )

    # ---- Import ----
    def _open_import_wizard(self):
        wizard = ImportWizard(self)
        if wizard.exec() == ImportWizard.DialogCode.Accepted:
            if wizard.imported_alignment:
                al = wizard.imported_alignment
                if self.pm.project is None:
                    self.pm.new_project("Import")
                self.pm.project.alignments.append(al)
                self._current_alignment = al
                self.pm.propagate_horizontal(al)
                self._refresh_all()
                self.statusBar().showMessage(f"Zaimportowano oś: {al.name}")
            elif wizard.imported_points:
                from railtrack.domain.alignment import SurveyPointSet
                from railtrack.domain.primitives import Point3D
                if self.pm.project is None:
                    self.pm.new_project("Import")
                sps = SurveyPointSet(name="Import", points=wizard.imported_points)
                self.pm.project.survey_point_sets.append(sps)
                self.statusBar().showMessage(f"Zaimportowano {len(wizard.imported_points)} punktów")

    # ---- Export ----
    def _open_export_dialog(self):
        if not self._current_alignment:
            QMessageBox.warning(self, "Brak osi", "Nie ma aktywnej osi do eksportu")
            return
        dlg = ExportDialog(self, alignment_name=self._current_alignment.name)
        if dlg.exec() == ExportDialog.DialogCode.Accepted:
            fmt = dlg.export_format
            path = dlg.export_path
            try:
                if fmt == "csv":
                    self.pm.export_csv(self._current_alignment, path)
                elif fmt == "xlsx":
                    self.pm.export_xlsx(self._current_alignment, path)
                elif fmt == "dxf":
                    self.pm.export_dxf(self._current_alignment, path)
                elif fmt == "landxml":
                    self.pm.export_landxml(path)
                elif fmt == "html":
                    self.pm.export_html_report(self._current_alignment, path)
                self.statusBar().showMessage(f"Eksport {fmt.upper()}: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Błąd eksportu", str(e))

    # ---- Geometry ----
    def _recalculate(self):
        if self._current_alignment:
            self.pm.propagate_horizontal(self._current_alignment)
            self.pm.propagate_vertical(self._current_alignment)
            self._refresh_views()
            self.statusBar().showMessage("Geometria przeliczona")

    def _generate_cant(self):
        if self._current_alignment:
            self.pm.generate_cant(self._current_alignment)
            self._refresh_views()
            self.statusBar().showMessage("Przechyłki wygenerowane")

    # ---- Validation ----
    def _validate_current(self):
        if self._current_alignment:
            issues = self.pm.validate_alignment(self._current_alignment)
            self.validation_panel.set_issues(issues)
            n_err = sum(1 for i in issues if i.severity.value == "error")
            n_warn = sum(1 for i in issues if i.severity.value == "warning")
            self.statusBar().showMessage(
                f"Walidacja: {n_err} błędów, {n_warn} ostrzeżeń"
            )

    def _validate_all(self):
        results = self.pm.validate_all()
        all_issues = []
        for issues in results.values():
            all_issues.extend(issues)
        self.validation_panel.set_issues(all_issues)

    # ---- Direct export shortcuts ----
    def _export_csv(self):
        if not self._current_alignment:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Eksport CSV", "", "CSV (*.csv)")
        if path:
            self.pm.export_csv(self._current_alignment, path)
            self.statusBar().showMessage(f"Eksport CSV: {path}")

    def _export_xlsx(self):
        if not self._current_alignment:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Eksport XLSX", "", "XLSX (*.xlsx)")
        if path:
            self.pm.export_xlsx(self._current_alignment, path)
            self.statusBar().showMessage(f"Eksport XLSX: {path}")

    def _export_dxf(self):
        if not self._current_alignment:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Eksport DXF", "", "DXF (*.dxf)")
        if path:
            self.pm.export_dxf(self._current_alignment, path)
            self.statusBar().showMessage(f"Eksport DXF: {path}")

    def _export_landxml(self):
        path, _ = QFileDialog.getSaveFileName(self, "Eksport LandXML", "", "LandXML (*.xml)")
        if path:
            self.pm.export_landxml(path)
            self.statusBar().showMessage(f"Eksport LandXML: {path}")

    def _export_html(self):
        if not self._current_alignment:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Eksport HTML", "", "HTML (*.html)")
        if path:
            self.pm.export_html_report(self._current_alignment, path)
            self.statusBar().showMessage(f"Eksport HTML: {path}")

    # ---- Element selection sync ----
    def _on_element_selected_in_table(self, index: int):
        """Highlight element in plan view when selected in table."""
        self.plan_view.highlight_element(index)

    def _on_element_selected_in_view(self, index: int):
        """Select element in table when clicked in plan view."""
        self.element_table.select_row(index)

    # ---- Callbacks ----
    def _on_alignment_selected(self, name: str):
        if self.pm.project:
            al = self.pm.project.alignment_by_name(name)
            if al:
                self._current_alignment = al
                self._refresh_views()

    def _on_element_changed(self):
        """Called when element table data is edited."""
        self._recalculate()

    # ---- Refresh ----
    def _refresh_all(self):
        if self.pm.project:
            self.project_tree.set_project(self.pm.project)
        self._refresh_views()

    def _refresh_views(self):
        al = self._current_alignment
        if al is None:
            return
        self.element_table.set_alignment(al)
        self.plan_view.set_alignment(al)
        self.profile_view.set_alignment(al)
        self.properties_panel.set_alignment(al, self.pm.project.design_criteria if self.pm.project else None)
