"""Main application window with full interactive CAD functionality."""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon, QKeySequence
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
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from railtrack.application.project_manager import ProjectManager
from railtrack.domain.alignment import Alignment
from railtrack.domain.horizontal import (
    CircularArc, CurveDirection, HorizontalElementUnion, Straight, TransitionCurve,
)
from railtrack.domain.primitives import Point2D, azimuth_from_dx_dy
from railtrack.domain.vertical import VerticalGrade, VerticalCurve
from railtrack.geometry_engine.horizontal_engine import (
    build_straight_curve_straight, propagate_geometry,
)
from railtrack.ui.cad.command_manager import (
    AddElementCommand, AddVerticalElementCommand, CommandManager,
    CompoundCommand, ModifyElementCommand, ModifyVerticalElementCommand,
    RemoveElementCommand, RemoveVerticalElementCommand,
    ReplaceAllElementsCommand,
)
from railtrack.ui.cad.layers import LayerManager
from railtrack.ui.cad.snap_engine import SnapEngine
from railtrack.ui.cad.tools import (
    DrawArcTool, DrawSCSTool, DrawStraightTool, DrawTransitionTool,
    InsertPITool, MeasureAngleTool, MeasureDistanceTool, SelectTool,
    SplitElementTool, ToolType,
)
from railtrack.ui.dialogs.element_properties_dialog import (
    CoordinateInputDialog, HorizontalElementDialog, SCSParametersDialog,
    VerticalElementDialog,
)
from railtrack.ui.dialogs.export_dialog import ExportDialog
from railtrack.ui.dialogs.import_wizard import ImportWizard
from railtrack.ui.views.plan_view import PlanView
from railtrack.ui.views.profile_view import ProfileView
from railtrack.ui.widgets.element_table import ElementTable
from railtrack.ui.widgets.layer_panel import LayerPanel
from railtrack.ui.widgets.project_tree import ProjectTree
from railtrack.ui.widgets.properties_panel import PropertiesPanel
from railtrack.ui.widgets.validation_panel import ValidationPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RailTrack - Railway Geometry Design")
        self.resize(1600, 1000)

        self.pm = ProjectManager()
        self._current_alignment: Alignment | None = None

        # Command manager for undo/redo
        self.cmd_manager = CommandManager()

        self._setup_menus()
        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()
        self._connect_signals()

        # Start with new project
        self._new_project()

    # ---- Menus ----
    def _setup_menus(self):
        mb = self.menuBar()

        # --- Projekt ---
        file_menu = mb.addMenu("&Projekt")
        file_menu.addAction("Nowy projekt", self._new_project, "Ctrl+N")
        file_menu.addAction("Otwórz...", self._open_project, "Ctrl+O")
        file_menu.addAction("Zapisz", self._save_project, "Ctrl+S")
        file_menu.addAction("Zapisz jako...", self._save_project_as, "Ctrl+Shift+S")
        file_menu.addSeparator()
        file_menu.addAction("Wyjście", self.close, "Ctrl+Q")

        # --- Edycja ---
        edit_menu = mb.addMenu("&Edycja")
        self._undo_action = edit_menu.addAction("Cofnij", self._undo, "Ctrl+Z")
        self._redo_action = edit_menu.addAction("Ponów", self._redo, "Ctrl+Y")
        self._undo_action.setEnabled(False)
        self._redo_action.setEnabled(False)
        edit_menu.addSeparator()
        edit_menu.addAction("Właściwości elementu...", self._edit_element_properties, "Ctrl+P")
        edit_menu.addAction("Wprowadź współrzędne...", self._input_coordinates, "Ctrl+G")
        edit_menu.addSeparator()
        edit_menu.addAction("Usuń zaznaczone", self._delete_selected, "Delete")

        # --- Oś ---
        align_menu = mb.addMenu("&Oś")
        align_menu.addAction("Dodaj oś", self._add_alignment)
        align_menu.addAction("Przelicz geometrię", self._recalculate, "F5")
        align_menu.addAction("Generuj przechyłki", self._generate_cant)
        align_menu.addAction("Minimalizuj elementy", self._minimize_elements)
        align_menu.addSeparator()
        align_menu.addAction("Wstaw rozjazd z katalogu...", self._insert_turnout_from_catalog)
        align_menu.addSeparator()
        align_menu.addAction("Dodaj element pionowy...", self._add_vertical_element)

        # --- Narzędzia rysowania ---
        draw_menu = mb.addMenu("&Rysowanie")
        draw_menu.addAction("Zaznaczanie (S)", self._tool_select, "S")
        draw_menu.addSeparator()
        draw_menu.addAction("Rysuj prostą (L)", self._tool_draw_straight, "L")
        draw_menu.addAction("Rysuj łuk 3-pkt (A)", self._tool_draw_arc, "A")
        draw_menu.addAction("Rysuj klotoidę (T)", self._tool_draw_transition, "T")
        draw_menu.addAction("Rysuj S-T-C-T-S (C)", self._tool_draw_scs, "C")
        draw_menu.addAction("Metoda PI (P)", self._tool_insert_pi, "P")
        draw_menu.addSeparator()
        draw_menu.addAction("Podziel element (X)", self._tool_split, "X")

        # --- Pomiary ---
        measure_menu = mb.addMenu("&Pomiary")
        measure_menu.addAction("Odległość (D)", self._tool_measure_distance, "D")
        measure_menu.addAction("Kąt (G)", self._tool_measure_angle, "G")
        measure_menu.addSeparator()
        measure_menu.addAction("Wyczyść pomiary", self._clear_measurements)

        # --- Widok ---
        view_menu = mb.addMenu("W&idok")
        view_menu.addAction("Dopasuj widok", self._zoom_to_fit, "F")
        view_menu.addSeparator()
        self._handles_action = view_menu.addAction("Pokaż uchwyty")
        self._handles_action.setCheckable(True)
        self._handles_action.setChecked(True)
        self._handles_action.triggered.connect(
            lambda checked: self.plan_view.toggle_handles(checked)
        )
        self._chainage_action = view_menu.addAction("Pokaż pikietaż")
        self._chainage_action.setCheckable(True)
        self._chainage_action.setChecked(True)
        self._chainage_action.triggered.connect(
            lambda checked: self.plan_view.toggle_chainage_labels(checked)
        )
        self._tangent_action = view_menu.addAction("Linie styczne")
        self._tangent_action.setCheckable(True)
        self._tangent_action.setChecked(False)
        self._tangent_action.triggered.connect(
            lambda checked: self.plan_view.toggle_tangent_lines(checked)
        )
        view_menu.addSeparator()
        self._snap_action = view_menu.addAction("Snap włączony")
        self._snap_action.setCheckable(True)
        self._snap_action.setChecked(True)
        self._snap_action.triggered.connect(self._toggle_snap)

        # --- Import ---
        import_menu = mb.addMenu("&Import")
        import_menu.addAction("Kreator importu...", self._open_import_wizard, "Ctrl+I")

        # --- Eksport ---
        export_menu = mb.addMenu("&Eksport")
        export_menu.addAction("Eksport z opcjami...", self._open_export_dialog, "Ctrl+E")
        export_menu.addSeparator()
        export_menu.addAction("CSV...", self._export_csv)
        export_menu.addAction("XLSX...", self._export_xlsx)
        export_menu.addAction("DXF...", self._export_dxf)
        export_menu.addAction("LandXML...", self._export_landxml)
        export_menu.addAction("Raport HTML...", self._export_html)

        # --- Walidacja ---
        valid_menu = mb.addMenu("&Walidacja")
        valid_menu.addAction("Sprawdź aktywną oś", self._validate_current, "F6")
        valid_menu.addAction("Sprawdź cały projekt", self._validate_all)
        valid_menu.addSeparator()
        valid_menu.addAction("Walidacja w czasie rzeczywistym",
                            self._toggle_realtime_validation).setCheckable(True)

    # ---- Toolbar ----
    def _setup_toolbar(self):
        tb = QToolBar("Narzędzia CAD")
        tb.setMovable(False)
        tb.setIconSize(QSize(24, 24))
        self.addToolBar(tb)

        # Selection
        self._act_select = tb.addAction("▮ Zaznacz")
        self._act_select.setToolTip("Zaznaczanie i edycja (S)")
        self._act_select.setCheckable(True)
        self._act_select.setChecked(True)
        self._act_select.triggered.connect(self._tool_select)

        tb.addSeparator()

        # Drawing tools
        self._act_straight = tb.addAction("/ Prosta")
        self._act_straight.setToolTip("Rysuj prostą (L)")
        self._act_straight.setCheckable(True)
        self._act_straight.triggered.connect(self._tool_draw_straight)

        self._act_arc = tb.addAction("◠ Łuk")
        self._act_arc.setToolTip("Rysuj łuk 3-pkt (A)")
        self._act_arc.setCheckable(True)
        self._act_arc.triggered.connect(self._tool_draw_arc)

        self._act_transition = tb.addAction("∿ Klotoida")
        self._act_transition.setToolTip("Rysuj krzywą przejściową (T)")
        self._act_transition.setCheckable(True)
        self._act_transition.triggered.connect(self._tool_draw_transition)

        self._act_scs = tb.addAction("⌒ SCS")
        self._act_scs.setToolTip("Rysuj S-T-C-T-S (C)")
        self._act_scs.setCheckable(True)
        self._act_scs.triggered.connect(self._tool_draw_scs)

        self._act_pi = tb.addAction("△ PI")
        self._act_pi.setToolTip("Metoda punkt. przecięcia (P)")
        self._act_pi.setCheckable(True)
        self._act_pi.triggered.connect(self._tool_insert_pi)

        tb.addSeparator()

        # Edit tools
        self._act_split = tb.addAction("✂ Podziel")
        self._act_split.setToolTip("Podziel element (X)")
        self._act_split.setCheckable(True)
        self._act_split.triggered.connect(self._tool_split)

        tb.addSeparator()

        # Measurement tools
        self._act_measure_dist = tb.addAction("↔ Odległość")
        self._act_measure_dist.setToolTip("Pomiar odległości (D)")
        self._act_measure_dist.setCheckable(True)
        self._act_measure_dist.triggered.connect(self._tool_measure_distance)

        self._act_measure_angle = tb.addAction("∠ Kąt")
        self._act_measure_angle.setToolTip("Pomiar kąta (G)")
        self._act_measure_angle.setCheckable(True)
        self._act_measure_angle.triggered.connect(self._tool_measure_angle)

        tb.addSeparator()

        # Undo/redo
        self._act_undo = tb.addAction("↩ Cofnij")
        self._act_undo.setToolTip("Cofnij (Ctrl+Z)")
        self._act_undo.setEnabled(False)
        self._act_undo.triggered.connect(self._undo)

        self._act_redo = tb.addAction("↪ Ponów")
        self._act_redo.setToolTip("Ponów (Ctrl+Y)")
        self._act_redo.setEnabled(False)
        self._act_redo.triggered.connect(self._redo)

        tb.addSeparator()

        # Quick actions
        tb.addAction("⟳ Przelicz (F5)", self._recalculate)
        tb.addAction("✓ Waliduj (F6)", self._validate_current)
        tb.addAction("⊞ Dopasuj (F)", self._zoom_to_fit)

        self._tool_actions = [
            self._act_select, self._act_straight, self._act_arc,
            self._act_transition, self._act_scs, self._act_pi,
            self._act_split, self._act_measure_dist, self._act_measure_angle,
        ]

    def _uncheck_all_tools(self) -> None:
        for act in self._tool_actions:
            act.setChecked(False)

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

        # Layer panel (right dock, under properties)
        self.layer_panel = LayerPanel(LayerManager())
        dock_layers = QDockWidget("Warstwy", self)
        dock_layers.setWidget(self.layer_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_layers)
        self.tabifyDockWidget(dock_props, dock_layers)
        dock_props.raise_()

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

        splitter.setSizes([600, 180])
        layout.addWidget(splitter)
        self.setCentralWidget(central)

        # Validation panel (bottom dock)
        self.validation_panel = ValidationPanel()
        dock_valid = QDockWidget("Walidacja", self)
        dock_valid.setWidget(self.validation_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock_valid)

    def _setup_statusbar(self):
        self.statusBar().showMessage("Gotowy — S: Zaznacz | L: Prosta | A: Łuk | T: Klotoida | D: Pomiar | Ctrl+Z: Cofnij")

    # ---- Signals ----
    def _connect_signals(self):
        # Plan view
        self.plan_view.element_clicked.connect(self._on_element_selected_in_view)
        self.plan_view.tool_action.connect(self._handle_tool_action)

        # Profile view
        self.profile_view.element_added.connect(self._handle_profile_action)
        self.profile_view.element_removed.connect(self._on_vertical_element_removed)

        # Command manager
        self.cmd_manager.can_undo_changed.connect(self._undo_action.setEnabled)
        self.cmd_manager.can_undo_changed.connect(self._act_undo.setEnabled)
        self.cmd_manager.can_redo_changed.connect(self._redo_action.setEnabled)
        self.cmd_manager.can_redo_changed.connect(self._act_redo.setEnabled)

        # Layer panel
        self.layer_panel.layer_toggled.connect(self._on_layer_toggled)

    # ---- Tool Switching ----
    def _tool_select(self):
        self._uncheck_all_tools()
        self._act_select.setChecked(True)
        self.plan_view.set_tool(SelectTool())
        self.statusBar().showMessage("Narzędzie: Zaznaczanie")

    def _tool_draw_straight(self):
        self._uncheck_all_tools()
        self._act_straight.setChecked(True)
        self.plan_view.set_tool(DrawStraightTool())
        self.statusBar().showMessage("Narzędzie: Rysuj prostą — klik = dodaj punkt, Esc = anuluj")

    def _tool_draw_arc(self):
        self._uncheck_all_tools()
        self._act_arc.setChecked(True)
        self.plan_view.set_tool(DrawArcTool())
        self.statusBar().showMessage("Narzędzie: Rysuj łuk 3-pkt — 3 kliknięcia definiują łuk")

    def _tool_draw_transition(self):
        self._uncheck_all_tools()
        self._act_transition.setChecked(True)
        self.plan_view.set_tool(DrawTransitionTool())
        self.statusBar().showMessage("Narzędzie: Rysuj klotoidę — klik start/end")

    def _tool_draw_scs(self):
        self._uncheck_all_tools()
        self._act_scs.setChecked(True)
        self.plan_view.set_tool(DrawSCSTool())
        self.statusBar().showMessage("Narzędzie: S-T-C-T-S — punkt startowy, kierunkowy, strona łuku")

    def _tool_insert_pi(self):
        self._uncheck_all_tools()
        self._act_pi.setChecked(True)
        self.plan_view.set_tool(InsertPITool())
        self.statusBar().showMessage("Narzędzie: PI — klik = punkt przecięcia, Enter = zakończ")

    def _tool_split(self):
        self._uncheck_all_tools()
        self._act_split.setChecked(True)
        self.plan_view.set_tool(SplitElementTool())
        self.statusBar().showMessage("Narzędzie: Podziel element — klik na element")

    def _tool_measure_distance(self):
        self._uncheck_all_tools()
        self._act_measure_dist.setChecked(True)
        self.plan_view.set_tool(MeasureDistanceTool())
        self.statusBar().showMessage("Narzędzie: Pomiar odległości")

    def _tool_measure_angle(self):
        self._uncheck_all_tools()
        self._act_measure_angle.setChecked(True)
        self.plan_view.set_tool(MeasureAngleTool())
        self.statusBar().showMessage("Narzędzie: Pomiar kąta")

    # ---- Undo/Redo ----
    def _undo(self):
        self.cmd_manager.undo()
        self._recalculate()
        self.statusBar().showMessage(f"Cofnięto: {self.cmd_manager.redo_description}")

    def _redo(self):
        self.cmd_manager.redo()
        self._recalculate()
        self.statusBar().showMessage(f"Ponowiono: {self.cmd_manager.undo_description}")

    # ---- Tool Action Handler ----
    def _handle_tool_action(self, action: dict):
        """Process actions from interactive tools."""
        if not self._current_alignment:
            return

        atype = action.get("type", "")

        if atype == "add_straight":
            start = action["start"]
            azimuth = action["azimuth"]
            length = action["length"]
            elem = Straight(0, length, start, azimuth)
            cmd = AddElementCommand(self._current_alignment, elem)
            self.cmd_manager.execute(cmd)
            self._recalculate()
            self.statusBar().showMessage(
                f"Dodano prostą: L={length:.2f} m, Az={math.degrees(azimuth):.2f}°"
            )

        elif atype == "add_arc_3pt":
            p1 = action["p1"]
            radius = action["radius"]
            direction = action["direction"]
            arc_length = action["arc_length"]
            azimuth = action["start_azimuth"]

            # Compute proper start azimuth from tangent at p1
            center = action["center"]
            dx = p1.x - center.x
            dy = p1.y - center.y
            if direction == CurveDirection.RIGHT:
                start_az = azimuth_from_dx_dy(-dy, dx)
            else:
                start_az = azimuth_from_dx_dy(dy, -dx)

            elem = CircularArc(0, arc_length, p1, start_az, radius, direction)
            cmd = AddElementCommand(self._current_alignment, elem)
            self.cmd_manager.execute(cmd)
            self._recalculate()
            self.statusBar().showMessage(
                f"Dodano łuk: R={radius:.1f} m, L={arc_length:.2f} m, {direction.value}"
            )

        elif atype == "add_transition":
            start = action["start"]
            azimuth = action["azimuth"]
            length = action["length"]
            rs = action["radius_start"]
            re = action["radius_end"]
            direction = action["direction"]
            elem = TransitionCurve(0, length, start, azimuth, rs, re, direction)
            cmd = AddElementCommand(self._current_alignment, elem)
            self.cmd_manager.execute(cmd)
            self._recalculate()
            self.statusBar().showMessage(f"Dodano klotoidę: L={length:.2f} m")

        elif atype == "add_scs":
            start = action["start"]
            azimuth = action["azimuth"]
            direction = action["direction"]
            s1_len = action["straight1_length"]

            dlg = SCSParametersDialog(self, direction)
            dlg.straight1_spin.setValue(s1_len)
            if dlg.exec() == SCSParametersDialog.DialogCode.Accepted:
                params = dlg.params
                elements = build_straight_curve_straight(
                    start, azimuth, 0.0,
                    params["straight1_length"],
                    params["transition1_length"],
                    params["arc_radius"],
                    params["arc_length"],
                    params["direction"],
                    params["transition2_length"],
                    params["straight2_length"],
                )
                new_all = list(self._current_alignment.horizontal_elements) + elements
                cmd = ReplaceAllElementsCommand(self._current_alignment, new_all)
                self.cmd_manager.execute(cmd)
                self._recalculate()
                self.statusBar().showMessage("Dodano sekwencję S-T-C-T-S")

        elif atype == "add_pi_sequence" or atype == "finish_pi_sequence":
            points = action["points"]
            radius = action["radius"]
            trans_len = action["transition_length"]
            if len(points) >= 2:
                self._build_from_pi_points(points, radius, trans_len)

        elif atype == "split_element":
            idx = action["index"]
            split_pt = action["point"]
            self._split_element_at(idx, split_pt)

        elif atype == "move_element":
            idx = action["index"]
            from_pt = action["from"]
            to_pt = action["to"]
            self._move_element(idx, from_pt, to_pt)

        elif atype == "delete_elements":
            indices = sorted(action["indices"], reverse=True)
            cmds = [RemoveElementCommand(self._current_alignment, i) for i in indices]
            if cmds:
                compound = CompoundCommand(cmds, "Usuń elementy")
                self.cmd_manager.execute(compound)
                self._recalculate()
                self.statusBar().showMessage(f"Usunięto {len(indices)} elementów")

    def _handle_profile_action(self, action: dict):
        """Handle profile view actions."""
        if not self._current_alignment:
            return
        atype = action.get("type", "")

        if atype == "add_vertical_point":
            ch = action["chainage"]
            elev = action["elevation"]
            dlg = VerticalElementDialog(
                chainage=ch, elevation=elev, parent=self,
            )
            if dlg.exec() == VerticalElementDialog.DialogCode.Accepted and dlg.result_element:
                cmd = AddVerticalElementCommand(self._current_alignment, dlg.result_element)
                self.cmd_manager.execute(cmd)
                self.pm.propagate_vertical(self._current_alignment)
                self._refresh_views()
                self.statusBar().showMessage("Dodano element pionowy")

    def _on_vertical_element_removed(self, index: int):
        if not self._current_alignment:
            return
        if 0 <= index < len(self._current_alignment.vertical_elements):
            cmd = RemoveVerticalElementCommand(self._current_alignment, index)
            self.cmd_manager.execute(cmd)
            self.pm.propagate_vertical(self._current_alignment)
            self._refresh_views()
            self.statusBar().showMessage("Usunięto element pionowy")

    # ---- Element Operations ----
    def _build_from_pi_points(self, points: list[Point2D], radius: float,
                               trans_len: float) -> None:
        """Build alignment from PI (Point of Intersection) sequence."""
        if len(points) < 2:
            return

        elements: list[HorizontalElementUnion] = []

        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]
            dx = p2.x - p1.x
            dy = p2.y - p1.y
            length = math.hypot(dx, dy)
            azimuth = azimuth_from_dx_dy(dx, dy)

            if i == 0:
                # First tangent
                elements.append(Straight(0, length, p1, azimuth))
            else:
                # Insert transition + arc + transition between tangents
                prev_az = elements[-1].end_azimuth
                az_diff = azimuth - prev_az
                if az_diff > math.pi:
                    az_diff -= 2 * math.pi
                elif az_diff < -math.pi:
                    az_diff += 2 * math.pi

                direction = CurveDirection.RIGHT if az_diff > 0 else CurveDirection.LEFT
                deflection = abs(az_diff)
                arc_length = radius * deflection

                if trans_len > 0:
                    elements.append(TransitionCurve(
                        0, trans_len, Point2D(0, 0), 0,
                        math.inf, radius, direction,
                    ))

                if arc_length > 0.01:
                    elements.append(CircularArc(
                        0, arc_length, Point2D(0, 0), 0,
                        radius, direction,
                    ))

                if trans_len > 0:
                    elements.append(TransitionCurve(
                        0, trans_len, Point2D(0, 0), 0,
                        radius, math.inf, direction,
                    ))

                # Next tangent
                elements.append(Straight(0, length, Point2D(0, 0), 0))

        propagated = propagate_geometry(elements)
        new_all = list(self._current_alignment.horizontal_elements) + propagated
        cmd = ReplaceAllElementsCommand(self._current_alignment, new_all)
        self.cmd_manager.execute(cmd)
        self._recalculate()
        self.statusBar().showMessage(f"Dodano trasę z {len(points)} punktów PI")

    def _split_element_at(self, index: int, point: Point2D) -> None:
        """Split element at nearest chainage to point."""
        if not self._current_alignment:
            return
        elems = self._current_alignment.horizontal_elements
        if index < 0 or index >= len(elems):
            return

        elem = elems[index]
        # Find chainage at closest point
        best_ch = elem.start_chainage
        best_d = float("inf")
        n = max(20, int(elem.length / 1.0))
        for i in range(n + 1):
            ch = elem.start_chainage + elem.length * i / n
            p = elem.point_at(ch)
            d = point.distance_to(p)
            if d < best_d:
                best_d = d
                best_ch = ch

        split_len = best_ch - elem.start_chainage
        remain_len = elem.length - split_len

        if split_len < 0.1 or remain_len < 0.1:
            return

        # Create two new elements
        new_elems = list(elems)
        if isinstance(elem, Straight):
            e1 = Straight(elem.start_chainage, split_len, elem.start_point, elem.start_azimuth)
            e2 = Straight(best_ch, remain_len, e1.end_point, e1.end_azimuth)
        elif isinstance(elem, CircularArc):
            e1 = CircularArc(elem.start_chainage, split_len, elem.start_point,
                            elem.start_azimuth, elem.radius, elem.direction)
            e2 = CircularArc(best_ch, remain_len, e1.end_point,
                            e1.end_azimuth, elem.radius, elem.direction)
        elif isinstance(elem, TransitionCurve):
            # For transitions, compute intermediate radii
            r_at_split = elem.radius_at(best_ch)
            e1 = TransitionCurve(elem.start_chainage, split_len, elem.start_point,
                                elem.start_azimuth, elem.radius_start, r_at_split, elem.direction)
            e2 = TransitionCurve(best_ch, remain_len, e1.end_point,
                                e1.end_azimuth, r_at_split, elem.radius_end, elem.direction)
        else:
            return

        new_elems[index] = e1
        new_elems.insert(index + 1, e2)

        cmd = ReplaceAllElementsCommand(self._current_alignment, new_elems)
        self.cmd_manager.execute(cmd)
        self._recalculate()
        self.statusBar().showMessage(f"Podzielono element w km {best_ch:.3f}")

    def _move_element(self, index: int, from_pt: Point2D, to_pt: Point2D) -> None:
        """Move element start point."""
        if not self._current_alignment:
            return
        elems = self._current_alignment.horizontal_elements
        if index < 0 or index >= len(elems):
            return

        dx = to_pt.x - from_pt.x
        dy = to_pt.y - from_pt.y
        elem = elems[index]
        new_pt = Point2D(elem.start_point.x + dx, elem.start_point.y + dy)

        if isinstance(elem, Straight):
            new_elem = Straight(elem.start_chainage, elem.length, new_pt, elem.start_azimuth)
        elif isinstance(elem, CircularArc):
            new_elem = CircularArc(elem.start_chainage, elem.length, new_pt,
                                   elem.start_azimuth, elem.radius, elem.direction)
        elif isinstance(elem, TransitionCurve):
            new_elem = TransitionCurve(elem.start_chainage, elem.length, new_pt,
                                       elem.start_azimuth, elem.radius_start,
                                       elem.radius_end, elem.direction)
        else:
            return

        cmd = ModifyElementCommand(self._current_alignment, index, new_elem)
        self.cmd_manager.execute(cmd)
        self._recalculate()
        self.statusBar().showMessage(f"Przesunięto element #{index + 1}")

    def _edit_element_properties(self):
        """Open properties dialog for selected element."""
        if not self._current_alignment:
            return
        selected = self.plan_view._selected_indices
        if not selected:
            QMessageBox.information(self, "Brak zaznaczenia", "Zaznacz element do edycji")
            return

        idx = next(iter(selected))
        if idx >= len(self._current_alignment.horizontal_elements):
            return

        elem = self._current_alignment.horizontal_elements[idx]
        dlg = HorizontalElementDialog(elem, self)
        if dlg.exec() == HorizontalElementDialog.DialogCode.Accepted and dlg.result_element:
            cmd = ModifyElementCommand(self._current_alignment, idx, dlg.result_element)
            self.cmd_manager.execute(cmd)
            self._recalculate()
            self.statusBar().showMessage(f"Zmieniono element #{idx + 1}")

    def _input_coordinates(self):
        """Open coordinate input dialog."""
        dlg = CoordinateInputDialog(self)
        if dlg.exec() == CoordinateInputDialog.DialogCode.Accepted:
            pt = dlg.point
            # Feed to current tool as if clicked
            from railtrack.ui.cad.snap_engine import SnapResult, SnapType
            snap = SnapResult(pt, SnapType.NONE)
            if self.plan_view._current_tool:
                result = self.plan_view._current_tool.on_mouse_press(pt, snap)
                if result:
                    self._handle_tool_action(result)

    def _delete_selected(self):
        """Delete selected elements."""
        if not self._current_alignment:
            return
        selected = self.plan_view._selected_indices
        if not selected:
            return
        indices = sorted(selected, reverse=True)
        cmds = [RemoveElementCommand(self._current_alignment, i) for i in indices]
        compound = CompoundCommand(cmds, "Usuń elementy")
        self.cmd_manager.execute(compound)
        self.plan_view._selected_indices.clear()
        self._recalculate()

    def _add_vertical_element(self):
        """Add vertical element via dialog."""
        if not self._current_alignment:
            return
        ch = 0.0
        elev = 100.0
        if self._current_alignment.vertical_elements:
            last = self._current_alignment.vertical_elements[-1]
            ch = last.end_chainage
            elev = last.elevation_at(ch)

        dlg = VerticalElementDialog(chainage=ch, elevation=elev, parent=self)
        if dlg.exec() == VerticalElementDialog.DialogCode.Accepted and dlg.result_element:
            cmd = AddVerticalElementCommand(self._current_alignment, dlg.result_element)
            self.cmd_manager.execute(cmd)
            self.pm.propagate_vertical(self._current_alignment)
            self._refresh_views()
            self.statusBar().showMessage("Dodano element pionowy")

    # ---- Snap toggle ----
    def _toggle_snap(self, enabled: bool):
        self.plan_view.snap_engine.enabled = enabled
        self.statusBar().showMessage(f"Snap: {'włączony' if enabled else 'wyłączony'}")

    # ---- Realtime validation ----
    def _toggle_realtime_validation(self):
        pass  # Connected via menu checkable

    # ---- Measurements ----
    def _clear_measurements(self):
        self.plan_view.clear_measurements()
        self.statusBar().showMessage("Pomiary wyczyszczone")

    def _zoom_to_fit(self):
        self.plan_view.zoom_to_fit()

    # ---- Layer toggle ----
    def _on_layer_toggled(self, name: str, visible: bool):
        self.plan_view._redraw()

    # ---- Project operations ----
    def _new_project(self):
        self.pm.new_project("Nowy projekt")
        alignment = self.pm.add_alignment("Oś 1")
        self._current_alignment = alignment
        self.cmd_manager.clear()
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
                self.cmd_manager.clear()
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
            self.statusBar().showMessage(f"Minimalizacja: {before} → {after} elementów")

    def _insert_turnout_from_catalog(self):
        if not self._current_alignment:
            QMessageBox.warning(self, "Brak osi", "Nie ma aktywnej osi")
            return
        from railtrack.ui.dialogs.turnout_dialog import TurnoutCatalogDialog
        dlg = TurnoutCatalogDialog(self)
        if dlg.exec() == TurnoutCatalogDialog.DialogCode.Accepted and dlg.created_turnout:
            self._current_alignment.turnouts.append(dlg.created_turnout)
            self._refresh_all()
            self.statusBar().showMessage(f"Wstawiono rozjazd: {dlg.created_turnout.name}")

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
            self.plan_view.show_validation_issues(issues)
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
        self.plan_view.highlight_element(index)

    def _on_element_selected_in_view(self, index: int):
        self.element_table.select_row(index)

    # ---- Callbacks ----
    def _on_alignment_selected(self, name: str):
        if self.pm.project:
            al = self.pm.project.alignment_by_name(name)
            if al:
                self._current_alignment = al
                self._refresh_views()

    def _on_element_changed(self):
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
        self.properties_panel.set_alignment(
            al, self.pm.project.design_criteria if self.pm.project else None
        )
