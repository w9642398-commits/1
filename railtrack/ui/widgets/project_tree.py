"""Project tree widget showing alignment hierarchy."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from railtrack.domain.alignment import Project


class ProjectTree(QTreeWidget):
    alignment_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabel("Projekt")
        self.itemClicked.connect(self._on_item_clicked)

    def set_project(self, project: Project):
        self.clear()
        root = QTreeWidgetItem(self, [project.name])
        root.setExpanded(True)

        alignments_node = QTreeWidgetItem(root, ["Osie"])
        alignments_node.setExpanded(True)
        for al in project.alignments:
            al_item = QTreeWidgetItem(alignments_node, [al.name])
            al_item.setData(0, 256, al.name)  # store alignment name
            QTreeWidgetItem(al_item, [f"Geometria pozioma ({len(al.horizontal_elements)} elem.)"])
            QTreeWidgetItem(al_item, [f"Profil pionowy ({len(al.vertical_elements)} elem.)"])
            QTreeWidgetItem(al_item, [f"Przechyłki ({len(al.cant_elements)} elem.)"])
            QTreeWidgetItem(al_item, [f"Rozjazdy ({len(al.turnouts)})"])

        criteria_node = QTreeWidgetItem(root, ["Kryteria projektowe"])
        QTreeWidgetItem(criteria_node, [f"V_max = {project.design_criteria.max_speed_kmh} km/h"])
        QTreeWidgetItem(criteria_node, [f"Rozstaw = {project.design_criteria.gauge} m"])

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        name = item.data(0, 256)
        if name:
            self.alignment_selected.emit(name)
