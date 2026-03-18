"""Tests for validation engine."""
import math

import pytest

from railtrack.domain.alignment import Alignment, DesignCriteria
from railtrack.domain.cant import CantSegment
from railtrack.domain.horizontal import (
    CircularArc,
    CurveDirection,
    Straight,
    TransitionCurve,
)
from railtrack.domain.primitives import Point2D
from railtrack.domain.vertical import VerticalCurve, VerticalGrade
from railtrack.geometry_engine.horizontal_engine import propagate_geometry
from railtrack.validation.rule_loader import load_rules
from railtrack.validation.validator import AlignmentValidator


@pytest.fixture
def validator():
    return AlignmentValidator()


@pytest.fixture
def criteria_120():
    return DesignCriteria(max_speed_kmh=120)


class TestTangencyValidation:
    def test_tangent_alignment_no_errors(self, validator, criteria_120):
        al = Alignment(name="test")
        al.horizontal_elements = propagate_geometry([
            Straight(0, 100, Point2D(0, 0), 0.0),
            Straight(0, 100, Point2D(0, 0), 0.0),
        ])
        issues = validator.validate(al, criteria_120)
        tangency_issues = [i for i in issues if i.code.startswith("H-TANG")]
        assert len(tangency_issues) == 0

    def test_broken_tangency_detected(self, validator, criteria_120):
        """Two straights with different azimuths should trigger tangency error."""
        al = Alignment(name="test")
        al.horizontal_elements = [
            Straight(0, 100, Point2D(0, 0), 0.0),
            Straight(100, 100, Point2D(0, 100), 0.5),  # wrong azimuth
        ]
        issues = validator.validate(al, criteria_120)
        az_issues = [i for i in issues if i.code == "H-TANG-AZ"]
        assert len(az_issues) > 0


class TestRadiusValidation:
    def test_radius_below_min(self, validator):
        """R=200 at V=120 should trigger error (min=500 for this speed)."""
        criteria = DesignCriteria(max_speed_kmh=120)
        al = Alignment(name="test")
        al.horizontal_elements = [
            CircularArc(0, 100, Point2D(0, 0), 0.0, 200.0, CurveDirection.RIGHT)
        ]
        issues = validator.validate(al, criteria)
        rad_issues = [i for i in issues if i.code == "H-RAD-MIN"]
        assert len(rad_issues) > 0

    def test_radius_above_min_ok(self, validator):
        criteria = DesignCriteria(max_speed_kmh=80)
        al = Alignment(name="test")
        al.horizontal_elements = [
            CircularArc(0, 100, Point2D(0, 0), 0.0, 500.0, CurveDirection.RIGHT)
        ]
        issues = validator.validate(al, criteria)
        rad_issues = [i for i in issues if i.code == "H-RAD-MIN"]
        assert len(rad_issues) == 0


class TestTransitionValidation:
    def test_short_transition(self, validator):
        criteria = DesignCriteria(max_speed_kmh=120)
        al = Alignment(name="test")
        al.horizontal_elements = [
            TransitionCurve(0, 10, Point2D(0, 0), 0.0,
                            math.inf, 500, CurveDirection.RIGHT)
        ]
        issues = validator.validate(al, criteria)
        trans_issues = [i for i in issues if i.code == "H-TRANS-SHORT"]
        assert len(trans_issues) > 0


class TestSequenceValidation:
    def test_reverse_curves_no_transition(self, validator, criteria_120):
        """Two arcs in opposite directions without transition."""
        al = Alignment(name="test")
        al.horizontal_elements = [
            CircularArc(0, 100, Point2D(0, 0), 0.0, 500, CurveDirection.RIGHT),
            CircularArc(100, 100, Point2D(50, 50), 0.5, 500, CurveDirection.LEFT),
        ]
        issues = validator.validate(al, criteria_120)
        seq_issues = [i for i in issues if i.code == "H-SEQ-REVERSE"]
        assert len(seq_issues) > 0


class TestVerticalValidation:
    def test_gradient_exceeds_max(self, validator):
        criteria = DesignCriteria(max_speed_kmh=120)
        al = Alignment(name="test")
        al.horizontal_elements = [Straight(0, 1000, Point2D(0, 0), 0.0)]
        al.vertical_elements = [VerticalGrade(0, 1000, 100, 0.030)]  # 30‰ > 12‰
        issues = validator.validate(al, criteria)
        grad_issues = [i for i in issues if i.code == "V-GRAD-MAX"]
        assert len(grad_issues) > 0


class TestCantValidation:
    def test_cant_exceeds_max(self, validator):
        criteria = DesignCriteria(max_speed_kmh=120)
        al = Alignment(name="test")
        al.horizontal_elements = [Straight(0, 100, Point2D(0, 0), 0.0)]
        al.cant_elements = [CantSegment(0, 100, 0.200)]  # 200mm > 160mm
        issues = validator.validate(al, criteria)
        cant_issues = [i for i in issues if i.code == "C-CANT-MAX"]
        assert len(cant_issues) > 0


class TestInputValidation:
    def test_negative_length(self, validator, criteria_120):
        al = Alignment(name="test")
        al.horizontal_elements = [Straight(0, -10, Point2D(0, 0), 0.0)]
        issues = validator.validate(al, criteria_120)
        input_issues = [i for i in issues if i.code == "H-INPUT-LEN"]
        assert len(input_issues) > 0


class TestRuleLoader:
    def test_load_default_rules(self):
        rules = load_rules()
        assert len(rules.speed_categories) > 0
        assert rules.global_rules.max_cant == 0.160

    def test_speed_category_lookup(self):
        rules = load_rules()
        cat = rules.rules_for_speed(120)
        assert cat is not None
        assert cat.max_speed >= 120
