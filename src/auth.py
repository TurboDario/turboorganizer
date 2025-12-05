"""Authentication helpers for Google APIs."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/calendar.events",
]
TOKEN_PATH = Path("token.json")
CREDENTIALS_PATH = Path("credentials.json")


def _build_flow() -> InstalledAppFlow:
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            "Missing credentials.json. Follow the README to create an OAuth client."
        )
    return InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)


def load_credentials(force_reauth: bool = False) -> Credentials:
    """Load credentials from disk or start a new OAuth flow."""

    creds: Optional[Credentials] = None
    if TOKEN_PATH.exists() and not force_reauth:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        flow = _build_flow()
        creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def clear_credentials() -> None:
    """Remove any cached OAuth tokens from disk."""

    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
