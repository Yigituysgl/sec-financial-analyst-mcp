"""Cached access to SEC submissions records shared by profile and filing tools."""

from functools import lru_cache

from sec_financial_analyst_mcp.clients.sec_client import fetch_submissions


@lru_cache(maxsize=64)
def load_submissions(cik: str) -> dict:
    """Return a company's submissions record, downloading it at most once per process."""
    return fetch_submissions(cik)
