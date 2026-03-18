"""Alignment validator - checks geometry against design rules.

Detects:
- Tangency breaks
- Radius below minimum
- Transition curve too short
- Tangent insertion too short
- Speed/radius conflict
- Cant/geometry conflict
- Chainage discontinuity
- Invalid element sequence
- Vertical geometry issues
- Inconsistency between plan, profile, and cant
"""
from __future__ import annotations

import math

from railtrack.domain.alignment import Alignment, DesignCriteria
from railtrack.domain.cant import CantRamp, CantSegment, cant_deficiency, equilibrium_cant
from railtrack.domain.horizontal import (
    CircularArc,
    HorizontalElementUnion,
    Straight,
    TransitionCurve,
)
from railtrack.domain.validation_types import Severity, ValidationIssue
from railtrack.domain.vertical import VerticalCurve, VerticalGrade
from railtrack.geometry_engine.horizontal_engine import (
    AZIMUTH_TOLERANCE,
    TANGENCY_TOLERANCE,
    check_chainage_continuity,
    check_tangency,
)
from railtrack.validation.rule_loader import RuleSet, load_rules


class AlignmentValidator:
    """Validates an alignment against a rule set."""

    def __init__(self, rules: RuleSet | None = None):
        self.rules = rules or load_rules()

    def validate(
        self,
        alignment: Alignment,
        criteria: DesignCriteria | None = None,
    ) -> list[ValidationIssue]:
        """Run all validation checks and return issues."""
        issues: list[ValidationIssue] = []
        speed = criteria.max_speed_kmh if criteria else 120.0
        cat = self.rules.rules_for_speed(speed)

        issues.extend(self._check_tangency(alignment))
        issues.extend(self._check_chainage(alignment))
        issues.extend(self._check_element_sequence(alignment))
        if cat:
            issues.extend(self._check_radius_limits(alignment, cat))
            issues.extend(self._check_transition_lengths(alignment, cat))
            issues.extend(self._check_tangent_lengths(alignment, cat))
            issues.extend(self._check_speed_radius_compatibility(alignment, speed, cat))
            issues.extend(self._check_cant_geometry(alignment, speed, cat))
            issues.extend(self._check_vertical_geometry(alignment, cat))
        issues.extend(self._check_input_validity(alignment))
        return issues

    def _check_tangency(self, alignment: Alignment) -> list[ValidationIssue]:
        issues = []
        errors = check_tangency(alignment.horizontal_elements)
        for err in errors:
            e1 = alignment.horizontal_elements[err.index]
            e2 = alignment.horizontal_elements[err.index + 1]
            if err.is_position_break:
                issues.append(ValidationIssue(
                    severity=Severity.ERROR,
                    code="H-TANG-POS",
                    title="Position break in horizontal alignment",
                    message=f"Position gap of {err.position_gap:.4f} m between elements {err.index} and {err.index+1}",
                    affected_object=alignment.name,
                    chainage=e1.end_chainage,
                    expected_value=f"< {TANGENCY_TOLERANCE} m",
                    actual_value=f"{err.position_gap:.4f} m",
                    suggestion="Propagate geometry to fix position continuity",
                ))
            if err.is_azimuth_break:
                issues.append(ValidationIssue(
                    severity=Severity.ERROR,
                    code="H-TANG-AZ",
                    title="Azimuth break in horizontal alignment",
                    message=f"Azimuth gap of {math.degrees(err.azimuth_gap):.6f}° between elements {err.index} and {err.index+1}",
                    affected_object=alignment.name,
                    chainage=e1.end_chainage,
                    expected_value=f"< {math.degrees(AZIMUTH_TOLERANCE):.6f}°",
                    actual_value=f"{math.degrees(err.azimuth_gap):.6f}°",
                    suggestion="Check element parameters or propagate geometry",
                ))
        return issues

    def _check_chainage(self, alignment: Alignment) -> list[ValidationIssue]:
        issues = []
        ch_issues = check_chainage_continuity(alignment.horizontal_elements)
        for idx, gap in ch_issues:
            issues.append(ValidationIssue(
                severity=Severity.ERROR,
                code="H-CH-GAP",
                title="Chainage discontinuity",
                message=f"Chainage gap of {gap:.4f} m between elements {idx} and {idx+1}",
                affected_object=alignment.name,
                chainage=alignment.horizontal_elements[idx].end_chainage,
                actual_value=f"{gap:.4f} m",
                suggestion="Recalculate chainage or fix element lengths",
            ))
        return issues

    def _check_element_sequence(self, alignment: Alignment) -> list[ValidationIssue]:
        """Check for invalid element sequences (e.g. two arcs without transition)."""
        issues = []
        elems = alignment.horizontal_elements
        for i in range(len(elems) - 1):
            e1, e2 = elems[i], elems[i + 1]
            # Two circular arcs directly adjacent (no transition)
            if isinstance(e1, CircularArc) and isinstance(e2, CircularArc):
                if e1.direction != e2.direction:
                    issues.append(ValidationIssue(
                        severity=Severity.ERROR,
                        code="H-SEQ-REVERSE",
                        title="Reverse curves without transition",
                        message=f"Reverse circular arcs at element {i}/{i+1} without transition curve",
                        affected_object=alignment.name,
                        chainage=e1.end_chainage,
                        suggestion="Insert transition curves between reverse curves",
                    ))
                elif e1.radius != e2.radius:
                    issues.append(ValidationIssue(
                        severity=Severity.WARNING,
                        code="H-SEQ-COMPOUND",
                        title="Compound curves without transition",
                        message=f"Adjacent arcs with different radii ({e1.radius:.1f} / {e2.radius:.1f}) without transition",
                        affected_object=alignment.name,
                        chainage=e1.end_chainage,
                        suggestion="Consider inserting a transition curve",
                    ))
        return issues

    def _check_radius_limits(self, alignment, cat) -> list[ValidationIssue]:
        issues = []
        for i, elem in enumerate(alignment.horizontal_elements):
            if isinstance(elem, CircularArc):
                if elem.radius < cat.min_radius:
                    issues.append(ValidationIssue(
                        severity=Severity.ERROR,
                        code="H-RAD-MIN",
                        title="Radius below minimum",
                        message=f"Arc {i} radius {elem.radius:.1f} m < minimum {cat.min_radius:.1f} m for V={cat.max_speed} km/h",
                        affected_object=alignment.name,
                        chainage=elem.start_chainage,
                        chainage_end=elem.end_chainage,
                        expected_value=f">= {cat.min_radius:.1f} m",
                        actual_value=f"{elem.radius:.1f} m",
                        rule_reference=f"ST-T1-A6 speed category {cat.name}",
                    ))
        return issues

    def _check_transition_lengths(self, alignment, cat) -> list[ValidationIssue]:
        issues = []
        for i, elem in enumerate(alignment.horizontal_elements):
            if isinstance(elem, TransitionCurve):
                if elem.length < cat.min_transition_length:
                    issues.append(ValidationIssue(
                        severity=Severity.ERROR,
                        code="H-TRANS-SHORT",
                        title="Transition curve too short",
                        message=f"Transition {i} length {elem.length:.1f} m < minimum {cat.min_transition_length:.1f} m",
                        affected_object=alignment.name,
                        chainage=elem.start_chainage,
                        chainage_end=elem.end_chainage,
                        expected_value=f">= {cat.min_transition_length:.1f} m",
                        actual_value=f"{elem.length:.1f} m",
                        rule_reference=f"ST-T1-A6 speed category {cat.name}",
                    ))
        return issues

    def _check_tangent_lengths(self, alignment, cat) -> list[ValidationIssue]:
        """Check minimum straight (tangent) lengths between curves."""
        issues = []
        elems = alignment.horizontal_elements
        for i, elem in enumerate(elems):
            if isinstance(elem, Straight):
                # Only check straights between curves
                has_curve_before = i > 0 and not isinstance(elems[i - 1], Straight)
                has_curve_after = i < len(elems) - 1 and not isinstance(elems[i + 1], Straight)
                if has_curve_before and has_curve_after:
                    if elem.length < cat.min_tangent_between_curves:
                        issues.append(ValidationIssue(
                            severity=Severity.WARNING,
                            code="H-TANG-SHORT",
                            title="Short tangent between curves",
                            message=f"Tangent {i} length {elem.length:.1f} m < recommended {cat.min_tangent_between_curves:.1f} m",
                            affected_object=alignment.name,
                            chainage=elem.start_chainage,
                            chainage_end=elem.end_chainage,
                            expected_value=f">= {cat.min_tangent_between_curves:.1f} m",
                            actual_value=f"{elem.length:.1f} m",
                            rule_reference=f"ST-T1-A6 speed category {cat.name}",
                        ))
        return issues

    def _check_speed_radius_compatibility(self, alignment, speed, cat) -> list[ValidationIssue]:
        """Check speed / radius / cant deficiency compatibility."""
        issues = []
        gauge = self.rules.global_rules.track_gauge
        for i, elem in enumerate(alignment.horizontal_elements):
            if isinstance(elem, CircularArc):
                eq_cant = equilibrium_cant(speed, elem.radius, gauge)
                if eq_cant > cat.max_cant + cat.max_cant_deficiency:
                    issues.append(ValidationIssue(
                        severity=Severity.ERROR,
                        code="H-SPEED-RAD",
                        title="Speed/radius incompatibility",
                        message=f"At V={speed} km/h, R={elem.radius:.0f} m: equilibrium cant {eq_cant*1000:.0f} mm exceeds max cant + deficiency ({(cat.max_cant+cat.max_cant_deficiency)*1000:.0f} mm)",
                        affected_object=alignment.name,
                        chainage=elem.start_chainage,
                        chainage_end=elem.end_chainage,
                        expected_value=f"<= {(cat.max_cant+cat.max_cant_deficiency)*1000:.0f} mm",
                        actual_value=f"{eq_cant*1000:.0f} mm",
                        rule_reference="ST-T1-A6 cant deficiency",
                    ))
        return issues

    def _check_cant_geometry(self, alignment, speed, cat) -> list[ValidationIssue]:
        """Check cant values against limits."""
        issues = []
        for i, elem in enumerate(alignment.cant_elements):
            if isinstance(elem, CantSegment):
                if elem.cant > cat.max_cant:
                    issues.append(ValidationIssue(
                        severity=Severity.ERROR,
                        code="C-CANT-MAX",
                        title="Cant exceeds maximum",
                        message=f"Cant {elem.cant*1000:.0f} mm > maximum {cat.max_cant*1000:.0f} mm",
                        affected_object=alignment.name,
                        chainage=elem.start_chainage,
                        chainage_end=elem.end_chainage,
                        expected_value=f"<= {cat.max_cant*1000:.0f} mm",
                        actual_value=f"{elem.cant*1000:.0f} mm",
                        rule_reference="ST-T1-A6 maximum cant",
                    ))
            elif isinstance(elem, CantRamp):
                # Check cant ramp gradient
                if elem.length > 0:
                    cant_change = abs(elem.cant_end - elem.cant_start)
                    if cant_change > 0:
                        ramp_ratio = elem.length / cant_change
                        min_ratio = self.rules.global_rules.min_cant_ramp_ratio_normal
                        if ramp_ratio < min_ratio:
                            issues.append(ValidationIssue(
                                severity=Severity.WARNING,
                                code="C-RAMP-STEEP",
                                title="Cant ramp too steep",
                                message=f"Cant ramp ratio 1:{ramp_ratio:.0f} < minimum 1:{min_ratio:.0f}",
                                affected_object=alignment.name,
                                chainage=elem.start_chainage,
                                chainage_end=elem.end_chainage,
                                expected_value=f">= 1:{min_ratio:.0f}",
                                actual_value=f"1:{ramp_ratio:.0f}",
                                rule_reference="ST-T1-A6 cant ramp gradient",
                            ))
        return issues

    def _check_vertical_geometry(self, alignment, cat) -> list[ValidationIssue]:
        issues = []
        for i, elem in enumerate(alignment.vertical_elements):
            if isinstance(elem, VerticalGrade):
                if abs(elem.gradient) > cat.max_gradient:
                    issues.append(ValidationIssue(
                        severity=Severity.ERROR,
                        code="V-GRAD-MAX",
                        title="Gradient exceeds maximum",
                        message=f"Gradient {elem.gradient*1000:.1f}‰ exceeds maximum {cat.max_gradient*1000:.1f}‰",
                        affected_object=alignment.name,
                        chainage=elem.start_chainage,
                        chainage_end=elem.end_chainage,
                        expected_value=f"<= {cat.max_gradient*1000:.1f}‰",
                        actual_value=f"{elem.gradient*1000:.1f}‰",
                        rule_reference=f"ST-T1-A6 speed category {cat.name}",
                    ))
            elif isinstance(elem, VerticalCurve):
                if elem.radius < cat.min_vertical_curve_radius:
                    issues.append(ValidationIssue(
                        severity=Severity.ERROR,
                        code="V-RAD-MIN",
                        title="Vertical curve radius too small",
                        message=f"Vertical curve radius {elem.radius:.0f} m < minimum {cat.min_vertical_curve_radius:.0f} m",
                        affected_object=alignment.name,
                        chainage=elem.start_chainage,
                        chainage_end=elem.end_chainage,
                        expected_value=f">= {cat.min_vertical_curve_radius:.0f} m",
                        actual_value=f"{elem.radius:.0f} m",
                        rule_reference=f"ST-T1-A6 speed category {cat.name}",
                    ))
        return issues

    def _check_input_validity(self, alignment: Alignment) -> list[ValidationIssue]:
        """Check for basic input validity (negative lengths, zero radius, etc.)."""
        issues = []
        for i, elem in enumerate(alignment.horizontal_elements):
            if elem.length <= 0:
                issues.append(ValidationIssue(
                    severity=Severity.ERROR,
                    code="H-INPUT-LEN",
                    title="Non-positive element length",
                    message=f"Element {i} has length {elem.length:.4f} <= 0",
                    affected_object=alignment.name,
                    chainage=elem.start_chainage,
                ))
            if isinstance(elem, CircularArc) and elem.radius <= 0:
                issues.append(ValidationIssue(
                    severity=Severity.ERROR,
                    code="H-INPUT-RAD",
                    title="Non-positive radius",
                    message=f"Arc {i} has radius {elem.radius:.4f} <= 0",
                    affected_object=alignment.name,
                    chainage=elem.start_chainage,
                ))
        return issues
