"""Google Tasks and Calendar service helpers."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, MutableMapping

from dateutil import tz
from googleapiclient.discovery import build

from .utils import parse_task_duration, round_up_to_five_minutes


def build_tasks_service(creds):
    return build("tasks", "v1", credentials=creds, cache_discovery=False)


def build_calendar_service(creds):
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def fetch_tasks(creds) -> List[MutableMapping]:
    """Fetch all tasks grouped by their Google Task List (projects)."""

    service = build_tasks_service(creds)
    projects = service.tasklists().list(maxResults=200).execute().get("items", [])
    collected: List[MutableMapping] = []

    for project in projects:
        project_id = project.get("id")
        project_name = project.get("title", "Untitled Project")
        items = (
            service.tasks()
            .list(tasklist=project_id, showCompleted=False, showHidden=False)
            .execute()
            .get("items", [])
        )
        for task in items:
            title = task.get("title", "Untitled Task")
            duration = parse_task_duration(title)
            collected.append(
                {
                    "id": task.get("id"),
                    "title": title,
                    "project": project_name,
                    "duration": duration,
                    "tasklist": project_id,
                    "notes": task.get("notes"),
                }
            )
    return collected


def schedule_task(creds, task: MutableMapping, mark_complete: bool = False) -> Dict:
    """Create a Calendar event for the provided task and optionally complete it."""

    calendar = build_calendar_service(creds)
    start_time = round_up_to_five_minutes(datetime.now(tz.UTC))
    duration_minutes = int(task.get("duration", 15))
    end_time = start_time + timedelta(minutes=duration_minutes)

    event_body = {
        "summary": task.get("title", "Task"),
        "description": f"From TurboOrganizer project: {task.get('project', 'Inbox')}",
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": str(start_time.tzinfo),
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": str(end_time.tzinfo),
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
    service.tasks().update(
        tasklist=task["tasklist"],
        task=task["id"],
        body={"status": "completed"},
    ).execute()
