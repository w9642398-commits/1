"""Turnout (switch / point) domain model.

MVP provides data model and validation hooks.
Full geometric modelling of turnout components is on the roadmap.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TurnoutType(Enum):
    SIMPLE = "simple"
    SYMMETRIC = "symmetric"
    CURVED = "curved"


class TurnoutHand(Enum):
    LEFT = "left"
    RIGHT = "right"


@dataclass
class Turnout:
    """Parametric turnout placed on an alignment."""
    name: str
    chainage: float  # chainage of the turnout tip (start)
    hand: TurnoutHand
    turnout_type: TurnoutType
    tangent_angle: float  # frog angle in radians (e.g. 1:9 → atan(1/9))
    total_length: float  # total length of the turnout
    curve_radius: float  # radius of diverging track
    speed_through: float  # max speed on through route (km/h)
    speed_diverging: float  # max speed on diverging route (km/h)

    @property
    def end_chainage(self) -> float:
        return self.chainage + self.total_length

    @property
    def frog_ratio(self) -> str:
        """Human-readable frog ratio like '1:9'."""
        import math
        ratio = 1.0 / math.tan(self.tangent_angle)
        return f"1:{ratio:.0f}"
