from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class CompanyOut(BaseModel):
    id: UUID
    name: str
    country: str | None = None


class ProductOut(BaseModel):
    id: UUID
    udi_di: str
    reg_no: str | None = None
    name: str
    status: str
    approved_date: date | None = None
    expiry_date: date | None = None
    class_name: str | None = None
    company: CompanyOut | None = None


class SearchItem(BaseModel):
    product: ProductOut


class SearchData(BaseModel):
    total: int
    page: int
    page_size: int
    sort_by: str
    sort_order: str
    items: list[SearchItem]


class StatusItem(BaseModel):
    id: int
    source: str
    status: str
    message: str | None = None
    records_total: int
    records_success: int
    records_failed: int
    added_count: int
    updated_count: int
    removed_count: int
    started_at: datetime
    finished_at: datetime | None = None


class StatusData(BaseModel):
    latest_runs: list[StatusItem]


class DashboardSummary(BaseModel):
    start_date: date
    end_date: date
    total_new: int
    total_updated: int
    total_removed: int
    latest_active_subscriptions: int


class DashboardTrendItem(BaseModel):
    metric_date: date
    new_products: int
    updated_products: int
    cancelled_products: int


class DashboardTrendData(BaseModel):
    items: list[DashboardTrendItem]


class DashboardRankingItem(BaseModel):
    metric_date: date
    value: int


class DashboardRankingsData(BaseModel):
    top_new_days: list[DashboardRankingItem]
    top_removed_days: list[DashboardRankingItem]


class DashboardRadarItem(BaseModel):
    metric: str
    value: int


class DashboardRadarData(BaseModel):
    metric_date: date | None = None
    items: list[DashboardRadarItem]


class AdminConfigItem(BaseModel):
    config_key: str
    config_value: dict
    updated_at: datetime


class AdminConfigsData(BaseModel):
    items: list[AdminConfigItem]


class AdminConfigUpdateIn(BaseModel):
    config_value: dict


class ApiResponseSummary(BaseModel):
    code: int
    message: str
    data: DashboardSummary


class ApiResponseTrend(BaseModel):
    code: int
    message: str
    data: DashboardTrendData


class ApiResponseRankings(BaseModel):
    code: int
    message: str
    data: DashboardRankingsData


class ApiResponseRadar(BaseModel):
    code: int
    message: str
    data: DashboardRadarData


class ApiResponseSearch(BaseModel):
    code: int
    message: str
    data: SearchData


class ApiResponseProduct(BaseModel):
    code: int
    message: str
    data: ProductOut


class ApiResponseCompany(BaseModel):
    code: int
    message: str
    data: CompanyOut


class ApiResponseStatus(BaseModel):
    code: int
    message: str
    data: StatusData


class ApiResponseAdminConfigs(BaseModel):
    code: int
    message: str
    data: AdminConfigsData


class ApiResponseAdminConfig(BaseModel):
    code: int
    message: str
    data: AdminConfigItem
