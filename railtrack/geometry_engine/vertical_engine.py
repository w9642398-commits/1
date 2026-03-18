"""Vertical geometry computation engine.

Handles:
- Building vertical alignment from grade/curve definitions
- Gradient continuity checks
- Elevation computation along chainage
"""
from __future__ import annotations

import math

from railtrack.domain.vertical import VerticalCurve, VerticalElementUnion, VerticalGrade


def propagate_vertical(
    elements: list[VerticalElementUnion],
) -> list[VerticalElementUnion]:
    """Rebuild vertical element chain ensuring elevation continuity.

    First element is fixed; subsequent elements inherit end elevation
    and gradient from the previous element.
    """
    if not elements:
        return []

    result: list[VerticalElementUnion] = [elements[0]]
    for i in range(1, len(elements)):
        prev = result[-1]
        elem = elements[i]
        new_start_ch = prev.end_chainage
        new_start_elev = prev.elevation_at(prev.end_chainage)

        if isinstance(elem, VerticalGrade):
            result.append(VerticalGrade(
                start_chainage=new_start_ch,
                length=elem.length,
                start_elevation=new_start_elev,
                gradient=elem.gradient,
            ))
        elif isinstance(elem, VerticalCurve):
            result.append(VerticalCurve(
                start_chainage=new_start_ch,
                length=elem.length,
                start_elevation=new_start_elev,
                gradient_in=prev.gradient_at(prev.end_chainage),
                gradient_out=elem.gradient_out,
            ))
    return result


def check_gradient_continuity(
    elements: list[VerticalElementUnion],
    tolerance: float = 1e-6,
) -> list[tuple[int, float]]:
    """Check gradient continuity between consecutive elements.

    Returns list of (index, gradient_gap) for breaks.
    Vertical curves should normally handle gradient transitions,
    but this checks for any remaining discontinuities.
    """
    issues = []
    for i in range(len(elements) - 1):
        g_out = elements[i].gradient_at(elements[i].end_chainage)
        g_in = elements[i + 1].gradient_at(elements[i + 1].start_chainage)
        gap = abs(g_out - g_in)
        if gap > tolerance:
            issues.append((i, gap))
    return issues


def compute_elevation_profile(
    elements: list[VerticalElementUnion],
    interval: float = 10.0,
) -> list[tuple[float, float]]:
    """Compute elevation at regular intervals."""
    points = []
    if not elements:
        return points

    ch_start = elements[0].start_chainage
    ch_end = elements[-1].end_chainage
    ch = ch_start

    while ch <= ch_end + 1e-9:
        for elem in elements:
            if elem.chainage_range.contains(ch):
                points.append((ch, elem.elevation_at(ch)))
                break
        ch += interval

    if points and abs(points[-1][0] - ch_end) > 1e-6:
        for elem in elements:
            if elem.chainage_range.contains(ch_end):
                points.append((ch_end, elem.elevation_at(ch_end)))
                break

    return points
