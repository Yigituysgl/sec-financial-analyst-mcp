"""Tests for the deterministic ratio calculations."""

from sec_financial_analyst_mcp.services.ratios import _annual_values, _free_cash_flow, _net_debt, _with_growth, safe_divide


def _entry(
    end: str,
    val: float,
    filed: str,
    start: str | None = None,
    form: str = "10-K",
    fy: int | None = None,
) -> dict:
    """Build one XBRL fact entry in the shape SEC's companyfacts endpoint returns."""
    entry = {"end": end, "val": val, "filed": filed, "form": form, "fy": fy}
    if start is not None:
        entry["start"] = start
    return entry


def _facts(tag: str, entries: list[dict]) -> dict:
    """Wrap entries in the nested structure SEC's companyfacts endpoint returns."""
    return {"facts": {"us-gaap": {tag: {"units": {"USD": entries}}}}}


def test_safe_divide_returns_rounded_ratio():
    assert safe_divide(1, 3) == 0.3333


def test_safe_divide_keeps_negative_values():
    assert safe_divide(-50.0, 200.0) == -0.25


def test_safe_divide_returns_none_for_zero_denominator():
    assert safe_divide(100.0, 0) is None


def test_safe_divide_returns_none_for_missing_input():
    assert safe_divide(None, 50.0) is None
    assert safe_divide(50.0, None) is None


def test_annual_values_keys_by_period_end_not_fiscal_year():
    # The FY2026 10-K repeats FY2025 revenue, so both entries carry fy=2026.
    facts = _facts("Revenues", [
        _entry("2025-09-27", 100, "2025-10-31", start="2024-09-29", fy=2025),
        _entry("2025-09-27", 100, "2026-10-30", start="2024-09-29", fy=2026),
        _entry("2026-09-26", 120, "2026-10-30", start="2025-09-28", fy=2026),
    ])

    result = _annual_values(facts, "Revenues")

    assert set(result) == {"2025-09-27", "2026-09-26"}
    assert result["2026-09-26"]["val"] == 120


def test_annual_values_prefers_latest_filing_for_restated_period():
    # The newer filing comes first, so the result cannot depend on list order.
    facts = _facts("NetIncomeLoss", [
        _entry("2025-09-27", 95, "2026-10-30", start="2024-09-29"),
        _entry("2025-09-27", 100, "2025-10-31", start="2024-09-29"),
    ])

    result = _annual_values(facts, "NetIncomeLoss")

    assert result["2025-09-27"]["val"] == 95


def test_annual_values_skips_quarterly_periods_inside_annual_reports():
    facts = _facts("Revenues", [
        _entry("2026-09-26", 30, "2026-10-30", start="2026-06-28"),
        _entry("2026-09-26", 120, "2026-10-30", start="2025-09-28"),
    ])

    result = _annual_values(facts, "Revenues")

    assert result["2026-09-26"]["val"] == 120


def test_annual_values_ignores_10q_and_keeps_balance_sheet_items():
    facts = _facts("AssetsCurrent", [
        _entry("2026-06-27", 140, "2026-08-01", form="10-Q"),
        _entry("2026-09-26", 150, "2026-10-30"),
    ])

    result = _annual_values(facts, "AssetsCurrent")

    assert list(result) == ["2026-09-26"]
    assert result["2026-09-26"]["val"] == 150


def test_annual_values_returns_empty_dict_for_missing_tag():
    assert _annual_values({}, "Revenues") == {}


def test_free_cash_flow_subtracts_capex_reported_as_positive():
    values = {"OperatingCashFlow": 145.0, "CapitalExpenditure": 9.0}

    assert _free_cash_flow(values) == 136.0


def test_free_cash_flow_is_none_when_capex_is_missing():
    values = {"OperatingCashFlow": 145.0, "CapitalExpenditure": None}

    assert _free_cash_flow(values) is None


def test_net_debt_subtracts_cash_and_short_term_investments():
    values = {
        "LongTermDebt": 78.0,
        "CommercialPaper": 2.0,
        "CashAndEquivalents": 36.0,
        "ShortTermInvestments": 20.0,
    }

    assert _net_debt(values) == 24.0


def test_net_debt_counts_missing_optional_items_as_zero():
    values = {
        "LongTermDebt": 78.0,
        "CommercialPaper": None,
        "CashAndEquivalents": 36.0,
        "ShortTermInvestments": None,
    }

    assert _net_debt(values) == 42.0


def test_net_debt_is_none_when_cash_is_missing():
    values = {
        "LongTermDebt": 78.0,
        "CommercialPaper": 2.0,
        "CashAndEquivalents": None,
        "ShortTermInvestments": 20.0,
    }

    assert _net_debt(values) is None    


def test_with_growth_computes_year_over_year_change():
    points = _with_growth([("2025-09-27", 100.0, "2025-10-31"), ("2026-09-26", 120.0, "2026-10-30")])

    assert points[0].growth is None
    assert points[1].growth == 0.2


def test_with_growth_skips_growth_across_a_missing_year():
    points = _with_growth([("2024-09-28", 100.0, "2024-11-01"), ("2026-09-26", 120.0, "2026-10-30")])

    assert points[1].growth is None


def test_with_growth_skips_growth_after_a_non_positive_value():
    points = _with_growth([("2025-09-27", -10.0, "2025-10-31"), ("2026-09-26", 5.0, "2026-10-30")])

    assert points[1].growth is None   