"""Tests for vertical geometry."""
import math

import pytest

from railtrack.domain.vertical import VerticalCurve, VerticalGrade
from railtrack.geometry_engine.vertical_engine import (
    check_gradient_continuity,
    compute_elevation_profile,
    propagate_vertical,
)


class TestVerticalGrade:
    def test_elevation_at(self):
        g = VerticalGrade(0, 1000, 100.0, 0.01)
        assert abs(g.elevation_at(500) - 105.0) < 1e-6
        assert abs(g.end_elevation - 110.0) < 1e-6

    def test_gradient_constant(self):
        g = VerticalGrade(0, 1000, 100.0, 0.015)
        assert g.gradient_at(0) == 0.015
        assert g.gradient_at(500) == 0.015


class TestVerticalCurve:
    def test_parabolic_sag(self):
        """Sag curve: gradient goes from -0.01 to +0.01."""
        vc = VerticalCurve(0, 200, 100.0, -0.01, 0.01)
        # At midpoint, gradient should be 0
        assert abs(vc.gradient_at(100) - 0.0) < 1e-10
        # Start elevation
        assert abs(vc.elevation_at(0) - 100.0) < 1e-10
        # End: z = 100 + (-0.01)*200 + (0.02)/(400)*200^2
        expected_end = 100 + (-0.01) * 200 + 0.02 / 400 * 200 * 200
        assert abs(vc.end_elevation - expected_end) < 1e-6

    def test_radius(self):
        vc = VerticalCurve(0, 500, 100.0, -0.005, 0.005)
        # radius = L / |g_out - g_in| = 500 / 0.01 = 50000
        assert abs(vc.radius - 50000.0) < 1e-6


class TestVerticalPropagation:
    def test_grade_grade_continuity(self):
        """Two grades: first 1%, then 0.5%."""
        elems = [
            VerticalGrade(0, 500, 100.0, 0.01),
            VerticalGrade(0, 500, 0.0, 0.005),  # will be fixed
        ]
        result = propagate_vertical(elems)
        assert abs(result[1].start_chainage - 500) < 1e-6
        assert abs(result[1].start_elevation - 105.0) < 1e-6

    def test_elevation_profile(self):
        elems = [VerticalGrade(0, 100, 100.0, 0.01)]
        profile = compute_elevation_profile(elems, interval=50)
        assert len(profile) >= 2
        assert abs(profile[0][1] - 100.0) < 1e-6
        assert abs(profile[-1][1] - 101.0) < 1e-6
