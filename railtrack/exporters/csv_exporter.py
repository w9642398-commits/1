"""CSV exporter for alignment element tables and point data."""
from __future__ import annotations

import csv
import math
from pathlib import Path

from railtrack.domain.alignment import Alignment
from railtrack.domain.horizontal import CircularArc, Straight, TransitionCurve


def export_horizontal_elements_csv(
    alignment: Alignment,
    path: Path | str,
) -> None:
    """Export horizontal element table to CSV."""
    path = Path(path)
    fieldnames = [
        "index", "type", "start_chainage", "end_chainage", "length",
        "start_x", "start_y", "end_x", "end_y",
        "start_azimuth_deg", "end_azimuth_deg",
        "radius", "direction", "radius_start", "radius_end",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, elem in enumerate(alignment.horizontal_elements):
            row = {
                "index": i,
                "start_chainage": f"{elem.start_chainage:.4f}",
                "end_chainage": f"{elem.end_chainage:.4f}",
                "length": f"{elem.length:.4f}",
                "start_x": f"{elem.start_point.x:.4f}",
                "start_y": f"{elem.start_point.y:.4f}",
                "end_x": f"{elem.end_point.x:.4f}",
                "end_y": f"{elem.end_point.y:.4f}",
                "start_azimuth_deg": f"{math.degrees(elem.start_azimuth):.6f}",
                "end_azimuth_deg": f"{math.degrees(elem.end_azimuth):.6f}",
            }
            if isinstance(elem, Straight):
                row["type"] = "straight"
                row["radius"] = "inf"
            elif isinstance(elem, CircularArc):
                row["type"] = "arc"
                row["radius"] = f"{elem.radius:.4f}"
                row["direction"] = elem.direction.value
            elif isinstance(elem, TransitionCurve):
                row["type"] = "transition"
                row["direction"] = elem.direction.value
                row["radius_start"] = "inf" if math.isinf(elem.radius_start) else f"{elem.radius_start:.4f}"
                row["radius_end"] = "inf" if math.isinf(elem.radius_end) else f"{elem.radius_end:.4f}"
            writer.writerow(row)


def export_points_csv(
    points: list[tuple[float, float, float]],
    path: Path | str,
    header: tuple[str, ...] = ("chainage", "x", "y"),
) -> None:
    """Export computed points to CSV."""
    path = Path(path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in points:
            writer.writerow([f"{v:.4f}" for v in row])
