from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import Field


class SignalFactor(BaseModel):
    name: str
    value: Any
    unit: str | None = None
    explanation: str
    drill_link: str | None = None


class SignalResponse(BaseModel):
    level: str
    score: float
    factors: list[SignalFactor] = Field(default_factory=list)
    updated_at: datetime


class TopRiskRegistrationItem(BaseModel):
    registration_no: str
    company: str | None = None
    level: str
    days_to_expiry: int | None = None


class TopCompetitiveTrackItem(BaseModel):
    track_id: str
    track_name: str
    level: str
    total_count: int | None = None
    new_rate_12m: float | None = None


class TopGrowthCompanyItem(BaseModel):
    company_id: str
    company_name: str | None = None
    level: str
    new_registrations_12m: int | None = None
    new_tracks_12m: int | None = None


class TopRiskRegistrationsResponse(BaseModel):
    items: list[TopRiskRegistrationItem] = Field(default_factory=list)


class TopCompetitiveTracksResponse(BaseModel):
    items: list[TopCompetitiveTrackItem] = Field(default_factory=list)


class TopGrowthCompaniesResponse(BaseModel):
    items: list[TopGrowthCompanyItem] = Field(default_factory=list)


class BatchSignalItem(BaseModel):
    registration_no: str
    lifecycle_level: str
    lifecycle_factors_summary: str | None = None
    track_id: str | None = None
    track_level: str | None = None
    company_id: str | None = None
    company_level: str | None = None


class BatchSignalsResponse(BaseModel):
    items: list[BatchSignalItem] = Field(default_factory=list)
