"""Layer management panel widget."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from railtrack.ui.cad.layers import Layer, LayerManager


class LayerPanel(QWidget):
    """Panel for controlling layer visibility."""

    layer_toggled = Signal(str, bool)

    def __init__(self, layer_manager: LayerManager, parent=None):
        super().__init__(parent)
        self._lm = layer_manager
        self._checkboxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        title = QLabel("Warstwy")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setContentsMargins(2, 2, 2, 2)
        self._scroll_layout.setSpacing(1)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        self._rebuild()
        self._lm.layers_changed.connect(self._rebuild)

    def _rebuild(self) -> None:
        # Clear existing
        while self._scroll_layout.count():
            item = self._scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._checkboxes.clear()

        for layer in self._lm.all_layers():
            row = QHBoxLayout()
            cb = QCheckBox(layer.name)
            cb.setChecked(layer.visible)
            cb.stateChanged.connect(lambda state, name=layer.name: self._on_toggle(name, state))
            self._checkboxes[layer.name] = cb

            # Color indicator
            r, g, b = layer.color
            indicator = QLabel("■")
            indicator.setStyleSheet(f"color: rgb({r},{g},{b}); font-size: 14px;")
            indicator.setFixedWidth(18)

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(2, 0, 2, 0)
            row_layout.addWidget(indicator)
            row_layout.addWidget(cb)
            row_layout.addStretch()

            self._scroll_layout.addWidget(row_widget)

        self._scroll_layout.addStretch()

    def _on_toggle(self, name: str, state: int) -> None:
        visible = state == Qt.CheckState.Checked.value
        self._lm.set_visible(name, visible)
        self.layer_toggled.emit(name, visible)
