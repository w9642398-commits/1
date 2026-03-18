"""Turnout library - catalog of standard railway turnout types.

Based on Polish railway standards (PKP/PLK) and European norms.
Each entry defines the geometric and operational parameters of a turnout type.
The library is extensible - additional entries can be loaded from YAML.

Usage:
    from railtrack.domain.turnout_library import TURNOUT_LIBRARY, create_turnout

    # Browse catalog
    for entry in TURNOUT_LIBRARY.all():
        print(entry.catalog_id, entry.description)

    # Create a turnout instance from catalog
    turnout = TURNOUT_LIBRARY.create("Rz-S49-1:9-300", chainage=1500.0, hand=TurnoutHand.RIGHT)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from railtrack.domain.turnout import Turnout, TurnoutHand, TurnoutType


@dataclass(frozen=True)
class TurnoutCatalogEntry:
    """A single turnout type definition in the catalog."""

    catalog_id: str          # e.g. "Rz-S49-1:9-300"
    description: str         # e.g. "Rozjazd zwyczajny S49, 1:9, R=300m"
    rail_type: str           # e.g. "S49", "60E1", "49E1"
    turnout_type: TurnoutType
    frog_ratio: int          # denominator, e.g. 9 for 1:9
    curve_radius: float      # metres, diverging track radius
    total_length: float      # metres, overall length from tip to end
    speed_through: float     # km/h, max speed on through route
    speed_diverging: float   # km/h, max speed on diverging route
    gauge: float = 1.435     # track gauge
    min_tangent_before: float = 6.0   # metres, required tangent before
    min_tangent_after: float = 6.0    # metres, required tangent after
    weight_kg: float = 0.0   # approximate weight for logistics
    notes: str = ""

    @property
    def tangent_angle(self) -> float:
        """Frog angle in radians."""
        return math.atan(1.0 / self.frog_ratio)

    @property
    def tangent_angle_deg(self) -> float:
        return math.degrees(self.tangent_angle)

    def create_turnout(
        self,
        chainage: float,
        hand: TurnoutHand,
        name: str = "",
    ) -> Turnout:
        """Create a Turnout domain object from this catalog entry."""
        if not name:
            name = f"{self.catalog_id} km {chainage:.3f}"
        return Turnout(
            name=name,
            chainage=chainage,
            hand=hand,
            turnout_type=self.turnout_type,
            tangent_angle=self.tangent_angle,
            total_length=self.total_length,
            curve_radius=self.curve_radius,
            speed_through=self.speed_through,
            speed_diverging=self.speed_diverging,
        )


class TurnoutLibrary:
    """Catalog of available turnout types."""

    def __init__(self) -> None:
        self._entries: dict[str, TurnoutCatalogEntry] = {}

    def register(self, entry: TurnoutCatalogEntry) -> None:
        self._entries[entry.catalog_id] = entry

    def get(self, catalog_id: str) -> TurnoutCatalogEntry | None:
        return self._entries.get(catalog_id)

    def all(self) -> list[TurnoutCatalogEntry]:
        return list(self._entries.values())

    def by_rail_type(self, rail_type: str) -> list[TurnoutCatalogEntry]:
        return [e for e in self._entries.values() if e.rail_type == rail_type]

    def by_frog_ratio(self, ratio: int) -> list[TurnoutCatalogEntry]:
        return [e for e in self._entries.values() if e.frog_ratio == ratio]

    def by_min_speed_diverging(self, min_speed: float) -> list[TurnoutCatalogEntry]:
        return [e for e in self._entries.values() if e.speed_diverging >= min_speed]

    def by_type(self, tt: TurnoutType) -> list[TurnoutCatalogEntry]:
        return [e for e in self._entries.values() if e.turnout_type == tt]

    def create(
        self,
        catalog_id: str,
        chainage: float,
        hand: TurnoutHand,
        name: str = "",
    ) -> Turnout:
        """Create a turnout instance from the catalog."""
        entry = self._entries.get(catalog_id)
        if entry is None:
            raise KeyError(f"Turnout '{catalog_id}' not found in library")
        return entry.create_turnout(chainage, hand, name)

    def load_from_yaml(self, path: Path | str) -> int:
        """Load additional turnout definitions from YAML file.

        Returns the number of entries loaded.
        """
        import yaml
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        count = 0
        for item in data.get("turnouts", []):
            tt_str = item.get("turnout_type", "simple").lower()
            tt_map = {"simple": TurnoutType.SIMPLE, "symmetric": TurnoutType.SYMMETRIC, "curved": TurnoutType.CURVED}
            entry = TurnoutCatalogEntry(
                catalog_id=item["catalog_id"],
                description=item.get("description", ""),
                rail_type=item.get("rail_type", ""),
                turnout_type=tt_map.get(tt_str, TurnoutType.SIMPLE),
                frog_ratio=item["frog_ratio"],
                curve_radius=item["curve_radius"],
                total_length=item["total_length"],
                speed_through=item.get("speed_through", 0),
                speed_diverging=item.get("speed_diverging", 0),
                gauge=item.get("gauge", 1.435),
                min_tangent_before=item.get("min_tangent_before", 6.0),
                min_tangent_after=item.get("min_tangent_after", 6.0),
                weight_kg=item.get("weight_kg", 0),
                notes=item.get("notes", ""),
            )
            self.register(entry)
            count += 1
        return count


def _build_default_library() -> TurnoutLibrary:
    """Build the default turnout library with standard Polish/European types."""
    lib = TurnoutLibrary()

    # ========================================================================
    # S49 rail turnouts (older standard, still widely used)
    # ========================================================================
    lib.register(TurnoutCatalogEntry(
        catalog_id="Rz-S49-1:9-300",
        description="Rozjazd zwyczajny S49, 1:9, R=300m",
        rail_type="S49",
        turnout_type=TurnoutType.SIMPLE,
        frog_ratio=9,
        curve_radius=300.0,
        total_length=27.095,
        speed_through=120,
        speed_diverging=40,
        min_tangent_before=6.0,
        min_tangent_after=6.0,
    ))
    lib.register(TurnoutCatalogEntry(
        catalog_id="Rz-S49-1:9-190",
        description="Rozjazd zwyczajny S49, 1:9, R=190m",
        rail_type="S49",
        turnout_type=TurnoutType.SIMPLE,
        frog_ratio=9,
        curve_radius=190.0,
        total_length=24.630,
        speed_through=100,
        speed_diverging=40,
        min_tangent_before=6.0,
        min_tangent_after=6.0,
    ))
    lib.register(TurnoutCatalogEntry(
        catalog_id="Rz-S49-1:12-500",
        description="Rozjazd zwyczajny S49, 1:12, R=500m",
        rail_type="S49",
        turnout_type=TurnoutType.SIMPLE,
        frog_ratio=12,
        curve_radius=500.0,
        total_length=39.264,
        speed_through=120,
        speed_diverging=60,
        min_tangent_before=8.0,
        min_tangent_after=8.0,
    ))
    lib.register(TurnoutCatalogEntry(
        catalog_id="Rz-S49-1:14-760",
        description="Rozjazd zwyczajny S49, 1:14, R=760m",
        rail_type="S49",
        turnout_type=TurnoutType.SIMPLE,
        frog_ratio=14,
        curve_radius=760.0,
        total_length=46.580,
        speed_through=120,
        speed_diverging=80,
        min_tangent_before=10.0,
        min_tangent_after=10.0,
    ))

    # ========================================================================
    # 60E1 rail turnouts (modern standard)
    # ========================================================================
    lib.register(TurnoutCatalogEntry(
        catalog_id="Rz-60E1-1:9-300",
        description="Rozjazd zwyczajny 60E1, 1:9, R=300m",
        rail_type="60E1",
        turnout_type=TurnoutType.SIMPLE,
        frog_ratio=9,
        curve_radius=300.0,
        total_length=28.440,
        speed_through=160,
        speed_diverging=40,
        min_tangent_before=6.0,
        min_tangent_after=6.0,
    ))
    lib.register(TurnoutCatalogEntry(
        catalog_id="Rz-60E1-1:12-500",
        description="Rozjazd zwyczajny 60E1, 1:12, R=500m",
        rail_type="60E1",
        turnout_type=TurnoutType.SIMPLE,
        frog_ratio=12,
        curve_radius=500.0,
        total_length=40.674,
        speed_through=160,
        speed_diverging=60,
        min_tangent_before=8.0,
        min_tangent_after=8.0,
    ))
    lib.register(TurnoutCatalogEntry(
        catalog_id="Rz-60E1-1:14-760",
        description="Rozjazd zwyczajny 60E1, 1:14, R=760m",
        rail_type="60E1",
        turnout_type=TurnoutType.SIMPLE,
        frog_ratio=14,
        curve_radius=760.0,
        total_length=48.048,
        speed_through=160,
        speed_diverging=80,
        min_tangent_before=10.0,
        min_tangent_after=10.0,
    ))
    lib.register(TurnoutCatalogEntry(
        catalog_id="Rz-60E1-1:18.5-1200",
        description="Rozjazd zwyczajny 60E1, 1:18.5, R=1200m",
        rail_type="60E1",
        turnout_type=TurnoutType.SIMPLE,
        frog_ratio=18,
        curve_radius=1200.0,
        total_length=65.360,
        speed_through=200,
        speed_diverging=100,
        min_tangent_before=12.0,
        min_tangent_after=12.0,
    ))
    lib.register(TurnoutCatalogEntry(
        catalog_id="Rz-60E1-1:26.5-2500",
        description="Rozjazd zwyczajny 60E1, 1:26.5, R=2500m (KDP)",
        rail_type="60E1",
        turnout_type=TurnoutType.SIMPLE,
        frog_ratio=26,
        curve_radius=2500.0,
        total_length=97.000,
        speed_through=250,
        speed_diverging=130,
        min_tangent_before=15.0,
        min_tangent_after=15.0,
        notes="Rozjazd do linii dużych prędkości (KDP)",
    ))

    # ========================================================================
    # Symmetric turnouts
    # ========================================================================
    lib.register(TurnoutCatalogEntry(
        catalog_id="Rs-S49-1:9-300",
        description="Rozjazd symetryczny S49, 1:9, R=300m",
        rail_type="S49",
        turnout_type=TurnoutType.SYMMETRIC,
        frog_ratio=9,
        curve_radius=300.0,
        total_length=22.350,
        speed_through=40,
        speed_diverging=40,
        min_tangent_before=6.0,
        min_tangent_after=6.0,
    ))
    lib.register(TurnoutCatalogEntry(
        catalog_id="Rs-60E1-1:9-300",
        description="Rozjazd symetryczny 60E1, 1:9, R=300m",
        rail_type="60E1",
        turnout_type=TurnoutType.SYMMETRIC,
        frog_ratio=9,
        curve_radius=300.0,
        total_length=23.500,
        speed_through=50,
        speed_diverging=50,
        min_tangent_before=6.0,
        min_tangent_after=6.0,
    ))

    # ========================================================================
    # Curved turnouts (łuki na torze odchylonym i zasadniczym)
    # ========================================================================
    lib.register(TurnoutCatalogEntry(
        catalog_id="Rk-60E1-1:12-500/2000",
        description="Rozjazd krzywoliniowy 60E1, 1:12, R=500/2000m",
        rail_type="60E1",
        turnout_type=TurnoutType.CURVED,
        frog_ratio=12,
        curve_radius=500.0,
        total_length=42.500,
        speed_through=80,
        speed_diverging=60,
        min_tangent_before=8.0,
        min_tangent_after=8.0,
        notes="Tor zasadniczy R=2000m, tor odchylony R=500m",
    ))

    # ========================================================================
    # 49E1 rail turnouts (intermediate)
    # ========================================================================
    lib.register(TurnoutCatalogEntry(
        catalog_id="Rz-49E1-1:9-190",
        description="Rozjazd zwyczajny 49E1, 1:9, R=190m",
        rail_type="49E1",
        turnout_type=TurnoutType.SIMPLE,
        frog_ratio=9,
        curve_radius=190.0,
        total_length=24.630,
        speed_through=100,
        speed_diverging=40,
        min_tangent_before=6.0,
        min_tangent_after=6.0,
    ))
    lib.register(TurnoutCatalogEntry(
        catalog_id="Rz-49E1-1:9-300",
        description="Rozjazd zwyczajny 49E1, 1:9, R=300m",
        rail_type="49E1",
        turnout_type=TurnoutType.SIMPLE,
        frog_ratio=9,
        curve_radius=300.0,
        total_length=27.095,
        speed_through=120,
        speed_diverging=40,
        min_tangent_before=6.0,
        min_tangent_after=6.0,
    ))
    lib.register(TurnoutCatalogEntry(
        catalog_id="Rz-49E1-1:12-500",
        description="Rozjazd zwyczajny 49E1, 1:12, R=500m",
        rail_type="49E1",
        turnout_type=TurnoutType.SIMPLE,
        frog_ratio=12,
        curve_radius=500.0,
        total_length=39.264,
        speed_through=120,
        speed_diverging=60,
        min_tangent_before=8.0,
        min_tangent_after=8.0,
    ))

    return lib


# Module-level singleton
TURNOUT_LIBRARY = _build_default_library()
