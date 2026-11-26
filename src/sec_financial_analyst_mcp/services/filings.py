"""Filing history: list the reports a company has submitted to SEC."""

from sec_financial_analyst_mcp.models import Filing
from sec_financial_analyst_mcp.services.companies import resolve_company
from sec_financial_analyst_mcp.services.submissions import load_submissions

ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"


def list_filings(ticker: str, form_type: str = "10-K", limit: int = 5) -> list[Filing]:
    """Return a company's most recent filings of one form type, newest first.

    SEC stores recent filings as parallel lists, one list per field, so each
    filing is rebuilt by reading the same position from every list.
    """
    company = resolve_company(ticker)
    recent = load_submissions(company.cik)["filings"]["recent"]
    wanted = form_type.strip().upper()
    cik_number = str(int(company.cik))

    filings: list[Filing] = []
    for i, form in enumerate(recent["form"]):
        if form != wanted:
            continue
        accession = recent["accessionNumber"][i]
        filings.append(
            Filing(
                form=form,
                filing_date=recent["filingDate"][i],
                report_date=recent["reportDate"][i] or None,
                accession_number=accession,
                url=ARCHIVES_URL.format(
                    cik=cik_number,
                    accession=accession.replace("-", ""),
                    document=recent["primaryDocument"][i],
                ),
            )
        )
        if len(filings) >= limit:
            break
    return filings
