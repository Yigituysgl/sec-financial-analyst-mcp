"""Data models returned by the MCP tools."""

from pydantic import BaseModel


class Company(BaseModel):
    """A US-listed company as identified by SEC."""

    name: str
    ticker: str
    cik: str