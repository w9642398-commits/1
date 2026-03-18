"""Tests for horizontal geometry elements and engine."""
import math

import pytest

from railtrack.domain.horizontal import (
    CircularArc,
    CurveDirection,
    Straight,
    TransitionCurve,
)
from railtrack.domain.primitives import Point2D
from railtrack.geometry_engine.horizontal_engine import (
    build_straight_curve_straight,
    check_chainage_continuity,
    check_tangency,
    propagate_geometry,
)


class TestStraight:
    def test_end_point_north(self):
        """Straight heading north (azimuth 0) for 100m."""
        s = Straight(0.0, 100.0, Point2D(0.0, 0.0), 0.0)
        ep = s.end_point
        assert abs(ep.x) < 1e-6
        assert abs(ep.y - 100.0) < 1e-6

    def test_end_point_east(self):
        """Straight heading east (azimuth pi/2) for 50m."""
        s = Straight(0.0, 50.0, Point2D(0.0, 0.0), math.pi / 2)
        ep = s.end_point
        assert abs(ep.x - 50.0) < 1e-6
        assert abs(ep.y) < 1e-6

    def test_chainage(self):
        s = Straight(100.0, 200.0, Point2D(0, 0), 0.0)
        assert s.end_chainage == 300.0
        assert s.chainage_range.length == 200.0

    def test_azimuth_constant(self):
        s = Straight(0.0, 100.0, Point2D(0, 0), 1.23)
        assert s.azimuth_at(50.0) == 1.23
        assert s.end_azimuth == 1.23

    def test_radius_infinite(self):
        s = Straight(0.0, 100.0, Point2D(0, 0), 0.0)
        assert math.isinf(s.radius_at(50.0))

    def test_point_at_midpoint(self):
        s = Straight(0.0, 100.0, Point2D(0.0, 0.0), 0.0)
        mid = s.point_at(50.0)
        assert abs(mid.x) < 1e-6
        assert abs(mid.y - 50.0) < 1e-6


class TestCircularArc:
    def test_right_arc_90deg(self):
        """90-degree right arc, R=100, starting north."""
        arc_length = 100.0 * math.pi / 2  # quarter circle
        arc = CircularArc(0, arc_length, Point2D(0, 0), 0.0, 100.0, CurveDirection.RIGHT)
        # End azimuth should be pi/2 (east)
        assert abs(arc.end_azimuth - math.pi / 2) < 1e-4
        # End point should be approximately (100, 100)
        ep = arc.end_point
        assert abs(ep.x - 100.0) < 0.5
        assert abs(ep.y - 100.0) < 0.5

    def test_left_arc_90deg(self):
        """90-degree left arc, R=100, starting north."""
        arc_length = 100.0 * math.pi / 2
        arc = CircularArc(0, arc_length, Point2D(0, 0), 0.0, 100.0, CurveDirection.LEFT)
        # End azimuth should be 3*pi/2 (west)
        expected_az = 2 * math.pi - math.pi / 2  # = 3*pi/2
        assert abs(arc.end_azimuth - expected_az) < 1e-4
        ep = arc.end_point
        assert abs(ep.x - (-100.0)) < 0.5
        assert abs(ep.y - 100.0) < 0.5

    def test_center_right_arc(self):
        """Center of right arc starting north at origin should be at (R, 0)."""
        arc = CircularArc(0, 10.0, Point2D(0, 0), 0.0, 100.0, CurveDirection.RIGHT)
        c = arc.center
        assert abs(c.x - 100.0) < 1e-6
        assert abs(c.y) < 1e-6

    def test_radius_constant(self):
        arc = CircularArc(0, 100.0, Point2D(0, 0), 0.0, 500.0, CurveDirection.RIGHT)
        assert arc.radius_at(0.0) == 500.0
        assert arc.radius_at(50.0) == 500.0


class TestTransitionCurve:
    def test_entry_spiral_basic(self):
        """Entry spiral from straight to R=500, length=80m."""
        tc = TransitionCurve(0, 80.0, Point2D(0, 0), 0.0,
                             math.inf, 500.0, CurveDirection.RIGHT)
        # End radius should be 500
        r_end = tc.radius_at(tc.end_chainage)
        assert abs(r_end - 500.0) < 1.0

        # Start radius should be infinite
        r_start = tc.radius_at(tc.start_chainage)
        assert math.isinf(r_start) or r_start > 1e10

    def test_exit_spiral_basic(self):
        """Exit spiral from R=500 to straight, length=80m."""
        tc = TransitionCurve(0, 80.0, Point2D(0, 0), 0.0,
                             500.0, math.inf, CurveDirection.RIGHT)
        r_start = tc.radius_at(tc.start_chainage)
        assert abs(r_start - 500.0) < 1.0
        r_end = tc.radius_at(tc.end_chainage)
        assert math.isinf(r_end) or r_end > 1e10

    def test_deflection_angle(self):
        """For entry spiral: deflection = L / (2*R)."""
        L, R = 80.0, 500.0
        tc = TransitionCurve(0, L, Point2D(0, 0), 0.0,
                             math.inf, R, CurveDirection.RIGHT)
        expected = L / (2.0 * R)
        assert abs(tc.total_deflection - expected) < 1e-6

    def test_clothoid_parameter(self):
        """A^2 = R * L for entry spiral."""
        L, R = 80.0, 500.0
        tc = TransitionCurve(0, L, Point2D(0, 0), 0.0,
                             math.inf, R, CurveDirection.RIGHT)
        A = tc.clothoid_parameter_A
        assert abs(A * A - R * L) < 1e-6

    def test_spiral_end_close_to_expected(self):
        """End point of entry spiral should be near clothoid approximation."""
        L, R = 80.0, 1000.0
        tc = TransitionCurve(0, L, Point2D(0, 0), 0.0,
                             math.inf, R, CurveDirection.RIGHT)
        ep = tc.end_point
        # For small deflection, the spiral end x ≈ L, y ≈ L^3 / (6*R*L) = L^2/(6R)
        # (in local frame along initial azimuth, which is north)
        # Since azimuth=0 (north), local x=northing, local y=easting (right)
        # Approximate: northing ≈ L, easting ≈ L^2/(6R) for right curve
        expected_y = L  # northing ≈ L for small deflection
        expected_x = L * L * L / (6.0 * R * L)  # easting
        assert abs(ep.y - expected_y) < 1.0  # within 1m
        assert abs(ep.x - expected_x) < 0.5


class TestPropagation:
    def test_straight_straight_tangent(self):
        """Two consecutive straights, same azimuth."""
        elems = [
            Straight(0, 100, Point2D(0, 0), 0.0),
            Straight(0, 100, Point2D(0, 0), 0.0),  # will be fixed
        ]
        result = propagate_geometry(elems)
        assert len(result) == 2
        # Second straight should start where first ends
        assert abs(result[1].start_point.y - 100.0) < 1e-6
        assert abs(result[1].start_chainage - 100.0) < 1e-6

    def test_tangency_after_propagation(self):
        """After propagation, tangency should be perfect."""
        elems = [
            Straight(0, 100, Point2D(0, 0), 0.0),
            TransitionCurve(0, 60, Point2D(0, 0), 0.0,
                            math.inf, 500, CurveDirection.RIGHT),
            CircularArc(0, 200, Point2D(0, 0), 0.0, 500, CurveDirection.RIGHT),
            TransitionCurve(0, 60, Point2D(0, 0), 0.0,
                            500, math.inf, CurveDirection.RIGHT),
            Straight(0, 100, Point2D(0, 0), 0.0),
        ]
        result = propagate_geometry(elems)
        errors = check_tangency(result)
        assert len(errors) == 0

    def test_chainage_continuity(self):
        elems = [
            Straight(0, 100, Point2D(0, 0), 0.0),
            Straight(0, 100, Point2D(0, 0), 0.0),
        ]
        result = propagate_geometry(elems)
        issues = check_chainage_continuity(result)
        assert len(issues) == 0


class TestSCS:
    def test_build_scs(self):
        """Build a standard straight-transition-curve-transition-straight."""
        result = build_straight_curve_straight(
            start_point=Point2D(0, 0),
            start_azimuth=0.0,
            start_chainage=0.0,
            straight1_length=200.0,
            transition1_length=60.0,
            arc_radius=500.0,
            arc_length=300.0,
            direction=CurveDirection.RIGHT,
            transition2_length=60.0,
            straight2_length=200.0,
        )
        assert len(result) == 5
        errors = check_tangency(result)
        assert len(errors) == 0
        ch_issues = check_chainage_continuity(result)
        assert len(ch_issues) == 0
        # Total length
        total = sum(e.length for e in result)
        assert abs(total - 820.0) < 1e-6
