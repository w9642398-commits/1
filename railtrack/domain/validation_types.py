"""Validation result types used across the system."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationRule:
    """A single configurable validation rule.

    Represents a named check with configurable parameters that the validator
    can evaluate against alignment data.
    """
    code: str
    title: str
    description: str
    severity: Severity
    category: str  # e.g. "horizontal", "vertical", "cant", "turnout"
    parameters: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def with_parameters(self, **kwargs: Any) -> ValidationRule:
        """Return a copy with updated parameters."""
        new_params = {**self.parameters, **kwargs}
        return ValidationRule(
            code=self.code,
            title=self.title,
            description=self.description,
            severity=self.severity,
            category=self.category,
            parameters=new_params,
            enabled=self.enabled,
        )


@dataclass
class ValidationIssue:
    """Single validation finding."""
    severity: Severity
    code: str
    title: str
    message: str
    affected_object: str  # name or identifier of the affected element
    chainage: float | None = None
    chainage_end: float | None = None
    expected_value: str = ""
    actual_value: str = ""
    rule_reference: str = ""
    suggestion: str = ""

    @property
    def chainage_display(self) -> str:
        if self.chainage is None:
            return ""
        if self.chainage_end is not None:
            return f"{self.chainage:.3f} - {self.chainage_end:.3f}"
        return f"{self.chainage:.3f}"
