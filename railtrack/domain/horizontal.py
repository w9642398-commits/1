"""Horizontal alignment domain model for railway geometry.

Elements:
- Straight (tangent)
- CircularArc
- TransitionCurve (clothoid / Euler spiral)

All angles are azimuths (from north, clockwise positive) in radians.
All lengths are in metres.  All coordinates are in a local survey system.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import numpy as np

from railtrack.domain.primitives import ChainageRange, Point2D, normalize_angle


class CurveDirection(Enum):
    LEFT = "left"
    RIGHT = "right"


class HorizontalElementType(Enum):
    STRAIGHT = "straight"
    CIRCULAR_ARC = "circular_arc"
    TRANSITION_CURVE = "transition_curve"


# ---------------------------------------------------------------------------
# Protocol for all horizontal elements
# ---------------------------------------------------------------------------
class HorizontalElement(Protocol):
    """Protocol every horizontal geometry element must satisfy."""

    @property
    def element_type(self) -> HorizontalElementType: ...

    @property
    def start_chainage(self) -> float: ...

    @property
    def end_chainage(self) -> float: ...

    @property
    def length(self) -> float: ...

    @property
    def start_point(self) -> Point2D: ...

    @property
    def end_point(self) -> Point2D: ...

    @property
    def start_azimuth(self) -> float: ...

    @property
    def end_azimuth(self) -> float: ...

    def point_at(self, chainage: float) -> Point2D:
        """XY coordinates at a given chainage."""
        ...

    def azimuth_at(self, chainage: float) -> float:
        """Azimuth (bearing) at a given chainage."""
        ...

    def radius_at(self, chainage: float) -> float:
        """Radius of curvature at chainage. Infinity for straights."""
        ...

    @property
    def chainage_range(self) -> ChainageRange: ...


# ---------------------------------------------------------------------------
# Straight
# ---------------------------------------------------------------------------
@dataclass
class Straight:
    """Tangent (straight) segment."""

    start_chainage: float
    length: float
    start_point: Point2D
    start_azimuth: float  # radians, azimuth

    element_type: HorizontalElementType = field(
        default=HorizontalElementType.STRAIGHT, init=False
    )

    @property
    def end_chainage(self) -> float:
        return self.start_chainage + self.length

    @property
    def end_azimuth(self) -> float:
        return self.start_azimuth

    @property
    def end_point(self) -> Point2D:
        return self.point_at(self.end_chainage)

    @property
    def chainage_range(self) -> ChainageRange:
        return ChainageRange(self.start_chainage, self.end_chainage)

    def point_at(self, chainage: float) -> Point2D:
        ds = chainage - self.start_chainage
        dx = ds * math.sin(self.start_azimuth)
        dy = ds * math.cos(self.start_azimuth)
        return Point2D(self.start_point.x + dx, self.start_point.y + dy)

    def azimuth_at(self, chainage: float) -> float:
        return self.start_azimuth

    def radius_at(self, chainage: float) -> float:
        return math.inf


# ---------------------------------------------------------------------------
# CircularArc
# ---------------------------------------------------------------------------
@dataclass
class CircularArc:
    """Circular arc segment."""

    start_chainage: float
    length: float
    start_point: Point2D
    start_azimuth: float
    radius: float  # always positive
    direction: CurveDirection

    element_type: HorizontalElementType = field(
        default=HorizontalElementType.CIRCULAR_ARC, init=False
    )

    @property
    def signed_radius(self) -> float:
        return self.radius if self.direction == CurveDirection.RIGHT else -self.radius

    @property
    def end_chainage(self) -> float:
        return self.start_chainage + self.length

    @property
    def deflection_angle(self) -> float:
        """Total deflection angle (always positive)."""
        return self.length / self.radius

    @property
    def end_azimuth(self) -> float:
        sign = 1.0 if self.direction == CurveDirection.RIGHT else -1.0
        return normalize_angle(self.start_azimuth + sign * self.deflection_angle)

    @property
    def center(self) -> Point2D:
        """Centre of the circular arc."""
        sign = 1.0 if self.direction == CurveDirection.RIGHT else -1.0
        perp = self.start_azimuth + sign * math.pi / 2.0
        return Point2D(
            self.start_point.x + self.radius * math.sin(perp),
            self.start_point.y + self.radius * math.cos(perp),
        )

    @property
    def end_point(self) -> Point2D:
        return self.point_at(self.end_chainage)

    @property
    def chainage_range(self) -> ChainageRange:
        return ChainageRange(self.start_chainage, self.end_chainage)

    def point_at(self, chainage: float) -> Point2D:
        ds = chainage - self.start_chainage
        # In survey coords (x=east, y=north), RIGHT = CW = negative math rotation
        sign = -1.0 if self.direction == CurveDirection.RIGHT else 1.0
        theta = sign * ds / self.radius
        c = self.center
        # Vector from center to start point, then rotate by theta
        vx = self.start_point.x - c.x
        vy = self.start_point.y - c.y
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        return Point2D(
            c.x + vx * cos_t - vy * sin_t,
            c.y + vx * sin_t + vy * cos_t,
        )

    def azimuth_at(self, chainage: float) -> float:
        ds = chainage - self.start_chainage
        sign = 1.0 if self.direction == CurveDirection.RIGHT else -1.0
        return normalize_angle(self.start_azimuth + sign * ds / self.radius)

    def radius_at(self, chainage: float) -> float:
        return self.radius


# ---------------------------------------------------------------------------
# TransitionCurve (Clothoid / Euler Spiral)
# ---------------------------------------------------------------------------
@dataclass
class TransitionCurve:
    """Clothoid transition curve.

    The clothoid parameter A satisfies: A^2 = R * L
    where R is the radius at the end and L is the total length.

    radius_start: radius at start (inf for tangent-to-curve)
    radius_end:   radius at end   (inf for curve-to-tangent)
    """

    start_chainage: float
    length: float
    start_point: Point2D
    start_azimuth: float
    radius_start: float  # may be inf
    radius_end: float    # may be inf
    direction: CurveDirection

    element_type: HorizontalElementType = field(
        default=HorizontalElementType.TRANSITION_CURVE, init=False
    )

    # Number of integration steps for Fresnel-type numerical integration
    _INTEGRATION_STEPS: int = field(default=500, init=False, repr=False)

    @property
    def clothoid_parameter_A(self) -> float:
        """Clothoid parameter A where A^2 = R_end * L (for entry spiral)."""
        r = self.radius_end if math.isinf(self.radius_start) else self.radius_start
        return math.sqrt(r * self.length)

    @property
    def end_chainage(self) -> float:
        return self.start_chainage + self.length

    @property
    def chainage_range(self) -> ChainageRange:
        return ChainageRange(self.start_chainage, self.end_chainage)

    def _curvature_at_local(self, s: float) -> float:
        """Curvature at local distance s from element start.

        Curvature varies linearly from 1/radius_start to 1/radius_end.
        """
        k_start = 0.0 if math.isinf(self.radius_start) else 1.0 / self.radius_start
        k_end = 0.0 if math.isinf(self.radius_end) else 1.0 / self.radius_end
        if self.length == 0:
            return k_start
        return k_start + (k_end - k_start) * s / self.length

    def _deflection_at_local(self, s: float) -> float:
        """Total deflection angle from element start to local distance s."""
        k_start = 0.0 if math.isinf(self.radius_start) else 1.0 / self.radius_start
        k_end = 0.0 if math.isinf(self.radius_end) else 1.0 / self.radius_end
        # integral of k(t) dt from 0 to s  where k(t) = k_start + (k_end-k_start)*t/L
        return k_start * s + (k_end - k_start) * s * s / (2.0 * self.length)

    @property
    def total_deflection(self) -> float:
        return self._deflection_at_local(self.length)

    @property
    def end_azimuth(self) -> float:
        sign = 1.0 if self.direction == CurveDirection.RIGHT else -1.0
        return normalize_angle(self.start_azimuth + sign * self.total_deflection)

    def _compute_local_coords(self, s: float) -> tuple[float, float]:
        """Compute local (tangent-frame) coordinates via numerical integration.

        Uses Simpson's rule over the clothoid integral.
        The local x-axis is along the initial azimuth direction.
        """
        sign = 1.0 if self.direction == CurveDirection.RIGHT else -1.0
        n = max(4, int(self._INTEGRATION_STEPS * s / max(self.length, 1.0)))
        if n % 2 == 1:
            n += 1
        dt = s / n if n > 0 else 0.0
        x_local = 0.0
        y_local = 0.0
        for i in range(n + 1):
            t = i * dt
            angle = sign * self._deflection_at_local(t)
            # In local frame: dx = cos(angle)*dt, dy = sin(angle)*dt
            w = 1.0
            if 0 < i < n:
                w = 4.0 if i % 2 == 1 else 2.0
            x_local += w * math.cos(angle)
            y_local += w * math.sin(angle)
        x_local *= dt / 3.0
        y_local *= dt / 3.0
        return x_local, y_local

    def point_at(self, chainage: float) -> Point2D:
        s = chainage - self.start_chainage
        s = max(0.0, min(s, self.length))
        lx, ly = self._compute_local_coords(s)
        # Transform from local frame (along start azimuth) to global
        az = self.start_azimuth
        sin_a, cos_a = math.sin(az), math.cos(az)
        gx = self.start_point.x + lx * sin_a + ly * cos_a
        gy = self.start_point.y + lx * cos_a - ly * sin_a
        return Point2D(gx, gy)

    @property
    def end_point(self) -> Point2D:
        return self.point_at(self.end_chainage)

    def azimuth_at(self, chainage: float) -> float:
        s = chainage - self.start_chainage
        s = max(0.0, min(s, self.length))
        sign = 1.0 if self.direction == CurveDirection.RIGHT else -1.0
        return normalize_angle(self.start_azimuth + sign * self._deflection_at_local(s))

    def radius_at(self, chainage: float) -> float:
        s = chainage - self.start_chainage
        k = self._curvature_at_local(s)
        return 1.0 / k if k > 1e-15 else math.inf


# Type alias
HorizontalElementUnion = Straight | CircularArc | TransitionCurve
