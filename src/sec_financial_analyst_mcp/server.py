"""MCP server exposing SEC-based financial analysis tools."""

from fastmcp import FastMCP

from sec_financial_analyst_mcp.models import Company, CompanyProfile, Filing
from sec_financial_analyst_mcp.services import companies, filings

mcp = FastMCP("SEC Financial Analyst")

MAX_FILINGS = 20


@mcp.tool
def search_company(query: str, limit: int = 10) -> list[Company]:
    """Find US-listed companies by ticker or name and return their SEC CIK.

    Use this first whenever the user mentions a company, because the other
    SEC tools need its ticker or CIK. Example queries: "AAPL", "apple".
    """
    return companies.search_companies(query, limit)


@mcp.tool
def get_company_profile(ticker: str) -> CompanyProfile:
    """Return a company's identity details from its SEC submissions record.

    Includes legal name, CIK, tickers, exchanges, industry, fiscal year end
    and state of incorporation. Check the fiscal year end before interpreting
    any financial figures. Requires an exact ticker; call search_company first
    if you only have a company name.
    """
    return companies.get_company_profile(ticker)


@mcp.tool
def list_filings(ticker: str, form_type: str = "10-K", limit: int = 5) -> list[Filing]:
    """List a company's most recent SEC filings of one type, newest first.

    Each filing includes the period it covers, the date it was filed and a
    link to the original document, so answers can cite their source. Use
    form_type "10-K" for annual reports and "10-Q" for quarterly reports.
    Returns at most 20 filings.
    """
    return filings.list_filings(ticker, form_type, min(limit, MAX_FILINGS))


def main() -> None:
    """Start the MCP server over stdio."""
    mcp.run()