"""Financial ratios computed deterministically from SEC XBRL facts."""

from datetime import date

from sec_financial_analyst_mcp.models import FinancialRatios, MetricTrend, RatioResult, TrendPoint
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
    "OperatingCashFlow": ["NetCashProvidedByUsedInOperatingActivities"],
    "CapitalExpenditure": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "LongTermDebt": ["LongTermDebt"],
    "CommercialPaper": ["CommercialPaper"],
    "CashAndEquivalents": ["CashAndCashEquivalentsAtCarryingValue"],
    "ShortTermInvestments": ["MarketableSecuritiesCurrent"],
}

RATIO_DEFINITIONS: list[tuple[str, str, str]] = [
    ("Debt to equity", "Liabilities", "StockholdersEquity"),
    ("Current ratio", "AssetsCurrent", "LiabilitiesCurrent"),
    ("Interest coverage", "OperatingIncomeLoss", "InterestExpense"),
    ("Net profit margin", "NetIncomeLoss", "Revenues"),
    ("Return on equity", "NetIncomeLoss", "StockholdersEquity"),
]

# Many companies issue no commercial paper or hold no short-term investments,
# so these items count as zero when missing and are flagged in the warnings.
OPTIONAL_ITEMS = {"CommercialPaper", "ShortTermInvestments"}


def safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    """Divide two reported values, returning None when the result would be meaningless.

    A missing input or a zero denominator yields None instead of an error or
    an invented number, so the caller can report the gap explicitly.
    """
    if numerator is None or denominator is None or denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _known(inputs: dict[str, float | None]) -> dict[str, float]:
    """Keep only inputs that have a value, so missing data is never shown as zero."""
    return {name: value for name, value in inputs.items() if value is not None}


def _free_cash_flow(values: dict[str, float | None]) -> float | None:
    """Operating cash flow minus capital expenditure.

    SEC reports capital expenditure as a positive payment, so it is subtracted.
    """
    operating, capex = values["OperatingCashFlow"], values["CapitalExpenditure"]
    if operating is None or capex is None:
        return None
    return operating - capex


def _net_debt(values: dict[str, float | None]) -> float | None:
    """Financial debt minus cash and short-term investments.

    LongTermDebt already includes its current portion, so the current and
    noncurrent tags are not added again. Long-term debt and cash are required.
    """
    debt, cash = values["LongTermDebt"], values["CashAndEquivalents"]
    if debt is None or cash is None:
        return None
    return (
        debt
        + (values["CommercialPaper"] or 0)
        - cash
        - (values["ShortTermInvestments"] or 0)
    )


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
    """Compute key ratios and cash metrics for one fiscal year from a company's 10-K.

    Uses the latest fiscal year unless period_end (YYYY-MM-DD) is given. Every
    metric carries the raw inputs it used; a missing required input produces
    None and a warning rather than an estimate.
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

    metrics: list[RatioResult] = []
    for name, numerator, denominator in RATIO_DEFINITIONS:
        note = None
        if denominator == "StockholdersEquity" and (values[denominator] or 0) < 0:
            note = "Equity is negative, so this ratio is not meaningful."
        metrics.append(
            RatioResult(
                name=name,
                formula=f"{numerator} / {denominator}",
                value=safe_divide(values[numerator], values[denominator]),
                inputs=_known({key: values[key] for key in (numerator, denominator)}),
                note=note,
            )
        )

    free_cash_flow = _free_cash_flow(values)
    net_debt = _net_debt(values)
    positive_fcf = free_cash_flow is not None and free_cash_flow > 0
    metrics.extend(
        [
            RatioResult(
                name="Free cash flow",
                formula="OperatingCashFlow - CapitalExpenditure",
                value=free_cash_flow,
                inputs=_known({key: values[key] for key in ("OperatingCashFlow", "CapitalExpenditure")}),
                unit="USD",
            ),
            RatioResult(
                name="Free cash flow margin",
                formula="FreeCashFlow / Revenues",
                value=safe_divide(free_cash_flow, values["Revenues"]),
                inputs=_known({"FreeCashFlow": free_cash_flow, "Revenues": values["Revenues"]}),
            ),
            RatioResult(
                name="Net debt",
                formula="LongTermDebt + CommercialPaper - CashAndEquivalents - ShortTermInvestments",
                value=net_debt,
                inputs=_known(
                    {
                        key: values[key]
                        for key in ("LongTermDebt", "CommercialPaper", "CashAndEquivalents", "ShortTermInvestments")
                    }
                ),
                unit="USD",
                note="Negative net debt means cash exceeds debt." if (net_debt or 0) < 0 else None,
            ),
            RatioResult(
                name="Net debt to free cash flow",
                formula="NetDebt / FreeCashFlow",
                value=safe_divide(net_debt, free_cash_flow) if positive_fcf else None,
                inputs=_known({"NetDebt": net_debt, "FreeCashFlow": free_cash_flow}),
                note=None if positive_fcf else "Free cash flow is not positive, so this ratio is not meaningful.",
            ),
        ]
    )

    warnings = []
    for item, value in values.items():
        if value is None:
            suffix = " Counted as zero in net debt." if item in OPTIONAL_ITEMS else ""
            warnings.append(f"{item} is not reported for {end}.{suffix}")

    return FinancialRatios(
        ticker=company.ticker,
        company_name=company.name,
        period_end=end,
        source_form=source["form"],
        source_filed=source["filed"],
        ratios=metrics,
        warnings=warnings,
    )


TREND_METRICS = (*TAG_PRIORITY, "FreeCashFlow")
MAX_TREND_YEARS = 10


def _series(facts: dict, item: str) -> dict[str, dict]:
    """Map each fiscal year-end to an item's annual entry, using the first tag that reports it."""
    series: dict[str, dict] = {}
    for tag in TAG_PRIORITY[item]:
        for end, entry in _annual_values(facts, tag).items():
            series.setdefault(end, entry)
    return series


def _metric_series(facts: dict, metric: str) -> dict[str, tuple[float, str]]:
    """Return the value and filing date per fiscal year-end for a reported or derived metric."""
    if metric == "FreeCashFlow":
        operating = _series(facts, "OperatingCashFlow")
        capex = _series(facts, "CapitalExpenditure")
        return {
            end: (
                float(operating[end]["val"]) - float(capex[end]["val"]),
                max(operating[end]["filed"], capex[end]["filed"]),
            )
            for end in operating.keys() & capex.keys()
        }
    return {end: (float(entry["val"]), entry["filed"]) for end, entry in _series(facts, metric).items()}


def _with_growth(points: list[tuple[str, float, str]]) -> list[TrendPoint]:
    """Attach year-over-year growth to consecutive fiscal years.

    Growth is None for the first year, when the previous value is not
    positive, or when a fiscal year is missing in between, so a two-year
    change is never reported as one year's growth.
    """
    result: list[TrendPoint] = []
    previous: tuple[str, float, str] | None = None
    for end, value, filed in points:
        growth = None
        if previous is not None and previous[1] > 0:
            gap_days = (date.fromisoformat(end) - date.fromisoformat(previous[0])).days
            if ANNUAL_PERIOD_MIN_DAYS <= gap_days <= ANNUAL_PERIOD_MAX_DAYS:
                growth = safe_divide(value - previous[1], previous[1])
        result.append(TrendPoint(period_end=end, value=value, growth=growth, source_filed=filed))
        previous = (end, value, filed)
    return result


def get_metric_trend(ticker: str, metric: str, years: int = 5) -> MetricTrend:
    """Return one metric over recent fiscal years with year-over-year growth computed in code.

    One extra year is loaded so the oldest year shown also has a growth figure.
    """
    if metric not in TREND_METRICS:
        raise ValueError(f"Unknown metric '{metric}'. Supported metrics: {', '.join(TREND_METRICS)}.")
    company = resolve_company(ticker)
    series = _metric_series(load_company_facts(company.cik), metric)
    if not series:
        raise ValueError(f"No annual 10-K values found for {metric} at '{ticker}'.")

    count = min(max(years, 1), MAX_TREND_YEARS)
    ends = sorted(series)[-(count + 1):]
    points = _with_growth([(end, *series[end]) for end in ends])[-count:]
    return MetricTrend(
        ticker=company.ticker,
        company_name=company.name,
        metric=metric,
        unit="USD",
        points=points,
    )


