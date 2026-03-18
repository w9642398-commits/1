"""Undo/redo command system using Command pattern."""
from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal

from railtrack.domain.alignment import Alignment
from railtrack.domain.horizontal import (
    CircularArc, CurveDirection, HorizontalElementUnion, Straight, TransitionCurve,
)
from railtrack.domain.vertical import VerticalElementUnion, VerticalGrade, VerticalCurve
from railtrack.domain.primitives import Point2D


class Command(ABC):
    """Abstract command for undo/redo."""

    @abstractmethod
    def execute(self) -> None: ...

    @abstractmethod
    def undo(self) -> None: ...

    @property
    def description(self) -> str:
        return self.__class__.__name__


class CommandManager(QObject):
    """Manages undo/redo stack."""

    changed = Signal()  # emitted when command stack changes
    can_undo_changed = Signal(bool)
    can_redo_changed = Signal(bool)

    def __init__(self, max_history: int = 200):
        super().__init__()
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []
        self._max_history = max_history

    def execute(self, command: Command) -> None:
        command.execute()
        self._undo_stack.append(command)
        self._redo_stack.clear()
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
        self._emit_signals()

    def undo(self) -> None:
        if not self._undo_stack:
            return
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        self._emit_signals()

    def redo(self) -> None:
        if not self._redo_stack:
            return
        cmd = self._redo_stack.pop()
        cmd.execute()
        self._undo_stack.append(cmd)
        self._emit_signals()

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def undo_description(self) -> str:
        if self._undo_stack:
            return self._undo_stack[-1].description
        return ""

    @property
    def redo_description(self) -> str:
        if self._redo_stack:
            return self._redo_stack[-1].description
        return ""

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._emit_signals()

    def _emit_signals(self) -> None:
        self.can_undo_changed.emit(self.can_undo)
        self.can_redo_changed.emit(self.can_redo)
        self.changed.emit()


# --- Concrete Commands ---

class AddElementCommand(Command):
    """Add a horizontal element to alignment."""

    def __init__(self, alignment: Alignment, element: HorizontalElementUnion,
                 index: int | None = None):
        self._alignment = alignment
        self._element = element
        self._index = index if index is not None else len(alignment.horizontal_elements)

    def execute(self) -> None:
        self._alignment.horizontal_elements.insert(self._index, self._element)

    def undo(self) -> None:
        self._alignment.horizontal_elements.pop(self._index)

    @property
    def description(self) -> str:
        return f"Dodaj {self._element.element_type.value}"


class RemoveElementCommand(Command):
    """Remove a horizontal element from alignment."""

    def __init__(self, alignment: Alignment, index: int):
        self._alignment = alignment
        self._index = index
        self._element: HorizontalElementUnion | None = None

    def execute(self) -> None:
        self._element = self._alignment.horizontal_elements.pop(self._index)

    def undo(self) -> None:
        if self._element is not None:
            self._alignment.horizontal_elements.insert(self._index, self._element)

    @property
    def description(self) -> str:
        return "Usuń element"


class MoveElementCommand(Command):
    """Move an element's start point (and propagate)."""

    def __init__(self, alignment: Alignment, index: int,
                 new_start_point: Point2D, old_start_point: Point2D):
        self._alignment = alignment
        self._index = index
        self._new_point = new_start_point
        self._old_point = old_start_point
        self._old_elements: list[HorizontalElementUnion] = []

    def execute(self) -> None:
        self._old_elements = list(self._alignment.horizontal_elements)
        elem = self._alignment.horizontal_elements[self._index]
        self._replace_start_point(elem, self._new_point)

    def undo(self) -> None:
        self._alignment.horizontal_elements[:] = self._old_elements

    def _replace_start_point(self, elem: HorizontalElementUnion, pt: Point2D) -> None:
        idx = self._index
        elems = self._alignment.horizontal_elements
        if isinstance(elem, Straight):
            elems[idx] = Straight(elem.start_chainage, elem.length, pt, elem.start_azimuth)
        elif isinstance(elem, CircularArc):
            elems[idx] = CircularArc(elem.start_chainage, elem.length, pt,
                                     elem.start_azimuth, elem.radius, elem.direction)
        elif isinstance(elem, TransitionCurve):
            elems[idx] = TransitionCurve(elem.start_chainage, elem.length, pt,
                                         elem.start_azimuth, elem.radius_start,
                                         elem.radius_end, elem.direction)

    @property
    def description(self) -> str:
        return "Przesuń element"


class ModifyElementCommand(Command):
    """Replace element with modified version."""

    def __init__(self, alignment: Alignment, index: int,
                 new_element: HorizontalElementUnion):
        self._alignment = alignment
        self._index = index
        self._new_element = new_element
        self._old_element: HorizontalElementUnion | None = None

    def execute(self) -> None:
        self._old_element = self._alignment.horizontal_elements[self._index]
        self._alignment.horizontal_elements[self._index] = self._new_element

    def undo(self) -> None:
        if self._old_element is not None:
            self._alignment.horizontal_elements[self._index] = self._old_element

    @property
    def description(self) -> str:
        return "Zmień element"


class ReplaceAllElementsCommand(Command):
    """Replace entire element list (for bulk operations)."""

    def __init__(self, alignment: Alignment,
                 new_elements: list[HorizontalElementUnion]):
        self._alignment = alignment
        self._new_elements = new_elements
        self._old_elements: list[HorizontalElementUnion] = []

    def execute(self) -> None:
        self._old_elements = list(self._alignment.horizontal_elements)
        self._alignment.horizontal_elements[:] = self._new_elements

    def undo(self) -> None:
        self._alignment.horizontal_elements[:] = self._old_elements

    @property
    def description(self) -> str:
        return "Zmień geometrię"


class AddVerticalElementCommand(Command):
    """Add a vertical element to alignment."""

    def __init__(self, alignment: Alignment, element: VerticalElementUnion,
                 index: int | None = None):
        self._alignment = alignment
        self._element = element
        self._index = index if index is not None else len(alignment.vertical_elements)

    def execute(self) -> None:
        self._alignment.vertical_elements.insert(self._index, self._element)

    def undo(self) -> None:
        self._alignment.vertical_elements.pop(self._index)

    @property
    def description(self) -> str:
        return "Dodaj element pionowy"


class RemoveVerticalElementCommand(Command):
    """Remove a vertical element."""

    def __init__(self, alignment: Alignment, index: int):
        self._alignment = alignment
        self._index = index
        self._element: VerticalElementUnion | None = None

    def execute(self) -> None:
        self._element = self._alignment.vertical_elements.pop(self._index)

    def undo(self) -> None:
        if self._element is not None:
            self._alignment.vertical_elements.insert(self._index, self._element)

    @property
    def description(self) -> str:
        return "Usuń element pionowy"


class ModifyVerticalElementCommand(Command):
    """Replace vertical element with modified version."""

    def __init__(self, alignment: Alignment, index: int,
                 new_element: VerticalElementUnion):
        self._alignment = alignment
        self._index = index
        self._new_element = new_element
        self._old_element: VerticalElementUnion | None = None

    def execute(self) -> None:
        self._old_element = self._alignment.vertical_elements[self._index]
        self._alignment.vertical_elements[self._index] = self._new_element

    def undo(self) -> None:
        if self._old_element is not None:
            self._alignment.vertical_elements[self._index] = self._old_element

    @property
    def description(self) -> str:
        return "Zmień element pionowy"


class CompoundCommand(Command):
    """Execute multiple commands as a single undo/redo step."""

    def __init__(self, commands: list[Command], desc: str = "Operacja złożona"):
        self._commands = commands
        self._desc = desc

    def execute(self) -> None:
        for cmd in self._commands:
            cmd.execute()

    def undo(self) -> None:
        for cmd in reversed(self._commands):
            cmd.undo()

    @property
    def description(self) -> str:
        return self._desc
