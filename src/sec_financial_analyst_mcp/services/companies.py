"""Company lookup: map names and tickers to SEC identifiers."""

from functools import lru_cache

from sec_financial_analyst_mcp.clients.sec_client import fetch_company_tickers
from sec_financial_analyst_mcp.models import Company


@lru_cache(maxsize=1)
def _load_companies() -> tuple[Company, ...]:
    """Download the SEC ticker list once per process; it changes rarely."""
    raw = fetch_company_tickers()
    return tuple(
        Company(
            name=entry["title"],
            ticker=entry["ticker"],
            cik=str(entry["cik_str"]).zfill(10),
        )
        for entry in raw.values()
    )


def search_companies(query: str, limit: int = 10) -> list[Company]:
    """Return companies whose ticker or name matches the query.

    Exact ticker matches come first, so "AAPL" returns Apple before any
    company that merely contains those letters in its name.
    """
    needle = query.strip().upper()
    if not needle:
        return []
    companies = _load_companies()
    exact = [c for c in companies if c.ticker == needle]
    partial = [c for c in companies if c.ticker != needle and needle in c.name.upper()]
    return (exact + partial)[:limit]