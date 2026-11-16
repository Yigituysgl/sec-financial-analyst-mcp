"""Data models returned by the MCP tools."""

from pydantic import BaseModel


class Company(BaseModel):
    """A US-listed company as identified by SEC."""

    name: str
    ticker: str
    cik: str


class CompanyProfile(BaseModel):
    """Identity details of a company from its SEC submissions record."""

    name: str
    cik: str
    tickers: list[str]
    exchanges: list[str]
    industry: str | None
    sic_code: str | None
    fiscal_year_end: str | None
    state_of_incorporation: str | None    



class Filing(BaseModel):
    """A single report a company filed with SEC."""

    form: str
    filing_date: str
    report_date: str | None
    accession_number: str
    url: str    