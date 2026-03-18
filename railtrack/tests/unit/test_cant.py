"""Tests for cant computation."""
import math

import pytest

from railtrack.domain.cant import (
    CantRamp,
    CantSegment,
    cant_deficiency,
    equilibrium_cant,
)
from railtrack.domain.horizontal import (
    CircularArc,
    CurveDirection,
    Straight,
    TransitionCurve,
)
from railtrack.domain.primitives import Point2D
from railtrack.geometry_engine.cant_engine import generate_cant_elements
from railtrack.geometry_engine.horizontal_engine import propagate_geometry


class TestEquilibriumCant:
    def test_basic(self):
        """V=120 km/h, R=800 m, gauge=1.435 m."""
        eq = equilibrium_cant(120, 800, 1.435)
        # D_eq = 1.435 * (120/3.6)^2 / (9.81 * 800)
        v = 120 / 3.6
        expected = 1.435 * v * v / (9.81 * 800)
        assert abs(eq - expected) < 1e-6

    def test_straight(self):
        eq = equilibrium_cant(120, math.inf)
        assert eq == 0.0

    def test_deficiency(self):
        d = cant_deficiency(0.100, 0.150)
        assert abs(d - 0.050) < 1e-6


class TestCantSegment:
    def test_constant(self):
        cs = CantSegment(0, 100, 0.120)
        assert cs.cant_at(50) == 0.120


class TestCantRamp:
    def test_linear(self):
        cr = CantRamp(0, 60, 0.0, 0.120)
        assert abs(cr.cant_at(0) - 0.0) < 1e-10
        assert abs(cr.cant_at(30) - 0.060) < 1e-6
        assert abs(cr.cant_at(60) - 0.120) < 1e-6

    def test_gradient(self):
        cr = CantRamp(0, 80, 0.0, 0.160)
        assert abs(cr.cant_gradient - 0.002) < 1e-6


class TestCantGeneration:
    def test_scs_generates_cant(self):
        """Generate cant for straight-transition-arc-transition-straight."""
        elems = propagate_geometry([
            Straight(0, 200, Point2D(0, 0), 0.0),
            TransitionCurve(0, 60, Point2D(0, 0), 0.0,
                            math.inf, 500, CurveDirection.RIGHT),
            CircularArc(0, 300, Point2D(0, 0), 0.0, 500, CurveDirection.RIGHT),
            TransitionCurve(0, 60, Point2D(0, 0), 0.0,
                            500, math.inf, CurveDirection.RIGHT),
            Straight(0, 200, Point2D(0, 0), 0.0),
        ])

        cant_elems = generate_cant_elements(elems, design_speed_kmh=120)
        assert len(cant_elems) == 5

        # First element (straight) - zero cant
        assert isinstance(cant_elems[0], CantSegment)
        assert cant_elems[0].cant == 0.0

        # Second (entry ramp)
        assert isinstance(cant_elems[1], CantRamp)
        assert cant_elems[1].cant_start == 0.0
        assert cant_elems[1].cant_end > 0.0

        # Third (constant cant on arc)
        assert isinstance(cant_elems[2], CantSegment)
        assert cant_elems[2].cant > 0.0

        # Fourth (exit ramp)
        assert isinstance(cant_elems[3], CantRamp)
        assert cant_elems[3].cant_start > 0.0
        assert cant_elems[3].cant_end == 0.0

        # Fifth (straight) - zero cant
        assert isinstance(cant_elems[4], CantSegment)
        assert cant_elems[4].cant == 0.0
