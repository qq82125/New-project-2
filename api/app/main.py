from __future__ import annotations

import os
from typing import Literal
from uuid import UUID

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from secrets import compare_digest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine, desc, func, select, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.session import SessionLocal, get_db
from app.models import ProductRejected, RawDocument, User
from app.repositories.dashboard import get_admin_stats, get_breakdown, get_radar, get_rankings, get_summary, get_trend
from app.repositories.data_sources import (
    activate_data_source,
    create_data_source,
    delete_data_source,
    get_data_source,
    list_data_sources,
    update_data_source,
)
from app.repositories.company_tracking import get_company_tracking_detail, list_company_tracking
from app.repositories.changes import get_change_detail, get_change_stats, list_recent_changes
from app.repositories.products import admin_search_products, get_company, get_product, list_full_products, search_products
from app.repositories.product_params import list_product_params
from app.repositories.radar import get_admin_config, get_product_timeline, list_admin_configs, upsert_admin_config
from app.repositories.radar import count_active_subscriptions_by_subscriber, create_subscription
from app.repositories.source_runs import latest_runs, list_source_runs, list_source_runs_page
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
    ApiResponseAdminStats,
    ApiResponsePublicContactInfo,
    ApiResponseProduct,
    ApiResponseProductParams,
    ApiResponseChangeStats,
    ApiResponseChangesList,
    ApiResponseChangeDetail,
    ApiResponseProductTimeline,
    ApiResponseRadar,
    ApiResponseRankings,
    ApiResponseBreakdown,
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
    DashboardBreakdownData,
    DashboardBreakdownItem,
    AdminStatsData,
    ProductOut,
    ProductParamOut,
    ProductParamsData,
    SearchData,
    SearchItem,
    StatusData,
    StatusItem,
    AuthLoginIn,
    AuthRegisterIn,
    AuthUserOut,
    PublicContactInfo,
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
    ApiResponseMe,
    MeOut,
    MePlanOut,
    MeUserOut,
    ProductTimelineItemOut,
    ProductTimelineOut,
    ChangeStatsOut,
    ChangeListItemOut,
    ChangesListOut,
    ChangeDetailOut,
    AdminRejectedProductsData,
    ApiResponseAdminRejectedProducts,
    ApiResponseParamsExtract,
    ApiResponseParamsRollback,
    ParamsExtractResultOut,
    ParamsRollbackResultOut,
    ProductRejectedOut,
)
from app.services.auth import (
    create_session_token,
    hash_password,
    normalize_email,
    parse_session_token,
    verify_password,
)
from app.services.entitlements import get_entitlements, get_membership_info
from app.services.exports import export_changes_to_csv, export_search_to_csv
from app.services.crypto import decrypt_json, encrypt_json
from app.services.plan import compute_plan
from app.services.source_audit import run_source_audit
from app.services.data_quality import run_data_quality_audit
from app.pipeline.ingest import save_raw_document
from app.services.product_params_extract import extract_params_for_raw_document, rollback_params_for_raw_document
from app.services.supplement_sync import (
    DEFAULT_SUPPLEMENT_SOURCE_NAME,
    run_nmpa_query_supplement_now,
    run_supplement_sync_now,
)
from app.services.ivd_dictionary import IVD_SCOPE_ALLOWLIST

app = FastAPI(title='IVD产品雷达 API', version='0.4.0')

PRIMARY_SOURCE_NAME = 'NMPA注册产品库（主数据源）'
POSTGRES_SOURCE_TYPE = 'postgres'
LOCAL_REGISTRY_SOURCE_TYPE = 'local_registry'

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
SearchMode = Literal['limited', 'full']
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
        expires='Thu, 01 Jan 1970 00:00:00 GMT',
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


def require_admin(current_user: User = Depends(_require_current_user)) -> User:
    # Public alias for dependency injection (keeps existing logic intact).
    return _require_admin_user(current_user)


def require_pro(
    current_user: User = Depends(_require_current_user),
    db: Session = Depends(get_db),
) -> User:
    p = compute_plan(current_user, db)
    if not getattr(p, 'is_pro', False):
        raise HTTPException(
            status_code=403,
            detail={'code': 'PRO_REQUIRED', 'message': 'Pro plan required. Please upgrade.'},
        )
    return current_user


def _raise_pro_required() -> None:
    raise HTTPException(
        status_code=403,
        detail={'code': 'PRO_REQUIRED', 'message': 'Pro plan required. Please upgrade.'},
    )


def _is_pro_user(current_user: User | None, db: Session) -> bool:
    if not current_user:
        return False
    try:
        return bool(getattr(compute_plan(current_user, db), 'is_pro', False))
    except Exception:
        return False


def _debug_enabled() -> bool:
    # Strict-ish gating: enabled by env override, otherwise only when cookie is not secure (dev compose default).
    if os.environ.get('ENABLE_DEBUG_ENDPOINTS', '').strip().lower() in {'1', 'true', 'yes', 'y'}:
        return True
    try:
        return not bool(_settings().auth_cookie_secure)
    except Exception:
        return False


def _require_debug_enabled() -> None:
    if not _debug_enabled():
        raise HTTPException(status_code=404, detail='Not found')


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
        ivd_category=getattr(product, 'ivd_category', None),
        company=serialize_company(product.company) if product.company else None,
    )


def serialize_product_limited(product) -> ProductOut:
    # Keep schema stable but trim optional fields for Free users (summary view).
    return ProductOut(
        id=product.id,
        udi_di=product.udi_di,
        reg_no=product.reg_no,
        name=product.name,
        status=product.status,
        approved_date=None,
        expiry_date=product.expiry_date,
        class_name=None,
        ivd_category=getattr(product, 'ivd_category', None),
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

    db = SessionLocal()
    try:
        if email and '@' in email and password:
            existing = get_user_by_email(db, email)
            if existing:
                if existing.role != 'admin':
                    existing.role = 'admin'
                    db.add(existing)
                    db.commit()
            else:
                password_hash = hash_password(password)
                create_user(db, email=email, password_hash=password_hash, role='admin')

        # Keep data-source policy aligned with current scope upgrade:
        # NMPA registration as primary source and UDI as supplement source.
        rows = list_data_sources(db)
        if rows:
            primary = None
            supplement = None
            for ds in rows:
                n = (ds.name or '').strip()
                n0 = n.lower()
                if primary is None and ('主源' in n or '注册产品库' in n or '主数据源' in n):
                    primary = ds
                if supplement is None and ('补全' in n or '纠错' in n or '补充' in n or 'udi' in n0):
                    supplement = ds
            if primary is None:
                primary = next(
                    (
                        x
                        for x in rows
                        if (
                            'nmpa' in (x.name or '').lower()
                            and '补全' not in (x.name or '')
                            and '纠错' not in (x.name or '')
                            and '补充' not in (x.name or '')
                            and 'udi' not in (x.name or '').lower()
                        )
                    ),
                    None,
                )
            if primary is None:
                primary = next((x for x in rows if bool(getattr(x, 'is_active', False))), rows[0])
            if supplement is None:
                supplement = next((x for x in rows if x.id != primary.id), None)

            name_to_id = {(x.name or '').strip(): int(x.id) for x in rows}
            if primary and primary.name != PRIMARY_SOURCE_NAME and PRIMARY_SOURCE_NAME not in name_to_id:
                primary = update_data_source(db, int(primary.id), name=PRIMARY_SOURCE_NAME) or primary
            if supplement and supplement.name != DEFAULT_SUPPLEMENT_SOURCE_NAME and DEFAULT_SUPPLEMENT_SOURCE_NAME not in name_to_id:
                supplement = update_data_source(db, int(supplement.id), name=DEFAULT_SUPPLEMENT_SOURCE_NAME) or supplement
            if primary and not bool(getattr(primary, 'is_active', False)):
                activate_data_source(db, int(primary.id))

            sched = get_admin_config(db, 'source_supplement_schedule')
            sched_raw = sched.config_value if (sched and isinstance(sched.config_value, dict)) else {}
            upsert_admin_config(
                db,
                'source_supplement_schedule',
                {
                    'enabled': bool(sched_raw.get('enabled', True)),
                    'interval_hours': max(1, int(sched_raw.get('interval_hours', 24) or 24)),
                    'batch_size': max(50, int(sched_raw.get('batch_size', 1000) or 1000)),
                    'recent_hours': max(1, int(sched_raw.get('recent_hours', 72) or 72)),
                    'source_name': (supplement.name if supplement else DEFAULT_SUPPLEMENT_SOURCE_NAME),
                    'nmpa_query_enabled': bool(sched_raw.get('nmpa_query_enabled', True)),
                    'nmpa_query_interval_hours': max(1, int(sched_raw.get('nmpa_query_interval_hours', 24) or 24)),
                    'nmpa_query_batch_size': max(10, int(sched_raw.get('nmpa_query_batch_size', 200) or 200)),
                    'nmpa_query_url': str(
                        sched_raw.get('nmpa_query_url')
                        or 'https://www.nmpa.gov.cn/datasearch/home-index.html?itemId=2c9ba384759c957701759ccef50f032b#category=ylqx'
                    ),
                    'nmpa_query_timeout_seconds': max(
                        5, int(sched_raw.get('nmpa_query_timeout_seconds', 20) or 20)
                    ),
                },
            )

        upsert_admin_config(
            db,
            'ivd_scope_policy',
            {
                'primary_source': PRIMARY_SOURCE_NAME,
                'supplement_source': DEFAULT_SUPPLEMENT_SOURCE_NAME,
                'allowlist': list(IVD_SCOPE_ALLOWLIST),
                'updated_by': 'startup-bootstrap',
            },
        )
    except Exception:
        # Never block API startup on optional bootstrap sync.
        try:
            db.rollback()
        except Exception:
            pass
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


@app.get('/api/me', response_model=ApiResponseMe)
def me_v2(
    current_user: User = Depends(_require_current_user),
    db: Session = Depends(get_db),
) -> ApiResponseMe:
    p = compute_plan(current_user, db)
    data = MeOut(
        user=MeUserOut(id=current_user.id, email=current_user.email, role=current_user.role),
        plan=MePlanOut(
            plan=p.plan,
            plan_status=p.plan_status,
            plan_expires_at=p.plan_expires_at,
            is_pro=p.is_pro,
            is_admin=p.is_admin,
        ),
    )
    return _ok(data)


@app.get('/api/_debug/pro-required')
def debug_pro_required(
    _dbg: None = Depends(_require_debug_enabled),
    user: User = Depends(require_pro),
) -> dict:
    return _ok({'ok': True, 'user_id': user.id, 'email': user.email})


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


@app.get('/api/public/contact-info', response_model=ApiResponsePublicContactInfo)
def public_contact_info(db: Session = Depends(get_db)) -> ApiResponsePublicContactInfo:
    """Public (no-auth) contact info used by /contact and upgrade flows.

    Data lives in admin_configs so admins can edit without code changes.
    Only whitelisted fields are exposed.
    """
    cfg = get_admin_config(db, 'public_contact_info')
    v = cfg.config_value if (cfg and isinstance(cfg.config_value, dict)) else {}

    def _clean_str(x):
        if not isinstance(x, str):
            return None
        s = x.strip()
        return s or None

    data = PublicContactInfo(
        email=_clean_str(v.get('email')),
        wecom=_clean_str(v.get('wecom')),
        form_url=_clean_str(v.get('form_url')),
    )
    return _ok(data)


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
    current_user: User = Depends(_require_current_user),
    db: Session = Depends(get_db),
) -> ApiResponseRankings:
    ent = get_entitlements(current_user)
    if getattr(current_user, 'role', None) != 'admin' and ent.trend_range_days <= 30:
        raise HTTPException(status_code=403, detail='Rankings are available on Pro only. Upgrade to Pro.')
    top_new, top_removed = get_rankings(db, days, limit)
    data = DashboardRankingsData(
        top_new_days=[DashboardRankingItem(metric_date=row[0], value=int(row[1])) for row in top_new],
        top_removed_days=[DashboardRankingItem(metric_date=row[0], value=int(row[1])) for row in top_removed],
    )
    return _ok(data)


@app.get('/api/dashboard/radar', response_model=ApiResponseRadar)
def dashboard_radar(
    current_user: User = Depends(_require_current_user),
    db: Session = Depends(get_db),
) -> ApiResponseRadar:
    ent = get_entitlements(current_user)
    if getattr(current_user, 'role', None) != 'admin' and ent.trend_range_days <= 30:
        raise HTTPException(status_code=403, detail='Radar is available on Pro only. Upgrade to Pro.')
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


@app.get('/api/dashboard/breakdown', response_model=ApiResponseBreakdown)
def dashboard_breakdown(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(_require_current_user),
    db: Session = Depends(get_db),
) -> ApiResponseBreakdown:
    # Keep it consistent with other "premium dashboard insights".
    ent = get_entitlements(current_user)
    if getattr(current_user, 'role', None) != 'admin' and ent.trend_range_days <= 30:
        raise HTTPException(status_code=403, detail='Breakdown is available on Pro only. Upgrade to Pro.')

    raw = get_breakdown(db, limit=int(limit))
    data = DashboardBreakdownData(
        total_ivd_products=int(raw.get('total_ivd_products') or 0),
        by_ivd_category=[DashboardBreakdownItem(key=k, value=int(v)) for k, v in (raw.get('by_ivd_category') or [])],
        by_source=[DashboardBreakdownItem(key=k, value=int(v)) for k, v in (raw.get('by_source') or [])],
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
    mode: SearchMode | None = Query(default=None, description='limited (free) or full (pro)'),
    current_user: User | None = Depends(_get_current_user_optional),
    db: Session = Depends(get_db),
) -> ApiResponseSearch:
    ent = get_entitlements(current_user or object())
    is_admin = getattr(current_user, 'role', None) == 'admin' if current_user else False
    is_pro = ent.trend_range_days > 30

    # Pro-only full mode: Free users cannot request full data even if bypassing the frontend.
    plan_is_pro = _is_pro_user(current_user, db)
    effective_mode: SearchMode = mode or ('full' if plan_is_pro else 'limited')
    if effective_mode == 'full' and not plan_is_pro:
        _raise_pro_required()

    if effective_mode == 'limited' and not plan_is_pro:
        # Enforce "first 10 only" regardless of requested pagination params.
        page = 1
        page_size = 10

    # Pro-only search features:
    # - larger page size
    # - sorting by expiry_date (used for expiry risk workflows)
    if not is_admin and not is_pro:
        if page_size > 20:
            raise HTTPException(status_code=403, detail='Free users can only use page_size<=20. Upgrade to Pro for more.')
        if sort_by == 'expiry_date':
            raise HTTPException(status_code=403, detail='Sorting by expiry_date is available on Pro only. Upgrade to Pro.')

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
    serializer = serialize_product if effective_mode == 'full' else serialize_product_limited
    data = SearchData(
        total=total,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        items=[SearchItem(product=serializer(item)) for item in products],
    )
    return _ok(data)


@app.get('/api/admin/products', response_model=ApiResponseSearch)
def admin_products(
    q: str | None = Query(default=None),
    company: str | None = Query(default=None),
    reg_no: str | None = Query(default=None),
    status: str | None = Query(default=None),
    is_ivd: str = Query(default='true', pattern='^(true|false|all)$'),
    ivd_category: str | None = Query(default=None),
    ivd_version: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort_by: SortBy = Query(default='updated_at'),
    sort_order: SortOrder = Query(default='desc'),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> ApiResponseSearch:
    ivd_filter = True if is_ivd == 'true' else False if is_ivd == 'false' else None
    products, total = admin_search_products(
        db,
        query=q,
        company=company,
        reg_no=reg_no,
        status=status,
        is_ivd=ivd_filter,
        ivd_category=ivd_category,
        ivd_version=ivd_version,
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


@app.get('/api/admin/stats', response_model=ApiResponseAdminStats)
def admin_stats(
    limit: int = Query(default=50, ge=1, le=200),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> ApiResponseAdminStats:
    raw = get_admin_stats(db, limit=int(limit))
    data = AdminStatsData(
        total_ivd_products=int(raw.get('total_ivd_products') or 0),
        rejected_total=int(raw.get('rejected_total') or 0),
        by_ivd_category=[DashboardBreakdownItem(key=k, value=int(v)) for k, v in (raw.get('by_ivd_category') or [])],
        by_source=[DashboardBreakdownItem(key=k, value=int(v)) for k, v in (raw.get('by_source') or [])],
    )
    return _ok(data)


@app.get('/api/admin/rejected-products', response_model=ApiResponseAdminRejectedProducts)
def admin_rejected_products(
    q: str | None = Query(default=None, description='substring match on source_key'),
    source: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> ApiResponseAdminRejectedProducts:
    stmt = select(ProductRejected)
    if source:
        stmt = stmt.where(ProductRejected.source == str(source))
    if q:
        stmt = stmt.where(ProductRejected.source_key.ilike(f'%{q}%'))

    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = list(
        db.scalars(
            stmt.order_by(desc(ProductRejected.rejected_at)).offset((page - 1) * page_size).limit(page_size)
        ).all()
    )
    items = [
        ProductRejectedOut(
            id=x.id,
            source=x.source,
            source_key=x.source_key,
            raw_document_id=x.raw_document_id,
            reason=x.reason,
            ivd_version=x.ivd_version,
            rejected_at=x.rejected_at,
        )
        for x in rows
    ]
    return _ok(AdminRejectedProductsData(total=total, page=page, page_size=page_size, items=items))


def _infer_doc_type_from_filename(name: str) -> str:
    n = (name or '').lower()
    if n.endswith('.pdf'):
        return 'pdf'
    if n.endswith('.html') or n.endswith('.htm'):
        return 'html'
    return 'text'


@app.post('/api/admin/params/extract', response_model=ApiResponseParamsExtract)
async def admin_params_extract(
    mode: str = Query(default='dry-run', pattern='^(dry-run|execute)$'),
    raw_document_id: str | None = Form(default=None),
    di: str | None = Form(default=None),
    registry_no: str | None = Form(default=None),
    extract_version: str = Form(default='param_v1_20260213'),
    doc_type: str | None = Form(default=None),
    source_url: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> ApiResponseParamsExtract:
    rid: UUID | None = None
    if raw_document_id:
        rid = UUID(str(raw_document_id))
    else:
        if file is None:
            raise HTTPException(status_code=400, detail='either raw_document_id or file is required')
        content = await file.read()
        dtype = (doc_type or _infer_doc_type_from_filename(file.filename or '')).strip().lower()
        run_id = f'admin_params:{admin.id}'
        rid = save_raw_document(
            db,
            source='MANUAL',
            url=source_url,
            content=content,
            doc_type=dtype,
            run_id=run_id,
        )

    dry_run = mode != 'execute'
    res = extract_params_for_raw_document(
        db,
        raw_document_id=rid,
        di=(str(di).strip() or None) if di else None,
        registry_no=(str(registry_no).strip() or None) if registry_no else None,
        extract_version=str(extract_version),
        dry_run=bool(dry_run),
    )
    out = ParamsExtractResultOut(
        dry_run=res.dry_run,
        raw_document_id=res.raw_document_id,
        di=res.di,
        registry_no=res.registry_no,
        bound_product_id=res.bound_product_id,
        pages=res.pages,
        deleted_existing=res.deleted_existing,
        extracted=res.extracted,
        extract_version=res.extract_version,
        parse_log=res.parse_log,
    )
    return _ok(out)


@app.post('/api/admin/params/rollback', response_model=ApiResponseParamsRollback)
def admin_params_rollback(
    mode: str = Query(default='dry-run', pattern='^(dry-run|execute)$'),
    raw_document_id: str = Form(...),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> ApiResponseParamsRollback:
    rid = UUID(str(raw_document_id))
    dry_run = mode != 'execute'
    res = rollback_params_for_raw_document(db, raw_document_id=rid, dry_run=bool(dry_run))
    return _ok(ParamsRollbackResultOut(dry_run=res.dry_run, raw_document_id=res.raw_document_id, deleted=res.deleted))


@app.get('/api/products/full', response_model=ApiResponseSearch)
def products_full(
    q: str | None = Query(default=None),
    company: str | None = Query(default=None),
    reg_no: str | None = Query(default=None),
    status: str | None = Query(default=None),
    class_prefix: str | None = Query(default=None),
    ivd_category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=200),
    sort_by: SortBy = Query(default='updated_at'),
    sort_order: SortOrder = Query(default='desc'),
    _user: User = Depends(require_pro),
    db: Session = Depends(get_db),
) -> ApiResponseSearch:
    items, total = list_full_products(
        db,
        query=q,
        company=company,
        reg_no=reg_no,
        status=status,
        class_prefix=class_prefix,
        ivd_category=ivd_category,
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
        items=[SearchItem(product=serialize_product(item)) for item in items],
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


@app.get('/api/export/changes.csv')
def export_changes_csv(
    days: int = Query(default=30, ge=1, le=365),
    change_type: str | None = Query(default=None),
    q: str | None = Query(default=None),
    company: str | None = Query(default=None),
    reg_no: str | None = Query(default=None),
    _pro: User = Depends(require_pro),
    db: Session = Depends(get_db),
) -> Response:
    csv_text = export_changes_to_csv(
        db,
        plan='pro',
        days=days,
        change_type=change_type,
        q=q,
        company=company,
        reg_no=reg_no,
    )
    headers = {'Content-Disposition': 'attachment; filename="ivd_changes_export.csv"'}
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
def product_detail(
    product_id: str,
    mode: SearchMode | None = Query(default=None, description='limited (free) or full (pro)'),
    current_user: User | None = Depends(_get_current_user_optional),
    db: Session = Depends(get_db),
) -> ApiResponseProduct:
    plan_is_pro = _is_pro_user(current_user, db)
    effective_mode: SearchMode = mode or ('full' if plan_is_pro else 'limited')
    if effective_mode == 'full' and not plan_is_pro:
        _raise_pro_required()

    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')
    if effective_mode == 'limited' and not plan_is_pro:
        return _ok(serialize_product_limited(product))
    return _ok(serialize_product(product))


@app.get('/api/products/{product_id}/params', response_model=ApiResponseProductParams)
def product_params(
    product_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    _pro: User = Depends(require_pro),
    db: Session = Depends(get_db),
) -> ApiResponseProductParams:
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')

    rows = list_product_params(db, product=product, limit=limit)
    items = [
        ProductParamOut(
            id=param.id,
            param_code=param.param_code,
            value_num=(float(param.value_num) if param.value_num is not None else None),
            value_text=param.value_text,
            unit=param.unit,
            range_low=(float(param.range_low) if param.range_low is not None else None),
            range_high=(float(param.range_high) if param.range_high is not None else None),
            conditions=param.conditions,
            confidence=float(param.confidence),
            evidence_text=param.evidence_text,
            evidence_page=param.evidence_page,
            source=(doc.source if doc else None),
            source_url=(doc.source_url if doc else None),
            extract_version=param.extract_version,
        )
        for param, doc in rows
    ]
    return _ok(
        ProductParamsData(
            product_id=product.id,
            product_name=product.name,
            items=items,
        )
    )


@app.get('/api/products/{product_id}/timeline', response_model=ApiResponseProductTimeline)
def product_timeline(
    product_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    _pro: User = Depends(require_pro),
    db: Session = Depends(get_db),
) -> ApiResponseProductTimeline:
    from uuid import UUID

    try:
        pid = UUID(str(product_id))
    except Exception:
        raise HTTPException(status_code=404, detail='Product not found')

    items = get_product_timeline(db, product_id=pid, limit=limit)
    out = ProductTimelineOut(
        product_id=pid,
        items=[
            ProductTimelineItemOut(
                id=int(x.id),
                change_type=str(getattr(x, 'change_type', '') or ''),
                changed_fields=getattr(x, 'changed_fields', None) or {},
                changed_at=getattr(x, 'changed_at', None),
            )
            for x in items
        ],
    )
    return _ok(out)


@app.get('/api/companies/{company_id}', response_model=ApiResponseCompany)
def company_detail(company_id: str, db: Session = Depends(get_db)) -> ApiResponseCompany:
    company = get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail='Company not found')
    return _ok(serialize_company(company))


@app.get('/api/company-tracking')
def companies_tracking_list(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=200),
    _pro: User = Depends(require_pro),
    db: Session = Depends(get_db),
) -> dict:
    items, total = list_company_tracking(db, query=q, page=page, page_size=page_size)
    return _ok(
        {
            'total': total,
            'page': page,
            'page_size': page_size,
            'items': items,
        }
    )


@app.get('/api/company-tracking/{company_id}')
def company_tracking_detail(
    company_id: str,
    days: int = Query(default=30, ge=1, le=365),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=200),
    limit: int | None = Query(default=None, ge=1, le=200),
    _pro: User = Depends(require_pro),
    db: Session = Depends(get_db),
) -> dict:
    effective_page_size = int(limit) if limit is not None else int(page_size)
    out = get_company_tracking_detail(
        db,
        company_id=company_id,
        days=days,
        page=page,
        page_size=effective_page_size,
    )
    if not out:
        raise HTTPException(status_code=404, detail='Company tracking not found')
    return _ok(out)


@app.get('/api/status', response_model=ApiResponseStatus)
def status(
    current_user: User | None = Depends(_get_current_user_optional),
    db: Session = Depends(get_db),
) -> ApiResponseStatus:
    ent = get_entitlements(current_user or object())
    is_admin = getattr(current_user, 'role', None) == 'admin' if current_user else False
    is_pro = ent.trend_range_days > 30

    runs = latest_runs(db)
    if not is_admin and not is_pro:
        runs = runs[:1]
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
                ivd_kept_count=getattr(run, 'ivd_kept_count', 0),
                non_ivd_skipped_count=getattr(run, 'non_ivd_skipped_count', 0),
                started_at=run.started_at,
                finished_at=run.finished_at,
            )
            for run in runs
        ]
    )
    return _ok(data)


@app.get('/api/changes/stats', response_model=ApiResponseChangeStats)
def changes_stats(
    days: int = Query(default=30, ge=1, le=365),
    _user: User | None = Depends(_get_current_user_optional),
    db: Session = Depends(get_db),
) -> ApiResponseChangeStats:
    total, by_type = get_change_stats(db, days=days)
    return _ok(ChangeStatsOut(days=days, total=total, by_type=by_type))


@app.get('/api/changes', response_model=ApiResponseChangesList)
def changes_list(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    change_type: str | None = Query(default=None),
    q: str | None = Query(default=None),
    company: str | None = Query(default=None),
    reg_no: str | None = Query(default=None),
    _pro: User = Depends(require_pro),
    db: Session = Depends(get_db),
) -> ApiResponseChangesList:
    effective_page_size = int(page_size or limit or 50)
    result = list_recent_changes(
        db,
        days=days,
        limit=effective_page_size,
        page=page,
        page_size=effective_page_size,
        change_type=change_type,
        q=q,
        company=company,
        reg_no=reg_no,
    )
    # Backwards-compatible: older implementations (and some unit tests) expect
    # list_recent_changes() to return just the rows. Newer code returns (rows, total).
    if isinstance(result, tuple) and len(result) == 2:
        rows, total = result
    else:
        rows = result
        total = len(rows)
    items = []
    for change, product in rows:
        items.append(
            ChangeListItemOut(
                id=int(change.id),
                change_type=str(getattr(change, 'change_type', '') or ''),
                change_date=getattr(change, 'change_date', None),
                changed_at=getattr(change, 'changed_at', None),
                product=serialize_product(product),
            )
        )
    return _ok(ChangesListOut(days=days, total=total, page=page, page_size=effective_page_size, items=items))


@app.get('/api/changes/{change_id}', response_model=ApiResponseChangeDetail)
def change_detail(
    change_id: int,
    _pro: User = Depends(require_pro),
    db: Session = Depends(get_db),
) -> ApiResponseChangeDetail:
    change = get_change_detail(db, change_id=change_id)
    if not change:
        raise HTTPException(status_code=404, detail='Change not found')
    out = ChangeDetailOut(
        id=int(change.id),
        change_type=str(getattr(change, 'change_type', '') or ''),
        change_date=getattr(change, 'change_date', None),
        changed_at=getattr(change, 'changed_at', None),
        entity_type=str(getattr(change, 'entity_type', '') or ''),
        entity_id=getattr(change, 'entity_id', None),
        changed_fields=getattr(change, 'changed_fields', None) or {},
        before_json=getattr(change, 'before_json', None),
        after_json=getattr(change, 'after_json', None),
    )
    return _ok(out)


def _spawn_sync_thread() -> None:
    import threading

    def _job():
        from app.workers.sync import sync_nmpa_ivd

        sync_nmpa_ivd()

    threading.Thread(target=_job, daemon=True).start()


@app.get('/api/admin/source-runs')
def admin_source_runs(
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=200),
    limit: int | None = Query(default=None, ge=1, le=200),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    # Backward compatible:
    # - old clients send `limit=...` (no paging), treat as first page.
    safe_page = int(page or 1)
    safe_page_size = int(page_size or (limit or 10))

    runs, total = list_source_runs_page(db, page=safe_page, page_size=safe_page_size)
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
            'ivd_kept_count': int(getattr(r, 'ivd_kept_count', 0) or 0),
            'non_ivd_skipped_count': int(getattr(r, 'non_ivd_skipped_count', 0) or 0),
            'source_notes': getattr(r, 'source_notes', None),
            'started_at': r.started_at,
            'finished_at': getattr(r, 'finished_at', None),
        }
        for r in runs
    ]
    return _ok({'items': items, 'total': int(total), 'page': safe_page, 'page_size': safe_page_size})


@app.post('/api/admin/sync/run')
def admin_sync_run(
    background_tasks: BackgroundTasks,
    _admin: User = Depends(_require_admin_user),
) -> dict:
    background_tasks.add_task(_spawn_sync_thread)
    return _ok({'queued': True})


@app.post('/api/admin/source-audit/run')
def admin_run_source_audit(
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    report = run_source_audit(db, _settings())
    upsert_admin_config(db, 'source_audit_last', report)
    return _ok({'report': report})


@app.get('/api/admin/source-audit/last')
def admin_get_last_source_audit(
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    cfg = get_admin_config(db, 'source_audit_last')
    return _ok({'report': (cfg.config_value if cfg else None)})


@app.post('/api/admin/source-supplement/run')
def admin_run_source_supplement(
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    report = run_supplement_sync_now(db, reason='manual:admin')
    return _ok({'report': report})


@app.get('/api/admin/source-supplement/last')
def admin_get_last_source_supplement(
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    cfg = get_admin_config(db, 'source_supplement_last_run')
    return _ok({'report': (cfg.config_value if cfg else None)})


@app.post('/api/admin/source-nmpa-query/run')
def admin_run_source_nmpa_query(
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    report = run_nmpa_query_supplement_now(db, reason='manual:admin')
    return _ok({'report': report})


@app.get('/api/admin/source-nmpa-query/last')
def admin_get_last_source_nmpa_query(
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    cfg = get_admin_config(db, 'source_nmpa_query_last_run')
    return _ok({'report': (cfg.config_value if cfg else None)})


@app.post('/api/admin/data-quality/run')
def admin_run_data_quality_audit(
    sample_limit: int = Query(default=20, ge=1, le=100),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    report = run_data_quality_audit(db, sample_limit=sample_limit)
    upsert_admin_config(db, 'data_quality_last', report)
    return _ok({'report': report})


@app.get('/api/admin/data-quality/last')
def admin_get_last_data_quality_audit(
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    cfg = get_admin_config(db, 'data_quality_last')
    return _ok({'report': (cfg.config_value if cfg else None)})


def _ds_preview(cfg: dict) -> dict:
    return {
        'folder': cfg.get('folder') or '',
        'ingest_new': bool(cfg.get('ingest_new', True)),
        'ingest_chunk_size': int(cfg.get('ingest_chunk_size') or 2000),
        'host': cfg.get('host') or '',
        'port': int(cfg.get('port') or 5432),
        'database': cfg.get('database') or '',
        'username': cfg.get('username') or '',
        'sslmode': cfg.get('sslmode'),
        'source_table': cfg.get('source_table') or 'public.products',
        'source_query': cfg.get('source_query') or None,
    }


def _normalize_data_source_config(type_: str, cfg: dict) -> dict:
    if type_ == POSTGRES_SOURCE_TYPE:
        return {
            'host': str(cfg.get('host') or '').strip(),
            'port': int(cfg.get('port') or 5432),
            'database': str(cfg.get('database') or '').strip(),
            'username': str(cfg.get('username') or '').strip(),
            'password': cfg.get('password'),
            'sslmode': (str(cfg.get('sslmode')).strip() if cfg.get('sslmode') not in {None, ''} else None),
            'source_table': str(cfg.get('source_table') or 'public.products').strip() or 'public.products',
            'source_query': (str(cfg.get('source_query')).strip() if cfg.get('source_query') not in {None, ''} else None),
        }
    if type_ == LOCAL_REGISTRY_SOURCE_TYPE:
        folder = str(cfg.get('folder') or '').strip()
        if not folder:
            raise HTTPException(status_code=400, detail='config.folder is required for local_registry source')
        ingest_chunk_size = max(100, min(10000, int(cfg.get('ingest_chunk_size') or 2000)))
        return {
            'folder': folder,
            'ingest_new': bool(cfg.get('ingest_new', True)),
            'ingest_chunk_size': ingest_chunk_size,
        }
    raise HTTPException(status_code=400, detail='Unsupported data source type')


def _ds_out(ds, cfg: dict) -> dict:
    return {
        'id': ds.id,
        'name': ds.name,
        'type': ds.type,
        'is_active': bool(ds.is_active),
        'updated_at': ds.updated_at,
        'config_preview': _ds_preview(cfg),
    }


def _test_postgres_connection(cfg: dict) -> tuple[bool, str]:
    host = str(cfg.get('host') or '').strip()
    database = str(cfg.get('database') or '').strip()
    username = str(cfg.get('username') or '').strip()
    password = cfg.get('password')
    sslmode = cfg.get('sslmode')
    try:
        port = int(cfg.get('port') or 5432)
    except Exception:
        port = 5432

    if not host or not database or not username:
        return False, 'Missing required fields (host/database/username)'
    if not password:
        return False, 'Missing password'

    query = {}
    if sslmode:
        query['sslmode'] = str(sslmode)

    url = URL.create(
        'postgresql+psycopg',
        username=username,
        password=str(password),
        host=host,
        port=port,
        database=database,
        query=query,
    )

    try:
        engine = create_engine(url, poolclass=NullPool, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        return True, 'ok'
    except Exception as e:
        return False, str(e)


def _test_local_registry_source(cfg: dict) -> tuple[bool, str]:
    folder = str(cfg.get('folder') or '').strip()
    if not folder:
        return False, 'Missing required field (folder)'
    if not os.path.isdir(folder):
        return False, f'Folder not found: {folder}'
    try:
        names = os.listdir(folder)
    except Exception as e:
        return False, str(e)
    has_candidate = any((name.lower().endswith('.xlsx') or name.lower().endswith('.zip')) for name in names)
    if not has_candidate:
        return False, 'No .xlsx/.zip files found in folder'
    return True, 'ok'


@app.get('/api/admin/data-sources')
def admin_list_data_sources_api(
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    items = []
    for ds in list_data_sources(db):
        cfg = decrypt_json(ds.config_encrypted)
        items.append(_ds_out(ds, cfg))
    return _ok({'items': items})


@app.post('/api/admin/data-sources')
def admin_create_data_source_api(
    payload: dict,
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    type_ = (payload.get('type') or '').strip()
    if type_ not in {POSTGRES_SOURCE_TYPE, LOCAL_REGISTRY_SOURCE_TYPE}:
        raise HTTPException(status_code=400, detail='Only postgres/local_registry data sources are supported')

    name = (payload.get('name') or '').strip()
    if not name:
        raise HTTPException(status_code=400, detail='name is required')

    cfg = payload.get('config') if isinstance(payload.get('config'), dict) else None
    if not cfg:
        raise HTTPException(status_code=400, detail='config is required')
    cfg = _normalize_data_source_config(type_, cfg)

    token = encrypt_json(cfg)
    try:
        ds = create_data_source(db, name=name, type_=type_, config_encrypted=token)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='Data source name already exists')

    return _ok(_ds_out(ds, cfg))


@app.put('/api/admin/data-sources/{data_source_id}')
def admin_update_data_source_api(
    data_source_id: int,
    payload: dict,
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    ds = get_data_source(db, data_source_id)
    if not ds:
        raise HTTPException(status_code=404, detail='Data source not found')
    type_ = (getattr(ds, 'type', None) or '').strip()
    if type_ not in {POSTGRES_SOURCE_TYPE, LOCAL_REGISTRY_SOURCE_TYPE}:
        raise HTTPException(status_code=400, detail='Unsupported data source type')

    name = (payload.get('name') or '').strip()
    if not name:
        raise HTTPException(status_code=400, detail='name is required')

    cfg_in = payload.get('config') if isinstance(payload.get('config'), dict) else None
    if not cfg_in:
        raise HTTPException(status_code=400, detail='config is required')

    # Merge config with existing, keeping password unless explicitly provided.
    old_cfg = decrypt_json(ds.config_encrypted)
    if not isinstance(old_cfg, dict):
        old_cfg = {}
    new_cfg = {**old_cfg, **cfg_in}
    if type_ == POSTGRES_SOURCE_TYPE:
        if 'password' not in cfg_in:
            # Keep existing password.
            if 'password' in old_cfg:
                new_cfg['password'] = old_cfg.get('password')
        else:
            # If provided but blank, still keep old one.
            if not cfg_in.get('password') and 'password' in old_cfg:
                new_cfg['password'] = old_cfg.get('password')
    new_cfg = _normalize_data_source_config(type_, new_cfg)

    token = encrypt_json(new_cfg)
    try:
        ds2 = update_data_source(db, data_source_id, name=name, config_encrypted=token)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='Data source name already exists')
    if not ds2:
        raise HTTPException(status_code=404, detail='Data source not found')
    return _ok(_ds_out(ds2, new_cfg))


@app.post('/api/admin/data-sources/{data_source_id}/activate')
def admin_activate_data_source_api(
    data_source_id: int,
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    ds = activate_data_source(db, data_source_id)
    if not ds:
        raise HTTPException(status_code=404, detail='Data source not found')
    return _ok({'id': ds.id})


@app.post('/api/admin/data-sources/{data_source_id}/test')
def admin_test_data_source_api(
    data_source_id: int,
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    ds = get_data_source(db, data_source_id)
    if not ds:
        raise HTTPException(status_code=404, detail='Data source not found')
    type_ = (getattr(ds, 'type', None) or '').strip()
    if type_ not in {POSTGRES_SOURCE_TYPE, LOCAL_REGISTRY_SOURCE_TYPE}:
        raise HTTPException(status_code=400, detail='Unsupported data source type')

    cfg = decrypt_json(ds.config_encrypted)
    if not isinstance(cfg, dict):
        raise HTTPException(status_code=400, detail='Invalid data source config')

    if type_ == POSTGRES_SOURCE_TYPE:
        ok, message = _test_postgres_connection(cfg)
    else:
        ok, message = _test_local_registry_source(cfg)
    return _ok({'ok': bool(ok), 'message': message or ('ok' if ok else 'failed')})


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
    payload: dict,
    admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> ApiResponseAdminUserItem:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail='Invalid JSON body')

    user_id = payload.get('user_id')
    try:
        user_id = int(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail='user_id must be an integer')

    plan = str(payload.get('plan') or 'pro_annual').strip().lower()
    if plan != 'pro_annual':
        raise HTTPException(status_code=400, detail='Only plan=pro_annual is supported')

    months = payload.get('months')
    try:
        months = int(months)
    except Exception:
        raise HTTPException(status_code=400, detail='months must be an integer > 0')
    if months <= 0:
        raise HTTPException(status_code=400, detail='months must be an integer > 0')

    start_at = payload.get('start_at')
    # Keep backward compatible: allow null; if provided it must be ISO datetime string.
    if start_at is not None and not isinstance(start_at, str):
        raise HTTPException(status_code=400, detail='start_at must be an ISO datetime string')

    # Ensure user exists (404) before touching DB write path.
    if not admin_get_user(db, user_id):
        raise HTTPException(status_code=404, detail='User not found')

    reason = payload.get('reason')
    note = payload.get('note')
    try:
        user = admin_grant_membership(
            db,
            user_id=user_id,
            actor_user_id=admin.id,
            plan=plan,
            months=months,
            start_at=None,
            reason=str(reason).strip() if isinstance(reason, str) and reason.strip() else None,
            note=str(note).strip() if isinstance(note, str) and note.strip() else None,
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
    payload: dict,
    admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> ApiResponseAdminUserItem:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail='Invalid JSON body')

    user_id = payload.get('user_id')
    try:
        user_id = int(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail='user_id must be an integer')

    months = payload.get('months')
    try:
        months = int(months)
    except Exception:
        raise HTTPException(status_code=400, detail='months must be an integer > 0')
    if months <= 0:
        raise HTTPException(status_code=400, detail='months must be an integer > 0')

    if not admin_get_user(db, user_id):
        raise HTTPException(status_code=404, detail='User not found')

    reason = payload.get('reason')
    note = payload.get('note')
    user = admin_extend_membership(
        db,
        user_id=user_id,
        actor_user_id=admin.id,
        months=months,
        reason=str(reason).strip() if isinstance(reason, str) and reason.strip() else None,
        note=str(note).strip() if isinstance(note, str) and note.strip() else None,
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
