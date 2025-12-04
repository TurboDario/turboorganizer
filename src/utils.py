"""Utility helpers for task parsing and filtering."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, MutableMapping

DEFAULT_DURATION_MINUTES = 15
DURATION_PATTERN = re.compile(r"\[(\d+)\s*m\]", re.IGNORECASE)


def parse_task_duration(title: str, default: int = DEFAULT_DURATION_MINUTES) -> int:
    """Extract a duration in minutes from a task title.

    The parser looks for markers such as ``[45m]`` inside the title. If no
    marker is found, ``default`` minutes are returned.
    """

    if not title:
        return default

    match = DURATION_PATTERN.search(title)
    if not match:
        return default

    try:
        return int(match.group(1))
    except (TypeError, ValueError):
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


def filter_tasks_by_time(tasks: Iterable[MutableMapping], minutes_available: int) -> List[MutableMapping]:
    """Return tasks whose duration fits within the available window."""

    return [task for task in tasks if int(task.get("duration", DEFAULT_DURATION_MINUTES)) <= minutes_available]


def energy_badge(level: str) -> str:
    """Return a friendly label for an energy level selection."""

    normalized = (level or "").strip().lower()
    if normalized == "high":
        return "⚡ High focus"
    if normalized == "medium":
        return "🔆 Medium energy"
    return "🌱 Low lift"
