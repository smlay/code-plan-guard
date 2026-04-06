"""code-plan-guard: Plan-stage integrity guard for AI-generated change plans."""

from code_plan_guard.constants import __version__
from code_plan_guard.pipeline import validate_plan
from code_plan_guard.result import BlockerItem, ValidationResult, WarningItem

__all__ = [
    "__version__",
    "validate_plan",
    "ValidationResult",
    "BlockerItem",
    "WarningItem",
]
