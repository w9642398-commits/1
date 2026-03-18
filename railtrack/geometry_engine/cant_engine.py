"""Cant computation engine.

Handles:
- Cant calculation based on speed and radius
- Cant ramp generation aligned with transition curves
- Cant profile computation
"""
from __future__ import annotations

import math

from railtrack.domain.cant import (
    CantElementUnion,
    CantRamp,
    CantSegment,
    cant_deficiency,
    equilibrium_cant,
)
from railtrack.domain.horizontal import (
    CircularArc,
    CurveDirection,
    HorizontalElementUnion,
    Straight,
    TransitionCurve,
)


def generate_cant_elements(
    horizontal_elements: list[HorizontalElementUnion],
    design_speed_kmh: float,
    applied_cant_ratio: float = 0.67,
    gauge: float = 1.435,
) -> list[CantElementUnion]:
    """Generate cant elements from horizontal alignment.

    For each element:
    - Straight → zero cant
    - Circular arc → constant cant (fraction of equilibrium cant)
    - Transition curve → cant ramp from entry to exit cant

    applied_cant_ratio: fraction of equilibrium cant to apply (typically 2/3).
    """
    cant_elements: list[CantElementUnion] = []

    for elem in horizontal_elements:
        if isinstance(elem, Straight):
            cant_elements.append(CantSegment(
                start_chainage=elem.start_chainage,
                length=elem.length,
                cant=0.0,
                gauge=gauge,
            ))
        elif isinstance(elem, CircularArc):
            eq_cant = equilibrium_cant(design_speed_kmh, elem.radius, gauge)
            applied = eq_cant * applied_cant_ratio
            cant_elements.append(CantSegment(
                start_chainage=elem.start_chainage,
                length=elem.length,
                cant=applied,
                gauge=gauge,
            ))
        elif isinstance(elem, TransitionCurve):
            r_start = elem.radius_start
            r_end = elem.radius_end

            if math.isinf(r_start):
                cant_start = 0.0
            else:
                cant_start = equilibrium_cant(design_speed_kmh, r_start, gauge) * applied_cant_ratio

            if math.isinf(r_end):
                cant_end = 0.0
            else:
                cant_end = equilibrium_cant(design_speed_kmh, r_end, gauge) * applied_cant_ratio

            cant_elements.append(CantRamp(
                start_chainage=elem.start_chainage,
                length=elem.length,
                cant_start=cant_start,
                cant_end=cant_end,
                gauge=gauge,
            ))

    return cant_elements


def compute_cant_profile(
    cant_elements: list[CantElementUnion],
    interval: float = 10.0,
) -> list[tuple[float, float]]:
    """Compute cant at regular intervals."""
    points = []
    if not cant_elements:
        return points

    ch_start = cant_elements[0].start_chainage
    ch_end = cant_elements[-1].end_chainage
    ch = ch_start

    while ch <= ch_end + 1e-9:
        for elem in cant_elements:
            if elem.chainage_range.contains(ch):
                points.append((ch, elem.cant_at(ch)))
                break
        ch += interval

    if points and abs(points[-1][0] - ch_end) > 1e-6:
        for elem in cant_elements:
            if elem.chainage_range.contains(ch_end):
                points.append((ch_end, elem.cant_at(ch_end)))
                break

    return points
