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
from railtrack.domain.turnout import Turnout
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
        issues.extend(self._check_clothoid_parameters(alignment, cat))
        issues.extend(self._check_vertical_chainage(alignment))
        issues.extend(self._check_cant_chainage(alignment))
        issues.extend(self._check_range_consistency(alignment))
        issues.extend(self._check_cant_geometry_linkage(alignment))
        issues.extend(self._check_turnout_context(alignment))
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

    def _check_clothoid_parameters(self, alignment: Alignment, cat) -> list[ValidationIssue]:
        """Check clothoid (transition) minimum parameters: A_min and L_min."""
        issues = []
        if cat is None:
            return issues
        for i, elem in enumerate(alignment.horizontal_elements):
            if isinstance(elem, TransitionCurve):
                # Get the finite radius (the tighter end)
                r_finite = elem.radius_end if math.isinf(elem.radius_start) else elem.radius_start
                if math.isinf(r_finite):
                    continue
                # A_min = 0.021 * V^3 / R (simplified ST-T1-A6 formula for comfort)
                # Minimum clothoid parameter
                v = cat.max_speed
                a_actual = elem.clothoid_parameter_A
                a_min = max(0.021 * v, math.sqrt(r_finite * cat.min_transition_length))
                if a_actual < a_min * 0.95:  # 5% tolerance
                    issues.append(ValidationIssue(
                        severity=Severity.WARNING,
                        code="H-CLOTH-PARAM",
                        title="Clothoid parameter A too small",
                        message=f"Transition {i}: A={a_actual:.1f} < A_min={a_min:.1f}",
                        affected_object=alignment.name,
                        chainage=elem.start_chainage,
                        chainage_end=elem.end_chainage,
                        expected_value=f">= {a_min:.1f}",
                        actual_value=f"{a_actual:.1f}",
                        rule_reference="ST-T1-A6 clothoid parameter",
                        suggestion=f"Increase transition length or adjust radius",
                    ))
        return issues

    def _check_vertical_chainage(self, alignment: Alignment) -> list[ValidationIssue]:
        """Check vertical element chainage continuity."""
        issues = []
        velems = alignment.vertical_elements
        for i in range(len(velems) - 1):
            gap = velems[i + 1].start_chainage - velems[i].end_chainage
            if abs(gap) > 1e-6:
                issues.append(ValidationIssue(
                    severity=Severity.ERROR,
                    code="V-CH-GAP",
                    title="Vertical chainage discontinuity",
                    message=f"Gap of {gap:.4f} m between vertical elements {i} and {i+1}",
                    affected_object=alignment.name,
                    chainage=velems[i].end_chainage,
                    actual_value=f"{gap:.4f} m",
                    suggestion="Recalculate vertical geometry or fix element lengths",
                ))
        return issues

    def _check_cant_chainage(self, alignment: Alignment) -> list[ValidationIssue]:
        """Check cant element chainage continuity."""
        issues = []
        celems = alignment.cant_elements
        for i in range(len(celems) - 1):
            gap = celems[i + 1].start_chainage - celems[i].end_chainage
            if abs(gap) > 1e-6:
                issues.append(ValidationIssue(
                    severity=Severity.ERROR,
                    code="C-CH-GAP",
                    title="Cant chainage discontinuity",
                    message=f"Gap of {gap:.4f} m between cant elements {i} and {i+1}",
                    affected_object=alignment.name,
                    chainage=celems[i].end_chainage,
                    actual_value=f"{gap:.4f} m",
                    suggestion="Regenerate cant elements",
                ))
        return issues

    def _check_range_consistency(self, alignment: Alignment) -> list[ValidationIssue]:
        """Check that horizontal, vertical, and cant cover consistent chainage ranges."""
        issues = []
        if not alignment.horizontal_elements:
            return issues

        h_start = alignment.horizontal_elements[0].start_chainage
        h_end = alignment.horizontal_elements[-1].end_chainage

        if alignment.vertical_elements:
            v_start = alignment.vertical_elements[0].start_chainage
            v_end = alignment.vertical_elements[-1].end_chainage
            if v_start > h_start + 1.0:
                issues.append(ValidationIssue(
                    severity=Severity.WARNING,
                    code="RANGE-V-SHORT",
                    title="Vertical profile starts after horizontal",
                    message=f"Vertical starts at km {v_start:.3f}, horizontal at km {h_start:.3f}",
                    affected_object=alignment.name,
                    chainage=h_start,
                    suggestion="Extend vertical profile to cover full horizontal range",
                ))
            if v_end < h_end - 1.0:
                issues.append(ValidationIssue(
                    severity=Severity.WARNING,
                    code="RANGE-V-SHORT",
                    title="Vertical profile ends before horizontal",
                    message=f"Vertical ends at km {v_end:.3f}, horizontal at km {h_end:.3f}",
                    affected_object=alignment.name,
                    chainage=h_end,
                    suggestion="Extend vertical profile to cover full horizontal range",
                ))

        if alignment.cant_elements:
            c_start = alignment.cant_elements[0].start_chainage
            c_end = alignment.cant_elements[-1].end_chainage
            if c_start > h_start + 1.0:
                issues.append(ValidationIssue(
                    severity=Severity.WARNING,
                    code="RANGE-C-SHORT",
                    title="Cant profile starts after horizontal",
                    message=f"Cant starts at km {c_start:.3f}, horizontal at km {h_start:.3f}",
                    affected_object=alignment.name,
                    chainage=h_start,
                    suggestion="Regenerate cant elements",
                ))
            if c_end < h_end - 1.0:
                issues.append(ValidationIssue(
                    severity=Severity.WARNING,
                    code="RANGE-C-SHORT",
                    title="Cant profile ends before horizontal",
                    message=f"Cant ends at km {c_end:.3f}, horizontal at km {h_end:.3f}",
                    affected_object=alignment.name,
                    chainage=h_end,
                    suggestion="Regenerate cant elements",
                ))

        return issues

    def _check_cant_geometry_linkage(self, alignment: Alignment) -> list[ValidationIssue]:
        """Check that cant ramps align with transition curves and cant segments with arcs."""
        issues = []
        if not alignment.cant_elements or not alignment.horizontal_elements:
            return issues

        for c_elem in alignment.cant_elements:
            ch_mid = c_elem.start_chainage + (c_elem.end_chainage - c_elem.start_chainage) / 2.0
            # Find corresponding horizontal element
            h_elem = None
            for he in alignment.horizontal_elements:
                if he.chainage_range.contains(ch_mid):
                    h_elem = he
                    break
            if h_elem is None:
                continue

            if isinstance(c_elem, CantRamp) and isinstance(h_elem, Straight):
                # Cant ramp on a straight is suspicious (unless near transition)
                if abs(c_elem.cant_start) > 0.001 or abs(c_elem.cant_end) > 0.001:
                    issues.append(ValidationIssue(
                        severity=Severity.WARNING,
                        code="C-ALIGN-RAMP",
                        title="Cant ramp on straight section",
                        message=f"Non-zero cant ramp ({c_elem.cant_start*1000:.0f} → {c_elem.cant_end*1000:.0f} mm) on straight",
                        affected_object=alignment.name,
                        chainage=c_elem.start_chainage,
                        chainage_end=c_elem.end_chainage,
                        suggestion="Verify cant alignment matches horizontal geometry",
                    ))

            if isinstance(c_elem, CantSegment) and c_elem.cant > 0.001:
                if isinstance(h_elem, Straight):
                    issues.append(ValidationIssue(
                        severity=Severity.ERROR,
                        code="C-ALIGN-CANT",
                        title="Non-zero cant on straight section",
                        message=f"Cant {c_elem.cant*1000:.0f} mm applied on straight section",
                        affected_object=alignment.name,
                        chainage=c_elem.start_chainage,
                        chainage_end=c_elem.end_chainage,
                        suggestion="Cant should be zero on straight sections",
                    ))

        return issues

    def _check_turnout_context(self, alignment: Alignment) -> list[ValidationIssue]:
        """Check turnout placement rules."""
        issues = []
        if not alignment.turnouts:
            return issues

        tr = self.rules.turnout_rules
        for turnout in alignment.turnouts:
            # Check tangent before turnout
            min_before = tr.min_tangent_before_turnout
            min_after = tr.min_tangent_after_turnout

            for he in alignment.horizontal_elements:
                if he.chainage_range.contains(turnout.chainage):
                    if not isinstance(he, Straight):
                        issues.append(ValidationIssue(
                            severity=Severity.ERROR,
                            code="T-NOT-STRAIGHT",
                            title="Turnout not on straight section",
                            message=f"Turnout '{turnout.name}' at km {turnout.chainage:.3f} is not on a straight",
                            affected_object=alignment.name,
                            chainage=turnout.chainage,
                            suggestion="Move turnout to a straight section",
                        ))
                    elif isinstance(he, Straight):
                        dist_from_start = turnout.chainage - he.start_chainage
                        dist_to_end = he.end_chainage - turnout.end_chainage
                        if dist_from_start < min_before:
                            issues.append(ValidationIssue(
                                severity=Severity.WARNING,
                                code="T-TANG-BEFORE",
                                title="Insufficient tangent before turnout",
                                message=f"Only {dist_from_start:.1f} m tangent before turnout '{turnout.name}' (min {min_before:.1f} m)",
                                affected_object=alignment.name,
                                chainage=turnout.chainage,
                                expected_value=f">= {min_before:.1f} m",
                                actual_value=f"{dist_from_start:.1f} m",
                                rule_reference="ST-T1-A6 turnout rules",
                            ))
                        if dist_to_end < min_after:
                            issues.append(ValidationIssue(
                                severity=Severity.WARNING,
                                code="T-TANG-AFTER",
                                title="Insufficient tangent after turnout",
                                message=f"Only {dist_to_end:.1f} m tangent after turnout '{turnout.name}' (min {min_after:.1f} m)",
                                affected_object=alignment.name,
                                chainage=turnout.end_chainage,
                                expected_value=f">= {min_after:.1f} m",
                                actual_value=f"{dist_to_end:.1f} m",
                                rule_reference="ST-T1-A6 turnout rules",
                            ))
                    break

        return issues
