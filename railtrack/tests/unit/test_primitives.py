"""Tests for primitive types."""
import math

import pytest

from railtrack.domain.primitives import (
    ChainageRange,
    Point2D,
    Point3D,
    azimuth_from_dx_dy,
    normalize_angle,
)


class TestPoint2D:
    def test_distance(self):
        p1 = Point2D(0.0, 0.0)
        p2 = Point2D(3.0, 4.0)
        assert abs(p1.distance_to(p2) - 5.0) < 1e-10

    def test_translated(self):
        p = Point2D(1.0, 2.0).translated(3.0, 4.0)
        assert abs(p.x - 4.0) < 1e-10
        assert abs(p.y - 6.0) < 1e-10

    def test_rotated_90deg(self):
        p = Point2D(1.0, 0.0).rotated(math.pi / 2)
        assert abs(p.x - 0.0) < 1e-10
        assert abs(p.y - 1.0) < 1e-10

    def test_add_sub(self):
        p = Point2D(1, 2) + Point2D(3, 4)
        assert p == Point2D(4, 6)
        p2 = Point2D(5, 6) - Point2D(1, 2)
        assert p2 == Point2D(4, 4)


class TestPoint3D:
    def test_to_2d(self):
        p = Point3D(1, 2, 3)
        assert p.to_2d() == Point2D(1, 2)


class TestChainageRange:
    def test_length(self):
        cr = ChainageRange(100, 200)
        assert cr.length == 100

    def test_contains(self):
        cr = ChainageRange(100, 200)
        assert cr.contains(150)
        assert cr.contains(100)
        assert cr.contains(200)
        assert not cr.contains(99)

    def test_overlaps(self):
        a = ChainageRange(100, 200)
        b = ChainageRange(150, 250)
        assert a.overlaps(b)
        c = ChainageRange(200, 300)
        assert not a.overlaps(c)


class TestAzimuth:
    def test_north(self):
        az = azimuth_from_dx_dy(0, 1)
        assert abs(az) < 1e-10

    def test_east(self):
        az = azimuth_from_dx_dy(1, 0)
        assert abs(az - math.pi / 2) < 1e-10

    def test_south(self):
        az = azimuth_from_dx_dy(0, -1)
        assert abs(az - math.pi) < 1e-10

    def test_normalize(self):
        assert abs(normalize_angle(-math.pi / 2) - 3 * math.pi / 2) < 1e-10
