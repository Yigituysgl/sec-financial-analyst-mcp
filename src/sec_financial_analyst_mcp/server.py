"""MCP server exposing SEC-based financial analysis tools."""

from fastmcp import FastMCP

from sec_financial_analyst_mcp.models import Company, CompanyProfile
from sec_financial_analyst_mcp.services import companies

mcp = FastMCP("SEC Financial Analyst")


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


def main() -> None:
    """Start the MCP server over stdio."""
    mcp.run()