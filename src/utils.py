"""Utility helpers for task parsing and filtering."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, MutableMapping

DEFAULT_DURATION_MINUTES = 15
DURATION_PATTERN = re.compile(
    r"(?<!\d)(?:(?P<hours>\d+)\s*h)?\s*(?:(?P<minutes>\d+)\s*m)?(?![a-zA-Z0-9])",
    re.IGNORECASE,
)


def parse_task_duration(
    title: str, notes: str | None = None, default: int | None = DEFAULT_DURATION_MINUTES
) -> int | None:
    """Extract a duration in minutes from task title or notes.

    Supports patterns like ``80m`` or ``1h20m`` appearing anywhere in the text.
    If nothing is found, ``default`` minutes are returned.
    """

    text = f"{title or ''} {notes or ''}".lower()
    for match in DURATION_PATTERN.finditer(text):
        hours_part = match.group("hours")
        minutes_part = match.group("minutes")
        if not hours_part and not minutes_part:
            continue
        try:
            total_minutes = int(hours_part or 0) * 60 + int(minutes_part or 0)
        except (TypeError, ValueError):
            continue
        if total_minutes > 0:
            return total_minutes
    return default


def round_up_to_five_minutes(moment: datetime | None = None) -> datetime:
    """Round the provided timestamp up to the nearest 5 minutes."""

    if moment is None:
        moment = datetime.now(timezone.utc)

    rounded = moment.replace(second=0, microsecond=0)
    remainder = rounded.minute % 5
    if remainder:
        rounded += timedelta(minutes=5 - remainder)
    if rounded < moment:
        rounded += timedelta(minutes=5)
    return rounded


def filter_tasks_by_time(tasks: Iterable[MutableMapping], minutes_available: int | None) -> List[MutableMapping]:
    """Return tasks whose duration fits within the available window.

    Tasks with undefined duration (None) are only included when minutes_available is None (indefinido).
    """

    if minutes_available is None:
        return list(tasks)
    filtered = []
    for task in tasks:
        duration = task.get("duration")
        if duration is None:
            continue
        try:
            duration_int = int(duration)
        except (TypeError, ValueError):
            continue
        if duration_int <= minutes_available:
            filtered.append(task)
    return filtered


def energy_badge(level: str) -> str:
    """Return a friendly label for an energy level selection."""

    normalized = (level or "").strip().lower()
    if normalized == "high":
        return "⚡ High focus"
    if normalized == "medium":
        return "🔆 Medium energy"
    return "🌱 Low lift"
