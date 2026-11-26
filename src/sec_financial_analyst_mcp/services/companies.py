"""Company lookup and profiles: map tickers to SEC identifiers and identity details."""

from functools import lru_cache

from sec_financial_analyst_mcp.clients.sec_client import fetch_company_tickers
from sec_financial_analyst_mcp.models import Company, CompanyProfile
from sec_financial_analyst_mcp.services.submissions import load_submissions


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


def resolve_company(ticker: str) -> Company:
    """Return the company for an exact ticker, or raise a clear error.

    Tools that need a single company accept a ticker rather than a free-text
    name, so the model resolves ambiguous names with search_company first.
    """
    needle = ticker.strip().upper()
    for company in _load_companies():
        if company.ticker == needle:
            return company
    raise ValueError(f"Unknown ticker '{ticker}'. Use search_company to find the correct ticker.")


def _format_fiscal_year_end(raw: str | None) -> str | None:
    """Turn SEC's 'MMDD' format into 'MM-DD' for readability."""
    if not raw or len(raw) != 4:
        return None
    return f"{raw[:2]}-{raw[2:]}"


def get_company_profile(ticker: str) -> CompanyProfile:
    """Build a company's identity profile from its SEC submissions record."""
    company = resolve_company(ticker)
    data = load_submissions(company.cik)
    return CompanyProfile(
        name=data["name"],
        cik=company.cik,
        tickers=data.get("tickers", []),
        exchanges=[exchange for exchange in data.get("exchanges", []) if exchange],
        industry=data.get("sicDescription") or None,
        sic_code=data.get("sic") or None,
        fiscal_year_end=_format_fiscal_year_end(data.get("fiscalYearEnd")),
        state_of_incorporation=data.get("stateOfIncorporation") or None,
    )
