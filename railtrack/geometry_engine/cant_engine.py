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


def applied_cant_ratio_for_speed(speed_kmh: float) -> float:
    """Speed-dependent applied cant ratio.

    Lower speeds allow higher ratio (closer to equilibrium),
    higher speeds require lower ratio for passenger comfort.
    """
    if speed_kmh <= 80:
        return 0.75
    elif speed_kmh <= 120:
        return 0.70
    elif speed_kmh <= 160:
        return 0.67
    elif speed_kmh <= 200:
        return 0.60
    else:
        return 0.55


def compute_cant_deficiency_at(
    speed_kmh: float,
    radius: float,
    applied_cant: float,
    gauge: float = 1.435,
) -> float:
    """Calculate cant deficiency at a specific point.

    Returns: cant deficiency in metres (positive = under-canted).
    """
    if math.isinf(radius) or radius <= 0:
        return 0.0
    eq = equilibrium_cant(speed_kmh, radius, gauge)
    return cant_deficiency(applied_cant, eq)


def generate_cant_elements(
    horizontal_elements: list[HorizontalElementUnion],
    design_speed_kmh: float,
    applied_cant_ratio: float | None = None,
    gauge: float = 1.435,
    max_cant: float = 0.160,
) -> list[CantElementUnion]:
    """Generate cant elements from horizontal alignment.

    For each element:
    - Straight → zero cant
    - Circular arc → constant cant (fraction of equilibrium cant)
    - Transition curve → cant ramp from entry to exit cant

    If applied_cant_ratio is None, a speed-dependent ratio is used.
    Applied cant is clamped to max_cant.
    """
    if applied_cant_ratio is None:
        applied_cant_ratio = applied_cant_ratio_for_speed(design_speed_kmh)

    cant_elements: list[CantElementUnion] = []

    def _applied_cant(radius: float) -> float:
        if math.isinf(radius) or radius <= 0:
            return 0.0
        eq = equilibrium_cant(design_speed_kmh, radius, gauge)
        return min(eq * applied_cant_ratio, max_cant)

    for elem in horizontal_elements:
        if isinstance(elem, Straight):
            cant_elements.append(CantSegment(
                start_chainage=elem.start_chainage,
                length=elem.length,
                cant=0.0,
                gauge=gauge,
            ))
        elif isinstance(elem, CircularArc):
            cant_elements.append(CantSegment(
                start_chainage=elem.start_chainage,
                length=elem.length,
                cant=_applied_cant(elem.radius),
                gauge=gauge,
            ))
        elif isinstance(elem, TransitionCurve):
            cant_elements.append(CantRamp(
                start_chainage=elem.start_chainage,
                length=elem.length,
                cant_start=_applied_cant(elem.radius_start),
                cant_end=_applied_cant(elem.radius_end),
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
