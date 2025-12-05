import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
import unicodedata
from urllib.parse import quote

import streamlit as st

from src.auth import SCOPES, TOKEN_PATH, clear_credentials, load_credentials
from src.services import fetch_tasks, schedule_task, snooze_task
from src.utils import energy_badge, filter_tasks_by_time

st.set_page_config(page_title="TurboOrganizer", page_icon="TO", layout="wide")

st.title("TurboOrganizer")

st.markdown(
    """
    <style>
    /* Turn radios into pill buttons for the mode selector */
    div[data-testid="stRadio"] > div {
        flex-direction: row;
        gap: 0.75rem;
        width: 100%;
    }
    /* Hide the main radio label ("Modo") container so it doesn't render as a button */
    div[data-testid="stRadio"] > label {
        display: none !important;
    }
    /* Hide radio input and ensure it doesn't affect layout */
    div[data-testid="stRadio"] input {
        display: none !important;
        width: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        position: absolute !important;
    }
    div[data-testid="stRadio"] svg {
        display: none !important;
        width: 0 !important;
        margin: 0 !important;
    }
    div[data-testid="stRadio"] [data-baseweb="radio"] {
        padding: 0 !important;
        margin: 0 !important;
        width: 100%;
        display: flex;
        align-items: stretch;
    }
    div[data-testid="stRadio"] [data-baseweb="radio"] > div:first-child {
        display: none !important;
        width: 0 !important;
    }
    div[data-testid="stRadio"] [data-baseweb="radio"] > div:last-child {
        width: 100%;
        display: flex;
    }
    div[data-testid="stRadio"] label {
        display: flex;
        flex: 1 1 0;
        min-width: 200px;
        border: 1px solid #333;
        background: #111;
        color: #fafafa;
        padding: 48px 32px !important;
        border-radius: 14px;
        cursor: pointer;
        transition: all 0.15s ease;
        justify-content: center;
        align-items: center;
        text-align: center;
        margin: 0 !important;
        width: 100%;
        gap: 0;
        font-size: 1.4rem;
        font-weight: 600;
        min-height: 48px;
    }
    div[data-testid="stRadio"] label > div,
    div[data-testid="stRadio"] label p,
    div[data-testid="stRadio"] label span {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        text-align: center !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    div[data-testid="stRadio"] label:hover {
        border-color: #555;
    }
    div[data-testid="stRadio"] [data-baseweb="radio"] > div:first-child {
        display: none;
    }
    div[data-testid="stRadio"] [data-baseweb="radio"] {
        padding-left: 0;
    }
    div[data-testid="stRadio"] label:has(input:checked) {
        background: #ff5f57;
        border-color: #ff5f57;
        color: #ffffff;
        box-shadow: 0 4px 12px rgba(255,95,87,0.35);
    }
    .task-link {
        color: inherit !important;
        text-decoration: none !important;
    }
    .task-link:hover {
        text-decoration: underline !important;
    }
    /* Hide default Streamlit menu */
    #MainMenu { visibility: hidden; }
    /* Pill style for filter buttons */
    div[data-testid="baseButton-primary"] > button,
    div[data-testid="baseButton-secondary"] > button {
        border: 1px solid #333;
        background: #111;
        color: #fafafa;
        padding: 10px 16px;
        border-radius: 10px;
        font-weight: 500;
        transition: all 0.15s ease;
    }
    /* Full-width, consistent spacing in the sidebar */
    div[data-testid="stSidebar"] div[data-testid^="baseButton"] > button {
        width: 100%;
        margin-bottom: 8px;
    }
    div[data-testid="baseButton-secondary"] > button:hover {
        border-color: #555;
    }
    div[data-testid="baseButton-primary"] > button {
        background: #ff5f57;
        border-color: #ff5f57;
        color: #ffffff;
        box-shadow: 0 4px 12px rgba(255,95,87,0.35);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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
    if minutes is None:
        return "Indefinido"
    mins = max(int(minutes or 0), 0)
    hours, rem = divmod(mins, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if rem or not parts:
        parts.append(f"{rem}min")
    return " ".join(parts)


def load_tasks():
    try:
        st.session_state.tasks = fetch_tasks(st.session_state.credentials)
        st.session_state.tasks_loaded = True
        st.success("Tasks loaded from Google Tasks")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Unable to load tasks: {exc}")


with st.sidebar:
    if st.button("Connect Google", type="primary", use_container_width=True):
        try:
            st.session_state.credentials = load_credentials()
            st.success("Authenticated with Google!")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Authentication failed: {exc}")

    if st.session_state.credentials and st.button("Refresh token", use_container_width=True):
        try:
            st.session_state.credentials = load_credentials(force_reauth=True)
            st.success("Token refreshed")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to refresh: {exc}")

    if st.session_state.credentials and st.button("Load my Tasks", type="primary", use_container_width=True):
        load_tasks()

    if st.session_state.credentials and st.button("Disconnect", use_container_width=True):
        clear_credentials()
        st.session_state.credentials = None
        st.session_state.tasks = []
        st.session_state.tasks_loaded = False
        st.info("Signed out and cache cleared.")

st.sidebar.divider()
st.sidebar.subheader("Menú")
if st.sidebar.button("🔄 Reiniciar app", use_container_width=True):
    st.rerun()
if st.sidebar.button("🧹 Limpiar caché", use_container_width=True):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.success("Caché limpiada")
with st.sidebar.expander("Acerca de"):
    st.markdown(
        """
        **TurboOrganizer**  
        - Integra Google Tasks y Google Calendar.  
        - Filtra por tiempo, energía, fecha y tags.  
        - Programa tareas directamente en tu calendario.
        """
    )
st.sidebar.markdown(
    "[Ayuda de Streamlit](https://docs.streamlit.io/) · "
    "[Reportar problema](https://github.com/)  ",
    unsafe_allow_html=True,
)

st.markdown("")
with st.container(border=True):
    st.subheader("Decision Engine")
    engine_cols = st.columns([2, 1])
    time_values = list(range(15, 241, 15)) + [1440, -1]  # -1 = indefinido

    def time_label_from_value(val: int) -> str:
        if val == -1:
            return "Indefinido"
        if val == 1440:
            return "1 día"
        return f"{val} min"

    default_time_value = -1  # Indefinido by default
    saved_value = st.session_state.get("time_choice", default_time_value)
    if saved_value not in time_values:
        st.session_state.pop("time_choice", None)
        saved_value = default_time_value

    time_choice_value = engine_cols[0].select_slider(
        "¿Cuánto tiempo tienes?",
        options=time_values,
        value=saved_value,
        format_func=time_label_from_value,
        key="time_choice",
    )
    time_available = None if time_choice_value == -1 else time_choice_value
    energy_level = engine_cols[1].selectbox(
        "Nivel de energía", ["Low", "Medium", "High"], index=1, key="energy_main"
    )


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

    def extract_tags(task) -> set[str]:
        pattern = re.compile(r"#([A-Za-z0-9_-]+)")
        title_tags = pattern.findall(task.get('title', ''))
        note_tags = pattern.findall(task.get('notes', '') or '')
        return {tag.lower() for tag in title_tags + note_tags}

    def normalize_project(name: str) -> str:
        base = unicodedata.normalize("NFD", (name or '').strip().lower())
        return "".join(ch for ch in base if unicodedata.category(ch) != "Mn")

    def is_in_inbox(task) -> bool:
        normalized = normalize_project(task.get('project'))
        return normalized in {'buzon', 'inbox', ''}

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

    def task_link(task) -> str | None:
        task_id = task.get("id")
        tasklist = task.get("tasklist")
        if not task_id or not tasklist:
            return None
        list_q = quote(str(tasklist))
        task_q = quote(str(task_id))
        # Use the hash fragment to jump directly to the task inside the list.
        return f"https://tasks.google.com/embed/list?list={list_q}#task/{task_q}"

    mode_options = ["Solo hoy", "Buzon", "Todo"]
    if st.session_state.filter_mode not in mode_options:
        st.session_state.filter_mode = mode_options[0]
    st.caption("Modo")
    st.session_state.filter_mode = st.radio(
        "Modo",
        mode_options,
        horizontal=True,
        index=mode_options.index(st.session_state.filter_mode),
        key="filter_mode_radio",
        label_visibility="collapsed",
    )

    if st.session_state.filter_mode == "Buzon":
        filtered_tasks = [task for task in filtered_tasks if is_in_inbox(task)]
    elif st.session_state.filter_mode == "Solo hoy":
        filtered_tasks = [task for task in filtered_tasks if is_due_today(task)]

    st.subheader("Suggested tasks")
    if time_available is None:
        time_summary = "sin limite de tiempo"
    elif time_available == 1440:
        time_summary = "dentro de 1 dia"
    else:
        time_summary = f"dentro de {time_available} minutos"
    st.caption(f"Mostrando tareas que caben {time_summary}. {energy_badge(energy_level)}")

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

                task_url = task_link(task)
                if task_url:
                    title_md = (
                        f"<a class='task-link' href='{task_url}' target='_blank'>"
                        f"<strong>{title_prefix}{task['title']} ↗</strong></a>"
                    )
                else:
                    title_md = f"<strong>{title_prefix}{task['title']}</strong>"
                cols[0].markdown(
                    f"{title_md}<br><br>"
                    f"Project: `{task['project']}`<br><br>"
                    f"Duration: {format_duration(task.get('duration'))}<br><br>"
                    f"Tags: {tags_display}",
                    unsafe_allow_html=True,
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
