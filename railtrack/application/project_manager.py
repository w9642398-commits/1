"""Application-level project management and use cases."""
from __future__ import annotations

import json
import math
from pathlib import Path

from railtrack.domain.alignment import (
    Alignment, ClearanceConstraint, DesignCriteria, ExistingTrackGeometry,
    Project, SpeedProfile, SpeedSegment, StationPoint, SurveyPointSet,
)
from railtrack.domain.cant import CantElementUnion, CantRamp, CantSegment
from railtrack.domain.horizontal import (
    CircularArc,
    CurveDirection,
    HorizontalElementUnion,
    Straight,
    TransitionCurve,
)
from railtrack.domain.primitives import ChainageRange, Point2D, Point3D
from railtrack.domain.turnout import Turnout
from railtrack.domain.validation_types import ValidationIssue
from railtrack.domain.vertical import VerticalCurve, VerticalElementUnion, VerticalGrade
from railtrack.exporters.csv_exporter import export_horizontal_elements_csv
from railtrack.exporters.dxf_exporter import export_alignment_dxf
from railtrack.exporters.html_report import export_validation_html
from railtrack.exporters.landxml_exporter import export_landxml
from railtrack.exporters.xlsx_exporter import export_alignment_xlsx
from railtrack.geometry_engine.cant_engine import generate_cant_elements
from railtrack.geometry_engine.horizontal_engine import propagate_geometry
from railtrack.geometry_engine.vertical_engine import propagate_vertical
from railtrack.validation.validator import AlignmentValidator


class ProjectManager:
    """Coordinates project-level operations."""

    def __init__(self):
        self.project: Project | None = None
        self.validator = AlignmentValidator()
        self._file_path: Path | None = None

    def new_project(self, name: str, description: str = "") -> Project:
        self.project = Project(name=name, description=description)
        self._file_path = None
        return self.project

    def add_alignment(self, name: str) -> Alignment:
        if self.project is None:
            raise RuntimeError("No project open")
        alignment = Alignment(name=name)
        self.project.alignments.append(alignment)
        return alignment

    def propagate_horizontal(self, alignment: Alignment) -> None:
        """Recalculate horizontal geometry chain."""
        alignment.horizontal_elements = propagate_geometry(
            alignment.horizontal_elements
        )

    def propagate_vertical(self, alignment: Alignment) -> None:
        """Recalculate vertical geometry chain."""
        alignment.vertical_elements = propagate_vertical(
            alignment.vertical_elements
        )

    def generate_cant(
        self,
        alignment: Alignment,
        speed_kmh: float | None = None,
    ) -> None:
        """Generate cant elements from horizontal geometry."""
        speed = speed_kmh or (
            self.project.design_criteria.max_speed_kmh if self.project else 120.0
        )
        alignment.cant_elements = generate_cant_elements(
            alignment.horizontal_elements, speed
        )

    def validate_alignment(self, alignment: Alignment) -> list[ValidationIssue]:
        criteria = self.project.design_criteria if self.project else None
        return self.validator.validate(alignment, criteria)

    def validate_all(self) -> dict[str, list[ValidationIssue]]:
        if self.project is None:
            return {}
        results = {}
        for al in self.project.alignments:
            results[al.name] = self.validate_alignment(al)
        return results

    # --- Export ---
    def export_csv(self, alignment: Alignment, path: Path | str) -> None:
        export_horizontal_elements_csv(alignment, path)

    def export_xlsx(self, alignment: Alignment, path: Path | str) -> None:
        issues = self.validate_alignment(alignment)
        export_alignment_xlsx(alignment, path, issues)

    def export_dxf(self, alignment: Alignment, path: Path | str) -> None:
        export_alignment_dxf(alignment, path)

    def export_landxml(self, path: Path | str) -> None:
        if self.project is None:
            return
        export_landxml(self.project.alignments, path, self.project.name)

    def export_html_report(self, alignment: Alignment, path: Path | str) -> None:
        issues = self.validate_alignment(alignment)
        export_validation_html(alignment, issues, path)

    # --- Serialization ---
    def save_project(self, path: Path | str) -> None:
        """Save project to JSON."""
        if self.project is None:
            return
        path = Path(path)
        data = _serialize_project(self.project)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self._file_path = path

    def load_project(self, path: Path | str) -> Project:
        """Load project from JSON."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.project = _deserialize_project(data)
        self._file_path = path
        return self.project


def _serialize_project(project: Project) -> dict:
    return {
        "name": project.name,
        "description": project.description,
        "design_criteria": {
            "max_speed_kmh": project.design_criteria.max_speed_kmh,
            "gauge": project.design_criteria.gauge,
            "min_radius": project.design_criteria.min_radius,
            "min_transition_length": project.design_criteria.min_transition_length,
            "max_cant": project.design_criteria.max_cant,
            "max_cant_deficiency": project.design_criteria.max_cant_deficiency,
            "max_gradient": project.design_criteria.max_gradient,
            "min_vertical_curve_radius": project.design_criteria.min_vertical_curve_radius,
            "min_tangent_length": project.design_criteria.min_tangent_length,
            "rules_file": project.design_criteria.rules_file,
        },
        "alignments": [_serialize_alignment(a) for a in project.alignments],
        "survey_point_sets": [_serialize_survey_set(s) for s in project.survey_point_sets],
    }


def _serialize_alignment(alignment: Alignment) -> dict:
    return {
        "name": alignment.name,
        "horizontal_elements": [_serialize_h_elem(e) for e in alignment.horizontal_elements],
        "vertical_elements": [_serialize_v_elem(e) for e in alignment.vertical_elements],
        "cant_elements": [_serialize_cant_elem(e) for e in alignment.cant_elements],
        "turnouts": [_serialize_turnout(t) for t in alignment.turnouts],
        "speed_profile": _serialize_speed_profile(alignment.speed_profile),
        "station_points": [
            {"name": sp.name, "chainage": sp.chainage, "description": sp.description}
            for sp in alignment.station_points
        ],
        "clearance_constraints": [
            {
                "start_chainage": cc.chainage_range.start,
                "end_chainage": cc.chainage_range.end,
                "min_clearance_left": cc.min_clearance_left,
                "min_clearance_right": cc.min_clearance_right,
                "description": cc.description,
            }
            for cc in alignment.clearance_constraints
        ],
    }


def _serialize_h_elem(elem: HorizontalElementUnion) -> dict:
    base = {
        "start_chainage": elem.start_chainage,
        "length": elem.length,
        "start_x": elem.start_point.x,
        "start_y": elem.start_point.y,
        "start_azimuth": elem.start_azimuth,
    }
    if isinstance(elem, Straight):
        base["type"] = "straight"
    elif isinstance(elem, CircularArc):
        base["type"] = "arc"
        base["radius"] = elem.radius
        base["direction"] = elem.direction.value
    elif isinstance(elem, TransitionCurve):
        base["type"] = "transition"
        base["radius_start"] = None if math.isinf(elem.radius_start) else elem.radius_start
        base["radius_end"] = None if math.isinf(elem.radius_end) else elem.radius_end
        base["direction"] = elem.direction.value
    return base


def _serialize_v_elem(elem: VerticalElementUnion) -> dict:
    if isinstance(elem, VerticalGrade):
        return {
            "type": "grade",
            "start_chainage": elem.start_chainage,
            "length": elem.length,
            "start_elevation": elem.start_elevation,
            "gradient": elem.gradient,
        }
    elif isinstance(elem, VerticalCurve):
        return {
            "type": "curve",
            "start_chainage": elem.start_chainage,
            "length": elem.length,
            "start_elevation": elem.start_elevation,
            "gradient_in": elem.gradient_in,
            "gradient_out": elem.gradient_out,
        }
    return {}


def _serialize_cant_elem(elem: CantElementUnion) -> dict:
    if isinstance(elem, CantSegment):
        return {
            "type": "constant",
            "start_chainage": elem.start_chainage,
            "length": elem.length,
            "cant": elem.cant,
            "gauge": elem.gauge,
        }
    elif isinstance(elem, CantRamp):
        return {
            "type": "ramp",
            "start_chainage": elem.start_chainage,
            "length": elem.length,
            "cant_start": elem.cant_start,
            "cant_end": elem.cant_end,
            "gauge": elem.gauge,
        }
    return {}


def _serialize_turnout(turnout: Turnout) -> dict:
    return {
        "name": turnout.name,
        "chainage": turnout.chainage,
        "hand": turnout.hand.value,
        "turnout_type": turnout.turnout_type.value,
        "tangent_angle": turnout.tangent_angle,
        "total_length": turnout.total_length,
        "curve_radius": turnout.curve_radius,
        "speed_through": turnout.speed_through,
        "speed_diverging": turnout.speed_diverging,
    }


def _serialize_speed_profile(sp: SpeedProfile) -> dict:
    return {
        "segments": [
            {
                "start_chainage": seg.start_chainage,
                "end_chainage": seg.end_chainage,
                "speed_kmh": seg.speed_kmh,
            }
            for seg in sp.segments
        ]
    }


def _serialize_survey_set(ss: SurveyPointSet) -> dict:
    return {
        "name": ss.name,
        "points": [{"x": p.x, "y": p.y, "z": p.z} for p in ss.points],
    }


def _deserialize_project(data: dict) -> Project:
    dc = data.get("design_criteria", {})
    criteria = DesignCriteria(
        max_speed_kmh=dc.get("max_speed_kmh", 160),
        gauge=dc.get("gauge", 1.435),
        min_radius=dc.get("min_radius", 300),
        min_transition_length=dc.get("min_transition_length", 20.0),
        max_cant=dc.get("max_cant", 0.160),
        max_cant_deficiency=dc.get("max_cant_deficiency", 0.100),
        max_gradient=dc.get("max_gradient", 0.025),
        min_vertical_curve_radius=dc.get("min_vertical_curve_radius", 2000.0),
        min_tangent_length=dc.get("min_tangent_length", 20.0),
        rules_file=dc.get("rules_file", ""),
    )
    project = Project(
        name=data.get("name", ""),
        description=data.get("description", ""),
        design_criteria=criteria,
    )
    for al_data in data.get("alignments", []):
        alignment = Alignment(name=al_data.get("name", ""))
        for he in al_data.get("horizontal_elements", []):
            alignment.horizontal_elements.append(_deserialize_h_elem(he))
        for ve in al_data.get("vertical_elements", []):
            alignment.vertical_elements.append(_deserialize_v_elem(ve))
        for ce in al_data.get("cant_elements", []):
            alignment.cant_elements.append(_deserialize_cant_elem(ce))
        for td in al_data.get("turnouts", []):
            alignment.turnouts.append(_deserialize_turnout(td))
        sp_data = al_data.get("speed_profile", {})
        for seg in sp_data.get("segments", []):
            alignment.speed_profile.segments.append(SpeedSegment(
                start_chainage=seg["start_chainage"],
                end_chainage=seg["end_chainage"],
                speed_kmh=seg["speed_kmh"],
            ))
        for spd in al_data.get("station_points", []):
            alignment.station_points.append(StationPoint(
                name=spd["name"],
                chainage=spd["chainage"],
                description=spd.get("description", ""),
            ))
        for ccd in al_data.get("clearance_constraints", []):
            alignment.clearance_constraints.append(ClearanceConstraint(
                chainage_range=ChainageRange(ccd["start_chainage"], ccd["end_chainage"]),
                min_clearance_left=ccd["min_clearance_left"],
                min_clearance_right=ccd["min_clearance_right"],
                description=ccd.get("description", ""),
            ))
        project.alignments.append(alignment)
    for ssd in data.get("survey_point_sets", []):
        project.survey_point_sets.append(SurveyPointSet(
            name=ssd["name"],
            points=[Point3D(p["x"], p["y"], p["z"]) for p in ssd.get("points", [])],
        ))
    return project


def _deserialize_h_elem(data: dict) -> HorizontalElementUnion:
    sp = Point2D(data["start_x"], data["start_y"])
    t = data["type"]
    if t == "straight":
        return Straight(data["start_chainage"], data["length"], sp, data["start_azimuth"])
    elif t == "arc":
        d = CurveDirection(data["direction"])
        return CircularArc(data["start_chainage"], data["length"], sp, data["start_azimuth"], data["radius"], d)
    elif t == "transition":
        d = CurveDirection(data["direction"])
        rs = data.get("radius_start")
        re = data.get("radius_end")
        return TransitionCurve(
            data["start_chainage"], data["length"], sp, data["start_azimuth"],
            math.inf if rs is None else rs,
            math.inf if re is None else re,
            d,
        )
    raise ValueError(f"Unknown element type: {t}")


def _deserialize_v_elem(data: dict) -> VerticalElementUnion:
    t = data["type"]
    if t == "grade":
        return VerticalGrade(data["start_chainage"], data["length"], data["start_elevation"], data["gradient"])
    elif t == "curve":
        return VerticalCurve(data["start_chainage"], data["length"], data["start_elevation"], data["gradient_in"], data["gradient_out"])
    raise ValueError(f"Unknown element type: {t}")


def _deserialize_cant_elem(data: dict) -> CantElementUnion:
    t = data["type"]
    if t == "constant":
        return CantSegment(
            start_chainage=data["start_chainage"],
            length=data["length"],
            cant=data["cant"],
            gauge=data.get("gauge", 1.435),
        )
    elif t == "ramp":
        return CantRamp(
            start_chainage=data["start_chainage"],
            length=data["length"],
            cant_start=data["cant_start"],
            cant_end=data["cant_end"],
            gauge=data.get("gauge", 1.435),
        )
    raise ValueError(f"Unknown cant element type: {t}")


def _deserialize_turnout(data: dict) -> Turnout:
    from railtrack.domain.turnout import TurnoutHand, TurnoutType
    return Turnout(
        name=data["name"],
        chainage=data["chainage"],
        hand=TurnoutHand(data.get("hand", "right")),
        turnout_type=TurnoutType(data.get("turnout_type", "simple")),
        tangent_angle=data.get("tangent_angle", 0.0),
        total_length=data.get("total_length", 0.0),
        curve_radius=data.get("curve_radius", 0.0),
        speed_through=data.get("speed_through", 0.0),
        speed_diverging=data.get("speed_diverging", 0.0),
    )
