"""Layer management system for controlling visibility and display."""
from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal


@dataclass
class Layer:
    """A display layer with visibility and styling."""
    name: str
    visible: bool = True
    locked: bool = False
    color: tuple[int, int, int] = (200, 200, 200)
    line_width: int = 2
    opacity: float = 1.0

    def toggle_visible(self) -> None:
        self.visible = not self.visible

    def toggle_locked(self) -> None:
        self.locked = not self.locked


class LayerManager(QObject):
    """Manages display layers."""

    layers_changed = Signal()

    # Default layers
    LAYER_GEOMETRY = "Geometria"
    LAYER_GRID = "Siatka"
    LAYER_CHAINAGE = "Pikietaż"
    LAYER_VALIDATION = "Walidacja"
    LAYER_HANDLES = "Uchwyty"
    LAYER_SNAP = "Snap"
    LAYER_MEASUREMENTS = "Pomiary"
    LAYER_PROFILE = "Profil"
    LAYER_CANT = "Przechyłki"
    LAYER_TURNOUTS = "Rozjazdy"
    LAYER_POINTS = "Punkty"
    LAYER_CONSTRUCTION = "Linie konstrukcyjne"

    def __init__(self):
        super().__init__()
        self._layers: dict[str, Layer] = {}
        self._init_default_layers()

    def _init_default_layers(self) -> None:
        defaults = [
            Layer(self.LAYER_GRID, True, True, (60, 60, 60), 1, 0.3),
            Layer(self.LAYER_GEOMETRY, True, False, (200, 200, 200), 2, 1.0),
            Layer(self.LAYER_CHAINAGE, True, True, (150, 150, 150), 1, 0.7),
            Layer(self.LAYER_VALIDATION, True, True, (255, 100, 100), 2, 0.8),
            Layer(self.LAYER_HANDLES, True, True, (255, 255, 100), 1, 1.0),
            Layer(self.LAYER_SNAP, True, True, (255, 165, 0), 1, 1.0),
            Layer(self.LAYER_MEASUREMENTS, True, False, (0, 255, 255), 1, 0.9),
            Layer(self.LAYER_PROFILE, True, False, (50, 150, 50), 2, 1.0),
            Layer(self.LAYER_CANT, True, False, (150, 50, 150), 2, 1.0),
            Layer(self.LAYER_TURNOUTS, True, False, (200, 150, 50), 2, 1.0),
            Layer(self.LAYER_POINTS, True, False, (100, 200, 255), 1, 0.8),
            Layer(self.LAYER_CONSTRUCTION, False, False, (128, 128, 128), 1, 0.5),
        ]
        for layer in defaults:
            self._layers[layer.name] = layer

    def get(self, name: str) -> Layer | None:
        return self._layers.get(name)

    def is_visible(self, name: str) -> bool:
        layer = self._layers.get(name)
        return layer.visible if layer else True

    def set_visible(self, name: str, visible: bool) -> None:
        layer = self._layers.get(name)
        if layer:
            layer.visible = visible
            self.layers_changed.emit()

    def toggle_visible(self, name: str) -> None:
        layer = self._layers.get(name)
        if layer:
            layer.toggle_visible()
            self.layers_changed.emit()

    def all_layers(self) -> list[Layer]:
        return list(self._layers.values())

    def add_layer(self, layer: Layer) -> None:
        self._layers[layer.name] = layer
        self.layers_changed.emit()

    def remove_layer(self, name: str) -> None:
        if name in self._layers:
            del self._layers[name]
            self.layers_changed.emit()
