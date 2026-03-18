"""Alignment and Project domain model.

An Alignment ties together horizontal, vertical, and cant geometry.
A Project contains one or more alignments.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from railtrack.domain.cant import CantElementUnion
from railtrack.domain.horizontal import HorizontalElementUnion
from railtrack.domain.primitives import ChainageRange, Point2D, Point3D
from railtrack.domain.turnout import Turnout
from railtrack.domain.vertical import VerticalElementUnion


@dataclass
class SpeedProfile:
    """Speed restrictions along an alignment."""
    segments: list[SpeedSegment] = field(default_factory=list)

    def speed_at(self, chainage: float) -> float | None:
        for seg in self.segments:
            if seg.chainage_range.contains(chainage):
                return seg.speed_kmh
        return None


@dataclass
class SpeedSegment:
    start_chainage: float
    end_chainage: float
    speed_kmh: float

    @property
    def chainage_range(self) -> ChainageRange:
        return ChainageRange(self.start_chainage, self.end_chainage)


@dataclass
class StationPoint:
    """Named point along the alignment (e.g. platform, signal, bridge)."""
    name: str
    chainage: float
    description: str = ""


@dataclass
class SurveyPointSet:
    """Set of surveyed points for comparison or import."""
    name: str
    points: list[Point3D] = field(default_factory=list)


@dataclass
class ClearanceConstraint:
    """Structure gauge / clearance constraint at a chainage range."""
    chainage_range: ChainageRange
    min_clearance_left: float
    min_clearance_right: float
    description: str = ""


@dataclass
class ExistingTrackGeometry:
    """Represents existing (surveyed or imported) track geometry for comparison.

    Stores a polyline of measured points along an existing track centerline.
    Used for comparison with designed geometry or as a basis for reconstruction.
    """
    name: str
    points: list[Point3D] = field(default_factory=list)
    description: str = ""
    source_file: str = ""

    @property
    def start_chainage(self) -> float:
        return 0.0

    @property
    def end_chainage(self) -> float:
        if len(self.points) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(self.points)):
            p0 = self.points[i - 1]
            p1 = self.points[i]
            total += p0.to_2d().distance_to(p1.to_2d())
        return total

    @property
    def length(self) -> float:
        return self.end_chainage


@dataclass
class Alignment:
    """Complete track alignment combining horizontal, vertical, and cant."""
    name: str
    horizontal_elements: list[HorizontalElementUnion] = field(default_factory=list)
    vertical_elements: list[VerticalElementUnion] = field(default_factory=list)
    cant_elements: list[CantElementUnion] = field(default_factory=list)
    turnouts: list[Turnout] = field(default_factory=list)
    speed_profile: SpeedProfile = field(default_factory=SpeedProfile)
    station_points: list[StationPoint] = field(default_factory=list)
    clearance_constraints: list[ClearanceConstraint] = field(default_factory=list)

    @property
    def start_chainage(self) -> float:
        if not self.horizontal_elements:
            return 0.0
        return self.horizontal_elements[0].start_chainage

    @property
    def end_chainage(self) -> float:
        if not self.horizontal_elements:
            return 0.0
        return self.horizontal_elements[-1].end_chainage

    @property
    def total_length(self) -> float:
        return self.end_chainage - self.start_chainage

    def point_at(self, chainage: float) -> Point2D | None:
        """Get 2D point at chainage from horizontal geometry."""
        for elem in self.horizontal_elements:
            if elem.chainage_range.contains(chainage):
                return elem.point_at(chainage)
        return None

    def elevation_at(self, chainage: float) -> float | None:
        """Get elevation at chainage from vertical geometry."""
        for elem in self.vertical_elements:
            if elem.chainage_range.contains(chainage):
                return elem.elevation_at(chainage)
        return None

    def cant_at(self, chainage: float) -> float | None:
        """Get cant at chainage."""
        for elem in self.cant_elements:
            if elem.chainage_range.contains(chainage):
                return elem.cant_at(chainage)
        return None

    def point3d_at(self, chainage: float) -> Point3D | None:
        pt = self.point_at(chainage)
        elev = self.elevation_at(chainage)
        if pt is not None and elev is not None:
            return Point3D(pt.x, pt.y, elev)
        return None

    def azimuth_at(self, chainage: float) -> float | None:
        for elem in self.horizontal_elements:
            if elem.chainage_range.contains(chainage):
                return elem.azimuth_at(chainage)
        return None

    def radius_at(self, chainage: float) -> float | None:
        for elem in self.horizontal_elements:
            if elem.chainage_range.contains(chainage):
                return elem.radius_at(chainage)
        return None


@dataclass
class DesignCriteria:
    """Design criteria / parameters for the project."""
    max_speed_kmh: float = 160.0
    gauge: float = 1.435
    min_radius: float = 300.0
    min_transition_length: float = 20.0
    max_cant: float = 0.160  # 160 mm
    max_cant_deficiency: float = 0.100  # 100 mm
    max_gradient: float = 0.025  # 25 permille
    min_vertical_curve_radius: float = 2000.0
    min_tangent_length: float = 20.0
    rules_file: str = ""


@dataclass
class Project:
    """Top-level project container."""
    name: str
    description: str = ""
    alignments: list[Alignment] = field(default_factory=list)
    design_criteria: DesignCriteria = field(default_factory=DesignCriteria)
    survey_point_sets: list[SurveyPointSet] = field(default_factory=list)

    def alignment_by_name(self, name: str) -> Alignment | None:
        for a in self.alignments:
            if a.name == name:
                return a
        return None
