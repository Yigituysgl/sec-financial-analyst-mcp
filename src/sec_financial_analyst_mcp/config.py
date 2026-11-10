"""Runtime settings loaded from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "")
REQUEST_TIMEOUT_SECONDS = 30.0


def get_sec_user_agent() -> str:
    """Return the SEC User-Agent, failing early if it is missing.

    SEC rejects anonymous requests, so a clear error here is better
    than an unexplained 403 response later.
    """
    if not SEC_USER_AGENT.strip():
        raise RuntimeError(
            "SEC_USER_AGENT is not set. Copy .env.example to .env "
            "and add your name and email."
        )
    return SEC_USER_AGENT