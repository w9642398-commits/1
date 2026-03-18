"""CSV/TXT importer for survey points and alignment elements."""
from __future__ import annotations

import csv
import math
from pathlib import Path

from railtrack.domain.horizontal import (
    CircularArc,
    CurveDirection,
    HorizontalElementUnion,
    Straight,
    TransitionCurve,
)
from railtrack.domain.primitives import Point2D, Point3D


def import_survey_points(
    path: Path | str,
    x_col: int = 0,
    y_col: int = 1,
    z_col: int | None = 2,
    delimiter: str = ",",
    skip_header: bool = True,
) -> list[Point3D]:
    """Import survey points from CSV/TXT.

    Columns are identified by zero-based index.
    """
    path = Path(path)
    points: list[Point3D] = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=delimiter)
        if skip_header:
            next(reader, None)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            try:
                x = float(row[x_col].strip())
                y = float(row[y_col].strip())
                z = float(row[z_col].strip()) if z_col is not None and z_col < len(row) else 0.0
                points.append(Point3D(x, y, z))
            except (ValueError, IndexError):
                continue
    return points


def import_horizontal_elements(
    path: Path | str,
    delimiter: str = ",",
    skip_header: bool = True,
) -> list[HorizontalElementUnion]:
    """Import horizontal elements from CSV.

    Expected columns:
    type, start_chainage, length, start_x, start_y, start_azimuth_deg,
    radius, direction, radius_start, radius_end

    type: straight | arc | transition
    direction: left | right (for arcs/transitions)
    """
    path = Path(path)
    elements: list[HorizontalElementUnion] = []

    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            etype = row.get("type", "").strip().lower()
            ch = float(row.get("start_chainage", 0))
            length = float(row.get("length", 0))
            sx = float(row.get("start_x", 0))
            sy = float(row.get("start_y", 0))
            az_deg = float(row.get("start_azimuth_deg", 0))
            az = math.radians(az_deg)
            sp = Point2D(sx, sy)

            if etype == "straight":
                elements.append(Straight(ch, length, sp, az))
            elif etype == "arc":
                r = float(row.get("radius", 0))
                d = CurveDirection.LEFT if row.get("direction", "").strip().lower() == "left" else CurveDirection.RIGHT
                elements.append(CircularArc(ch, length, sp, az, r, d))
            elif etype == "transition":
                rs = row.get("radius_start", "inf").strip()
                re = row.get("radius_end", "inf").strip()
                r_start = float(rs) if rs.lower() != "inf" else math.inf
                r_end = float(re) if re.lower() != "inf" else math.inf
                d = CurveDirection.LEFT if row.get("direction", "").strip().lower() == "left" else CurveDirection.RIGHT
                elements.append(TransitionCurve(ch, length, sp, az, r_start, r_end, d))

    return elements
