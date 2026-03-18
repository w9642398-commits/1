"""Validation result types used across the system."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


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
