"""Financial ratios computed deterministically from SEC XBRL facts."""

from datetime import date

from sec_financial_analyst_mcp.models import FinancialRatios, RatioResult
from sec_financial_analyst_mcp.services.companies import resolve_company
from sec_financial_analyst_mcp.services.facts import load_company_facts

ANNUAL_PERIOD_MIN_DAYS = 350
ANNUAL_PERIOD_MAX_DAYS = 380

# Companies report the same line item under different us-gaap tags, so each
# item lists its tags in order of preference.
TAG_PRIORITY: dict[str, list[str]] = {
    "Liabilities": ["Liabilities"],
    "StockholdersEquity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "AssetsCurrent": ["AssetsCurrent"],
    "LiabilitiesCurrent": ["LiabilitiesCurrent"],
    "OperatingIncomeLoss": ["OperatingIncomeLoss"],
    "InterestExpense": ["InterestExpense", "InterestExpenseNonoperating"],
    "NetIncomeLoss": ["NetIncomeLoss"],
    "Revenues": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"],
}

RATIO_DEFINITIONS: list[tuple[str, str, str]] = [
    ("Debt to equity", "Liabilities", "StockholdersEquity"),
    ("Current ratio", "AssetsCurrent", "LiabilitiesCurrent"),
    ("Interest coverage", "OperatingIncomeLoss", "InterestExpense"),
    ("Net profit margin", "NetIncomeLoss", "Revenues"),
    ("Return on equity", "NetIncomeLoss", "StockholdersEquity"),
]


def safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    """Divide two reported values, returning None when the result would be meaningless.

    A missing input or a zero denominator yields None instead of an error or
    an invented number, so the caller can report the gap explicitly.
    """
    if numerator is None or denominator is None or denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _annual_values(facts: dict, tag: str) -> dict[str, dict]:
    """Map each fiscal-year period end to its most recently filed annual value.

    Values are keyed by period end date rather than SEC's fy field, because
    every 10-K also repeats the prior year's figures. Income-statement facts
    must span about twelve months so quarterly figures are never mixed in.
    When a period appears in several filings, the latest filing wins, which
    picks up any restatement.
    """
    entries = (
        facts.get("facts", {})
        .get("us-gaap", {})
        .get(tag, {})
        .get("units", {})
        .get("USD", [])
    )
    selected: dict[str, dict] = {}
    for entry in entries:
        if entry.get("form") != "10-K":
            continue
        start = entry.get("start")
        if start is not None:
            days = (date.fromisoformat(entry["end"]) - date.fromisoformat(start)).days
            if not ANNUAL_PERIOD_MIN_DAYS <= days <= ANNUAL_PERIOD_MAX_DAYS:
                continue
        current = selected.get(entry["end"])
        if current is None or entry["filed"] > current["filed"]:
            selected[entry["end"]] = entry
    return selected


def _lookup(facts: dict, item: str, period_end: str) -> tuple[float | None, dict | None]:
    """Return an item's value for the period using the first tag that reports it."""
    for tag in TAG_PRIORITY[item]:
        entry = _annual_values(facts, tag).get(period_end)
        if entry is not None:
            return float(entry["val"]), entry
    return None, None


def _latest_period_end(facts: dict) -> str | None:
    """Return the most recent fiscal year-end that has a reported equity figure."""
    period_ends: set[str] = set()
    for tag in TAG_PRIORITY["StockholdersEquity"]:
        period_ends.update(_annual_values(facts, tag))
    return max(period_ends) if period_ends else None


def get_financial_ratios(ticker: str, period_end: str | None = None) -> FinancialRatios:
    """Compute key ratios for one fiscal year from a company's 10-K XBRL facts.

    Uses the latest fiscal year unless period_end (YYYY-MM-DD) is given. Every
    ratio carries the raw inputs it used; a missing input produces None and a
    warning rather than an estimate.
    """
    company = resolve_company(ticker)
    facts = load_company_facts(company.cik)
    end = period_end or _latest_period_end(facts)
    if end is None:
        raise ValueError(f"No annual 10-K balance sheet found for '{ticker}'.")

    values: dict[str, float | None] = {}
    source: dict | None = None
    for item in TAG_PRIORITY:
        value, entry = _lookup(facts, item, end)
        values[item] = value
        if entry is not None and (source is None or entry["filed"] > source["filed"]):
            source = entry
    if source is None:
        raise ValueError(f"No 10-K figures found for '{ticker}' with period end {end}.")

    ratios: list[RatioResult] = []
    for name, numerator, denominator in RATIO_DEFINITIONS:
        inputs = {
            key: values[key]
            for key in (numerator, denominator)
            if values[key] is not None
        }
        note = None
        if denominator == "StockholdersEquity" and (values[denominator] or 0) < 0:
            note = "Equity is negative, so this ratio is not meaningful."
        ratios.append(
            RatioResult(
                name=name,
                formula=f"{numerator} / {denominator}",
                value=safe_divide(values[numerator], values[denominator]),
                inputs=inputs,
                note=note,
            )
        )

    warnings = [f"{item} is not reported for {end}." for item, value in values.items() if value is None]
    return FinancialRatios(
        ticker=company.ticker,
        company_name=company.name,
        period_end=end,
        source_form=source["form"],
        source_filed=source["filed"],
        ratios=ratios,
        warnings=warnings,
    )