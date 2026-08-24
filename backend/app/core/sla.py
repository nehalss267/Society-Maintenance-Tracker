from datetime import datetime, timedelta

from app.core.config import settings


# Category-specific SLA targets in days (architecture.md SLA matrix).
# Categories not listed fall back to OVERDUE_THRESHOLD_DAYS.
CATEGORY_SLA_DAYS: dict[str, int] = {
    "PLUMBING": 3,
    "ELECTRICAL": 2,
    "CLEANING": 2,
    "SECURITY": 1,
}

OTHER_CATEGORY = "OTHER"

VALID_CATEGORIES: list[str] = [
    *CATEGORY_SLA_DAYS.keys(),
    OTHER_CATEGORY,
]


def is_valid_category(category: str) -> bool:
    return category.strip().upper() in VALID_CATEGORIES


def get_target_days(category: str) -> int:
    """SLA days for a category; unknown categories use the global threshold."""
    normalized = category.strip().upper()
    return CATEGORY_SLA_DAYS.get(
        normalized,
        settings.OVERDUE_THRESHOLD_DAYS,
    )


def compute_due_at(created_at: datetime, category: str) -> datetime:
    return created_at + timedelta(days=get_target_days(category))


def is_complaint_overdue(
    *,
    status_value: str,
    due_at: datetime | None,
    resolved: bool = False,
    now: datetime | None = None,
) -> bool:
    """Derived overdue state - never trusted as stored truth (principle #9).

    A complaint is overdue when it is unresolved AND its SLA due date has passed.
    """
    if resolved or status_value == "RESOLVED":
        return False

    if due_at is None:
        return False

    current = now or datetime.utcnow()
    return current > due_at
