# TurboOrganizer 🚀

A Streamlit-based "time blocking" assistant that bridges Google Tasks and Google Calendar. Fetch tasks, filter by the time you have, and schedule them instantly to beat procrastination.

## Features
- OAuth2 login with Google (Tasks + Calendar scopes)
- Treats each Google Task List as a project
- Parses task durations from titles like `Write script [45m]` (defaults to 15 minutes)
- Sidebar decision engine: available time + energy level
- One-click "Schedule now" to create calendar events, with optional auto-complete of the task

## Prerequisites
- Python 3.10+
- A Google Cloud project with the **Google Tasks API** and **Google Calendar API** enabled

### Create OAuth credentials
1. Go to the [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Create an **OAuth client ID** for a **Desktop application**.
3. Download the `credentials.json` file and place it in the project root (next to `app.py`).
4. The app will save your OAuth token in `token.json` after the first login (ignored by Git).

## Setup
```bash
python -m venv .venv

source .venv/bin/activate
or
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

## Running the app
```bash
streamlit run app.py
```

The first run opens a browser window for OAuth. After granting access, a `token.json` file is stored locally so you won't need to log in every time.

## Environment variables (optional)
- None required; all credentials are loaded from `credentials.json` and `token.json` on disk.

## Project structure
```
.
├── app.py
├── requirements.txt
├── packages.txt
├── .gitignore
└── src
    ├── auth.py
    ├── services.py
    └── utils.py
```

## Development notes
- Uses `st.session_state` for login and task cache.
- Errors during auth or API calls surface in the UI.
- Default task duration is 15 minutes when no `[XXm]` tag is found.
