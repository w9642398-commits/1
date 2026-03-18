"""LandXML 1.2 importer for alignments."""
from __future__ import annotations

import math
from pathlib import Path
from xml.etree import ElementTree as ET

from railtrack.domain.alignment import Alignment
from railtrack.domain.horizontal import (
    CircularArc,
    CurveDirection,
    HorizontalElementUnion,
    Straight,
    TransitionCurve,
)
from railtrack.domain.primitives import Point2D
from railtrack.domain.vertical import VerticalCurve, VerticalElementUnion, VerticalGrade

_NS = {"lx": "http://www.landxml.org/schema/LandXML-1.2"}


def _find(elem: ET.Element, path: str) -> ET.Element | None:
    """Find with namespace."""
    return elem.find(path, _NS)


def _findall(elem: ET.Element, path: str) -> list[ET.Element]:
    return elem.findall(path, _NS)


def _parse_point(text: str) -> Point2D:
    """Parse LandXML space-separated coordinate string (northing easting)."""
    parts = text.strip().split()
    # LandXML: northing easting [elevation]
    return Point2D(float(parts[1]), float(parts[0]))


def import_landxml(path: Path | str) -> list[Alignment]:
    """Import alignments from a LandXML 1.2 file."""
    tree = ET.parse(path)
    root = tree.getroot()

    # Handle both namespaced and non-namespaced
    alignments_elem = _find(root, ".//lx:Alignments")
    if alignments_elem is None:
        alignments_elem = root.find(".//Alignments")
    if alignments_elem is None:
        return []

    result = []
    for al_elem in _findall(alignments_elem, "lx:Alignment") or alignments_elem.findall("Alignment"):
        name = al_elem.get("name", "Unnamed")
        alignment = Alignment(name=name)

        # Horizontal
        coord_geom = _find(al_elem, "lx:CoordGeom") or al_elem.find("CoordGeom")
        if coord_geom is not None:
            alignment.horizontal_elements = _parse_coord_geom(coord_geom)

        # Vertical
        profile = _find(al_elem, "lx:Profile") or al_elem.find("Profile")
        if profile is not None:
            alignment.vertical_elements = _parse_profile(profile)

        result.append(alignment)

    return result


def _parse_coord_geom(cg: ET.Element) -> list[HorizontalElementUnion]:
    elements: list[HorizontalElementUnion] = []
    chainage = 0.0

    for child in cg:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "Line":
            start = _parse_point(child.find("Start", _NS).text if child.find("Start", _NS) is not None else child.find("Start").text)
            end = _parse_point(child.find("End", _NS).text if child.find("End", _NS) is not None else child.find("End").text)
            length = float(child.get("length", start.distance_to(end)))
            az = math.atan2(end.x - start.x, end.y - start.y)
            elements.append(Straight(chainage, length, start, az))
            chainage += length

        elif tag == "Curve":
            start_pt = _parse_point((child.find("Start", _NS) or child.find("Start")).text)
            end_pt = _parse_point((child.find("End", _NS) or child.find("End")).text)
            center_pt = _parse_point((child.find("Center", _NS) or child.find("Center")).text)
            radius = float(child.get("radius", 0))
            rot = child.get("rot", "cw")
            direction = CurveDirection.RIGHT if rot == "cw" else CurveDirection.LEFT
            length = float(child.get("length", 0))
            # Compute start azimuth from center to start (perpendicular)
            dx = start_pt.x - center_pt.x
            dy = start_pt.y - center_pt.y
            if direction == CurveDirection.RIGHT:
                az = math.atan2(dy, -dx)  # perpendicular CCW from radius
                az = math.atan2(-dy, dx)
                # tangent at start = perpendicular to radius, CW rotation
                az = math.atan2(dy, -dx)
                # Actually: tangent direction for CW arc
                az = math.atan2(dy, -dx)  # this gives the direction perpendicular
            else:
                az = math.atan2(-dy, dx)
            # Better approach: tangent at start of arc
            sign = 1.0 if direction == CurveDirection.RIGHT else -1.0
            perp_angle = math.atan2(dx, dy)  # azimuth from center to start
            az = perp_angle + sign * math.pi / 2.0
            az = az % (2 * math.pi)

            elements.append(CircularArc(chainage, length, start_pt, az, radius, direction))
            chainage += length

        elif tag == "Spiral":
            start_pt = _parse_point((child.find("Start", _NS) or child.find("Start")).text)
            length = float(child.get("length", 0))
            r_start = child.get("radiusStart", "INF")
            r_end = child.get("radiusEnd", "INF")
            radius_start = math.inf if r_start.upper() == "INF" else float(r_start)
            radius_end = math.inf if r_end.upper() == "INF" else float(r_end)
            rot = child.get("rot", "cw")
            direction = CurveDirection.RIGHT if rot == "cw" else CurveDirection.LEFT

            # Azimuth from previous element or PI
            az = 0.0
            if elements:
                az = elements[-1].end_azimuth

            elements.append(TransitionCurve(
                chainage, length, start_pt, az,
                radius_start, radius_end, direction,
            ))
            chainage += length

    return elements


def _parse_profile(profile_elem: ET.Element) -> list[VerticalElementUnion]:
    """Parse vertical profile from LandXML Profile/ProfAlign elements."""
    elements: list[VerticalElementUnion] = []

    prof_align = _find(profile_elem, "lx:ProfAlign") or profile_elem.find("ProfAlign")
    if prof_align is None:
        return elements

    pvis = []
    for child in prof_align:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "PVI":
            parts = child.text.strip().split()
            ch = float(parts[0])
            elev = float(parts[1])
            pvis.append((ch, elev))

    # Convert PVIs to grade segments
    for i in range(len(pvis) - 1):
        ch1, e1 = pvis[i]
        ch2, e2 = pvis[i + 1]
        length = ch2 - ch1
        gradient = (e2 - e1) / length if length > 0 else 0.0
        elements.append(VerticalGrade(ch1, length, e1, gradient))

    return elements
