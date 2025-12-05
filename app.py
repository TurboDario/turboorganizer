import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import streamlit as st

from src.auth import SCOPES, TOKEN_PATH, clear_credentials, load_credentials
from src.services import fetch_tasks, schedule_task, snooze_task
from src.utils import energy_badge, filter_tasks_by_time

st.set_page_config(page_title="TurboOrganizer", page_icon="TO", layout="wide")

st.title("TurboOrganizer")

if "credentials" not in st.session_state:
    st.session_state.credentials = None
if "tasks" not in st.session_state:
    st.session_state.tasks = []
if "tasks_loaded" not in st.session_state:
    st.session_state.tasks_loaded = False
if "auto_auth_attempted" not in st.session_state:
    st.session_state.auto_auth_attempted = False
if "auto_tasks_attempted" not in st.session_state:
    st.session_state.auto_tasks_attempted = False
if "filter_mode" not in st.session_state:
    st.session_state.filter_mode = "Solo hoy"
if "filter_date" not in st.session_state:
    st.session_state.filter_date = None
if "filter_tags" not in st.session_state:
    st.session_state.filter_tags = []
DEFAULT_TIMEZONE = ZoneInfo("Europe/Madrid")

# Auto-connect if a cached token exists, but avoid triggering a fresh OAuth flow implicitly.
if (
    not st.session_state.credentials
    and not st.session_state.auto_auth_attempted
    and TOKEN_PATH.exists()
):
    try:
        st.session_state.credentials = load_credentials()
        st.session_state.auto_auth_attempted = True
        st.toast("Reconnected with saved Google token.", icon="✅")
    except Exception as exc:  # noqa: BLE001
        st.session_state.auto_auth_attempted = True
        st.error(f"Auto-connection failed: {exc}")


def remove_task_from_state(task_id: str) -> None:
    st.session_state.tasks = [task for task in st.session_state.tasks if task.get("id") != task_id]


def format_duration(minutes: int | None) -> str:
    mins = max(int(minutes or 0), 0)
    hours, rem = divmod(mins, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if rem or not parts:
        parts.append(f"{rem}min")
    return " ".join(parts)


with st.sidebar:
    if st.button("Connect Google", type="primary"):
        try:
            st.session_state.credentials = load_credentials()
            st.success("Authenticated with Google!")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Authentication failed: {exc}")

    if st.session_state.credentials and st.button("Refresh token"):
        try:
            st.session_state.credentials = load_credentials(force_reauth=True)
            st.success("Token refreshed")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to refresh: {exc}")

    if st.session_state.credentials and st.button("Disconnect"):
        clear_credentials()
        st.session_state.credentials = None
        st.session_state.tasks = []
        st.session_state.tasks_loaded = False
        st.info("Signed out and cache cleared.")


st.sidebar.header("Decision Engine")
time_available = st.sidebar.slider("How much time do you have?", 15, 240, 60, step=15)
energy_level = st.sidebar.selectbox("Energy level", ["Low", "Medium", "High"], index=1)


def load_tasks():
    try:
        st.session_state.tasks = fetch_tasks(st.session_state.credentials)
        st.session_state.tasks_loaded = True
        st.success("Tasks loaded from Google Tasks")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Unable to load tasks: {exc}")


if st.session_state.credentials and st.button("Load my Tasks", type="primary"):
    load_tasks()

# If authenticated and tasks haven't been loaded yet, do it automatically once.
if (
    st.session_state.credentials
    and not st.session_state.tasks_loaded
    and not st.session_state.auto_tasks_attempted
):
    st.session_state.auto_tasks_attempted = True
    load_tasks()

if not st.session_state.credentials:
    st.warning("Connect your Google account to fetch tasks.")
elif not st.session_state.tasks_loaded:
    st.info("Click 'Load my Tasks' to see your Google Tasks inbox.")
else:
    filtered_tasks = filter_tasks_by_time(st.session_state.tasks, time_available)
    filters = st.columns([1, 1, 1])

    def normalize_project(name: str) -> str:
        return (name or '').strip().lower()

    def is_in_inbox(task) -> bool:
        return normalize_project(task.get('project')) == 'buzon'

    def is_due_today(task) -> bool:
        due_str = task.get('due')
        if not due_str:
            return False
        try:
            due_dt = datetime.fromisoformat(due_str)
        except ValueError:
            return False
        if due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=DEFAULT_TIMEZONE)
        return due_dt.date() == datetime.now(DEFAULT_TIMEZONE).date()

    def matches_exact_date(task, target_date: date | None) -> bool:
        if not target_date:
            return True
        due_str = task.get('due')
        if not due_str:
            return False
        try:
            due_dt = datetime.fromisoformat(due_str)
        except ValueError:
            return False
        if due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=DEFAULT_TIMEZONE)
        return due_dt.date() == target_date

    def extract_tags(task) -> set[str]:
        pattern = re.compile(r"#([A-Za-z0-9_-]+)")
        title_tags = pattern.findall(task.get('title', ''))
        note_tags = pattern.findall(task.get('notes', '') or '')
        return {tag.lower() for tag in title_tags + note_tags}

    all_tags = set()
    for t in st.session_state.tasks:
        all_tags |= extract_tags(t)
    tag_options = sorted(all_tags)

    st.session_state.filter_mode = filters[0].radio(
        'Modo',
        options=['Solo hoy', 'Buzon', 'Todo'],
        index=['Solo hoy', 'Buzon', 'Todo'].index(st.session_state.filter_mode),
        horizontal=True,
    )

    with filters[1].popover('Fecha'):
        date_value = st.date_input(
            'Elige fecha',
            value=st.session_state.filter_date or date.today(),
            key='filter_date_input',
        )
        st.session_state.filter_date = date_value
        if st.session_state.filter_date:
            if st.button('Quitar fecha', key='clear_date_filter'):
                st.session_state.filter_date = None

    with filters[2].popover('Tags'):
        if not tag_options:
            st.caption('Sin tags. Usa #tag en titulo o notas.')
        else:
            tag_cols = st.columns(min(len(tag_options), 4))
            for idx, tag in enumerate(tag_options):
                col = tag_cols[idx % len(tag_cols)]
                active = tag in st.session_state.filter_tags
                style = 'background-color:#d32f2f;color:white;' if active else 'background-color:#111;color:white;'
                if col.button(f"#{tag}", key=f'tag_{tag}'):
                    if active:
                        st.session_state.filter_tags.remove(tag)
                    else:
                        st.session_state.filter_tags.append(tag)
                col.markdown(
                    f"<div style="{style} padding:6px 10px; border-radius:6px; border:1px solid #333; text-align:center; margin-top:4px;">#{tag}</div>",
                    unsafe_allow_html=True,
                )

    if st.session_state.filter_mode == 'Buzon':
        filtered_tasks = [task for task in filtered_tasks if is_in_inbox(task)]
    elif st.session_state.filter_mode == 'Solo hoy':
        filtered_tasks = [task for task in filtered_tasks if is_due_today(task)]

    if st.session_state.filter_date:
        filtered_tasks = [
            task for task in filtered_tasks if matches_exact_date(task, st.session_state.filter_date)
        ]

    if st.session_state.filter_tags:
        filtered_tasks = [
            task
            for task in filtered_tasks
            if extract_tags(task).intersection(st.session_state.filter_tags)
        ]

        st.subheader("Suggested tasks")
    st.caption(f"Showing tasks that fit within {time_available} minutes. {energy_badge(energy_level)}")

    if not filtered_tasks:
        st.success("No tasks fit the current window. Enjoy a break or widen the time range!")
    else:
        for task in filtered_tasks:
            with st.container(border=True):
                cols = st.columns([3, 2])
                is_routine = bool(task.get("is_routine"))
                title_prefix = "ROUTINE | " if is_routine else ""

                if is_routine:
                    cols[0].warning("Routine priority")

                tags_list = sorted(extract_tags(task))
                tags_display = ", ".join(f"#{t}" for t in tags_list) if tags_list else "None"

                cols[0].markdown(
                    f"{title_prefix}**{task['title']}**\n\n"
                    f"Project: `{task['project']}`\n\n"
                    f"Duration: {format_duration(task.get('duration'))}\n\n"
                    f"Tags: {tags_display}"
                )

                mark_done = cols[1].checkbox(
                    "Mark completed after scheduling",
                    value=True,
                    key=f"done_{task['id']}",
                )

                if cols[1].button("Schedule now", key=f"schedule_now_{task['id']}"):
                    try:
                        event = schedule_task(
                            st.session_state.credentials, task, mark_complete=mark_done
                        )
                        remove_task_from_state(task["id"])
                        st.success(
                            f"Scheduled on Google Calendar starting at {event['start']['dateTime']}"
                        )
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Could not schedule: {exc}")

                with cols[1].popover("Schedule at"):
                    with st.form(f"schedule_form_{task['id']}"):
                        schedule_date = st.date_input(
                            "Schedule date",
                            value=date.today(),
                            key=f"date_{task['id']}",
                        )
                        schedule_time = st.time_input(
                            "Schedule time (local)",
                            value=datetime.now(DEFAULT_TIMEZONE).time().replace(second=0, microsecond=0),
                            step=300,
                            key=f"time_{task['id']}",
                        )
                        submit_schedule = st.form_submit_button("Confirm Schedule")

                    if submit_schedule:
                        try:
                            start_at = datetime.combine(schedule_date, schedule_time).replace(tzinfo=DEFAULT_TIMEZONE)
                            event = schedule_task(
                                st.session_state.credentials,
                                task,
                                mark_complete=mark_done,
                                start_time=start_at,
                            )
                            remove_task_from_state(task["id"])
                            st.success(
                                f"Scheduled on Google Calendar at {event['start']['dateTime']} ({DEFAULT_TIMEZONE})"
                            )
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"Could not schedule at chosen time: {exc}")

                with cols[1].popover("Snooze"):
                    with st.form(f"snooze_form_{task['id']}"):
                        snooze_option = st.radio(
                            "Snooze until",
                            options=["Tomorrow", "Next Week", "Custom Date"],
                            horizontal=False,
                            key=f"snooze_option_{task['id']}",
                        )
                        custom_date = None
                        if snooze_option == "Custom Date":
                            custom_date = st.date_input(
                                "Pick date",
                                value=date.today(),
                                key=f"snooze_date_{task['id']}",
                            )
                        submit_snooze = st.form_submit_button("Confirm Snooze")

                    if submit_snooze:
                        try:
                            if snooze_option == "Tomorrow":
                                days = 1
                            elif snooze_option == "Next Week":
                                days = 7
                            else:
                                delta = (custom_date - date.today()).days if custom_date else 1
                                days = max(1, delta)

                            snooze_task(st.session_state.credentials, task, days=days)
                            remove_task_from_state(task["id"])
                            st.info(f"Snoozed to {days} day(s) ahead.")
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"Could not snooze task: {exc}")
