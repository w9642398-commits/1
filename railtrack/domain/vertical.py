"""Vertical alignment domain model.

Vertical alignment consists of:
- VerticalGrade: constant gradient segment
- VerticalCurve: parabolic vertical curve connecting two grades
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from railtrack.domain.primitives import ChainageRange


class VerticalElementType(Enum):
    GRADE = "grade"
    CURVE = "curve"


class VerticalElement(Protocol):
    @property
    def element_type(self) -> VerticalElementType: ...
    @property
    def start_chainage(self) -> float: ...
    @property
    def end_chainage(self) -> float: ...
    @property
    def length(self) -> float: ...
    def elevation_at(self, chainage: float) -> float: ...
    def gradient_at(self, chainage: float) -> float: ...
    @property
    def chainage_range(self) -> ChainageRange: ...


@dataclass
class VerticalGrade:
    """Constant gradient segment.

    gradient is expressed as a ratio (e.g. 0.01 = 1% = 10 permille).
    """
    start_chainage: float
    length: float
    start_elevation: float
    gradient: float  # rise/run, positive = ascending

    element_type: VerticalElementType = field(
        default=VerticalElementType.GRADE, init=False
    )

    @property
    def end_chainage(self) -> float:
        return self.start_chainage + self.length

    @property
    def end_elevation(self) -> float:
        return self.start_elevation + self.gradient * self.length

    @property
    def chainage_range(self) -> ChainageRange:
        return ChainageRange(self.start_chainage, self.end_chainage)

    def elevation_at(self, chainage: float) -> float:
        ds = chainage - self.start_chainage
        return self.start_elevation + self.gradient * ds

    def gradient_at(self, chainage: float) -> float:
        return self.gradient


@dataclass
class VerticalCurve:
    """Parabolic vertical curve.

    Connects two grades with a circular-equivalent parabolic curve.
    The curve is defined by the PVI (Point of Vertical Intersection),
    or equivalently by start chainage, length, and entry/exit gradients.

    radius: radius of the vertical curve (always positive).
    The algebraic difference of grades determines sag/crest:
      gradient_out - gradient_in > 0 → sag
      gradient_out - gradient_in < 0 → crest
    """
    start_chainage: float
    length: float
    start_elevation: float
    gradient_in: float
    gradient_out: float

    element_type: VerticalElementType = field(
        default=VerticalElementType.CURVE, init=False
    )

    @property
    def end_chainage(self) -> float:
        return self.start_chainage + self.length

    @property
    def chainage_range(self) -> ChainageRange:
        return ChainageRange(self.start_chainage, self.end_chainage)

    @property
    def algebraic_difference(self) -> float:
        """Algebraic difference of gradients."""
        return self.gradient_out - self.gradient_in

    @property
    def radius(self) -> float:
        """Equivalent vertical curve radius."""
        ad = abs(self.algebraic_difference)
        if ad < 1e-12:
            return math.inf
        return self.length / ad

    @property
    def end_elevation(self) -> float:
        return self.elevation_at(self.end_chainage)

    def elevation_at(self, chainage: float) -> float:
        ds = chainage - self.start_chainage
        # Parabolic: z = z0 + g_in * ds + (g_out - g_in) / (2*L) * ds^2
        if self.length < 1e-12:
            return self.start_elevation
        return (
            self.start_elevation
            + self.gradient_in * ds
            + self.algebraic_difference / (2.0 * self.length) * ds * ds
        )

    def gradient_at(self, chainage: float) -> float:
        ds = chainage - self.start_chainage
        if self.length < 1e-12:
            return self.gradient_in
        return self.gradient_in + self.algebraic_difference / self.length * ds


VerticalElementUnion = VerticalGrade | VerticalCurve
