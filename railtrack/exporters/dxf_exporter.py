"""DXF exporter for alignment axis geometry."""
from __future__ import annotations

import math
from pathlib import Path

import ezdxf
from ezdxf.math import Vec3

from railtrack.domain.alignment import Alignment
from railtrack.domain.horizontal import CircularArc, Straight, TransitionCurve
from railtrack.geometry_engine.horizontal_engine import compute_points_along


def export_alignment_dxf(
    alignment: Alignment,
    path: Path | str,
    point_interval: float = 5.0,
    layer_axis: str = "TRACK_AXIS",
    layer_points: str = "TRACK_POINTS",
    layer_chainage: str = "TRACK_CHAINAGE",
    chainage_label_interval: float = 100.0,
) -> None:
    """Export alignment to DXF with true geometric representation.

    - Straights as LINE entities
    - Circular arcs as ARC entities
    - Transition curves as fine polylines (clothoids have no DXF primitive)
    - Chainage labels at intervals
    """
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    doc.layers.add(layer_axis, color=1)      # red
    doc.layers.add(layer_points, color=3)    # green
    doc.layers.add(layer_chainage, color=5)  # blue

    for elem in alignment.horizontal_elements:
        if isinstance(elem, Straight):
            sp = elem.start_point
            ep = elem.end_point
            msp.add_line(
                (sp.x, sp.y), (ep.x, ep.y),
                dxfattribs={"layer": layer_axis},
            )

        elif isinstance(elem, CircularArc):
            c = elem.center
            r = elem.radius
            # Compute start/end angles in DXF convention (CCW from +X axis)
            start_angle_rad = math.atan2(
                elem.start_point.y - c.y,
                elem.start_point.x - c.x,
            )
            end_angle_rad = math.atan2(
                elem.end_point.y - c.y,
                elem.end_point.x - c.x,
            )
            start_deg = math.degrees(start_angle_rad)
            end_deg = math.degrees(end_angle_rad)

            if elem.direction == elem.direction.RIGHT:
                # CW in survey = CW in math, but DXF arcs are CCW
                # Swap start/end for DXF
                start_deg, end_deg = end_deg, start_deg

            msp.add_arc(
                center=(c.x, c.y),
                radius=r,
                start_angle=start_deg,
                end_angle=end_deg,
                dxfattribs={"layer": layer_axis},
            )

        elif isinstance(elem, TransitionCurve):
            # Clothoids → polyline approximation (no DXF primitive exists)
            n_pts = max(20, int(elem.length / 2.0))
            pts = []
            for j in range(n_pts + 1):
                ch = elem.start_chainage + elem.length * j / n_pts
                p = elem.point_at(ch)
                pts.append((p.x, p.y))
            msp.add_lwpolyline(
                pts,
                dxfattribs={"layer": layer_axis},
            )

    # Chainage labels
    ch = alignment.start_chainage
    while ch <= alignment.end_chainage + 1e-6:
        pt = alignment.point_at(ch)
        az = alignment.azimuth_at(ch)
        if pt is not None and az is not None:
            # Short tick perpendicular to alignment
            perp = az + math.pi / 2
            tick_len = 3.0
            tx = pt.x + tick_len * math.sin(perp)
            ty = pt.y + tick_len * math.cos(perp)
            msp.add_line(
                (pt.x, pt.y), (tx, ty),
                dxfattribs={"layer": layer_chainage},
            )
            msp.add_text(
                f"{ch:.0f}",
                height=2.0,
                dxfattribs={
                    "layer": layer_chainage,
                    "insert": (tx + 1, ty + 1),
                },
            )
        ch += chainage_label_interval

    doc.saveas(path)
