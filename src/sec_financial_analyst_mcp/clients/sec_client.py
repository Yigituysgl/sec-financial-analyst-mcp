"""HTTP client for SEC EDGAR endpoints."""

import httpx

from sec_financial_analyst_mcp.config import REQUEST_TIMEOUT_SECONDS, get_sec_user_agent

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def fetch_json(url: str) -> dict:
    """Fetch a JSON document from SEC with the required identifying headers."""
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