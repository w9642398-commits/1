"""LandXML 1.2 exporter for alignments.

Produces valid LandXML with explicit geometric elements:
- Line for straights
- Curve for circular arcs
- Spiral for transition curves
No polyline substitution for arcs.
"""
from __future__ import annotations

import math
from pathlib import Path
from xml.etree import ElementTree as ET

from railtrack.domain.alignment import Alignment
from railtrack.domain.horizontal import CircularArc, Straight, TransitionCurve
from railtrack.domain.vertical import VerticalCurve, VerticalGrade

_NS = "http://www.landxml.org/schema/LandXML-1.2"


def _pt_str(x: float, y: float) -> str:
    """Format point as 'northing easting' per LandXML convention."""
    return f"{y:.6f} {x:.6f}"


def export_landxml(
    alignments: list[Alignment],
    path: Path | str,
    project_name: str = "RailTrack Export",
) -> None:
    """Export alignments to LandXML 1.2."""
    ET.register_namespace("", _NS)

    root = ET.Element("LandXML", {
        "xmlns": _NS,
        "version": "1.2",
        "date": "",
        "time": "",
    })

    project = ET.SubElement(root, "Project", {"name": project_name})
    units = ET.SubElement(root, "Units")
    metric = ET.SubElement(units, "Metric", {
        "linearUnit": "meter",
        "areaUnit": "squareMeter",
        "volumeUnit": "cubicMeter",
        "angularUnit": "radians",
    })

    alignments_elem = ET.SubElement(root, "Alignments")

    for alignment in alignments:
        al_elem = ET.SubElement(alignments_elem, "Alignment", {
            "name": alignment.name,
            "length": f"{alignment.total_length:.4f}",
            "staStart": f"{alignment.start_chainage:.4f}",
        })

        # Horizontal geometry
        cg = ET.SubElement(al_elem, "CoordGeom")
        for elem in alignment.horizontal_elements:
            if isinstance(elem, Straight):
                line = ET.SubElement(cg, "Line", {
                    "length": f"{elem.length:.6f}",
                })
                start = ET.SubElement(line, "Start")
                start.text = _pt_str(elem.start_point.x, elem.start_point.y)
                end = ET.SubElement(line, "End")
                end.text = _pt_str(elem.end_point.x, elem.end_point.y)

            elif isinstance(elem, CircularArc):
                rot = "cw" if elem.direction.value == "right" else "ccw"
                curve = ET.SubElement(cg, "Curve", {
                    "rot": rot,
                    "radius": f"{elem.radius:.6f}",
                    "length": f"{elem.length:.6f}",
                })
                start = ET.SubElement(curve, "Start")
                start.text = _pt_str(elem.start_point.x, elem.start_point.y)
                center = ET.SubElement(curve, "Center")
                c = elem.center
                center.text = _pt_str(c.x, c.y)
                end = ET.SubElement(curve, "End")
                end.text = _pt_str(elem.end_point.x, elem.end_point.y)

            elif isinstance(elem, TransitionCurve):
                rot = "cw" if elem.direction.value == "right" else "ccw"
                r_start = "INF" if math.isinf(elem.radius_start) else f"{elem.radius_start:.6f}"
                r_end = "INF" if math.isinf(elem.radius_end) else f"{elem.radius_end:.6f}"
                spiral = ET.SubElement(cg, "Spiral", {
                    "length": f"{elem.length:.6f}",
                    "radiusStart": r_start,
                    "radiusEnd": r_end,
                    "rot": rot,
                    "spiType": "clothoid",
                })
                start = ET.SubElement(spiral, "Start")
                start.text = _pt_str(elem.start_point.x, elem.start_point.y)
                end_sub = ET.SubElement(spiral, "End")
                end_sub.text = _pt_str(elem.end_point.x, elem.end_point.y)

        # Vertical profile
        if alignment.vertical_elements:
            profile = ET.SubElement(al_elem, "Profile")
            prof_align = ET.SubElement(profile, "ProfAlign", {"name": f"{alignment.name}_profile"})
            for velem in alignment.vertical_elements:
                if isinstance(velem, VerticalGrade):
                    pvi = ET.SubElement(prof_align, "PVI")
                    pvi.text = f"{velem.start_chainage:.4f} {velem.start_elevation:.4f}"
            # Add final PVI
            if alignment.vertical_elements:
                last = alignment.vertical_elements[-1]
                pvi = ET.SubElement(prof_align, "PVI")
                pvi.text = f"{last.end_chainage:.4f} {last.elevation_at(last.end_chainage):.4f}"

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
