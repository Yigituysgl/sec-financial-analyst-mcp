"""MCP server exposing SEC-based financial analysis tools."""

from fastmcp import FastMCP

from sec_financial_analyst_mcp.models import Company, CompanyProfile, Filing, FinancialRatios, MetricTrend
from sec_financial_analyst_mcp.services import companies, filings, ratios

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


@mcp.tool
def get_financial_ratios(ticker: str, period_end: str | None = None) -> FinancialRatios:
    """Compute a company's key financial ratios and cash metrics for one fiscal year from its 10-K.

    Returns debt to equity, current ratio, interest coverage, net profit
    margin, return on equity, free cash flow, free cash flow margin, net debt
    and net debt to free cash flow. Each metric has a unit, either "ratio" or
    "USD". Every metric includes its formula and the raw reported inputs, and
    the result names the source form and filing date, so cite them in your
    answer. A metric is null when SEC data lacks a required input: say it
    could not be computed and never estimate it. For growth over time, call get_metric_trend instead of calculating it yourself.
    Large share buybacks shrink equity and can inflate debt to equity and return on equity, so judge
    leverage with net debt and net debt to free cash flow instead. Uses the
    latest fiscal year unless period_end (YYYY-MM-DD) is given. Requires an
    exact ticker; call search_company first if you only have a company name.
    """
       
    return ratios.get_financial_ratios(ticker, period_end)


@mcp.tool
def get_metric_trend(ticker: str, metric: str, years: int = 5) -> MetricTrend:
    """Return one financial metric for a company over recent fiscal years with growth.

    Use this for questions about growth or change over time, and use its
    growth figures instead of calculating growth yourself. Growth is
    (value - previous) / previous, computed in code; it is null when no
    earlier year exists, the previous value is not positive, or a fiscal year
    is missing. Values are in USD from annual 10-K filings, each with its
    filing date. Supported metrics: Revenues, NetIncomeLoss,
    OperatingIncomeLoss, OperatingCashFlow, CapitalExpenditure, FreeCashFlow,
    LongTermDebt, CommercialPaper, CashAndEquivalents, ShortTermInvestments,
    StockholdersEquity, Liabilities, AssetsCurrent, LiabilitiesCurrent and
    InterestExpense. Returns at most 10 years. Requires an exact ticker.
    """
    return ratios.get_metric_trend(ticker, metric, years)



def main() -> None:
    """Start the MCP server over stdio."""
    mcp.run()