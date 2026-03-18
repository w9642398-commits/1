"""Cant (superelevation) domain model for railway alignment.

Cant is the difference in elevation between the two rails.
In curves, cant counteracts centrifugal force.

Cant alignment consists of:
- CantSegment: constant cant
- CantRamp: linear transition of cant (associated with transition curves)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from railtrack.domain.primitives import ChainageRange


class CantElementType(Enum):
    CONSTANT = "constant"
    RAMP = "ramp"


@dataclass
class CantSegment:
    """Constant cant segment (typically over a circular arc)."""
    start_chainage: float
    length: float
    cant: float  # metres, positive = outer rail higher
    gauge: float = 1.435  # track gauge in metres (standard gauge)

    element_type: CantElementType = field(
        default=CantElementType.CONSTANT, init=False
    )

    @property
    def end_chainage(self) -> float:
        return self.start_chainage + self.length

    @property
    def chainage_range(self) -> ChainageRange:
        return ChainageRange(self.start_chainage, self.end_chainage)

    def cant_at(self, chainage: float) -> float:
        return self.cant


@dataclass
class CantRamp:
    """Linear cant ramp (typically over a transition curve)."""
    start_chainage: float
    length: float
    cant_start: float
    cant_end: float
    gauge: float = 1.435

    element_type: CantElementType = field(
        default=CantElementType.RAMP, init=False
    )

    @property
    def end_chainage(self) -> float:
        return self.start_chainage + self.length

    @property
    def chainage_range(self) -> ChainageRange:
        return ChainageRange(self.start_chainage, self.end_chainage)

    @property
    def cant_gradient(self) -> float:
        """Cant gradient (change of cant per unit length)."""
        if self.length < 1e-12:
            return 0.0
        return (self.cant_end - self.cant_start) / self.length

    def cant_at(self, chainage: float) -> float:
        ds = chainage - self.start_chainage
        if self.length < 1e-12:
            return self.cant_start
        return self.cant_start + (self.cant_end - self.cant_start) * ds / self.length


CantElementUnion = CantSegment | CantRamp


def equilibrium_cant(speed_kmh: float, radius: float, gauge: float = 1.435) -> float:
    """Calculate equilibrium cant for a given speed and radius.

    D_eq = G * V^2 / (g * R)
    where G = gauge, V = speed (m/s), g = 9.81, R = radius.
    """
    if math.isinf(radius) or radius <= 0:
        return 0.0
    v_ms = speed_kmh / 3.6
    return gauge * v_ms * v_ms / (9.81 * radius)


def cant_deficiency(applied_cant: float, equilibrium: float) -> float:
    """Cant deficiency = equilibrium cant - applied cant."""
    return equilibrium - applied_cant
