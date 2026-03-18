"""Primitive geometric types for railway geometry."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Point2D:
    """2D point in local coordinate system (easting, northing)."""
    x: float
    y: float

    def distance_to(self, other: Point2D) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def translated(self, dx: float, dy: float) -> Point2D:
        return Point2D(self.x + dx, self.y + dy)

    def rotated(self, angle: float, origin: Point2D | None = None) -> Point2D:
        """Rotate point around origin by angle (radians, CCW positive)."""
        o = origin or Point2D(0.0, 0.0)
        dx, dy = self.x - o.x, self.y - o.y
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        return Point2D(
            o.x + dx * cos_a - dy * sin_a,
            o.y + dx * sin_a + dy * cos_a,
        )

    def __add__(self, other: Point2D) -> Point2D:
        return Point2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Point2D) -> Point2D:
        return Point2D(self.x - other.x, self.y - other.y)


@dataclass(frozen=True)
class Point3D:
    """3D point (easting, northing, elevation)."""
    x: float
    y: float
    z: float

    def to_2d(self) -> Point2D:
        return Point2D(self.x, self.y)

    def distance_to(self, other: Point3D) -> float:
        return math.sqrt(
            (self.x - other.x) ** 2
            + (self.y - other.y) ** 2
            + (self.z - other.z) ** 2
        )


@dataclass(frozen=True)
class ChainageRange:
    """Range of chainage along an alignment."""
    start: float
    end: float

    @property
    def length(self) -> float:
        return self.end - self.start

    def contains(self, chainage: float, tolerance: float = 1e-6) -> bool:
        return self.start - tolerance <= chainage <= self.end + tolerance

    def overlaps(self, other: ChainageRange) -> bool:
        return self.start < other.end and other.start < self.end


def normalize_angle(angle: float) -> float:
    """Normalize angle to [0, 2*pi)."""
    return angle % (2.0 * math.pi)


def azimuth_from_dx_dy(dx: float, dy: float) -> float:
    """Compute azimuth (bearing from north, CW positive) from coordinate deltas.

    In survey coordinates: x=easting, y=northing.
    Azimuth 0 = north, pi/2 = east.
    """
    return normalize_angle(math.atan2(dx, dy))
