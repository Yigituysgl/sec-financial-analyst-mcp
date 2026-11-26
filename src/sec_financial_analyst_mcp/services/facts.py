"""Cached access to SEC XBRL company facts used by the ratio tools."""

from functools import lru_cache

from sec_financial_analyst_mcp.clients.sec_client import fetch_company_facts


@lru_cache(maxsize=32)
def load_company_facts(cik: str) -> dict:
    """Return a company's XBRL facts, downloading them at most once per process."""
    return fetch_company_facts(cik)
