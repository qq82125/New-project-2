from __future__ import annotations

from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from secrets import compare_digest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.repositories.dashboard import get_radar, get_rankings, get_summary, get_trend
from app.repositories.products import get_company, get_product, search_products
from app.repositories.radar import list_admin_configs, upsert_admin_config
from app.repositories.source_runs import latest_runs
from app.schemas.api import (
    AdminConfigItem,
    AdminConfigUpdateIn,
    AdminConfigsData,
    ApiResponseCompany,
    ApiResponseAdminConfig,
    ApiResponseAdminConfigs,
    ApiResponseProduct,
    ApiResponseRadar,
    ApiResponseRankings,
    ApiResponseSearch,
    ApiResponseStatus,
    ApiResponseSummary,
    ApiResponseTrend,
    CompanyOut,
    DashboardRadarData,
    DashboardRadarItem,
    DashboardRankingsData,
    DashboardRankingItem,
    DashboardSummary,
    DashboardTrendData,
    DashboardTrendItem,
    ProductOut,
    SearchData,
    SearchItem,
    StatusData,
    StatusItem,
)

app = FastAPI(title='NMPA IVD Dashboard API', version='0.4.0')


SortBy = Literal['updated_at', 'approved_date', 'expiry_date', 'name']
SortOrder = Literal['asc', 'desc']
security = HTTPBasic()


def _ok(data):
    return {'code': 0, 'message': 'ok', 'data': data}


def serialize_company(company) -> CompanyOut:
    return CompanyOut(id=company.id, name=company.name, country=company.country)


def serialize_product(product) -> ProductOut:
    return ProductOut(
        id=product.id,
        udi_di=product.udi_di,
        reg_no=product.reg_no,
        name=product.name,
        status=product.status,
        approved_date=product.approved_date,
        expiry_date=product.expiry_date,
        class_name=product.class_name,
        company=serialize_company(product.company) if product.company else None,
    )


def _require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    settings = get_settings()
    valid_user = compare_digest(credentials.username, settings.admin_username)
    valid_pass = compare_digest(credentials.password, settings.admin_password)
    if not (valid_user and valid_pass):
        raise HTTPException(
            status_code=401,
            detail='Unauthorized',
            headers={'WWW-Authenticate': 'Basic'},
        )
    return credentials.username


@app.get('/api/dashboard/summary', response_model=ApiResponseSummary)
def dashboard_summary(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> ApiResponseSummary:
    start_date, end_date, total_new, total_updated, total_removed, latest_active_subscriptions = get_summary(db, days)
    data = DashboardSummary(
        start_date=start_date,
        end_date=end_date,
        total_new=total_new,
        total_updated=total_updated,
        total_removed=total_removed,
        latest_active_subscriptions=latest_active_subscriptions,
    )
    return _ok(data)


@app.get('/api/dashboard/trend', response_model=ApiResponseTrend)
def dashboard_trend(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> ApiResponseTrend:
    items = get_trend(db, days)
    data = DashboardTrendData(
        items=[
            DashboardTrendItem(
                metric_date=item.metric_date,
                new_products=item.new_products,
                updated_products=item.updated_products,
                cancelled_products=item.cancelled_products,
            )
            for item in items
        ]
    )
    return _ok(data)


@app.get('/api/dashboard/rankings', response_model=ApiResponseRankings)
def dashboard_rankings(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ApiResponseRankings:
    top_new, top_removed = get_rankings(db, days, limit)
    data = DashboardRankingsData(
        top_new_days=[DashboardRankingItem(metric_date=row[0], value=int(row[1])) for row in top_new],
        top_removed_days=[DashboardRankingItem(metric_date=row[0], value=int(row[1])) for row in top_removed],
    )
    return _ok(data)


@app.get('/api/dashboard/radar', response_model=ApiResponseRadar)
def dashboard_radar(db: Session = Depends(get_db)) -> ApiResponseRadar:
    metric = get_radar(db)
    if not metric:
        return _ok(DashboardRadarData(metric_date=None, items=[]))

    data = DashboardRadarData(
        metric_date=metric.metric_date,
        items=[
            DashboardRadarItem(metric='new_products', value=metric.new_products),
            DashboardRadarItem(metric='updated_products', value=metric.updated_products),
            DashboardRadarItem(metric='cancelled_products', value=metric.cancelled_products),
            DashboardRadarItem(metric='expiring_in_90d', value=metric.expiring_in_90d),
            DashboardRadarItem(metric='active_subscriptions', value=metric.active_subscriptions),
        ],
    )
    return _ok(data)


@app.get('/api/search', response_model=ApiResponseSearch)
def search(
    q: str | None = Query(default=None, description='fuzzy query on name/reg_no/udi_di/company'),
    company: str | None = Query(default=None),
    reg_no: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: SortBy = Query(default='updated_at'),
    sort_order: SortOrder = Query(default='desc'),
    db: Session = Depends(get_db),
) -> ApiResponseSearch:
    products, total = search_products(
        db,
        query=q,
        company=company,
        reg_no=reg_no,
        status=status,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    data = SearchData(
        total=total,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        items=[SearchItem(product=serialize_product(item)) for item in products],
    )
    return _ok(data)


@app.get('/api/products/{product_id}', response_model=ApiResponseProduct)
def product_detail(product_id: str, db: Session = Depends(get_db)) -> ApiResponseProduct:
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')
    return _ok(serialize_product(product))


@app.get('/api/companies/{company_id}', response_model=ApiResponseCompany)
def company_detail(company_id: str, db: Session = Depends(get_db)) -> ApiResponseCompany:
    company = get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail='Company not found')
    return _ok(serialize_company(company))


@app.get('/api/status', response_model=ApiResponseStatus)
def status(db: Session = Depends(get_db)) -> ApiResponseStatus:
    runs = latest_runs(db)
    data = StatusData(
        latest_runs=[
            StatusItem(
                id=run.id,
                source=run.source,
                status=run.status,
                message=run.message,
                records_total=run.records_total,
                records_success=run.records_success,
                records_failed=run.records_failed,
                added_count=getattr(run, 'added_count', 0),
                updated_count=getattr(run, 'updated_count', 0),
                removed_count=getattr(run, 'removed_count', 0),
                started_at=run.started_at,
                finished_at=run.finished_at,
            )
            for run in runs
        ]
    )
    return _ok(data)


@app.get('/api/admin/configs', response_model=ApiResponseAdminConfigs)
def admin_list_configs(
    _admin: str = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> ApiResponseAdminConfigs:
    configs = list_admin_configs(db)
    data = AdminConfigsData(
        items=[
            AdminConfigItem(
                config_key=cfg.config_key,
                config_value=cfg.config_value,
                updated_at=cfg.updated_at,
            )
            for cfg in configs
        ]
    )
    return _ok(data)


@app.put('/api/admin/configs/{config_key}', response_model=ApiResponseAdminConfig)
def admin_upsert_config(
    config_key: str,
    payload: AdminConfigUpdateIn,
    _admin: str = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> ApiResponseAdminConfig:
    cfg = upsert_admin_config(db, config_key, payload.config_value)
    data = AdminConfigItem(
        config_key=cfg.config_key,
        config_value=cfg.config_value,
        updated_at=cfg.updated_at,
    )
    return _ok(data)
