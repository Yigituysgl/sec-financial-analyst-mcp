"""HTTP client for SEC EDGAR endpoints."""

import threading
import time

import httpx

from sec_financial_analyst_mcp.config import REQUEST_TIMEOUT_SECONDS, get_sec_user_agent

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

# SEC allows 10 requests per second; staying at 8 leaves a safety margin.
MAX_REQUESTS_PER_SECOND = 8
_MIN_INTERVAL_SECONDS = 1 / MAX_REQUESTS_PER_SECOND

_rate_lock = threading.Lock()
_last_request_time = 0.0


def _wait_for_rate_limit() -> None:
    """Sleep just long enough to keep requests under SEC's fair-access limit."""
    global _last_request_time
    with _rate_lock:
        elapsed = time.monotonic() - _last_request_time
        if elapsed < _MIN_INTERVAL_SECONDS:
            time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
        _last_request_time = time.monotonic()


def fetch_json(url: str) -> dict:
    """Fetch a JSON document from SEC with the required identifying headers."""
    _wait_for_rate_limit()
    headers = {
        "User-Agent": get_sec_user_agent(),
        "Accept-Encoding": "gzip, deflate",
    }
    response = httpx.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def fetch_company_tickers() -> dict:
    """Return SEC's ticker-to-CIK mapping for all listed filers."""
    return fetch_json(COMPANY_TICKERS_URL)


def fetch_submissions(cik: str) -> dict:
    """Return a company's profile and filing history from SEC's submissions API."""
    return fetch_json(SUBMISSIONS_URL.format(cik=cik))

