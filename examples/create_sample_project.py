#!/usr/bin/env python3
"""Create a sample RailTrack project demonstrating all features.

Run: python examples/create_sample_project.py

Produces:
- examples/output/sample_project.rtk.json
- examples/output/horizontal_elements.csv
- examples/output/alignment_report.xlsx
- examples/output/alignment.dxf
- examples/output/alignment.xml (LandXML)
- examples/output/validation_report.html
"""
import math
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from railtrack.application.project_manager import ProjectManager
from railtrack.domain.alignment import DesignCriteria, SpeedProfile, SpeedSegment
from railtrack.domain.horizontal import (
    CircularArc,
    CurveDirection,
    Straight,
    TransitionCurve,
)
from railtrack.domain.primitives import Point2D
from railtrack.domain.vertical import VerticalCurve, VerticalGrade
from railtrack.geometry_engine.horizontal_engine import build_straight_curve_straight


def main():
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    pm = ProjectManager()
    project = pm.new_project(
        "Przykładowy Projekt - Linia 123",
        description="Odcinek km 0+000 do km 1+500, V=120 km/h"
    )
    project.design_criteria = DesignCriteria(
        max_speed_kmh=120,
        gauge=1.435,
        min_radius=500,
        min_transition_length=40,
        max_cant=0.160,
        max_cant_deficiency=0.100,
        max_gradient=0.012,
        min_vertical_curve_radius=5000,
        min_tangent_length=30,
    )

    # --- Alignment 1: Main track ---
    al = pm.add_alignment("Tor główny")

    # Build: Straight - Transition - Right Arc - Transition - Straight - Transition - Left Arc - Transition - Straight
    elems = build_straight_curve_straight(
        start_point=Point2D(5000.0, 10000.0),
        start_azimuth=math.radians(10),  # 10° from north
        start_chainage=0.0,
        straight1_length=300.0,
        transition1_length=60.0,
        arc_radius=800.0,
        arc_length=250.0,
        direction=CurveDirection.RIGHT,
        transition2_length=60.0,
        straight2_length=100.0,
    )

    # Add second curve (left)
    from railtrack.geometry_engine.horizontal_engine import propagate_geometry
    extra = [
        TransitionCurve(0, 50, Point2D(0, 0), 0, math.inf, 1000, CurveDirection.LEFT),
        CircularArc(0, 200, Point2D(0, 0), 0, 1000, CurveDirection.LEFT),
        TransitionCurve(0, 50, Point2D(0, 0), 0, 1000, math.inf, CurveDirection.LEFT),
        Straight(0, 200, Point2D(0, 0), 0),
    ]
    all_elems = elems + extra
    al.horizontal_elements = propagate_geometry(all_elems)

    # Vertical profile
    al.vertical_elements = [
        VerticalGrade(0.0, 400.0, 150.0, 0.005),      # +5‰
        VerticalCurve(400.0, 200.0, 152.0, 0.005, -0.003),  # crest
        VerticalGrade(600.0, 670.0, 152.6, -0.003),    # -3‰
    ]

    # Speed profile
    total_len = al.total_length
    al.speed_profile = SpeedProfile(segments=[
        SpeedSegment(0, total_len, 120.0),
    ])

    # Generate cant
    pm.generate_cant(al, speed_kmh=120)

    # Propagate
    pm.propagate_horizontal(al)
    pm.propagate_vertical(al)

    # Validate
    issues = pm.validate_alignment(al)
    print(f"\n=== Walidacja: {al.name} ===")
    print(f"Elementy poziome: {len(al.horizontal_elements)}")
    print(f"Elementy pionowe: {len(al.vertical_elements)}")
    print(f"Elementy przechyłki: {len(al.cant_elements)}")
    print(f"Długość osi: {al.total_length:.1f} m")
    print(f"\nWyniki walidacji ({len(issues)} problemów):")
    for issue in issues:
        print(f"  [{issue.severity.value.upper():7s}] {issue.code}: {issue.title}")
        print(f"           {issue.message}")
        if issue.suggestion:
            print(f"           → {issue.suggestion}")

    # Export all formats
    print("\n=== Eksport ===")

    pm.save_project(output_dir / "sample_project.rtk.json")
    print(f"  Projekt: {output_dir / 'sample_project.rtk.json'}")

    pm.export_csv(al, output_dir / "horizontal_elements.csv")
    print(f"  CSV:     {output_dir / 'horizontal_elements.csv'}")

    pm.export_xlsx(al, output_dir / "alignment_report.xlsx")
    print(f"  XLSX:    {output_dir / 'alignment_report.xlsx'}")

    pm.export_dxf(al, output_dir / "alignment.dxf")
    print(f"  DXF:     {output_dir / 'alignment.dxf'}")

    pm.export_landxml(output_dir / "alignment.xml")
    print(f"  LandXML: {output_dir / 'alignment.xml'}")

    pm.export_html_report(al, output_dir / "validation_report.html")
    print(f"  HTML:    {output_dir / 'validation_report.html'}")

    print("\nGotowe!")


if __name__ == "__main__":
    main()
