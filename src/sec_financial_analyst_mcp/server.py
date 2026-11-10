"""MCP server exposing SEC-based financial analysis tools."""

from fastmcp import FastMCP

from sec_financial_analyst_mcp.models import Company
from sec_financial_analyst_mcp.services.companies import search_companies

mcp = FastMCP("SEC Financial Analyst")


@mcp.tool
def search_company(query: str, limit: int = 10) -> list[Company]:
    """Find US-listed companies by ticker or name and return their SEC CIK.

    Use this first whenever the user mentions a company, because the other
    SEC tools need its ticker or CIK. Example queries: "AAPL", "apple".
    """
    return search_companies(query, limit)


def main() -> None:
    """Start the MCP server over stdio."""
    mcp.run()