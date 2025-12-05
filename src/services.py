"""Google Tasks and Calendar service helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, MutableMapping

from dateutil import parser as date_parser
from googleapiclient.discovery import build

from .utils import parse_task_duration, round_up_to_five_minutes

ROUTINE_LIST_NAME = "Rutinas"


def build_tasks_service(creds):
    return build("tasks", "v1", credentials=creds, cache_discovery=False)


def build_calendar_service(creds):
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _parse_due_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = date_parser.isoparse(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def fetch_tasks(creds) -> List[MutableMapping]:
    """Fetch actionable tasks grouped by their Google Task List (projects)."""

    service = build_tasks_service(creds)
    projects = service.tasklists().list(maxResults=200).execute().get("items", [])
    collected: List[MutableMapping] = []
    now = datetime.now(timezone.utc).date()

    for project in projects:
        project_id = project.get("id")
        project_name = project.get("title", "Untitled Project")
        is_routine_list = project_name.strip().lower() == ROUTINE_LIST_NAME.lower()
        items = (
            service.tasks()
            .list(tasklist=project_id, showCompleted=False, showHidden=False)
            .execute()
            .get("items", [])
        )
        for task in items:
            due_date = _parse_due_date(task.get("due"))
            title = task.get("title", "Untitled Task")
            duration = parse_task_duration(title, task.get("notes"), default=None)
            is_overdue = bool(due_date and due_date.date() < now)
            collected.append(
                {
                    "id": task.get("id"),
                    "title": title,
                    "project": project_name,
                    "duration": duration,
                    "tasklist": project_id,
                    "notes": task.get("notes"),
                    "due": due_date.isoformat() if due_date else None,
                    "is_routine": is_routine_list,
                    "is_overdue": is_overdue,
                }
            )

    def sort_key(task: MutableMapping) -> tuple:
        # Lower tuple sorts earlier.
        priority_overdue = 0 if task.get("is_overdue") else 1
        priority_routine = 0 if task.get("is_routine") else 1
        return (priority_overdue, priority_routine, task.get("title", "").lower())

    return sorted(collected, key=sort_key)


def schedule_task(
    creds,
    task: MutableMapping,
    mark_complete: bool = False,
    start_time: datetime | None = None,
) -> Dict:
    """Create a Calendar event for the provided task and optionally complete it."""

    calendar = build_calendar_service(creds)
    start = start_time or round_up_to_five_minutes(datetime.now(timezone.utc))
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    duration_minutes = int(task.get("duration") or 15)
    end_time = start + timedelta(minutes=duration_minutes)
    time_zone = getattr(start.tzinfo, "key", None) or "UTC"

    event_body = {
        "summary": task.get("title", "Task"),
        "description": f"From TurboOrganizer project: {task.get('project', 'Inbox')}",
        "start": {
            "dateTime": start.isoformat(),
            "timeZone": time_zone,
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": time_zone,
        },
    }
    event = (
        calendar.events()
        .insert(calendarId="primary", body=event_body, sendUpdates="none")
        .execute()
    )

    if mark_complete:
        mark_task_complete(creds, task)

    return event


def mark_task_complete(creds, task: MutableMapping) -> None:
    service = build_tasks_service(creds)
    service.tasks().patch(
        tasklist=task["tasklist"],
        task=task["id"],
        body={"id": task["id"], "status": "completed"},
    ).execute()


def snooze_task(creds, task: MutableMapping, days: int = 1) -> MutableMapping:
    """Postpone a task by pushing its due date forward."""

    service = build_tasks_service(creds)
    new_due = (
        datetime.now(timezone.utc) + timedelta(days=days)
    ).replace(hour=0, minute=0, second=0, microsecond=0)

    return (
        service.tasks()
        .patch(
            tasklist=task["tasklist"],
            task=task["id"],
            body={"id": task["id"], "due": new_due.isoformat()},
        )
        .execute()
    )


def move_task(creds, task: MutableMapping, destination_tasklist: str) -> MutableMapping:
    """Move a task to another task list by recreating it and deleting the original."""

    service = build_tasks_service(creds)
    body = {
        "title": task.get("title"),
        "notes": task.get("notes"),
        "due": task.get("due"),
    }
    created = (
        service.tasks()
        .insert(tasklist=destination_tasklist, body=body)
        .execute()
    )
    service.tasks().delete(tasklist=task["tasklist"], task=task["id"]).execute()
    return created
