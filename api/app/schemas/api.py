from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field


class CompanyOut(BaseModel):
    id: UUID
    name: str
    country: str | None = None


class ProductOut(BaseModel):
    id: UUID
    # Some products only have reg_no or incomplete UDI mapping; keep API stable by allowing null.
    udi_di: str | None = None
    reg_no: str | None = None
    name: str
    status: str
    approved_date: date | None = None
    expiry_date: date | None = None
    class_name: str | None = None
    ivd_category: str | None = None
    company: CompanyOut | None = None


class ProductParamOut(BaseModel):
    id: UUID
    param_code: str
    value_num: float | None = None
    value_text: str | None = None
    unit: str | None = None
    range_low: float | None = None
    range_high: float | None = None
    conditions: dict | None = None
    confidence: float
    evidence_text: str
    evidence_page: int | None = None
    source: str | None = None
    source_url: str | None = None
    extract_version: str


class ProductParamsData(BaseModel):
    product_id: UUID
    product_name: str
    items: list[ProductParamOut]


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
    ivd_kept_count: int = 0
    non_ivd_skipped_count: int = 0
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


class ApiResponseProductParams(BaseModel):
    code: int
    message: str
    data: ProductParamsData


class ApiResponseCompany(BaseModel):
    code: int
    message: str
    data: CompanyOut


class ProductTimelineItemOut(BaseModel):
    id: int
    change_type: str
    changed_fields: dict = Field(default_factory=dict)
    changed_at: datetime | None = None


class ProductTimelineOut(BaseModel):
    product_id: UUID
    items: list[ProductTimelineItemOut]


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


class PublicContactInfo(BaseModel):
    email: str | None = None
    wecom: str | None = None
    form_url: str | None = None


class ApiResponsePublicContactInfo(BaseModel):
    code: int
    message: str
    data: PublicContactInfo


class MeUserOut(BaseModel):
    id: int
    email: str
    role: str


class MePlanOut(BaseModel):
    plan: str
    plan_status: str
    plan_expires_at: datetime | None = None
    is_pro: bool
    is_admin: bool


class MeOut(BaseModel):
    user: MeUserOut
    plan: MePlanOut


class ApiResponseMe(BaseModel):
    code: int
    message: str
    data: MeOut


class ApiResponseProductTimeline(BaseModel):
    code: int
    message: str
    data: ProductTimelineOut


class RawDocumentOut(BaseModel):
    id: UUID
    source: str
    source_url: str | None = None
    doc_type: str | None = None
    storage_uri: str
    sha256: str
    fetched_at: datetime
    run_id: str
    parse_status: str | None = None
    parse_log: dict | None = None
    error: str | None = None


class ProductRejectedOut(BaseModel):
    id: UUID
    source: str | None = None
    source_key: str | None = None
    raw_document_id: UUID | None = None
    reason: dict | None = None
    ivd_version: str | None = None
    rejected_at: datetime


class AdminRejectedProductsData(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ProductRejectedOut]


class ApiResponseAdminRejectedProducts(BaseModel):
    code: int
    message: str
    data: AdminRejectedProductsData


class ParamsExtractResultOut(BaseModel):
    ok: bool = True
    dry_run: bool
    raw_document_id: UUID
    di: str | None = None
    registry_no: str | None = None
    bound_product_id: str | None = None
    pages: int
    deleted_existing: int
    extracted: int
    extract_version: str
    parse_log: dict | None = None


class ApiResponseParamsExtract(BaseModel):
    code: int
    message: str
    data: ParamsExtractResultOut


class ParamsRollbackResultOut(BaseModel):
    ok: bool = True
    dry_run: bool
    raw_document_id: UUID
    deleted: int


class ApiResponseParamsRollback(BaseModel):
    code: int
    message: str
    data: ParamsRollbackResultOut


class ChangeStatsOut(BaseModel):
    days: int = 30
    total: int
    by_type: dict[str, int] = Field(default_factory=dict)


class ApiResponseChangeStats(BaseModel):
    code: int
    message: str
    data: ChangeStatsOut


class ChangeListItemOut(BaseModel):
    id: int
    change_type: str
    change_date: datetime | None = None
    changed_at: datetime | None = None
    product: ProductOut


class ChangesListOut(BaseModel):
    days: int = 30
    total: int = 0
    page: int = 1
    page_size: int = 50
    items: list[ChangeListItemOut]


class ApiResponseChangesList(BaseModel):
    code: int
    message: str
    data: ChangesListOut


class ChangeDetailOut(BaseModel):
    id: int
    change_type: str
    change_date: datetime | None = None
    changed_at: datetime | None = None
    entity_type: str
    entity_id: UUID
    changed_fields: dict = Field(default_factory=dict)
    before_json: dict | None = None
    after_json: dict | None = None


class ApiResponseChangeDetail(BaseModel):
    code: int
    message: str
    data: ChangeDetailOut


class AuthUserOut(BaseModel):
    id: int
    email: str
    role: str
    created_at: datetime | None = None
    plan: str = 'free'
    plan_status: str = 'inactive'
    plan_expires_at: datetime | None = None
    plan_remaining_days: int | None = None
    entitlements: dict | None = None
    onboarded: bool = False


class ApiResponseOnboarded(BaseModel):
    code: int
    message: str
    data: dict


class SubscriptionCreateIn(BaseModel):
    subscription_type: str
    target_value: str
    channel: str = 'webhook'  # webhook/email
    webhook_url: str | None = None
    email_to: str | None = None


class SubscriptionOut(BaseModel):
    id: int
    subscriber_key: str
    channel: str
    email_to: str | None = None
    subscription_type: str
    target_value: str
    webhook_url: str | None = None
    is_active: bool
    created_at: datetime


class ApiResponseSubscription(BaseModel):
    code: int
    message: str
    data: SubscriptionOut


class AuthRegisterIn(BaseModel):
    email: str
    password: str


class AuthLoginIn(BaseModel):
    email: str
    password: str


class ApiResponseAuthUser(BaseModel):
    code: int
    message: str
    data: AuthUserOut


class AdminUserItemOut(BaseModel):
    id: int
    email: str
    role: str
    plan: str
    plan_status: str
    plan_expires_at: datetime | None = None
    created_at: datetime


class AdminUsersData(BaseModel):
    items: list[AdminUserItemOut]
    limit: int
    offset: int


class ApiResponseAdminUsers(BaseModel):
    code: int
    message: str
    data: AdminUsersData


class AdminMembershipGrantOut(BaseModel):
    id: UUID
    user_id: int
    granted_by_user_id: int | None = None
    plan: str
    start_at: datetime
    end_at: datetime
    reason: str | None = None
    note: str | None = None
    created_at: datetime


class AdminUserDetailOut(BaseModel):
    user: AdminUserItemOut
    recent_grants: list[AdminMembershipGrantOut]


class ApiResponseAdminUserDetail(BaseModel):
    code: int
    message: str
    data: AdminUserDetailOut


class AdminMembershipGrantIn(BaseModel):
    user_id: int
    plan: str = Field(default='pro_annual')
    months: int = Field(gt=0)
    start_at: datetime | None = None
    reason: str | None = None
    note: str | None = None


class AdminMembershipExtendIn(BaseModel):
    user_id: int
    months: int = Field(gt=0)
    reason: str | None = None
    note: str | None = None


class AdminMembershipActionIn(BaseModel):
    user_id: int
    reason: str | None = None
    note: str | None = None


class ApiResponseAdminUserItem(BaseModel):
    code: int
    message: str
    data: AdminUserItemOut
