from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CompanyOut(BaseModel):
    id: UUID
    name: str
    country: str | None = None


class RegistrationOut(BaseModel):
    id: UUID
    registration_no: str
    filing_no: str | None = None
    status: str | None = None


class ProductOut(BaseModel):
    id: UUID
    udi_di: str
    name: str
    model: str | None = None
    specification: str | None = None
    category: str | None = None
    company: CompanyOut | None = None
    registration: RegistrationOut | None = None


class SearchItem(BaseModel):
    product: ProductOut
    highlight: str | None = None


class SearchResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SearchItem]


class StatusItem(BaseModel):
    id: int
    source: str
    package_name: str | None = None
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    message: str | None = None


class StatusResponse(BaseModel):
    latest_runs: list[StatusItem]
