from __future__ import annotations

from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from secrets import compare_digest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal, get_db
from app.models import User
from app.repositories.dashboard import get_radar, get_rankings, get_summary, get_trend
from app.repositories.data_sources import (
    activate_data_source,
    create_data_source,
    delete_data_source,
    get_data_source,
    list_data_sources,
    update_data_source,
)
from app.repositories.products import get_company, get_product, search_products
from app.repositories.radar import list_admin_configs, upsert_admin_config
from app.repositories.radar import count_active_subscriptions_by_subscriber, create_subscription
from app.repositories.source_runs import latest_runs, list_source_runs
from app.repositories.users import create_user, get_user_by_email, get_user_by_id
from app.repositories.admin_membership import (
    admin_extend_membership,
    admin_get_user,
    admin_grant_membership,
    admin_list_recent_grants,
    admin_list_users,
    admin_revoke_membership,
    admin_suspend_membership,
)
from app.schemas.api import (
    AdminConfigItem,
    AdminConfigUpdateIn,
    AdminConfigsData,
    ApiResponseAuthUser,
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
    AuthLoginIn,
    AuthRegisterIn,
    AuthUserOut,
    ApiResponseSubscription,
    SubscriptionCreateIn,
    SubscriptionOut,
    ApiResponseOnboarded,
    AdminMembershipActionIn,
    AdminMembershipExtendIn,
    AdminMembershipGrantIn,
    AdminMembershipGrantOut,
    AdminUserDetailOut,
    AdminUserItemOut,
    AdminUsersData,
    ApiResponseAdminUserDetail,
    ApiResponseAdminUserItem,
    ApiResponseAdminUsers,
)
from app.services.auth import (
    create_session_token,
    hash_password,
    normalize_email,
    parse_session_token,
    verify_password,
)
from app.services.entitlements import get_entitlements, get_membership_info
from app.services.exports import export_search_to_csv
from app.services.crypto import decrypt_json, encrypt_json

app = FastAPI(title='IVD产品雷达 API', version='0.4.0')

def _settings():
    return get_settings()


cfg0 = _settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cfg0.cors_origins.split(',') if origin.strip()],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


SortBy = Literal['updated_at', 'approved_date', 'expiry_date', 'name']
SortOrder = Literal['asc', 'desc']
security = HTTPBasic()


def _ok(data):
    return {'code': 0, 'message': 'ok', 'data': data}


def _auth_user_out(user: User) -> AuthUserOut:
    info = get_membership_info(user)
    ent = get_entitlements(user)
    remaining_days = None
    exp = info.plan_expires_at
    if exp is not None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        exp0 = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
        remaining_days = int((exp0 - now).total_seconds() // 86400)
    return AuthUserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        created_at=getattr(user, 'created_at', None),
        plan=info.plan,
        plan_status=info.plan_status,
        plan_expires_at=info.plan_expires_at,
        plan_remaining_days=remaining_days,
        entitlements={
            'can_export': ent.can_export,
            'max_subscriptions': ent.max_subscriptions,
            'trend_range_days': ent.trend_range_days,
        },
        onboarded=bool(getattr(user, 'onboarded', False)),
    )


def _admin_user_item_out(user: User) -> AdminUserItemOut:
    return AdminUserItemOut(
        id=user.id,
        email=user.email,
        role=user.role,
        plan=(getattr(user, 'plan', None) or 'free'),
        plan_status=(getattr(user, 'plan_status', None) or 'inactive'),
        plan_expires_at=getattr(user, 'plan_expires_at', None),
        created_at=user.created_at,
    )


def _admin_grant_out(g) -> AdminMembershipGrantOut:
    return AdminMembershipGrantOut(
        id=g.id,
        user_id=g.user_id,
        granted_by_user_id=getattr(g, 'granted_by_user_id', None),
        plan=g.plan,
        start_at=g.start_at,
        end_at=g.end_at,
        reason=getattr(g, 'reason', None),
        note=getattr(g, 'note', None),
        created_at=g.created_at,
    )


def _set_auth_cookie(response: Response, user_id: int) -> None:
    cfg = _settings()
    token = create_session_token(
        user_id=user_id,
        secret=cfg.auth_secret,
        ttl_seconds=cfg.auth_session_ttl_hours * 3600,
    )
    response.set_cookie(
        key=cfg.auth_cookie_name,
        value=token,
        max_age=cfg.auth_session_ttl_hours * 3600,
        httponly=True,
        secure=cfg.auth_cookie_secure,
        samesite='lax',
        path='/',
    )


def _clear_auth_cookie(response: Response) -> None:
    cfg = _settings()
    # Must match the cookie attributes used in _set_auth_cookie, otherwise browsers
    # may keep the old cookie and users appear still logged in.
    response.set_cookie(
        key=cfg.auth_cookie_name,
        value='',
        max_age=0,
        expires=0,
        httponly=True,
        secure=cfg.auth_cookie_secure,
        samesite='lax',
        path='/',
    )


def _require_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    cfg = _settings()
    token = request.cookies.get(cfg.auth_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail='Not authenticated')
    user_id = parse_session_token(token=token, secret=cfg.auth_secret)
    if user_id is None:
        raise HTTPException(status_code=401, detail='Not authenticated')
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail='Not authenticated')
    return user


def _get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    cfg = _settings()
    token = request.cookies.get(cfg.auth_cookie_name)
    if not token:
        return None
    user_id = parse_session_token(token=token, secret=cfg.auth_secret)
    if user_id is None:
        return None
    return get_user_by_id(db, user_id)


def _require_admin_user(current_user: User = Depends(_require_current_user)) -> User:
    if getattr(current_user, 'role', None) != 'admin':
        raise HTTPException(status_code=403, detail='Admin only')
    return current_user


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
    cfg = get_settings()
    valid_user = compare_digest(credentials.username, cfg.admin_username)
    valid_pass = compare_digest(credentials.password, cfg.admin_password)
    if not (valid_user and valid_pass):
        raise HTTPException(
            status_code=401,
            detail='Unauthorized',
            headers={'WWW-Authenticate': 'Basic'},
        )
    return credentials.username


@app.on_event('startup')
def bootstrap_admin() -> None:
    cfg = _settings()
    email = normalize_email(cfg.bootstrap_admin_email)
    password = cfg.bootstrap_admin_password
    if not email or '@' not in email or not password:
        return

    db = SessionLocal()
    try:
        existing = get_user_by_email(db, email)
        if existing:
            if existing.role != 'admin':
                existing.role = 'admin'
                db.add(existing)
                db.commit()
            return
        password_hash = hash_password(password)
        create_user(db, email=email, password_hash=password_hash, role='admin')
    finally:
        db.close()


@app.post('/api/auth/register', response_model=ApiResponseAuthUser)
def register(payload: AuthRegisterIn, response: Response, db: Session = Depends(get_db)) -> ApiResponseAuthUser:
    email = normalize_email(payload.email)
    password = payload.password
    if not email or '@' not in email:
        raise HTTPException(status_code=400, detail='Invalid email')
    if len(password) < 8:
        raise HTTPException(status_code=400, detail='Password must be at least 8 characters')
    if get_user_by_email(db, email):
        raise HTTPException(status_code=409, detail='Email already registered')

    user = create_user(db, email=email, password_hash=hash_password(password), role='user')
    _set_auth_cookie(response, user.id)
    return _ok(_auth_user_out(user))


@app.post('/api/auth/login', response_model=ApiResponseAuthUser)
def login(payload: AuthLoginIn, response: Response, db: Session = Depends(get_db)) -> ApiResponseAuthUser:
    email = normalize_email(payload.email)
    user = get_user_by_email(db, email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail='Invalid email or password')
    _set_auth_cookie(response, user.id)
    return _ok(_auth_user_out(user))


@app.post('/api/auth/logout')
def logout(response: Response) -> dict:
    _clear_auth_cookie(response)
    return {'ok': True}


@app.get('/api/auth/me', response_model=ApiResponseAuthUser)
def me(current_user: User = Depends(_require_current_user)) -> ApiResponseAuthUser:
    return _ok(_auth_user_out(current_user))


@app.post('/api/users/onboarded', response_model=ApiResponseOnboarded)
def mark_onboarded(
    current_user: User = Depends(_require_current_user),
    db: Session = Depends(get_db),
) -> ApiResponseOnboarded:
    # Best-effort idempotent marker.
    if not getattr(current_user, 'onboarded', False):
        current_user.onboarded = True
        db.add(current_user)
        db.commit()
        try:
            db.refresh(current_user)
        except Exception:
            pass
    return _ok({'onboarded': True})


@app.get('/api/admin/me', response_model=ApiResponseAuthUser)
def admin_me(current_user: User = Depends(_require_admin_user)) -> ApiResponseAuthUser:
    return _ok(_auth_user_out(current_user))


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
    current_user: User | None = Depends(_get_current_user_optional),
    db: Session = Depends(get_db),
) -> ApiResponseTrend:
    ent = get_entitlements(current_user or object())
    if days > ent.trend_range_days:
        raise HTTPException(
            status_code=403,
            detail=f'Trend range exceeds your plan limit (max {ent.trend_range_days} days). Upgrade to Pro for more.',
        )
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


@app.get('/api/export/search.csv')
def export_search_csv(
    q: str | None = Query(default=None),
    company: str | None = Query(default=None),
    reg_no: str | None = Query(default=None),
    current_user: User = Depends(_require_current_user),
    db: Session = Depends(get_db),
) -> Response:
    ent = get_entitlements(current_user)
    if not ent.can_export:
        raise HTTPException(status_code=403, detail='Export is not available on your plan. Upgrade to Pro.')

    csv_text = export_search_to_csv(db, plan='pro', q=q, company=company, registration_no=reg_no)
    headers = {'Content-Disposition': 'attachment; filename="ivd_search_export.csv"'}
    return Response(content=csv_text, media_type='text/csv; charset=utf-8', headers=headers)


@app.post('/api/subscriptions', response_model=ApiResponseSubscription)
def create_subscription_api(
    payload: SubscriptionCreateIn,
    current_user: User = Depends(_require_current_user),
    db: Session = Depends(get_db),
) -> ApiResponseSubscription:
    ent = get_entitlements(current_user)
    subscriber_key = current_user.email
    active_count = count_active_subscriptions_by_subscriber(db, subscriber_key=subscriber_key)
    if active_count >= ent.max_subscriptions:
        # Required error contract for frontend handling.
        return JSONResponse(
            status_code=403,
            content={
                'error': 'SUBSCRIPTION_LIMIT',
                'message': 'Free 用户最多订阅 3 个，请升级或联系开通。',
            },
        )

    stype = (payload.subscription_type or '').strip().lower()
    if stype not in {'company', 'product', 'keyword'}:
        raise HTTPException(status_code=400, detail='Invalid subscription_type')

    channel = (payload.channel or 'webhook').strip().lower()
    if channel not in {'webhook', 'email'}:
        raise HTTPException(status_code=400, detail='Invalid channel')

    target_value = (payload.target_value or '').strip()
    if not target_value:
        raise HTTPException(status_code=400, detail='target_value is required')

    webhook_url = (payload.webhook_url or '').strip() if payload.webhook_url else None
    email_to = (payload.email_to or '').strip() if payload.email_to else None
    if channel == 'webhook' and not webhook_url:
        raise HTTPException(status_code=400, detail='webhook_url is required for webhook subscriptions')

    sub = create_subscription(
        db,
        subscription_type=stype,
        target_value=target_value,
        webhook_url=webhook_url,
        subscriber_key=subscriber_key,
        channel=channel,
        email_to=email_to,
    )
    out = SubscriptionOut(
        id=sub.id,
        subscriber_key=sub.subscriber_key,
        channel=sub.channel,
        email_to=sub.email_to,
        subscription_type=sub.subscription_type,
        target_value=sub.target_value,
        webhook_url=sub.webhook_url,
        is_active=bool(sub.is_active),
        created_at=sub.created_at,
    )
    return _ok(out)


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


def _spawn_sync_thread() -> None:
    import threading

    def _job():
        from app.workers.sync import sync_nmpa_ivd

        sync_nmpa_ivd()

    threading.Thread(target=_job, daemon=True).start()


@app.get('/api/admin/source-runs')
def admin_source_runs(
    limit: int = Query(default=50, ge=1, le=200),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    runs = list_source_runs(db, limit=limit)
    items = [
        {
            'id': r.id,
            'source': r.source,
            'status': r.status,
            'message': getattr(r, 'message', None),
            'records_total': int(getattr(r, 'records_total', 0) or 0),
            'records_success': int(getattr(r, 'records_success', 0) or 0),
            'records_failed': int(getattr(r, 'records_failed', 0) or 0),
            'added_count': int(getattr(r, 'added_count', 0) or 0),
            'updated_count': int(getattr(r, 'updated_count', 0) or 0),
            'removed_count': int(getattr(r, 'removed_count', 0) or 0),
            'started_at': r.started_at,
            'finished_at': getattr(r, 'finished_at', None),
        }
        for r in runs
    ]
    return _ok({'items': items})


@app.post('/api/admin/sync/run')
def admin_sync_run(
    background_tasks: BackgroundTasks,
    _admin: User = Depends(_require_admin_user),
) -> dict:
    background_tasks.add_task(_spawn_sync_thread)
    return _ok({'queued': True})


def _ds_preview(cfg: dict) -> dict:
    return {
        'host': cfg.get('host') or '',
        'port': int(cfg.get('port') or 5432),
        'database': cfg.get('database') or '',
        'username': cfg.get('username') or '',
        'sslmode': cfg.get('sslmode'),
    }


@app.get('/api/admin/data-sources')
def admin_list_data_sources_api(
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    items = []
    for ds in list_data_sources(db):
        cfg = decrypt_json(ds.config_encrypted)
        items.append(
            {
                'id': ds.id,
                'name': ds.name,
                'type': ds.type,
                'is_active': bool(ds.is_active),
                'updated_at': ds.updated_at,
                'config_preview': _ds_preview(cfg),
            }
        )
    return _ok({'items': items})


@app.post('/api/admin/data-sources')
def admin_create_data_source_api(
    payload: dict,
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    type_ = (payload.get('type') or '').strip()
    if type_ != 'postgres':
        raise HTTPException(status_code=400, detail='Only postgres data sources are supported')

    name = (payload.get('name') or '').strip()
    if not name:
        raise HTTPException(status_code=400, detail='name is required')

    cfg = payload.get('config') if isinstance(payload.get('config'), dict) else None
    if not cfg:
        raise HTTPException(status_code=400, detail='config is required')

    token = encrypt_json(cfg)
    try:
        ds = create_data_source(db, name=name, type_=type_, config_encrypted=token)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='Data source name already exists')

    return _ok(
        {
            'id': ds.id,
            'name': ds.name,
            'type': ds.type,
            'is_active': bool(ds.is_active),
            'updated_at': ds.updated_at,
            'config_preview': _ds_preview(cfg),
        }
    )


@app.delete('/api/admin/data-sources/{data_source_id}')
def admin_delete_data_source_api(
    data_source_id: int,
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    ds = get_data_source(db, data_source_id)
    if not ds:
        raise HTTPException(status_code=404, detail='Data source not found')
    if ds.is_active:
        raise HTTPException(status_code=409, detail='Cannot delete active data source')
    ok = delete_data_source(db, data_source_id)
    return _ok({'deleted': ok})


@app.get('/api/admin/users', response_model=ApiResponseAdminUsers)
def admin_users(
    query: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=1000000),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> ApiResponseAdminUsers:
    items = admin_list_users(db, query=query, limit=limit, offset=offset)
    out = [_admin_user_item_out(u) for u in items]
    return _ok(AdminUsersData(items=out, limit=limit, offset=offset))


@app.get('/api/admin/users/{user_id}', response_model=ApiResponseAdminUserDetail)
def admin_user_detail(
    user_id: int,
    grants_limit: int = Query(default=20, ge=0, le=200),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> ApiResponseAdminUserDetail:
    user = admin_get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    grants = admin_list_recent_grants(db, user_id=user_id, limit=grants_limit) if grants_limit else []
    detail = AdminUserDetailOut(user=_admin_user_item_out(user), recent_grants=[_admin_grant_out(g) for g in grants])
    return _ok(detail)


@app.post('/api/admin/membership/grant', response_model=ApiResponseAdminUserItem)
def admin_membership_grant(
    payload: AdminMembershipGrantIn,
    admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> ApiResponseAdminUserItem:
    plan = (payload.plan or '').strip().lower()
    if plan != 'pro_annual':
        raise HTTPException(status_code=400, detail='Only plan=pro_annual is supported')
    try:
        user = admin_grant_membership(
            db,
            user_id=payload.user_id,
            actor_user_id=admin.id,
            plan=plan,
            months=payload.months,
            start_at=payload.start_at,
            reason=payload.reason,
            note=payload.note,
        )
    except ValueError as e:
        if str(e) == 'already_active_pro':
            raise HTTPException(status_code=409, detail='User already has active Pro. Use /extend instead.')
        raise
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return _ok(_admin_user_item_out(user))


@app.post('/api/admin/membership/extend', response_model=ApiResponseAdminUserItem)
def admin_membership_extend(
    payload: AdminMembershipExtendIn,
    admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> ApiResponseAdminUserItem:
    user = admin_extend_membership(
        db,
        user_id=payload.user_id,
        actor_user_id=admin.id,
        months=payload.months,
        reason=payload.reason,
        note=payload.note,
    )
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return _ok(_admin_user_item_out(user))


@app.post('/api/admin/membership/suspend', response_model=ApiResponseAdminUserItem)
def admin_membership_suspend(
    payload: AdminMembershipActionIn,
    admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> ApiResponseAdminUserItem:
    user = admin_suspend_membership(
        db,
        user_id=payload.user_id,
        actor_user_id=admin.id,
        reason=payload.reason,
        note=payload.note,
    )
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return _ok(_admin_user_item_out(user))


@app.post('/api/admin/membership/revoke', response_model=ApiResponseAdminUserItem)
def admin_membership_revoke(
    payload: AdminMembershipActionIn,
    admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> ApiResponseAdminUserItem:
    user = admin_revoke_membership(
        db,
        user_id=payload.user_id,
        actor_user_id=admin.id,
        reason=payload.reason,
        note=payload.note,
    )
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return _ok(_admin_user_item_out(user))


@app.get('/api/admin/configs', response_model=ApiResponseAdminConfigs)
def admin_list_configs(
    _admin: User = Depends(_require_admin_user),
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
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> ApiResponseAdminConfig:
    cfg = upsert_admin_config(db, config_key, payload.config_value)
    data = AdminConfigItem(
        config_key=cfg.config_key,
        config_value=cfg.config_value,
        updated_at=cfg.updated_at,
    )
    return _ok(data)
