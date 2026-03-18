"""Integration tests for import/export roundtrip."""
import math
import tempfile
from pathlib import Path

import pytest

from railtrack.domain.alignment import Alignment, Project
from railtrack.domain.horizontal import (
    CircularArc,
    CurveDirection,
    Straight,
    TransitionCurve,
)
from railtrack.domain.primitives import Point2D
from railtrack.domain.vertical import VerticalGrade
from railtrack.exporters.csv_exporter import export_horizontal_elements_csv
from railtrack.exporters.landxml_exporter import export_landxml
from railtrack.geometry_engine.horizontal_engine import propagate_geometry
from railtrack.importers.csv_importer import import_horizontal_elements
from railtrack.application.project_manager import ProjectManager


@pytest.fixture
def sample_alignment():
    al = Alignment(name="Test Alignment")
    al.horizontal_elements = propagate_geometry([
        Straight(0, 200, Point2D(1000, 2000), 0.0),
        TransitionCurve(0, 60, Point2D(0, 0), 0.0, math.inf, 500, CurveDirection.RIGHT),
        CircularArc(0, 150, Point2D(0, 0), 0.0, 500, CurveDirection.RIGHT),
        TransitionCurve(0, 60, Point2D(0, 0), 0.0, 500, math.inf, CurveDirection.RIGHT),
        Straight(0, 200, Point2D(0, 0), 0.0),
    ])
    al.vertical_elements = [
        VerticalGrade(0, 670, 100.0, 0.005),
    ]
    return al


class TestCSVRoundtrip:
    def test_export_reimport_elements(self, sample_alignment):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            path = f.name
        export_horizontal_elements_csv(sample_alignment, path)
        reimported = import_horizontal_elements(path)
        assert len(reimported) == len(sample_alignment.horizontal_elements)
        for orig, re in zip(sample_alignment.horizontal_elements, reimported):
            assert orig.element_type == re.element_type
            assert abs(orig.length - re.length) < 0.01


class TestLandXMLExport:
    def test_export_produces_valid_xml(self, sample_alignment):
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name
        export_landxml([sample_alignment], path)
        content = Path(path).read_text(encoding="utf-8")
        assert "LandXML" in content
        assert "Line" in content
        assert "Spiral" in content
        assert "Curve" in content


class TestProjectSaveLoad:
    def test_save_load_roundtrip(self, sample_alignment):
        pm = ProjectManager()
        pm.new_project("Test Project")
        pm.project.alignments = [sample_alignment]

        with tempfile.NamedTemporaryFile(suffix=".rtk.json", delete=False) as f:
            path = f.name
        pm.save_project(path)

        pm2 = ProjectManager()
        project = pm2.load_project(path)
        assert project.name == "Test Project"
        assert len(project.alignments) == 1
        al = project.alignments[0]
        assert len(al.horizontal_elements) == 5
        assert abs(al.horizontal_elements[0].length - 200.0) < 0.01
