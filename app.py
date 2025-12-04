import streamlit as st

from src.auth import SCOPES, clear_credentials, load_credentials
from src.services import fetch_tasks, schedule_task
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
                cols = st.columns([3, 2, 1])
                cols[0].markdown(
                    f"**{task['title']}**\n\n"
                    f"Project: `{task['project']}`\n\n"
                    f"Duration: {task['duration']} min"
                )
                mark_done = cols[1].checkbox(
                    "Mark completed after scheduling", key=f"done_{task['id']}"
                )
                if cols[2].button("Schedule now", key=f"schedule_{task['id']}"):
                    try:
                        event = schedule_task(
                            st.session_state.credentials, task, mark_complete=mark_done
                        )
                        st.success(
                            f"Scheduled on Google Calendar starting at {event['start']['dateTime']}"
                        )
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Could not schedule: {exc}")
