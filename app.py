from datetime import date, datetime, timezone

import streamlit as st

from src.auth import SCOPES, clear_credentials, load_credentials
from src.services import fetch_tasks, schedule_task, snooze_task
from src.utils import energy_badge, filter_tasks_by_time

st.set_page_config(page_title="TurboOrganizer", page_icon="🚀", layout="wide")

st.title("🚀 TurboOrganizer: Time Blocking that fights procrastination")
st.caption(
    "Connect Google Tasks to Google Calendar, pick how much time you have, and schedule work instantly."
)

if "credentials" not in st.session_state:
    st.session_state.credentials = None
if "tasks" not in st.session_state:
    st.session_state.tasks = []
if "tasks_loaded" not in st.session_state:
    st.session_state.tasks_loaded = False


def remove_task_from_state(task_id: str) -> None:
    st.session_state.tasks = [task for task in st.session_state.tasks if task.get("id") != task_id]


with st.sidebar:
    st.header("Google Auth")
    st.write("The app needs access to Google Tasks and Calendar with the scopes below:")
    st.code("\n".join(SCOPES))

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

if not st.session_state.credentials:
    st.warning("Connect your Google account to fetch tasks.")
elif not st.session_state.tasks_loaded:
    st.info("Click 'Load my Tasks' to see your Google Tasks inbox.")
else:
    filtered_tasks = filter_tasks_by_time(st.session_state.tasks, time_available)
    st.subheader("Suggested tasks")
    st.caption(f"Showing tasks that fit within {time_available} minutes. {energy_badge(energy_level)}")

    if not filtered_tasks:
        st.success("No tasks fit the current window. Enjoy a break or widen the time range!")
    else:
        for task in filtered_tasks:
            with st.container(border=True):
                cols = st.columns([3, 2, 1, 1])
                cols[0].markdown(
                    f"**{task['title']}**\n\n"
                    f"Project: `{task['project']}`\n\n"
                    f"Duration: {task['duration']} min"
                )

                mark_done = cols[1].checkbox(
                    "Mark completed after scheduling",
                    value=True,
                    key=f"done_{task['id']}",
                )
                schedule_date = cols[1].date_input(
                    "Schedule date",
                    value=date.today(),
                    key=f"date_{task['id']}",
                )
                schedule_time = cols[1].time_input(
                    "Schedule time (UTC)",
                    value=datetime.now(timezone.utc).time().replace(second=0, microsecond=0),
                    step=300,
                    key=f"time_{task['id']}",
                )

                if cols[2].button("Schedule now", key=f"schedule_{task['id']}"):
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

                if cols[3].button("Schedule at", key=f"schedule_at_{task['id']}"):
                    try:
                        start_at = datetime.combine(schedule_date, schedule_time).replace(tzinfo=timezone.utc)
                        event = schedule_task(
                            st.session_state.credentials,
                            task,
                            mark_complete=mark_done,
                            start_time=start_at,
                        )
                        remove_task_from_state(task["id"])
                        st.success(
                            f"Scheduled on Google Calendar at {event['start']['dateTime']} (UTC)"
                        )
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Could not schedule at chosen time: {exc}")

                if cols[3].button("Snooze 💤", key=f"snooze_{task['id']}"):
                    try:
                        snooze_task(st.session_state.credentials, task, days=1)
                        remove_task_from_state(task["id"])
                        st.info("Snoozed to tomorrow.")
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Could not snooze task: {exc}")
