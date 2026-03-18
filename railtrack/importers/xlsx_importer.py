"""XLSX importer for survey points and alignment data."""
from __future__ import annotations

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


def import_survey_points_xlsx(
    path: Path | str,
    sheet_name: str | int = 0,
    x_col: str = "X",
    y_col: str = "Y",
    z_col: str = "Z",
) -> list[Point3D]:
    """Import survey points from XLSX."""
    import pandas as pd

    df = pd.read_excel(path, sheet_name=sheet_name)
    points: list[Point3D] = []
    for _, row in df.iterrows():
        try:
            x = float(row[x_col])
            y = float(row[y_col])
            z = float(row.get(z_col, 0))
            points.append(Point3D(x, y, z))
        except (ValueError, TypeError, KeyError):
            continue
    return points


def import_horizontal_elements_xlsx(
    path: Path | str,
    sheet_name: str | int = 0,
) -> list[HorizontalElementUnion]:
    """Import horizontal alignment elements from XLSX.

    Expected column names same as CSV importer.
    """
    import pandas as pd

    df = pd.read_excel(path, sheet_name=sheet_name)
    elements: list[HorizontalElementUnion] = []

    for _, row in df.iterrows():
        etype = str(row.get("type", "")).strip().lower()
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
            d = CurveDirection.LEFT if str(row.get("direction", "")).strip().lower() == "left" else CurveDirection.RIGHT
            elements.append(CircularArc(ch, length, sp, az, r, d))
        elif etype == "transition":
            rs = str(row.get("radius_start", "inf")).strip()
            re = str(row.get("radius_end", "inf")).strip()
            r_start = float(rs) if rs.lower() != "inf" else math.inf
            r_end = float(re) if re.lower() != "inf" else math.inf
            d = CurveDirection.LEFT if str(row.get("direction", "")).strip().lower() == "left" else CurveDirection.RIGHT
            elements.append(TransitionCurve(ch, length, sp, az, r_start, r_end, d))

    return elements
