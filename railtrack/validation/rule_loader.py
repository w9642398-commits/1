"""Load validation rules from YAML configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SpeedCategoryRules:
    """Rules for a specific speed category."""
    name: str
    max_speed: float
    min_radius: float
    min_transition_length: float
    max_cant: float
    max_cant_deficiency: float
    max_gradient: float
    min_vertical_curve_radius: float
    min_tangent_between_curves: float


@dataclass
class GlobalRules:
    max_cant: float = 0.160
    track_gauge: float = 1.435
    gravity: float = 9.81
    min_cant_ramp_ratio_normal: float = 600
    min_cant_ramp_ratio_high_speed: float = 800
    max_dD_dt: float = 0.055


@dataclass
class TurnoutRules:
    min_tangent_before_turnout: float = 10.0
    min_tangent_after_turnout: float = 10.0


@dataclass
class RuleSet:
    """Complete set of rules loaded from config."""
    metadata: dict = field(default_factory=dict)
    speed_categories: list[SpeedCategoryRules] = field(default_factory=list)
    global_rules: GlobalRules = field(default_factory=GlobalRules)
    turnout_rules: TurnoutRules = field(default_factory=TurnoutRules)

    def rules_for_speed(self, speed_kmh: float) -> SpeedCategoryRules | None:
        """Find the applicable speed category for a given design speed."""
        for cat in self.speed_categories:
            if speed_kmh <= cat.max_speed:
                return cat
        # Return the highest category if speed exceeds all
        return self.speed_categories[-1] if self.speed_categories else None


def load_rules(path: Path | str | None = None) -> RuleSet:
    """Load rules from YAML file. Uses default ST-T1-A6 if no path given."""
    if path is None:
        path = Path(__file__).parent.parent / "config" / "rules_st_t1_a6.yaml"
    else:
        path = Path(path)

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    speed_cats = []
    for sc in data.get("speed_categories", []):
        speed_cats.append(SpeedCategoryRules(
            name=sc["name"],
            max_speed=sc["max_speed"],
            min_radius=sc["min_radius"],
            min_transition_length=sc["min_transition_length"],
            max_cant=sc["max_cant"],
            max_cant_deficiency=sc["max_cant_deficiency"],
            max_gradient=sc["max_gradient"],
            min_vertical_curve_radius=sc["min_vertical_curve_radius"],
            min_tangent_between_curves=sc["min_tangent_between_curves"],
        ))

    gr = data.get("global_rules", {})
    global_rules = GlobalRules(
        max_cant=gr.get("max_cant", 0.160),
        track_gauge=gr.get("track_gauge", 1.435),
        gravity=gr.get("gravity", 9.81),
        min_cant_ramp_ratio_normal=gr.get("min_cant_ramp_ratio_normal", 600),
        min_cant_ramp_ratio_high_speed=gr.get("min_cant_ramp_ratio_high_speed", 800),
        max_dD_dt=gr.get("max_dD_dt", 0.055),
    )

    tr = data.get("turnout_rules", {})
    turnout_rules = TurnoutRules(
        min_tangent_before_turnout=tr.get("min_tangent_before_turnout", 10.0),
        min_tangent_after_turnout=tr.get("min_tangent_after_turnout", 10.0),
    )

    return RuleSet(
        metadata=data.get("metadata", {}),
        speed_categories=speed_cats,
        global_rules=global_rules,
        turnout_rules=turnout_rules,
    )
