from __future__ import annotations

import json
import os
from datetime import date as dt_date
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from secrets import compare_digest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine, desc, func, select, text, update
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.db.session import SessionLocal, get_db
from app.models import (
    ChangeLog,
    Company,
    CompanyAlias,
    ConflictQueue,
    MethodologyNode,
    MethodologyMaster,
    LriScore,
    NmpaSnapshot,
    PendingDocument,
    PendingRecord,
    PendingUdiLink,
    ProcurementLot,
    ProductUdiMap,
    ProductVariant,
    ProductRejected,
    RawDocument,
    RawSourceRecord,
    Registration,
    RegistrationConflictAudit,
    RegistrationEvent,
    RegistrationMethodology,
    SourceRun,
    SourceConfig,
    SourceDefinition,
    User,
)
from app.pipeline.doc_reader import read_file_bytes
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
from app.repositories.procurement import upsert_manual_registration_map
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
    ApiResponseProductLri,
    ApiResponseChangeStats,
    ApiResponseChangesList,
    ApiResponseChangeDetail,
    ApiResponseProductTimeline,
    ApiResponseRadar,
    ApiResponseRankings,
    ApiResponseBreakdown,
    ApiResponseDashboardLriTop,
    ApiResponseDashboardLriMap,
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
    DashboardLriTopData,
    DashboardLriTopItemOut,
    DashboardLriMapData,
    DashboardLriMapItemOut,
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
    ProductLriData,
    LriScoreOut,
    ApiResponseAdminLriList,
    AdminLriListData,
    AdminLriItemOut,
    ApiResponseRegistration,
    RegistrationOut,
    VariantOut,
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
from app.services.company_resolution import backfill_products_for_alias, normalize_company_name
from app.services.methodology_v1 import map_methodologies_v1
from app.services.normalize_keys import normalize_registration_no
from app.services.source_contract import apply_field_policy, registration_contract_summary, upsert_registration_with_contract
from app.services.ingest_runner import upsert_structured_record_via_runner
from app.common.errors import IngestErrorCode
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

SOURCE_REGISTRY_LEGACY_BINDINGS: dict[str, dict[str, str]] = {
    # role=primary means this source can become active datasource for sync primary path.
    'NMPA_REG': {'legacy_name': PRIMARY_SOURCE_NAME, 'legacy_type': POSTGRES_SOURCE_TYPE, 'role': 'primary'},
    # role=supplement means this source is consumed by supplement logic via configured name.
    'UDI_DI': {'legacy_name': DEFAULT_SUPPLEMENT_SOURCE_NAME, 'legacy_type': POSTGRES_SOURCE_TYPE, 'role': 'supplement'},
}

REGISTRATION_CONFLICT_FIELDS = {'filing_no', 'approval_date', 'expiry_date', 'status'}

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


@app.get('/api/registrations/{registration_no}')
def get_registration_detail(registration_no: str, db: Session = Depends(get_db)) -> ApiResponseRegistration:
    reg_no_norm = normalize_registration_no(str(registration_no))
    if not reg_no_norm:
        raise HTTPException(status_code=400, detail='invalid registration_no')

    reg = db.scalar(select(Registration).where(Registration.registration_no == reg_no_norm))
    if reg is None:
        raise HTTPException(status_code=404, detail='registration not found')

    is_stub, source_hint, verified_by_nmpa = _stub_meta_from_registration(reg)

    # Prefer the new anchor column product_variants.registration_id; keep backward compatibility by also
    # reading legacy product_variants.registry_no when registration_id is NULL.
    variants = (
        db.scalars(
            select(ProductVariant)
            .where(
                (ProductVariant.registration_id == reg.id)
                | ((ProductVariant.registration_id.is_(None)) & (ProductVariant.registry_no == reg.registration_no))
            )
            .order_by(ProductVariant.updated_at.desc(), ProductVariant.created_at.desc())
        )
        .all()
    )

    items = [
        VariantOut(
            di=str(v.di),
            registration_id=getattr(v, 'registration_id', None),
            model_spec=getattr(v, 'model_spec', None),
            manufacturer=getattr(v, 'manufacturer', None),
            packaging_json=getattr(v, 'packaging_json', None),
            evidence_raw_document_id=getattr(v, 'evidence_raw_document_id', None),
        )
        for v in variants
    ]

    return _ok(
        RegistrationOut(
            id=reg.id,
            registration_no=reg.registration_no,
            filing_no=getattr(reg, 'filing_no', None),
            approval_date=getattr(reg, 'approval_date', None),
            expiry_date=getattr(reg, 'expiry_date', None),
            status=getattr(reg, 'status', None),
            is_stub=is_stub,
            source_hint=source_hint,
            verified_by_nmpa=verified_by_nmpa,
            variants=items,
        )
    )


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


def _use_registration_anchor() -> bool:
    try:
        return bool(getattr(_settings(), 'use_registration_anchor', False))
    except Exception:
        return False


def serialize_company(company) -> CompanyOut:
    return CompanyOut(id=company.id, name=company.name, country=company.country)


def _product_attr(product, name: str, default=None):
    return getattr(product, name, default)


def _stub_meta_from_product(product) -> tuple[bool, str | None, bool | None]:
    """Return (is_stub, source_hint, verified_by_nmpa) from product raw_json stub flags.

    Contract:
    - UDI-created stubs carry product.raw_json['_stub'] with keys:
      evidence_level/source_hint/verified_by_nmpa.
    """
    try:
        raw = _product_attr(product, 'raw_json', None) or {}
        stub = raw.get('_stub') if isinstance(raw, dict) else None
        if not isinstance(stub, dict):
            return (False, None, True)
        source_hint = str(stub.get('source_hint') or '').strip() or None
        verified = stub.get('verified_by_nmpa')
        if isinstance(verified, bool):
            vb = verified
        elif verified is None:
            vb = False
        else:
            vb = str(verified).strip().lower() in {'1', 'true', 'yes', 'y'}
        # Any _stub implies "not verified" unless explicitly marked otherwise.
        return (True, source_hint, vb)
    except Exception:
        return (False, None, True)


def _stub_meta_from_registration(reg) -> tuple[bool, str | None, bool | None]:
    """Return (is_stub, source_hint, verified_by_nmpa) from registration raw_json stub flags."""
    try:
        raw = getattr(reg, 'raw_json', None) or {}
        stub = raw.get('_stub') if isinstance(raw, dict) else None
        if not isinstance(stub, dict):
            return (False, None, True)
        source_hint = str(stub.get('source_hint') or '').strip() or None
        verified = stub.get('verified_by_nmpa')
        if isinstance(verified, bool):
            vb = verified
        elif verified is None:
            vb = False
        else:
            vb = str(verified).strip().lower() in {'1', 'true', 'yes', 'y'}
        return (True, source_hint, vb)
    except Exception:
        return (False, None, True)


def serialize_product(product, overrides: dict | None = None) -> ProductOut:
    ov = overrides or {}
    is_stub, source_hint, verified_by_nmpa = _stub_meta_from_product(product)
    desc = None
    try:
        rj = _product_attr(product, "raw_json", None) or {}
        if isinstance(rj, dict):
            desc = rj.get("description") or (rj.get("udi_snapshot") or {}).get("description")
    except Exception:
        desc = None
    return ProductOut(
        id=_product_attr(product, 'id'),
        registration_id=ov.get('registration_id', _product_attr(product, 'registration_id')),
        udi_di=ov.get('udi_di', _product_attr(product, 'udi_di')),
        reg_no=ov.get('reg_no', _product_attr(product, 'reg_no')),
        name=ov.get('name', _product_attr(product, 'name')),
        status=ov.get('status', _product_attr(product, 'status')),
        approved_date=ov.get('approved_date', _product_attr(product, 'approved_date')),
        expiry_date=ov.get('expiry_date', _product_attr(product, 'expiry_date')),
        class_name=ov.get('class_name', _product_attr(product, 'class_name')),
        model=ov.get('model', _product_attr(product, 'model')),
        specification=ov.get('specification', _product_attr(product, 'specification')),
        category=ov.get('category', _product_attr(product, 'category')),
        description=ov.get('description', desc),
        ivd_category=ov.get('ivd_category', _product_attr(product, 'ivd_category', None)),
        anchor_summary=ov.get('anchor_summary', None),
        is_stub=ov.get('is_stub', is_stub),
        source_hint=ov.get('source_hint', source_hint),
        verified_by_nmpa=ov.get('verified_by_nmpa', verified_by_nmpa),
        company=serialize_company(_product_attr(product, 'company')) if _product_attr(product, 'company') else None,
    )


def serialize_product_limited(product, overrides: dict | None = None) -> ProductOut:
    # Keep schema stable but trim optional fields for Free users (summary view).
    ov = overrides or {}
    is_stub, source_hint, verified_by_nmpa = _stub_meta_from_product(product)
    return ProductOut(
        id=_product_attr(product, 'id'),
        registration_id=ov.get('registration_id', _product_attr(product, 'registration_id')),
        udi_di=ov.get('udi_di', _product_attr(product, 'udi_di')),
        reg_no=ov.get('reg_no', _product_attr(product, 'reg_no')),
        name=ov.get('name', _product_attr(product, 'name')),
        status=ov.get('status', _product_attr(product, 'status')),
        approved_date=None,
        expiry_date=ov.get('expiry_date', _product_attr(product, 'expiry_date')),
        class_name=None,
        model=None,
        specification=None,
        category=None,
        description=None,
        ivd_category=ov.get('ivd_category', _product_attr(product, 'ivd_category', None)),
        anchor_summary=ov.get('anchor_summary', None),
        is_stub=ov.get('is_stub', is_stub),
        source_hint=ov.get('source_hint', source_hint),
        verified_by_nmpa=ov.get('verified_by_nmpa', verified_by_nmpa),
        company=serialize_company(_product_attr(product, 'company')) if _product_attr(product, 'company') else None,
    )


def _resolve_registration_by_no(db: Session, reg_no: str | None) -> Registration | None:
    raw = str(reg_no or '').strip()
    if not raw:
        return None
    exact = db.scalar(select(Registration).where(Registration.registration_no == raw))
    if exact is not None:
        return exact

    norm = normalize_registration_no(raw)
    if not norm:
        return None
    stmt = text(
        """
        SELECT id
        FROM registrations
        WHERE regexp_replace(upper(coalesce(registration_no, '')), '[^0-9A-Z一-龥]+', '', 'g') = :n
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )
    rid = db.execute(stmt, {'n': norm}).scalar_one_or_none()
    if rid is None:
        return None
    try:
        return db.get(Registration, UUID(str(rid)))
    except Exception:
        return None


def _resolve_registration_anchor_context(db: Session, product) -> dict | None:
    reg: Registration | None = None
    source = 'none'
    pid = _product_attr(product, 'id')
    product_reg_id = _product_attr(product, 'registration_id')
    if product_reg_id:
        reg = db.get(Registration, product_reg_id)
        if reg is not None:
            source = 'products.registration_id'

    candidate_nos: list[str] = []
    p_reg_no = str(_product_attr(product, 'reg_no') or '').strip()
    if p_reg_no:
        candidate_nos.append(p_reg_no)
    if pid:
        var_nos = db.scalars(
            select(ProductVariant.registry_no)
            .where(ProductVariant.product_id == pid, ProductVariant.registry_no.is_not(None))
            .order_by(ProductVariant.updated_at.desc())
            .limit(20)
        ).all()
        for no in var_nos:
            v = str(no or '').strip()
            if v:
                candidate_nos.append(v)

    if reg is None and p_reg_no:
        norm = normalize_registration_no(p_reg_no)
        if norm:
            var_match_nos = db.scalars(
                text(
                    """
                    SELECT registry_no
                    FROM product_variants
                    WHERE registry_no IS NOT NULL
                      AND regexp_replace(upper(coalesce(registry_no, '')), '[^0-9A-Z一-龥]+', '', 'g') = :n
                    ORDER BY updated_at DESC
                    LIMIT 20
                    """
                ),
                {'n': norm},
            ).all()
            for no in var_match_nos:
                v = str(no or '').strip()
                if v:
                    candidate_nos.append(v)

    if reg is None:
        seen: set[str] = set()
        for no in candidate_nos:
            key = normalize_registration_no(no) or no
            if key in seen:
                continue
            seen.add(key)
            reg = _resolve_registration_by_no(db, no)
            if reg is not None:
                source = 'reg_no_or_variant'
                break

    if reg is None:
        return None

    snap_row = db.execute(
        select(func.max(NmpaSnapshot.snapshot_date), func.count(NmpaSnapshot.id)).where(NmpaSnapshot.registration_id == reg.id)
    ).first()
    latest_snap = (snap_row[0] if snap_row else None)
    snap_count = int((snap_row[1] if snap_row else 0) or 0)
    ev_row = db.execute(
        select(func.max(RegistrationEvent.event_date), func.count(RegistrationEvent.id)).where(
            RegistrationEvent.registration_id == reg.id
        )
    ).first()
    latest_event_date = (ev_row[0] if ev_row else None)
    event_count = int((ev_row[1] if ev_row else 0) or 0)
    latest_event_type = db.scalar(
        select(RegistrationEvent.event_type)
        .where(RegistrationEvent.registration_id == reg.id)
        .order_by(RegistrationEvent.event_date.desc(), RegistrationEvent.created_at.desc())
        .limit(1)
    )

    return {
        'registration_id': reg.id,
        'reg_no': reg.registration_no,
        'status': reg.status or _product_attr(product, 'status'),
        'approved_date': reg.approval_date or _product_attr(product, 'approved_date'),
        'expiry_date': reg.expiry_date or _product_attr(product, 'expiry_date'),
        'anchor_summary': {
            'enabled': True,
            'source': source,
            'snapshot_count': snap_count,
            'latest_snapshot_date': (latest_snap.isoformat() if latest_snap else None),
            'event_count': event_count,
            'latest_event_date': (latest_event_date.isoformat() if latest_event_date else None),
            'latest_event_type': (str(latest_event_type) if latest_event_type else None),
            'candidate_reg_nos': candidate_nos[:10],
        },
    }


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
                    'source_key': str(sched_raw.get('source_key') or 'UDI_DI').strip().upper() or 'UDI_DI',
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
                'sync_mode': 'nmpa_udi',
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


@app.get('/api/dashboard/lri/top', response_model=ApiResponseDashboardLriTop)
def dashboard_lri_top(
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0, le=1000000),
    model_version: str = Query(default='lri_v1'),
    current_user: User = Depends(_require_current_user),
    db: Session = Depends(get_db),
) -> ApiResponseDashboardLriTop:
    """High-risk certificate TopN (sellable).

    Pagination is mandatory to avoid full-table scans in UI.
    For free users, pro-only fields are redacted to null.
    """
    plan_is_pro = _is_pro_user(current_user, db)

    total = int(
        db.execute(
            text(
                """
                WITH latest AS (
                  SELECT DISTINCT ON (s.registration_id)
                    s.registration_id,
                    s.product_id,
                    s.lri_norm
                  FROM lri_scores s
                  WHERE s.model_version = :mv
                  ORDER BY s.registration_id, s.calculated_at DESC, s.id ASC
                )
                SELECT COUNT(1)
                FROM latest l
                JOIN products p ON p.id = l.product_id
                WHERE p.is_ivd IS TRUE
                """
            ),
            {'mv': str(model_version)},
        ).scalar()
        or 0
    )

    rows = db.execute(
        text(
            """
            WITH latest AS (
              SELECT DISTINCT ON (s.registration_id)
                s.registration_id,
                s.product_id,
                s.tte_days,
                s.competitive_count,
                s.gp_new_12m,
                s.tte_score,
                s.rh_score,
                s.cd_score,
                s.gp_score,
                s.lri_norm,
                s.risk_level,
                s.calculated_at
              FROM lri_scores s
              WHERE s.model_version = :mv
              ORDER BY s.registration_id, s.calculated_at DESC, s.id ASC
            )
            SELECT
              p.id AS product_id,
              p.name AS product_name,
              l.risk_level,
              l.lri_norm,
              l.tte_days,
              l.competitive_count,
              l.gp_new_12m,
              l.tte_score,
              l.rh_score,
              l.cd_score,
              l.gp_score,
              l.calculated_at
            FROM latest l
            JOIN products p ON p.id = l.product_id
            WHERE p.is_ivd IS TRUE
            ORDER BY l.lri_norm DESC NULLS LAST, l.calculated_at DESC, p.id ASC
            LIMIT :limit OFFSET :offset
            """
        ),
        {'mv': str(model_version), 'limit': int(limit), 'offset': int(offset)},
    ).mappings().all()

    items = [
        DashboardLriTopItemOut(
            product_id=r['product_id'],
            product_name=str(r.get('product_name') or ''),
            risk_level=str(r.get('risk_level') or ''),
            lri_norm=float(r.get('lri_norm') or 0),
            tte_days=(int(r.get('tte_days')) if r.get('tte_days') is not None else None),
            competitive_count=(int(r.get('competitive_count') or 0) if plan_is_pro else None),
            gp_new_12m=(int(r.get('gp_new_12m') or 0) if plan_is_pro else None),
            tte_score=(int(r.get('tte_score') or 0) if plan_is_pro else None),
            rh_score=(int(r.get('rh_score') or 0) if plan_is_pro else None),
            cd_score=(int(r.get('cd_score') or 0) if plan_is_pro else None),
            gp_score=(int(r.get('gp_score') or 0) if plan_is_pro else None),
            calculated_at=(r.get('calculated_at') if plan_is_pro else None),
        )
        for r in rows
    ]

    return _ok(DashboardLriTopData(total=total, limit=int(limit), offset=int(offset), items=items))


@app.get('/api/dashboard/lri/map', response_model=ApiResponseDashboardLriMap)
def dashboard_lri_map(
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=1000000),
    model_version: str = Query(default='lri_v1'),
    current_user: User = Depends(_require_current_user),
    db: Session = Depends(get_db),
) -> ApiResponseDashboardLriMap:
    """Track risk map (methodology + ivd_category).

    For free users, gp_new_12m is redacted (sellable detail).
    """
    plan_is_pro = _is_pro_user(current_user, db)

    total = int(
        db.execute(
            text(
                """
                WITH latest AS (
                  SELECT DISTINCT ON (s.registration_id)
                    s.registration_id,
                    s.product_id,
                    s.methodology_id,
                    s.lri_norm,
                    s.risk_level,
                    s.gp_new_12m
                  FROM lri_scores s
                  WHERE s.model_version = :mv
                  ORDER BY s.registration_id, s.calculated_at DESC, s.id ASC
                )
                SELECT COUNT(1)
                FROM (
                  SELECT
                    l.methodology_id,
                    COALESCE(NULLIF(btrim(p.ivd_category), ''), NULLIF(btrim(p.category), ''), 'unknown') AS ivd_category
                  FROM latest l
                  JOIN products p ON p.id = l.product_id
                  WHERE p.is_ivd IS TRUE
                  GROUP BY 1, 2
                ) x
                """
            ),
            {'mv': str(model_version)},
        ).scalar()
        or 0
    )

    rows = db.execute(
        text(
            """
            WITH latest AS (
              SELECT DISTINCT ON (s.registration_id)
                s.registration_id,
                s.product_id,
                s.methodology_id,
                s.lri_norm,
                s.risk_level,
                s.gp_new_12m
              FROM lri_scores s
              WHERE s.model_version = :mv
              ORDER BY s.registration_id, s.calculated_at DESC, s.id ASC
            ),
            dim AS (
              SELECT
                l.methodology_id,
                COALESCE(NULLIF(btrim(p.ivd_category), ''), NULLIF(btrim(p.category), ''), 'unknown') AS ivd_category,
                l.lri_norm,
                l.risk_level,
                l.gp_new_12m
              FROM latest l
              JOIN products p ON p.id = l.product_id
              WHERE p.is_ivd IS TRUE
            )
            SELECT
              d.methodology_id,
              m.code AS methodology_code,
              m.name_cn AS methodology_name_cn,
              d.ivd_category,
              COUNT(1)::int AS total_count,
              COUNT(1) FILTER (WHERE d.risk_level IN ('HIGH', 'CRITICAL'))::int AS high_risk_count,
              COALESCE(AVG(d.lri_norm), 0)::float AS avg_lri_norm,
              COALESCE(MAX(d.gp_new_12m), 0)::int AS gp_new_12m
            FROM dim d
            LEFT JOIN methodology_master m ON m.id = d.methodology_id
            GROUP BY 1, 2, 3, 4
            ORDER BY high_risk_count DESC, avg_lri_norm DESC, total_count DESC, ivd_category ASC
            LIMIT :limit OFFSET :offset
            """
        ),
        {'mv': str(model_version), 'limit': int(limit), 'offset': int(offset)},
    ).mappings().all()

    items = [
        DashboardLriMapItemOut(
            methodology_id=r.get('methodology_id'),
            methodology_code=r.get('methodology_code'),
            methodology_name_cn=r.get('methodology_name_cn'),
            ivd_category=str(r.get('ivd_category') or 'unknown'),
            total_count=int(r.get('total_count') or 0),
            high_risk_count=int(r.get('high_risk_count') or 0),
            avg_lri_norm=float(r.get('avg_lri_norm') or 0),
            gp_new_12m=(int(r.get('gp_new_12m') or 0) if plan_is_pro else None),
        )
        for r in rows
    ]

    return _ok(DashboardLriMapData(total=total, limit=int(limit), offset=int(offset), items=items))


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
    include_unverified: bool = Query(default=False, description='Include UDI stubs (unverified by NMPA)'),
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
        include_unverified=bool(include_unverified),
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


@app.get('/api/admin/home-summary')
def admin_home_summary(
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    """Fast-path summary for /admin home.

    Keep this endpoint cheap: avoid heavy GROUP BY / JSON extraction queries so
    the Admin Workbench can render quickly even on cold caches.
    """
    pending_docs = int(
        db.execute(text("SELECT COUNT(1) FROM pending_documents WHERE status = 'pending'")).scalar() or 0
    )
    conflicts_open = int(
        db.execute(text("SELECT COUNT(1) FROM conflicts_queue WHERE status = 'open'")).scalar() or 0
    )
    udi_pending = int(
        db.execute(text("SELECT COUNT(1) FROM pending_udi_links WHERE status = 'PENDING'")).scalar() or 0
    )

    row = db.execute(
        text(
            """
            SELECT
              metric_date,
              pending_count,
              lri_computed_count,
              lri_missing_methodology_count,
              risk_level_distribution,
              updated_at
            FROM daily_metrics
            ORDER BY metric_date DESC
            LIMIT 1
            """
        )
    ).mappings().first()
    if not row:
        lri_quality = {
            'metric_date': None,
            'pending_count': 0,
            'lri_computed_count': 0,
            'lri_missing_methodology_count': 0,
            'risk_level_distribution': {'LOW': 0, 'MID': 0, 'HIGH': 0, 'CRITICAL': 0},
            'updated_at': None,
        }
    else:
        dist = row.get('risk_level_distribution') or {}
        out_dist = {k: int(dist.get(k, 0) or 0) for k in ('LOW', 'MID', 'HIGH', 'CRITICAL')}
        lri_quality = {
            'metric_date': row.get('metric_date'),
            'pending_count': int(row.get('pending_count') or 0),
            'lri_computed_count': int(row.get('lri_computed_count') or 0),
            'lri_missing_methodology_count': int(row.get('lri_missing_methodology_count') or 0),
            'risk_level_distribution': out_dist,
            'updated_at': row.get('updated_at'),
        }

    return _ok(
        {
            'pending_documents_pending_total': pending_docs,
            'conflicts_open_total': conflicts_open,
            'udi_pending_total': udi_pending,
            'lri_quality': lri_quality,
        }
    )


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
    include_unverified: bool = Query(default=False, description='Include UDI stubs (unverified by NMPA)'),
    _user: User = Depends(require_pro),
    db: Session = Depends(get_db),
) -> ApiResponseSearch:
    items, total = list_full_products(
        db,
        query=q,
        company=company,
        reg_no=reg_no,
        status=status,
        include_unverified=bool(include_unverified),
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
    overrides: dict | None = None
    if _use_registration_anchor():
        overrides = _resolve_registration_anchor_context(db, product)
    if effective_mode == 'limited' and not plan_is_pro:
        return _ok(serialize_product_limited(product, overrides=overrides))
    return _ok(serialize_product(product, overrides=overrides))


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


@app.get('/api/products/{product_id}/lri', response_model=ApiResponseProductLri)
def product_lri_score(
    product_id: str,
    model_version: str = Query(default='lri_v1'),
    current_user: User = Depends(_require_current_user),
    db: Session = Depends(get_db),
) -> ApiResponseProductLri:
    plan_is_pro = _is_pro_user(current_user, db)
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')

    reg_id = getattr(product, 'registration_id', None)
    if not reg_id:
        return _ok(ProductLriData(product_id=UUID(str(product.id)), registration_id=None, score=None))

    row = db.execute(
        text(
            """
            SELECT
              s.registration_id,
              s.product_id,
              s.methodology_id,
              m.code AS methodology_code,
              m.name_cn AS methodology_name_cn,
              s.tte_days,
              s.renewal_count,
              s.competitive_count,
              s.gp_new_12m,
              s.tte_score,
              s.rh_score,
              s.cd_score,
              s.gp_score,
              s.lri_total,
              s.lri_norm,
              s.risk_level,
              s.model_version,
              s.calculated_at
            FROM lri_scores s
            LEFT JOIN methodology_master m ON m.id = s.methodology_id
            WHERE s.registration_id = :rid AND s.model_version = :mv
            ORDER BY s.calculated_at DESC, s.id ASC
            LIMIT 1
            """
        ),
        {'rid': reg_id, 'mv': str(model_version)},
    ).mappings().first()

    score = None
    if row:
        score = LriScoreOut(
            registration_id=row['registration_id'],
            product_id=row.get('product_id'),
            methodology_id=row.get('methodology_id'),
            methodology_code=row.get('methodology_code'),
            methodology_name_cn=row.get('methodology_name_cn'),
            tte_days=row.get('tte_days'),
            renewal_count=(int(row.get('renewal_count') or 0) if plan_is_pro else None),
            competitive_count=(int(row.get('competitive_count') or 0) if plan_is_pro else None),
            gp_new_12m=(int(row.get('gp_new_12m') or 0) if plan_is_pro else None),
            tte_score=(int(row.get('tte_score') or 0) if plan_is_pro else None),
            rh_score=(int(row.get('rh_score') or 0) if plan_is_pro else None),
            cd_score=(int(row.get('cd_score') or 0) if plan_is_pro else None),
            gp_score=(int(row.get('gp_score') or 0) if plan_is_pro else None),
            lri_total=(int(row.get('lri_total') or 0) if plan_is_pro else None),
            lri_norm=float(row.get('lri_norm') or 0),
            risk_level=str(row.get('risk_level') or ''),
            model_version=str(row.get('model_version') or ''),
            calculated_at=row.get('calculated_at'),
        )

    return _ok(
        ProductLriData(
            product_id=UUID(str(product.id)),
            registration_id=reg_id,
            score=score,
        )
    )


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


@app.get('/api/admin/source-supplement/runs')
def admin_list_source_supplement_runs(
    limit: int = Query(default=20, ge=1, le=200),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.scalars(
        select(SourceRun)
        .where(SourceRun.source == 'nmpa_supplement')
        .order_by(desc(SourceRun.started_at))
        .limit(int(limit))
    ).all()
    items: list[dict] = []
    for r in rows:
        notes = getattr(r, 'source_notes', None) or {}
        if not isinstance(notes, dict):
            notes = {}
        items.append(
            {
                'run_id': int(r.id),
                'source': str(r.source),
                'status': str(r.status),
                'message': (str(r.message) if getattr(r, 'message', None) is not None else None),
                'records_total': int(getattr(r, 'records_total', 0) or 0),
                'records_success': int(getattr(r, 'records_success', 0) or 0),
                'records_failed': int(getattr(r, 'records_failed', 0) or 0),
                'matched_by_udi_di': int(notes.get('matched_by_udi_di', 0) or 0),
                'matched_by_reg_no': int(notes.get('matched_by_reg_no', 0) or 0),
                'updated_by_udi_di': int(notes.get('updated_by_udi_di', 0) or 0),
                'updated_by_reg_no': int(notes.get('updated_by_reg_no', 0) or 0),
                'missing_identifier': int(notes.get('missing_identifier', 0) or 0),
                'missing_local': int(notes.get('missing_local', 0) or 0),
                'source_query_used': bool(notes.get('source_query_used', False)),
                'source_table': notes.get('source_table'),
                'source_name': notes.get('source_name'),
                'source_id': notes.get('source_id'),
                'started_at': getattr(r, 'started_at', None),
                'finished_at': getattr(r, 'finished_at', None),
            }
        )
    return _ok({'items': items, 'count': len(items)})


@app.get('/api/admin/source-contract/conflicts')
def admin_source_contract_conflicts(
    date: dt_date | None = Query(default=None),
    since: dt_date | None = Query(default=None),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    if date is not None and since is not None:
        raise HTTPException(status_code=400, detail='date and since are mutually exclusive')
    today = dt_date.today()
    if since is not None:
        start = datetime.combine(since, datetime.min.time())
        end = datetime.combine(today, datetime.min.time()) + timedelta(days=1)
    else:
        target = date or today
        start = datetime.combine(target, datetime.min.time())
        end = start + timedelta(days=1)
    report = registration_contract_summary(db, start=start, end=end)
    if since is not None:
        report['since'] = since.isoformat()
        report['date'] = None
    else:
        report['date'] = (date or today).isoformat()
        report['since'] = None
    return _ok({"report": report})


@app.get('/api/admin/conflicts-queue')
def admin_list_conflicts_queue(
    status: str = Query(default='open'),
    limit: int = Query(default=100, ge=1, le=500),
    group_by: str | None = Query(default=None),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    status_norm = str(status or 'open').strip().lower()
    group_by_norm = str(group_by or '').strip().lower()
    if group_by_norm and group_by_norm not in {'registration_no'}:
        raise HTTPException(status_code=400, detail='group_by must be registration_no')
    q = select(ConflictQueue).order_by(desc(ConflictQueue.created_at)).limit(int(limit))
    if status_norm != 'all':
        if status_norm not in {'open', 'resolved'}:
            raise HTTPException(status_code=400, detail='status must be open/resolved/all')
        q = q.where(ConflictQueue.status == status_norm)
    rows = db.scalars(q).all()
    if group_by_norm == 'registration_no':
        grouped: dict[str, dict] = {}
        for r in rows:
            key = str(r.registration_no or '').strip()
            if not key:
                continue
            bucket = grouped.get(key)
            if bucket is None:
                bucket = {
                    'registration_no': key,
                    'conflict_count': 0,
                    'fields_set': set(),
                    'top_sources_set': set(),
                    'latest_created_at': r.created_at,
                }
                grouped[key] = bucket
            bucket['conflict_count'] += 1
            if r.field_name:
                bucket['fields_set'].add(str(r.field_name))
            if r.created_at and (bucket['latest_created_at'] is None or r.created_at > bucket['latest_created_at']):
                bucket['latest_created_at'] = r.created_at
            candidates = r.candidates if isinstance(r.candidates, list) else []
            for c in candidates:
                if isinstance(c, dict):
                    src = str(c.get('source_key') or '').strip()
                    if src:
                        bucket['top_sources_set'].add(src)
        items = []
        for _, g in sorted(grouped.items(), key=lambda kv: kv[1]['latest_created_at'] or datetime.min, reverse=True):
            items.append(
                {
                    'registration_no': g['registration_no'],
                    'conflict_count': int(g['conflict_count']),
                    'fields': sorted(list(g['fields_set'])),
                    'latest_created_at': g['latest_created_at'],
                    'top_sources': sorted(list(g['top_sources_set'])),
                }
            )
        return _ok(
            {
                'items': items[: int(limit)],
                'count': min(len(items), int(limit)),
                'status': status_norm,
                'group_by': 'registration_no',
            }
        )

    return _ok(
        {
            'items': [
                {
                    'id': str(r.id),
                    'registration_no': r.registration_no,
                    'registration_id': (str(r.registration_id) if r.registration_id else None),
                    'field_name': r.field_name,
                    'candidates': (r.candidates if isinstance(r.candidates, list) else []),
                    'status': r.status,
                    'winner_value': r.winner_value,
                    'winner_source_key': r.winner_source_key,
                    'source_run_id': r.source_run_id,
                    'resolved_by': r.resolved_by,
                    'resolved_at': r.resolved_at,
                    'created_at': r.created_at,
                    'updated_at': r.updated_at,
                }
                for r in rows
            ],
            'count': len(rows),
            'status': status_norm,
        }
    )


@app.get('/api/admin/conflicts')
def admin_list_conflicts(
    status: str = Query(default='open'),
    limit: int = Query(default=100, ge=1, le=500),
    group_by: str | None = Query(default=None),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    # Backward-compatible alias of /api/admin/conflicts-queue.
    return admin_list_conflicts_queue(status=status, limit=limit, group_by=group_by, _admin=_admin, db=db)


@app.get('/api/admin/conflicts/report')
def admin_conflicts_report(
    window: str = Query(default='7d'),
    top_n: int = Query(default=10, ge=1, le=100),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    window_norm = str(window or '7d').strip().lower()
    window_days_map = {'1d': 1, '7d': 7, '30d': 30}
    if window_norm not in window_days_map:
        raise HTTPException(status_code=400, detail='window must be one of: 1d/7d/30d')
    days = int(window_days_map[window_norm])

    top_fields_rows = db.execute(
        text(
            """
            SELECT field_name, COUNT(*) AS conflict_count
            FROM conflicts_queue
            WHERE created_at >= NOW() - (:days || ' days')::interval
            GROUP BY field_name
            ORDER BY conflict_count DESC, field_name ASC
            LIMIT :top_n
            """
        ),
        {'days': days, 'top_n': int(top_n)},
    ).mappings().all()

    top_sources_rows = db.execute(
        text(
            """
            WITH filtered AS (
                SELECT candidates
                FROM conflicts_queue
                WHERE created_at >= NOW() - (:days || ' days')::interval
            )
            SELECT
                COALESCE(NULLIF(elem->>'source_key', ''), 'UNKNOWN') AS source_key,
                COUNT(*) AS conflict_count
            FROM filtered
            CROSS JOIN LATERAL jsonb_array_elements(COALESCE(filtered.candidates, '[]'::jsonb)) AS elem
            GROUP BY source_key
            ORDER BY conflict_count DESC, source_key ASC
            LIMIT :top_n
            """
        ),
        {'days': days, 'top_n': int(top_n)},
    ).mappings().all()

    trend_rows = db.execute(
        text(
            """
            SELECT DATE(created_at) AS metric_date, COUNT(*) AS conflict_count
            FROM conflicts_queue
            WHERE created_at >= NOW() - (:days || ' days')::interval
            GROUP BY DATE(created_at)
            ORDER BY metric_date ASC
            """
        ),
        {'days': days},
    ).mappings().all()

    return _ok(
        {
            'window': window_norm,
            'top_n': int(top_n),
            'top_fields': [
                {'field_name': str(r.get('field_name') or ''), 'conflict_count': int(r.get('conflict_count') or 0)}
                for r in top_fields_rows
            ],
            'top_sources': [
                {'source_key': str(r.get('source_key') or ''), 'conflict_count': int(r.get('conflict_count') or 0)}
                for r in top_sources_rows
            ],
            'trend': [
                {
                    'date': (r.get('metric_date').isoformat() if r.get('metric_date') is not None else None),
                    'conflict_count': int(r.get('conflict_count') or 0),
                }
                for r in trend_rows
            ],
        }
    )


@app.post('/api/admin/conflicts-queue/{conflict_id}/resolve')
def admin_resolve_conflict_queue(
    conflict_id: UUID,
    payload: dict,
    admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(ConflictQueue, conflict_id)
    if row is None:
        raise HTTPException(status_code=404, detail='conflict not found')
    if str(row.status or '').lower() == 'resolved':
        raise HTTPException(status_code=409, detail='conflict already resolved')

    field_name = str(row.field_name or '').strip()
    if field_name not in REGISTRATION_CONFLICT_FIELDS:
        raise HTTPException(status_code=400, detail=f'unsupported field_name: {field_name}')

    winner_value = str(payload.get('winner_value') or '').strip()
    if not winner_value:
        raise HTTPException(status_code=400, detail='winner_value is required')
    resolve_reason = str(payload.get('reason') or '').strip()
    if not resolve_reason:
        raise HTTPException(
            status_code=400,
            detail={
                'code': IngestErrorCode.E_REASON_REQUIRED.value,
                'message': 'reason is required',
            },
        )
    winner_source_key = str(payload.get('winner_source_key') or 'MANUAL').strip().upper() or 'MANUAL'

    reg_no = normalize_registration_no(str(row.registration_no or ''))
    reg = db.scalar(select(Registration).where(Registration.registration_no == reg_no))
    if reg is None:
        raise HTTPException(status_code=404, detail='registration not found')

    before = {
        'registration_no': reg.registration_no,
        'filing_no': (str(reg.filing_no) if reg.filing_no is not None else None),
        'approval_date': (reg.approval_date.isoformat() if reg.approval_date is not None else None),
        'expiry_date': (reg.expiry_date.isoformat() if reg.expiry_date is not None else None),
        'status': (str(reg.status) if reg.status is not None else None),
    }

    raw_json = reg.raw_json if isinstance(reg.raw_json, dict) else {}
    prov = raw_json.get('_contract_provenance') if isinstance(raw_json.get('_contract_provenance'), dict) else {}
    existing_meta = (prov.get(field_name) if isinstance(prov.get(field_name), dict) else None)
    old_val = before.get(field_name)
    now0 = datetime.now()
    decision = apply_field_policy(
        db,
        field_name=field_name,
        old_value=old_val,
        new_value=winner_value,
        source_key='admin',
        observed_at=now0,
        existing_meta=existing_meta,
        source_run_id=row.source_run_id,
        raw_source_record_id=None,
        policy_evidence_grade='A',
        policy_source_priority=-1,
    )
    if decision.action in {'keep', 'conflict'}:
        db.add(
            RegistrationConflictAudit(
                registration_id=reg.id,
                registration_no=reg.registration_no,
                field_name=field_name,
                old_value=old_val,
                incoming_value=winner_value,
                final_value=old_val,
                resolution='REJECTED',
                reason=f"manual_resolve:{resolve_reason};policy={decision.reason}",
                existing_meta=(existing_meta if isinstance(existing_meta, dict) else None),
                incoming_meta=(decision.incoming_meta if isinstance(decision.incoming_meta, dict) else None),
                source_run_id=row.source_run_id,
                observed_at=now0,
            )
        )
        raise HTTPException(
            status_code=409,
            detail={
                'code': IngestErrorCode.E_CONFLICT_UNRESOLVED.value,
                'message': f'field policy rejected manual resolve: {decision.reason}',
            },
        )

    winner_store = old_val if decision.action == 'noop' else str(decision.value_to_store or winner_value)
    if field_name in {'approval_date', 'expiry_date'}:
        if decision.action == 'apply':
            try:
                parsed = dt_date.fromisoformat(winner_store[:10])
            except Exception:
                raise HTTPException(status_code=400, detail='winner_value must be ISO date for approval_date/expiry_date')
            setattr(reg, field_name, parsed)
            winner_store = parsed.isoformat()
    elif decision.action == 'apply':
        setattr(reg, field_name, winner_store)

    prov[field_name] = {
        'source': winner_source_key,
        'source_key': 'admin',
        'source_run_id': row.source_run_id,
        'evidence_grade': 'A',
        'source_priority': -1,
        'observed_at': now0.isoformat(),
        'raw_source_record_id': None,
        'reason': resolve_reason,
        'conflict_id': str(row.id),
    }
    raw_json['_contract_provenance'] = prov
    reg.raw_json = raw_json
    db.add(reg)
    db.add(
        RegistrationConflictAudit(
            registration_id=reg.id,
            registration_no=reg.registration_no,
            field_name=field_name,
            old_value=old_val,
            incoming_value=winner_value,
            final_value=winner_store,
            resolution='APPLIED',
            reason=f"manual_resolve:{resolve_reason};policy={decision.reason}",
            existing_meta=(existing_meta if isinstance(existing_meta, dict) else None),
            incoming_meta=(decision.incoming_meta if isinstance(decision.incoming_meta, dict) else None),
            source_run_id=row.source_run_id,
            observed_at=now0,
        )
    )

    after = {
        'registration_no': reg.registration_no,
        'filing_no': (str(reg.filing_no) if reg.filing_no is not None else None),
        'approval_date': (reg.approval_date.isoformat() if reg.approval_date is not None else None),
        'expiry_date': (reg.expiry_date.isoformat() if reg.expiry_date is not None else None),
        'status': (str(reg.status) if reg.status is not None else None),
    }
    db.add(
        ChangeLog(
            product_id=None,
            entity_type='registration',
            entity_id=reg.id,
            change_type='update',
            changed_fields={field_name: {'old': old_val, 'new': winner_store}},
            before_json=before,
            after_json=after,
            before_raw=before,
            after_raw={
                '_contract_meta': {
                    'source': winner_source_key,
                    'source_key': 'admin',
                    'source_run_id': row.source_run_id,
                    'evidence_grade': 'A',
                    'source_priority': -1,
                    'observed_at': now0.isoformat(),
                    'raw_source_record_id': None,
                    'resolution': 'manual_conflict_queue',
                    'conflict_queue_id': str(row.id),
                    'reason': resolve_reason,
                }
            },
            source_run_id=row.source_run_id,
        )
    )

    row.status = 'resolved'
    row.winner_value = winner_store
    row.winner_source_key = winner_source_key
    row.resolved_by = (str(getattr(admin, 'email', '') or '') or 'admin')
    row.resolved_at = datetime.now()
    db.add(row)
    db.commit()

    return _ok(
        {
            'id': str(row.id),
            'registration_no': reg.registration_no,
            'field_name': field_name,
            'winner_value': winner_store,
            'winner_source_key': winner_source_key,
            'status': row.status,
            'reason': resolve_reason,
            'resolved_by': row.resolved_by,
            'resolved_at': row.resolved_at,
        }
    )


@app.post('/api/admin/conflicts/{conflict_id}/resolve')
def admin_resolve_conflict(
    conflict_id: UUID,
    payload: dict,
    admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    # Backward-compatible alias of /api/admin/conflicts-queue/{id}/resolve.
    return admin_resolve_conflict_queue(conflict_id=conflict_id, payload=payload, admin=admin, db=db)


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


@app.get('/api/admin/company-aliases')
def admin_list_company_aliases(
    query: str | None = Query(default=None),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    q = select(CompanyAlias).order_by(CompanyAlias.updated_at.desc())
    qtext = (query or '').strip()
    if qtext:
        q = q.where(CompanyAlias.alias_name.ilike(f'%{qtext}%'))
    rows = db.scalars(q.limit(200)).all()
    items = []
    # Best-effort: include company name for convenience.
    for a in rows:
        c = db.get(Company, getattr(a, 'company_id', None))
        items.append(
            {
                'id': str(a.id),
                'alias_name': a.alias_name,
                'company_id': str(a.company_id),
                'company_name': (c.name if c else None),
                'confidence': float(getattr(a, 'confidence', 0.0) or 0.0),
                'source': str(getattr(a, 'source', '') or ''),
                'created_at': getattr(a, 'created_at', None),
                'updated_at': getattr(a, 'updated_at', None),
            }
        )
    return _ok({'items': items, 'count': len(items)})


@app.post('/api/admin/company-aliases')
def admin_upsert_company_alias(
    background_tasks: BackgroundTasks,
    payload: dict,
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    alias_raw = str(payload.get('alias_name') or '').strip()
    if not alias_raw:
        raise HTTPException(status_code=400, detail='alias_name is required')

    alias_name = normalize_company_name(alias_raw)
    if not alias_name:
        raise HTTPException(status_code=400, detail='alias_name is invalid after normalization')

    company_id_raw = str(payload.get('company_id') or '').strip()
    if not company_id_raw:
        raise HTTPException(status_code=400, detail='company_id is required')
    try:
        company_id = UUID(company_id_raw)
    except Exception:
        raise HTTPException(status_code=400, detail='company_id must be a UUID')

    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail='company not found')

    source = str(payload.get('source') or 'manual').strip().lower() or 'manual'
    if source not in {'rule', 'manual', 'import'}:
        raise HTTPException(status_code=400, detail='source must be one of: rule/manual/import')

    try:
        confidence = float(payload.get('confidence', 0.8))
    except Exception:
        confidence = 0.8
    confidence = max(0.0, min(1.0, confidence))

    stmt = insert(CompanyAlias).values(
        alias_name=alias_name,
        company_id=company_id,
        confidence=confidence,
        source=source,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[CompanyAlias.alias_name],
        set_={
            'company_id': stmt.excluded.company_id,
            'confidence': stmt.excluded.confidence,
            'source': stmt.excluded.source,
            'updated_at': func.now(),
        },
    ).returning(CompanyAlias)

    alias_row = db.execute(stmt).scalar_one()
    db.commit()

    # Best-effort: rebind affected products in the background.
    background_tasks.add_task(backfill_products_for_alias, alias_name=alias_name, company_id=company_id)

    return _ok(
        {
            'id': str(alias_row.id),
            'alias_name': alias_row.alias_name,
            'company_id': str(alias_row.company_id),
            'company_name': company.name,
            'confidence': float(getattr(alias_row, 'confidence', 0.0) or 0.0),
            'source': str(getattr(alias_row, 'source', '') or ''),
        }
    )


@app.get('/api/admin/pending')
def admin_list_pending_records(
    status: str = Query(default='open'),
    source_key: str | None = Query(default=None),
    reason_code: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    order_by: str = Query(default='created_at desc'),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    status_norm = str(status or 'open').strip().lower()
    source_key_norm = str(source_key or '').strip()
    reason_code_norm = str(reason_code or '').strip()
    order_by_norm = ' '.join(str(order_by or '').strip().lower().split())
    if not order_by_norm:
        order_by_norm = 'created_at desc'
    if order_by_norm not in {'created_at desc', 'created_at asc'}:
        raise HTTPException(status_code=400, detail='order_by must be one of: created_at desc / created_at asc')

    filters = []
    if status_norm != 'all':
        if status_norm not in {'open', 'resolved', 'ignored', 'pending'}:
            raise HTTPException(status_code=400, detail='status must be open/resolved/ignored/pending/all')
        filters.append(PendingRecord.status == status_norm)
    if source_key_norm:
        filters.append(PendingRecord.source_key == source_key_norm)
    if reason_code_norm:
        filters.append(PendingRecord.reason_code == reason_code_norm)

    q = select(PendingRecord)
    q_total = select(func.count(PendingRecord.id))
    if filters:
        q = q.where(*filters)
        q_total = q_total.where(*filters)

    q = q.order_by(
        desc(PendingRecord.created_at) if order_by_norm == 'created_at desc' else PendingRecord.created_at.asc()
    ).offset(int(offset)).limit(int(limit))

    rows = db.scalars(q).all()
    total = int(db.scalar(q_total) or 0)
    return _ok(
        {
            'items': [
                {
                    'id': str(r.id),
                    'source_key': r.source_key,
                    'source_run_id': int(r.source_run_id),
                    'raw_document_id': str(r.raw_document_id),
                    'reason_code': r.reason_code,
                    'candidate_registry_no': r.candidate_registry_no,
                    'candidate_company': r.candidate_company,
                    'candidate_product_name': r.candidate_product_name,
                    'status': r.status,
                    'created_at': r.created_at,
                    'updated_at': r.updated_at,
                }
                for r in rows
            ],
            'total': total,
            'limit': int(limit),
            'offset': int(offset),
            'order_by': order_by_norm,
            'count': len(rows),
            'status': status_norm,
        }
    )


@app.get('/api/admin/pending/stats')
def admin_pending_stats(
    resolved_24h_hours: int = Query(default=24, ge=1, le=24 * 30),
    resolved_7d_days: int = Query(default=7, ge=1, le=365),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    # by_source_key: open/resolved/ignored counters (grouped by source_key)
    source_rows = db.execute(
        text(
            """
            SELECT
              source_key,
              COUNT(*) FILTER (WHERE status = 'open') AS open_count,
              COUNT(*) FILTER (WHERE status = 'resolved') AS resolved_count,
              COUNT(*) FILTER (WHERE status = 'ignored') AS ignored_count
            FROM pending_records
            WHERE status IN ('open', 'resolved', 'ignored')
            GROUP BY source_key
            ORDER BY source_key ASC
            """
        )
    ).mappings().all()

    # by_reason_code: open counters to locate parser/anchor defects
    reason_rows = db.execute(
        text(
            """
            SELECT
              reason_code,
              COUNT(*) AS open_count
            FROM pending_records
            WHERE status = 'open'
            GROUP BY reason_code
            ORDER BY open_count DESC, reason_code ASC
            """
        )
    ).mappings().all()

    backlog_row = db.execute(
        text(
            """
            SELECT
              COUNT(*) FILTER (WHERE status = 'open') AS open_total,
              COUNT(*) FILTER (
                WHERE status = 'resolved'
                  AND created_at >= NOW() - (:h || ' hours')::interval
              ) AS resolved_last_24h,
              COUNT(*) FILTER (
                WHERE status = 'resolved'
                  AND created_at >= NOW() - (:d || ' days')::interval
              ) AS resolved_last_7d
            FROM pending_records
            """
        ),
        {"h": int(resolved_24h_hours), "d": int(resolved_7d_days)},
    ).mappings().one()

    return _ok(
        {
            "by_source_key": [
                {
                    "source_key": str(r.get("source_key") or ""),
                    "open": int(r.get("open_count") or 0),
                    "resolved": int(r.get("resolved_count") or 0),
                    "ignored": int(r.get("ignored_count") or 0),
                }
                for r in source_rows
            ],
            "by_reason_code": [
                {
                    "reason_code": str(r.get("reason_code") or ""),
                    "open": int(r.get("open_count") or 0),
                }
                for r in reason_rows
            ],
            "backlog": {
                "open_total": int(backlog_row.get("open_total") or 0),
                "resolved_last_24h": int(backlog_row.get("resolved_last_24h") or 0),
                "resolved_last_7d": int(backlog_row.get("resolved_last_7d") or 0),
                "windows": {
                    "resolved_24h_hours": int(resolved_24h_hours),
                    "resolved_7d_days": int(resolved_7d_days),
                },
            },
        }
    )


@app.post('/api/admin/pending/{pending_id}/resolve')
def admin_resolve_pending_record(
    pending_id: UUID,
    payload: dict,
    admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    rec = db.get(PendingRecord, pending_id)
    if rec is None:
        raise HTTPException(status_code=404, detail='pending record not found')
    if str(rec.status or '').lower() == 'resolved':
        raise HTTPException(status_code=409, detail='pending record already resolved')

    reg_no_raw = str(payload.get('registration_no') or '').strip()
    if not reg_no_raw:
        raise HTTPException(
            status_code=400,
            detail={
                'code': IngestErrorCode.E_CANONICAL_KEY_MISSING.value,
                'legacy_code': IngestErrorCode.E_NO_REG_NO.value,
                'message': 'registration_no is required',
            },
        )
    reg_no = normalize_registration_no(reg_no_raw)
    if not reg_no:
        raise HTTPException(
            status_code=400,
            detail={
                'code': IngestErrorCode.E_PARSE_FAILED.value,
                'legacy_code': IngestErrorCode.E_REG_NO_NORMALIZE_FAILED.value,
                'message': 'registration_no normalize failed',
            },
        )

    # Best-effort binding for UDI-like payloads: map DI to normalized registration_no when DI exists in reason.raw.
    try:
        parsed_reason = json.loads(rec.reason) if rec.reason else {}
    except Exception:
        parsed_reason = {}
    raw_obj = parsed_reason.get('raw') if isinstance(parsed_reason, dict) else {}
    if not isinstance(raw_obj, dict):
        raw_obj = {}
    raw_obj = dict(raw_obj)
    di = str(raw_obj.get('di') or raw_obj.get('udi_di') or '').strip() or None
    raw_obj['registration_no'] = reg_no
    if not raw_obj.get('product_name') and rec.candidate_product_name:
        raw_obj['product_name'] = rec.candidate_product_name
    if not raw_obj.get('company_name') and rec.candidate_company:
        raw_obj['company_name'] = rec.candidate_company
    if not raw_obj.get('source_url'):
        raw_doc = db.get(RawDocument, rec.raw_document_id)
        if raw_doc is not None:
            raw_obj['source_url'] = raw_doc.source_url

    upsert_res = upsert_structured_record_via_runner(
        db,
        source_key=str(rec.source_key or 'ADMIN_PENDING_RESOLVE'),
        source_run_id=int(rec.source_run_id),
        row=raw_obj,
        parser_key=('udi_di_parser' if di else None),
        raw_document_id=rec.raw_document_id,
        observed_at=datetime.now(),
    )
    map_written = False
    if di:
        db.execute(
            text("DELETE FROM product_udi_map WHERE di = :di AND registration_no <> :registration_no"),
            {'di': di, 'registration_no': upsert_res.registration_no},
        )
        map_stmt = insert(ProductUdiMap).values(
            registration_no=upsert_res.registration_no,
            di=di,
            source='ADMIN_PENDING_RESOLVE',
            match_type='manual',
            confidence=0.95,
            raw_source_record_id=None,
        )
        map_stmt = map_stmt.on_conflict_do_update(
            index_elements=[ProductUdiMap.registration_no, ProductUdiMap.di],
            set_={
                'source': map_stmt.excluded.source,
                'match_type': map_stmt.excluded.match_type,
                'confidence': map_stmt.excluded.confidence,
                'updated_at': text('NOW()'),
            },
        )
        db.execute(map_stmt)
        map_written = True

    before_status = str(rec.status or '')
    before_candidate_no = rec.candidate_registry_no
    rec.candidate_registry_no = reg_no
    rec.status = 'resolved'
    rec.updated_at = datetime.now()
    db.add(rec)
    db.add(
        ChangeLog(
            product_id=None,
            entity_type='pending_record',
            entity_id=rec.id,
            change_type='resolve',
            changed_fields={
                'status': {'old': before_status, 'new': 'resolved'},
                'candidate_registry_no': {'old': before_candidate_no, 'new': reg_no},
            },
            before_json={'status': before_status, 'candidate_registry_no': before_candidate_no},
            after_json={'status': rec.status, 'candidate_registry_no': rec.candidate_registry_no},
            before_raw={'raw_document_id': str(rec.raw_document_id)},
            after_raw={
                'raw_document_id': str(rec.raw_document_id),
                'source_key': rec.source_key,
                'resolved_by': str(getattr(admin, 'email', '') or ''),
                'registration_no': reg_no,
                'variant_upserted': bool(upsert_res.variant_upserted),
                'udi_map_written': bool(map_written),
            },
            source_run_id=int(rec.source_run_id),
        )
    )
    db.commit()

    return _ok(
        {
            'id': str(rec.id),
            'status': rec.status,
            'source_key': rec.source_key,
            'registration_no': reg_no,
            'variant_upserted': bool(upsert_res.variant_upserted),
            'udi_map_written': bool(map_written),
            'resolved_by': str(getattr(admin, 'email', '') or ''),
            'updated_at': rec.updated_at,
        }
    )


@app.get('/api/admin/pending-documents')
def admin_list_pending_documents(
    status: str = Query(default='pending'),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    order_by: str = Query(default='created_at desc'),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    status_norm = str(status or 'pending').strip().lower()
    order_by_norm = ' '.join(str(order_by or '').strip().lower().split())
    if not order_by_norm:
        order_by_norm = 'created_at desc'
    if order_by_norm not in {'created_at desc', 'created_at asc'}:
        raise HTTPException(status_code=400, detail='order_by must be one of: created_at desc / created_at asc')

    filters = []
    if status_norm != 'all':
        if status_norm not in {'pending', 'resolved', 'ignored'}:
            raise HTTPException(status_code=400, detail='status must be pending/resolved/ignored/all')
        filters.append(PendingDocument.status == status_norm)

    q = select(PendingDocument)
    q_total = select(func.count(PendingDocument.id))
    if filters:
        q = q.where(*filters)
        q_total = q_total.where(*filters)

    q = q.order_by(
        desc(PendingDocument.created_at) if order_by_norm == 'created_at desc' else PendingDocument.created_at.asc()
    ).offset(int(offset)).limit(int(limit))

    rows = db.scalars(q).all()
    total = int(db.scalar(q_total) or 0)
    return _ok(
        {
            'items': [
                {
                    'id': str(r.id),
                    'raw_document_id': str(r.raw_document_id),
                    'source_run_id': (int(r.source_run_id) if r.source_run_id is not None else None),
                    'reason_code': str(r.reason_code or ''),
                    'status': str(r.status or ''),
                    'created_at': r.created_at,
                    'updated_at': r.updated_at,
                }
                for r in rows
            ],
            'total': total,
            'limit': int(limit),
            'offset': int(offset),
            'order_by': order_by_norm,
            'count': len(rows),
            'status': status_norm,
        }
    )


@app.get('/api/admin/pending-documents/stats')
def admin_pending_documents_stats(
    resolved_24h_hours: int = Query(default=24, ge=1, le=24 * 30),
    resolved_7d_days: int = Query(default=7, ge=1, le=365),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    # by_source_key: pending/resolved/ignored counters (grouped by raw_documents.source)
    source_rows = db.execute(
        text(
            """
            SELECT
              rd.source AS source_key,
              COUNT(*) FILTER (WHERE pd.status = 'pending') AS pending_count,
              COUNT(*) FILTER (WHERE pd.status = 'resolved') AS resolved_count,
              COUNT(*) FILTER (WHERE pd.status = 'ignored') AS ignored_count
            FROM pending_documents pd
            JOIN raw_documents rd ON rd.id = pd.raw_document_id
            WHERE pd.status IN ('pending', 'resolved', 'ignored')
            GROUP BY rd.source
            ORDER BY rd.source ASC
            """
        )
    ).mappings().all()

    # by_reason_code: pending counters to locate parser/anchor defects
    reason_rows = db.execute(
        text(
            """
            SELECT
              reason_code,
              COUNT(*) AS pending_count
            FROM pending_documents
            WHERE status = 'pending'
            GROUP BY reason_code
            ORDER BY pending_count DESC, reason_code ASC
            """
        )
    ).mappings().all()

    backlog_row = db.execute(
        text(
            """
            SELECT
              COUNT(*) FILTER (WHERE status = 'pending') AS pending_total,
              COUNT(*) FILTER (
                WHERE status = 'resolved'
                  AND updated_at >= NOW() - (:h || ' hours')::interval
              ) AS resolved_last_24h,
              COUNT(*) FILTER (
                WHERE status = 'resolved'
                  AND updated_at >= NOW() - (:d || ' days')::interval
              ) AS resolved_last_7d
            FROM pending_documents
            """
        ),
        {"h": int(resolved_24h_hours), "d": int(resolved_7d_days)},
    ).mappings().one()

    return _ok(
        {
            "by_source_key": [
                {
                    "source_key": str(r.get("source_key") or ""),
                    "pending": int(r.get("pending_count") or 0),
                    "resolved": int(r.get("resolved_count") or 0),
                    "ignored": int(r.get("ignored_count") or 0),
                }
                for r in source_rows
            ],
            "by_reason_code": [
                {
                    "reason_code": str(r.get("reason_code") or ""),
                    "pending": int(r.get("pending_count") or 0),
                }
                for r in reason_rows
            ],
            "backlog": {
                "pending_total": int(backlog_row.get("pending_total") or 0),
                "resolved_last_24h": int(backlog_row.get("resolved_last_24h") or 0),
                "resolved_last_7d": int(backlog_row.get("resolved_last_7d") or 0),
                "windows": {
                    "resolved_24h_hours": int(resolved_24h_hours),
                    "resolved_7d_days": int(resolved_7d_days),
                },
            },
        }
    )


@app.post('/api/admin/pending-documents/{pending_id}/resolve')
def admin_resolve_pending_document(
    pending_id: UUID,
    payload: dict,
    admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    rec = db.get(PendingDocument, pending_id)
    if rec is None:
        raise HTTPException(status_code=404, detail='pending document not found')
    if str(rec.status or '').lower() == 'resolved':
        raise HTTPException(status_code=409, detail='pending document already resolved')

    reg_no_raw = str(payload.get('registration_no') or '').strip()
    product_name_raw = str(payload.get('product_name') or '').strip() or None
    if not reg_no_raw:
        raise HTTPException(
            status_code=400,
            detail={
                'code': IngestErrorCode.E_CANONICAL_KEY_MISSING.value,
                'legacy_code': IngestErrorCode.E_NO_REG_NO.value,
                'message': 'registration_no is required',
            },
        )
    reg_no = normalize_registration_no(reg_no_raw)
    if not reg_no:
        raise HTTPException(
            status_code=400,
            detail={
                'code': IngestErrorCode.E_REG_NO_NORMALIZE_FAILED.value,
                'legacy_code': IngestErrorCode.E_REG_NO_NORMALIZE_FAILED.value,
                'message': 'registration_no normalize failed',
            },
        )

    raw_doc = db.get(RawDocument, rec.raw_document_id)
    if raw_doc is None:
        raise HTTPException(status_code=409, detail='raw_document not found for pending item')

    # Replay ingest from the stored raw_document JSON payload.
    try:
        raw_bytes = read_file_bytes(str(raw_doc.storage_uri))
        raw_obj = json.loads(raw_bytes.decode('utf-8', errors='ignore') or '{}')
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                'code': IngestErrorCode.E_PARSE_FAILED.value,
                'message': f'failed to load raw_document payload: {exc}',
            },
        )
    if not isinstance(raw_obj, dict):
        raise HTTPException(
            status_code=500,
            detail={
                'code': IngestErrorCode.E_PARSE_FAILED.value,
                'message': 'raw_document payload must be a JSON object',
            },
        )

    raw_obj = dict(raw_obj)
    raw_obj['registration_no'] = reg_no
    if product_name_raw:
        raw_obj['product_name'] = product_name_raw
    if not raw_obj.get('source_url') and raw_doc.source_url:
        raw_obj['source_url'] = raw_doc.source_url

    upsert_res = upsert_structured_record_via_runner(
        db,
        source_key=str(raw_doc.source or 'ADMIN_PENDING_DOC_RESOLVE').strip().upper() or 'ADMIN_PENDING_DOC_RESOLVE',
        source_run_id=(int(rec.source_run_id) if rec.source_run_id is not None else None),
        row=raw_obj,
        parser_key=None,
        raw_document_id=raw_doc.id,
        observed_at=datetime.now(),
    )

    before_status = str(rec.status or '')
    rec.status = 'resolved'
    rec.updated_at = datetime.now()
    db.add(rec)
    db.add(
        ChangeLog(
            product_id=None,
            entity_type='pending_document',
            entity_id=rec.id,
            change_type='resolve',
            changed_fields={
                'status': {'old': before_status, 'new': 'resolved'},
                'registration_no': {'old': None, 'new': reg_no},
            },
            before_json={'status': before_status},
            after_json={'status': rec.status, 'registration_no': reg_no},
            before_raw={'raw_document_id': str(rec.raw_document_id)},
            after_raw={
                'raw_document_id': str(rec.raw_document_id),
                'source': str(raw_doc.source or ''),
                'resolved_by': str(getattr(admin, 'email', '') or ''),
                'registration_no': reg_no,
                'variant_upserted': bool(upsert_res.variant_upserted),
            },
            source_run_id=(int(rec.source_run_id) if rec.source_run_id is not None else None),
        )
    )
    db.commit()

    return _ok(
        {
            'id': str(rec.id),
            'status': rec.status,
            'registration_no': reg_no,
            'source': str(raw_doc.source or ''),
            'variant_upserted': bool(upsert_res.variant_upserted),
            'updated_at': rec.updated_at,
        }
    )


@app.post('/api/admin/pending-documents/{pending_id}/ignore')
def admin_ignore_pending_document(
    pending_id: UUID,
    payload: dict,
    admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    rec = db.get(PendingDocument, pending_id)
    if rec is None:
        raise HTTPException(status_code=404, detail='pending document not found')
    if str(rec.status or '').lower() == 'resolved':
        raise HTTPException(status_code=409, detail='pending document already resolved')

    reason = str(payload.get('reason') or '').strip() or None
    before_status = str(rec.status or '')
    rec.status = 'ignored'
    rec.updated_at = datetime.now()
    db.add(rec)
    db.add(
        ChangeLog(
            product_id=None,
            entity_type='pending_document',
            entity_id=rec.id,
            change_type='ignore',
            changed_fields={'status': {'old': before_status, 'new': 'ignored'}},
            before_json={'status': before_status},
            after_json={'status': rec.status},
            before_raw={'raw_document_id': str(rec.raw_document_id)},
            after_raw={
                'raw_document_id': str(rec.raw_document_id),
                'ignored_by': str(getattr(admin, 'email', '') or ''),
                'reason': reason,
            },
            source_run_id=(int(rec.source_run_id) if rec.source_run_id is not None else None),
        )
    )
    db.commit()
    return _ok({'id': str(rec.id), 'status': rec.status, 'updated_at': rec.updated_at})


@app.get('/api/admin/udi/pending-links')
def admin_list_pending_udi_links(
    status: str = Query(default='pending'),
    source_key: str | None = Query(default=None),
    reason_code: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    order_by: str = Query(default='created_at desc'),
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    status_norm = str(status or 'pending').strip().lower()
    source_key_norm = str(source_key or '').strip()
    reason_code_norm = str(reason_code or '').strip()
    order_by_norm = ' '.join(str(order_by or '').strip().lower().split())
    if not order_by_norm:
        order_by_norm = 'created_at desc'
    if order_by_norm not in {'created_at desc', 'created_at asc'}:
        raise HTTPException(status_code=400, detail='order_by must be one of: created_at desc / created_at asc')

    status_map = {
        'pending': 'PENDING',
        'open': 'PENDING',
        'resolved': 'RESOLVED',
        'ignored': 'IGNORED',
    }
    filters = []
    if status_norm != 'all':
        if status_norm not in status_map:
            raise HTTPException(status_code=400, detail='status must be open/resolved/ignored/pending/all')
        filters.append(PendingUdiLink.status == status_map[status_norm])
    if reason_code_norm:
        filters.append(PendingUdiLink.reason_code == reason_code_norm)
    if source_key_norm:
        filters.append(RawSourceRecord.source == source_key_norm)

    join_cond = func.coalesce(PendingUdiLink.raw_source_record_id, PendingUdiLink.raw_id) == RawSourceRecord.id
    q = (
        select(PendingUdiLink, RawSourceRecord.source.label('source_key'))
        .select_from(PendingUdiLink)
        .outerjoin(RawSourceRecord, join_cond)
    )
    q_total = (
        select(func.count(PendingUdiLink.id))
        .select_from(PendingUdiLink)
        .outerjoin(RawSourceRecord, join_cond)
    )
    if filters:
        q = q.where(*filters)
        q_total = q_total.where(*filters)
    q = q.order_by(
        desc(PendingUdiLink.created_at) if order_by_norm == 'created_at desc' else PendingUdiLink.created_at.asc()
    ).offset(int(offset)).limit(int(limit))
    rows = db.execute(q).all()
    total = int(db.scalar(q_total) or 0)

    items: list[dict] = []
    for p, source_key_row in rows:
        raw_id = getattr(p, 'raw_source_record_id', None) or getattr(p, 'raw_id', None)
        raw_rec = db.get(RawSourceRecord, raw_id) if raw_id else None
        candidate_registry_no = None
        try:
            reason_obj = json.loads(str(getattr(p, 'reason', '') or ''))
        except Exception:
            reason_obj = {}
        if isinstance(reason_obj, dict):
            candidate_registry_no = (
                reason_obj.get('candidate_registry_no')
                or reason_obj.get('registration_no')
                or reason_obj.get('reg_no')
                or reason_obj.get('registry_no')
            )
            raw_reason = reason_obj.get('raw')
            if not candidate_registry_no and isinstance(raw_reason, dict):
                candidate_registry_no = (
                    raw_reason.get('candidate_registry_no')
                    or raw_reason.get('registration_no')
                    or raw_reason.get('reg_no')
                    or raw_reason.get('registry_no')
                )
        source_key_text = str(source_key_row or getattr(raw_rec, 'source', '') or '')
        items.append(
            {
                'id': str(p.id),
                'di': str(getattr(p, 'di', '') or ''),
                'source_key': source_key_text,
                'status': str(getattr(p, 'status', '') or ''),
                'reason': str(getattr(p, 'reason', '') or ''),
                'reason_code': (str(getattr(p, 'reason_code', '') or '') or None),
                'candidate_registry_no': (str(candidate_registry_no) if candidate_registry_no else None),
                'raw_id': (str(getattr(p, 'raw_id', None)) if getattr(p, 'raw_id', None) else None),
                'raw_source_record_id': (
                    str(getattr(p, 'raw_source_record_id', None))
                    if getattr(p, 'raw_source_record_id', None)
                    else None
                ),
                'raw_document_id': None,
                'candidate_company_name': getattr(p, 'candidate_company_name', None),
                'candidate_product_name': getattr(p, 'candidate_product_name', None),
                'retry_count': int(getattr(p, 'retry_count', 0) or 0),
                'next_retry_at': getattr(p, 'next_retry_at', None),
                'resolved_at': getattr(p, 'resolved_at', None),
                'resolved_by': getattr(p, 'resolved_by', None),
                'created_at': getattr(p, 'created_at', None),
                'updated_at': getattr(p, 'updated_at', None),
                'raw_payload': (raw_rec.payload if raw_rec is not None else None),
            }
        )
    return _ok(
        {
            'items': items,
            'total': total,
            'limit': int(limit),
            'offset': int(offset),
            'order_by': order_by_norm,
            'count': len(items),
            'status': status_norm,
        }
    )


@app.post('/api/admin/udi/pending-links/{pending_id}/bind')
def admin_bind_pending_udi_link(
    pending_id: UUID,
    payload: dict,
    admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    # Backward-compatible alias; shares idempotent resolve logic.
    return _admin_resolve_pending_udi_link(pending_id=pending_id, payload=payload, admin=admin, db=db)


def _admin_resolve_pending_udi_link(
    *,
    pending_id: UUID,
    payload: dict,
    admin: User,
    db: Session,
) -> dict:
    pending = db.get(PendingUdiLink, pending_id)
    if pending is None:
        raise HTTPException(status_code=404, detail='pending_udi_link not found')

    reg_no_raw = str(payload.get('registration_no') or '').strip()
    if not reg_no_raw:
        raise HTTPException(
            status_code=400,
            detail={
                'code': IngestErrorCode.E_CANONICAL_KEY_MISSING.value,
                'legacy_code': IngestErrorCode.E_NO_REG_NO.value,
                'message': 'registration_no is required',
            },
        )
    reg_no = normalize_registration_no(reg_no_raw)
    if not reg_no:
        raise HTTPException(
            status_code=400,
            detail={
                'code': IngestErrorCode.E_PARSE_FAILED.value,
                'legacy_code': IngestErrorCode.E_REG_NO_NORMALIZE_FAILED.value,
                'message': 'registration_no normalize failed',
            },
        )

    di = str(getattr(pending, 'di', '') or '').strip()
    if not di:
        raise HTTPException(status_code=400, detail='di is required')

    try:
        confidence = float(payload.get('confidence', 0.95))
    except Exception:
        confidence = 0.95
    confidence = max(0.0, min(1.0, confidence))

    raw_id = getattr(pending, 'raw_source_record_id', None) or getattr(pending, 'raw_id', None)
    reg_res = upsert_registration_with_contract(
        db,
        registration_no=reg_no,
        incoming_fields={},
        source='ADMIN_UDI_BIND',
        source_run_id=None,
        evidence_grade='A',
        source_priority=1,
        observed_at=datetime.now(),
        raw_source_record_id=raw_id,
        raw_payload={'manual_bind': True, 'pending_id': str(pending.id), 'di': di},
        write_change_log=True,
    )

    # Keep DI tied to one canonical registration_no.
    db.execute(
        text("DELETE FROM product_udi_map WHERE di = :di AND registration_no <> :registration_no"),
        {'di': di, 'registration_no': reg_res.registration_no},
    )
    stmt = insert(ProductUdiMap).values(
        registration_no=reg_res.registration_no,
        di=di,
        source='admin',
        match_type='manual',
        confidence=confidence,
        raw_source_record_id=raw_id,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[ProductUdiMap.registration_no, ProductUdiMap.di],
        set_={
            'source': stmt.excluded.source,
            'match_type': stmt.excluded.match_type,
            'confidence': stmt.excluded.confidence,
            'raw_source_record_id': stmt.excluded.raw_source_record_id,
            'updated_at': text('NOW()'),
        },
    )
    db.execute(stmt)

    before_status = str(getattr(pending, 'status', '') or '')
    before_resolved_at = getattr(pending, 'resolved_at', None)
    before_resolved_by = getattr(pending, 'resolved_by', None)
    pending.status = 'RESOLVED'
    if before_resolved_at is None:
        pending.resolved_at = datetime.now()
    pending.resolved_by = (str(getattr(admin, 'email', '') or '') or 'admin')
    db.add(pending)
    db.add(
        ChangeLog(
            product_id=None,
            entity_type='pending_udi_link',
            entity_id=pending.id,
            change_type='resolve',
            changed_fields={
                'status': {'old': before_status, 'new': pending.status},
                'registration_no': {'old': None, 'new': reg_res.registration_no},
                'di': {'old': di, 'new': di},
            },
            before_json={
                'status': before_status,
                'resolved_at': before_resolved_at.isoformat() if before_resolved_at else None,
                'resolved_by': before_resolved_by,
            },
            after_json={
                'status': pending.status,
                'resolved_at': pending.resolved_at.isoformat() if pending.resolved_at else None,
                'resolved_by': pending.resolved_by,
                'registration_no': reg_res.registration_no,
                'di': di,
            },
            before_raw={'pending_id': str(pending.id), 'raw_source_record_id': (str(raw_id) if raw_id else None)},
            after_raw={
                'pending_id': str(pending.id),
                'raw_source_record_id': (str(raw_id) if raw_id else None),
                'note': (str(payload.get('note') or '').strip() or None),
                'reason': (str(payload.get('reason') or '').strip() or None),
            },
            source_run_id=None,
        )
    )
    db.commit()

    return _ok(
        {
            'pending_id': str(pending.id),
            'di': di,
            'registration_no': reg_res.registration_no,
            'match_type': 'manual',
            'confidence': confidence,
            'status': pending.status,
            'idempotent': bool(before_status.upper() == 'RESOLVED'),
        }
    )


@app.post('/api/admin/udi/pending-links/{pending_id}/resolve')
def admin_resolve_pending_udi_link(
    pending_id: UUID,
    payload: dict,
    admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    return _admin_resolve_pending_udi_link(pending_id=pending_id, payload=payload, admin=admin, db=db)


@app.get('/api/admin/registrations/{registration_no}/methodologies')
def admin_get_registration_methodologies(
    registration_no: str,
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    reg_no = (registration_no or '').strip()
    if not reg_no:
        raise HTTPException(
            status_code=400,
            detail={
                "code": IngestErrorCode.E_CANONICAL_KEY_MISSING.value,
                "message": "registration_no is required",
                "legacy_detail": "registration_no is required",
            },
        )
    reg_no_norm = normalize_registration_no(reg_no)
    if not reg_no_norm:
        raise HTTPException(
            status_code=400,
            detail={
                "code": IngestErrorCode.E_PARSE_FAILED.value,
                "message": "registration_no normalize failed",
                "legacy_detail": "registration_no normalize failed",
            },
        )

    reg = db.scalar(select(Registration).where(Registration.registration_no == reg_no_norm))
    if not reg:
        raise HTTPException(status_code=404, detail='registration not found')

    rows = db.execute(
        select(RegistrationMethodology, MethodologyNode)
        .join(MethodologyNode, MethodologyNode.id == RegistrationMethodology.methodology_id)
        .where(RegistrationMethodology.registration_id == reg.id)
        .order_by(RegistrationMethodology.confidence.desc(), MethodologyNode.level.asc(), MethodologyNode.name.asc())
    ).all()

    items = []
    for rm, mn in rows:
        items.append(
            {
                'id': str(rm.id),
                'registration_id': str(rm.registration_id),
                'registration_no': reg.registration_no,
                'methodology_id': str(mn.id),
                'methodology_name': mn.name,
                'parent_id': (str(mn.parent_id) if mn.parent_id else None),
                'level': int(getattr(mn, 'level', 0) or 0),
                'synonyms': (mn.synonyms if isinstance(getattr(mn, 'synonyms', None), list) else []),
                'is_active': bool(getattr(mn, 'is_active', True)),
                'confidence': float(getattr(rm, 'confidence', 0.0) or 0.0),
                'source': str(getattr(rm, 'source', '') or ''),
                'created_at': getattr(rm, 'created_at', None),
                'updated_at': getattr(rm, 'updated_at', None),
            }
        )
    return _ok({'items': items, 'count': len(items)})


@app.post('/api/admin/registrations/{registration_no}/methodologies')
def admin_set_registration_methodologies(
    registration_no: str,
    payload: dict,
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    reg_no = (registration_no or '').strip()
    if not reg_no:
        raise HTTPException(
            status_code=400,
            detail={
                "code": IngestErrorCode.E_CANONICAL_KEY_MISSING.value,
                "message": "registration_no is required",
                "legacy_detail": "registration_no is required",
            },
        )
    reg_no_norm = normalize_registration_no(reg_no)
    if not reg_no_norm:
        raise HTTPException(
            status_code=400,
            detail={
                "code": IngestErrorCode.E_PARSE_FAILED.value,
                "message": "registration_no normalize failed",
                "legacy_detail": "registration_no normalize failed",
            },
        )
    reg = db.scalar(select(Registration).where(Registration.registration_no == reg_no_norm))
    if not reg:
        raise HTTPException(status_code=404, detail='registration not found')

    items = payload.get('items')
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail='payload.items must be a list')

    delete_ids = payload.get('delete_methodology_ids')
    if delete_ids is None:
        delete_ids = []
    if not isinstance(delete_ids, list):
        raise HTTPException(status_code=400, detail='delete_methodology_ids must be a list')
    delete_set = {str(x).strip() for x in delete_ids if str(x).strip()}

    upserts = 0
    deletes = 0

    # Upsert rows.
    for it in items:
        if not isinstance(it, dict):
            continue
        mid_raw = str(it.get('methodology_id') or '').strip()
        if not mid_raw:
            continue
        try:
            mid = UUID(mid_raw)
        except Exception:
            raise HTTPException(status_code=400, detail=f'invalid methodology_id: {mid_raw}')

        node = db.get(MethodologyNode, mid)
        if not node:
            raise HTTPException(status_code=404, detail=f'methodology node not found: {mid_raw}')

        try:
            confidence = float(it.get('confidence', 0.8))
        except Exception:
            confidence = 0.8
        confidence = max(0.0, min(1.0, confidence))

        source = str(it.get('source') or 'manual').strip().lower() or 'manual'
        if source not in {'rule', 'manual'}:
            raise HTTPException(status_code=400, detail='source must be one of: rule/manual')

        stmt = insert(RegistrationMethodology).values(
            registration_id=reg.id,
            methodology_id=mid,
            confidence=confidence,
            source=source,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[RegistrationMethodology.registration_id, RegistrationMethodology.methodology_id],
            set_={
                'confidence': stmt.excluded.confidence,
                'source': stmt.excluded.source,
                'updated_at': func.now(),
            },
        )
        db.execute(stmt)
        upserts += 1
        if mid_raw in delete_set:
            delete_set.discard(mid_raw)

    # Delete requested mappings.
    if delete_set:
        for mid_raw in list(delete_set):
            try:
                mid = UUID(mid_raw)
            except Exception:
                continue
            res = db.execute(
                text(
                    "DELETE FROM registration_methodologies WHERE registration_id = :rid AND methodology_id = :mid"
                ),
                {"rid": str(reg.id), "mid": str(mid)},
            )
            deletes += int(getattr(res, 'rowcount', 0) or 0)

    db.commit()
    return _ok({'ok': True, 'registration_no': reg.registration_no, 'upserts': upserts, 'deletes': deletes})


@app.post('/api/admin/procurement/lots/{lot_id}/map-registration')
def admin_map_procurement_lot_registration(
    lot_id: str,
    payload: dict,
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    lot_id_s = (lot_id or '').strip()
    if not lot_id_s:
        raise HTTPException(status_code=400, detail='lot_id is required')
    try:
        lot_uuid = UUID(lot_id_s)
    except Exception:
        raise HTTPException(status_code=400, detail='lot_id must be a UUID')

    lot = db.get(ProcurementLot, lot_uuid)
    if lot is None:
        raise HTTPException(status_code=404, detail='procurement lot not found')

    reg_no = str(payload.get('registration_no') or '').strip()
    if not reg_no:
        raise HTTPException(
            status_code=400,
            detail={
                "code": IngestErrorCode.E_CANONICAL_KEY_MISSING.value,
                "message": "registration_no is required",
                "legacy_detail": "registration_no is required",
            },
        )
    reg_no_norm = normalize_registration_no(reg_no)
    if not reg_no_norm:
        raise HTTPException(
            status_code=400,
            detail={
                "code": IngestErrorCode.E_PARSE_FAILED.value,
                "message": "registration_no normalize failed",
                "legacy_detail": "registration_no normalize failed",
            },
        )
    reg = db.scalar(select(Registration).where(Registration.registration_no == reg_no_norm))
    if reg is None:
        raise HTTPException(status_code=404, detail='registration not found')

    try:
        confidence = float(payload.get('confidence', 0.95))
    except Exception:
        confidence = 0.95
    confidence = max(0.0, min(1.0, confidence))

    out = upsert_manual_registration_map(
        db,
        lot_id=lot_uuid,
        registration_id=reg.id,
        confidence=confidence,
    )
    out['registration_no'] = reg.registration_no
    return _ok(out)


@app.get('/api/admin/lri', response_model=ApiResponseAdminLriList)
def admin_lri_list(
    date: str | None = Query(default=None, description='UTC date YYYY-MM-DD; if omitted, returns latest per registration'),
    risk_level: str | None = Query(default=None, description='LOW/MID/HIGH/CRITICAL'),
    model_version: str = Query(default='lri_v1'),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiResponseAdminLriList:
    date_norm: date | None = None
    if date:
        try:
            date_norm = datetime.strptime(str(date).strip(), "%Y-%m-%d").date()
        except Exception:
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")

    # Select latest score per registration (optionally constrained to a single UTC date).
    total = db.execute(
        text(
            """
            WITH latest AS (
              SELECT DISTINCT ON (s.registration_id)
                s.registration_id,
                s.product_id,
                s.methodology_id,
                s.tte_days,
                s.renewal_count,
                s.competitive_count,
                s.gp_new_12m,
                s.lri_norm,
                s.risk_level,
                s.model_version,
                s.calculated_at
              FROM lri_scores s
              WHERE s.model_version = :mv
                AND (CAST(:d AS date) IS NULL OR (s.calculated_at AT TIME ZONE 'UTC')::date = CAST(:d AS date))
              ORDER BY s.registration_id, s.calculated_at DESC, s.id ASC
            )
            SELECT COUNT(1)
            FROM latest
            WHERE (CAST(:rl AS text) IS NULL OR risk_level = CAST(:rl AS text))
            """
        ),
        {'mv': str(model_version), 'd': date_norm, 'rl': (str(risk_level).strip().upper() if risk_level else None)},
    ).scalar_one()

    rows = db.execute(
        text(
            """
            WITH latest AS (
              SELECT DISTINCT ON (s.registration_id)
                s.registration_id,
                s.product_id,
                s.methodology_id,
                s.tte_days,
                s.renewal_count,
                s.competitive_count,
                s.gp_new_12m,
                s.lri_norm,
                s.risk_level,
                s.model_version,
                s.calculated_at
              FROM lri_scores s
              WHERE s.model_version = :mv
                AND (CAST(:d AS date) IS NULL OR (s.calculated_at AT TIME ZONE 'UTC')::date = CAST(:d AS date))
              ORDER BY s.registration_id, s.calculated_at DESC, s.id ASC
            )
            SELECT
              l.registration_id,
              r.registration_no,
              l.product_id,
              p.name AS product_name,
              COALESCE(NULLIF(btrim(p.ivd_category), ''), NULLIF(btrim(p.category), '')) AS ivd_category,
              m.code AS methodology_code,
              m.name_cn AS methodology_name_cn,
              l.tte_days,
              l.renewal_count,
              l.competitive_count,
              l.gp_new_12m,
              l.lri_norm,
              l.risk_level,
              l.model_version,
              l.calculated_at
            FROM latest l
            JOIN registrations r ON r.id = l.registration_id
            LEFT JOIN products p ON p.id = l.product_id
            LEFT JOIN methodology_master m ON m.id = l.methodology_id
            WHERE (CAST(:rl AS text) IS NULL OR l.risk_level = CAST(:rl AS text))
            ORDER BY l.calculated_at DESC, l.registration_id ASC
            LIMIT :limit OFFSET :offset
            """
        ),
        {
            'mv': str(model_version),
            'd': date_norm,
            'rl': (str(risk_level).strip().upper() if risk_level else None),
            'limit': int(limit),
            'offset': int(offset),
        },
    ).mappings().all()

    items = [
        AdminLriItemOut(
            registration_id=r['registration_id'],
            registration_no=str(r['registration_no'] or ''),
            product_id=r.get('product_id'),
            product_name=r.get('product_name'),
            ivd_category=r.get('ivd_category'),
            methodology_code=r.get('methodology_code'),
            methodology_name_cn=r.get('methodology_name_cn'),
            tte_days=r.get('tte_days'),
            renewal_count=int(r.get('renewal_count') or 0),
            competitive_count=int(r.get('competitive_count') or 0),
            gp_new_12m=int(r.get('gp_new_12m') or 0),
            lri_norm=float(r.get('lri_norm') or 0),
            risk_level=str(r.get('risk_level') or ''),
            model_version=str(r.get('model_version') or ''),
            calculated_at=r.get('calculated_at'),
        )
        for r in rows
    ]

    return _ok(AdminLriListData(total=int(total or 0), items=items))


@app.post('/api/admin/lri/compute')
def admin_lri_compute(
    payload: dict,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    # Runs a synchronous compute with upsert (delete same-day window then insert),
    # so admins can validate config changes quickly.
    raw_date = payload.get('date')
    raw_mv = payload.get('model_version')
    upsert = bool(payload.get('upsert', True))

    asof = None
    if raw_date not in {None, ''}:
        try:
            asof = dt_date.fromisoformat(str(raw_date))
        except Exception:
            raise HTTPException(status_code=400, detail='date must be YYYY-MM-DD')

    mv = str(raw_mv or '').strip() if raw_mv not in {None, ''} else ''
    if not mv:
        cfg = get_admin_config(db, 'lri_v1_config')
        if cfg and isinstance(cfg.config_value, dict) and cfg.config_value.get('model_version'):
            mv = str(cfg.config_value.get('model_version') or '').strip()
    if not mv:
        mv = 'lri_v1'

    try:
        from app.services.lri_v1 import compute_lri_v1

        res = compute_lri_v1(
            db,
            asof=asof,
            dry_run=False,
            model_version=mv,
            upsert_mode=upsert,
        )
        return _ok(
            {
                'ok': bool(getattr(res, 'ok', True)),
                'dry_run': bool(getattr(res, 'dry_run', False)),
                'date': str(getattr(res, 'date', '') or ''),
                'model_version': str(getattr(res, 'model_version', '') or mv),
                'upsert_mode': bool(getattr(res, 'upsert_mode', upsert)),
                'would_write': int(getattr(res, 'would_write', 0) or 0),
                'wrote': int(getattr(res, 'wrote', 0) or 0),
                'risk_dist': dict(getattr(res, 'risk_dist', {}) or {}),
                'missing_methodology_ratio': float(getattr(res, 'missing_methodology_ratio', 0.0) or 0.0),
                'error': getattr(res, 'error', None),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={'code': 'LRI_COMPUTE_FAILED', 'message': str(e)})


@app.get('/api/admin/lri/quality-latest')
def admin_lri_quality_latest(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    row = db.execute(
        text(
            """
            SELECT
              metric_date,
              pending_count,
              lri_computed_count,
              lri_missing_methodology_count,
              risk_level_distribution,
              updated_at
            FROM daily_metrics
            ORDER BY metric_date DESC
            LIMIT 1
            """
        )
    ).mappings().first()
    if not row:
        return _ok(
            {
                'metric_date': None,
                'pending_count': 0,
                'lri_computed_count': 0,
                'lri_missing_methodology_count': 0,
                'risk_level_distribution': {'LOW': 0, 'MID': 0, 'HIGH': 0, 'CRITICAL': 0},
                'updated_at': None,
            }
        )
    dist = row.get('risk_level_distribution') or {}
    out_dist = {k: int(dist.get(k, 0) or 0) for k in ('LOW', 'MID', 'HIGH', 'CRITICAL')}
    return _ok(
        {
            'metric_date': row.get('metric_date'),
            'pending_count': int(row.get('pending_count') or 0),
            'lri_computed_count': int(row.get('lri_computed_count') or 0),
            'lri_missing_methodology_count': int(row.get('lri_missing_methodology_count') or 0),
            'risk_level_distribution': out_dist,
            'updated_at': row.get('updated_at'),
        }
    )


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
        'source_priority': int(cfg.get('source_priority') or 100),
        'default_evidence_grade': str(cfg.get('default_evidence_grade') or 'C'),
        'enforce_registration_anchor': bool(cfg.get('enforce_registration_anchor', True)),
        'allow_without_registration_no': bool(cfg.get('allow_without_registration_no', False)),
        'pending_queue_name': (str(cfg.get('pending_queue_name')).strip() if cfg.get('pending_queue_name') else None),
    }


def _normalize_data_source_config(type_: str, cfg: dict) -> dict:
    if type_ == POSTGRES_SOURCE_TYPE:
        grade_raw = str(cfg.get('default_evidence_grade') or 'C').strip().upper()
        default_grade = grade_raw if grade_raw in {'A', 'B', 'C', 'D'} else 'C'
        try:
            source_priority = int(cfg.get('source_priority') or 100)
        except Exception:
            source_priority = 100
        return {
            'host': str(cfg.get('host') or '').strip(),
            'port': int(cfg.get('port') or 5432),
            'database': str(cfg.get('database') or '').strip(),
            'username': str(cfg.get('username') or '').strip(),
            'password': cfg.get('password'),
            'sslmode': (str(cfg.get('sslmode')).strip() if cfg.get('sslmode') not in {None, ''} else None),
            'source_table': str(cfg.get('source_table') or 'public.products').strip() or 'public.products',
            'source_query': (str(cfg.get('source_query')).strip() if cfg.get('source_query') not in {None, ''} else None),
            'source_priority': source_priority,
            'default_evidence_grade': default_grade,
            'enforce_registration_anchor': bool(cfg.get('enforce_registration_anchor', True)),
            'allow_without_registration_no': bool(cfg.get('allow_without_registration_no', False)),
            'pending_queue_name': (str(cfg.get('pending_queue_name')).strip() if cfg.get('pending_queue_name') else None),
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


def _json_dict_or_400(v: object, *, field: str) -> dict:
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    raise HTTPException(status_code=400, detail=f'{field} must be an object')


def _source_item(defn: SourceDefinition, cfg: SourceConfig | None) -> dict:
    if cfg is None:
        config = {
            'id': None,
            'enabled': bool(defn.enabled_by_default),
            'schedule_cron': None,
            'fetch_params': {},
            'parse_params': {},
            'upsert_policy': {},
            'last_run_at': None,
            'last_status': None,
            'last_error': None,
            'created_at': None,
            'updated_at': None,
        }
    else:
        config = {
            'id': str(cfg.id),
            'enabled': bool(cfg.enabled),
            'schedule_cron': cfg.schedule_cron,
            'fetch_params': cfg.fetch_params if isinstance(cfg.fetch_params, dict) else {},
            'parse_params': cfg.parse_params if isinstance(cfg.parse_params, dict) else {},
            'upsert_policy': cfg.upsert_policy if isinstance(cfg.upsert_policy, dict) else {},
            'last_run_at': cfg.last_run_at,
            'last_status': cfg.last_status,
            'last_error': cfg.last_error,
            'created_at': cfg.created_at,
            'updated_at': cfg.updated_at,
        }
    return {
        'source_key': defn.source_key,
        'display_name': defn.display_name,
        'entity_scope': defn.entity_scope,
        'default_evidence_grade': defn.default_evidence_grade,
        'parser_key': defn.parser_key,
        'enabled_by_default': bool(defn.enabled_by_default),
        'config': config,
    }


def _source_binding_meta(source_key: str, cfg: SourceConfig | None) -> dict:
    binding = SOURCE_REGISTRY_LEGACY_BINDINGS.get(str(source_key or '').upper()) or {}
    fp = cfg.fetch_params if (cfg and isinstance(cfg.fetch_params, dict)) else {}
    if not isinstance(fp, dict):
        fp = {}
    lg = fp.get('legacy_data_source') if isinstance(fp.get('legacy_data_source'), dict) else {}
    legacy_name = str(lg.get('name') or binding.get('legacy_name') or '').strip()
    legacy_type = str(lg.get('type') or binding.get('legacy_type') or '').strip().lower()
    mode = str(lg.get('role') or binding.get('role') or 'mapped').strip().lower()
    if legacy_type not in {POSTGRES_SOURCE_TYPE, LOCAL_REGISTRY_SOURCE_TYPE}:
        legacy_type = ''
    if not legacy_name or not legacy_type:
        return {'bound': False, 'mode': 'none'}
    return {
        'bound': True,
        'mode': mode or 'mapped',
        'legacy_name': legacy_name,
        'legacy_type': legacy_type,
    }


def _sync_source_config_to_legacy_data_source(db: Session, *, defn: SourceDefinition, cfg: SourceConfig) -> dict:
    """Bridge Source Registry configs into legacy `data_sources` without changing worker logic."""
    meta = _source_binding_meta(defn.source_key, cfg)
    if not meta.get('bound'):
        return {'synced': False, 'reason': 'no_binding'}

    legacy_name = str(meta.get('legacy_name') or '').strip()
    legacy_type = str(meta.get('legacy_type') or '').strip()
    role = str(meta.get('mode') or 'mapped')
    if not legacy_name or legacy_type not in {POSTGRES_SOURCE_TYPE, LOCAL_REGISTRY_SOURCE_TYPE}:
        return {'synced': False, 'reason': 'invalid_binding'}

    fp = cfg.fetch_params if isinstance(cfg.fetch_params, dict) else {}
    if not isinstance(fp, dict):
        fp = {}
    legacy_block = fp.get('legacy_data_source') if isinstance(fp.get('legacy_data_source'), dict) else {}
    raw_cfg = legacy_block.get('config') if isinstance(legacy_block.get('config'), dict) else None
    if raw_cfg is None:
        raw_cfg = fp.get('connection') if isinstance(fp.get('connection'), dict) else fp
    if not isinstance(raw_cfg, dict):
        raw_cfg = {}

    rows = list_data_sources(db)
    legacy_ds = next((x for x in rows if (x.name or '').strip() == legacy_name), None)
    merged_cfg = dict(raw_cfg)
    # Keep a single control plane: top-level fetch_params overrides legacy nested config.
    top_level_overrides = [
        'host', 'port', 'database', 'username', 'password', 'sslmode',
        'source_table', 'source_query', 'batch_size', 'cutoff_window_hours',
    ]
    for key in top_level_overrides:
        if key in fp and fp.get(key) not in {None, ''}:
            merged_cfg[key] = fp.get(key)

    # Keep old password if caller omits it.
    if legacy_type == POSTGRES_SOURCE_TYPE and legacy_ds is not None:
        old_cfg = decrypt_json(legacy_ds.config_encrypted)
        if isinstance(old_cfg, dict):
            if 'password' not in merged_cfg or not merged_cfg.get('password'):
                if old_cfg.get('password'):
                    merged_cfg['password'] = old_cfg.get('password')

    try:
        normalized_cfg = _normalize_data_source_config(legacy_type, merged_cfg)
    except Exception as exc:
        return {'synced': False, 'reason': f'legacy_config_invalid: {exc}'}

    token = encrypt_json(normalized_cfg)
    if legacy_ds is None:
        legacy_ds = create_data_source(db, name=legacy_name, type_=legacy_type, config_encrypted=token)
    else:
        legacy_ds = update_data_source(
            db,
            int(legacy_ds.id),
            name=legacy_name,
            type_=legacy_type,
            config_encrypted=token,
        ) or legacy_ds

    # Keep primary source active state aligned with source_config.enabled.
    if role == 'primary':
        if bool(cfg.enabled):
            activate_data_source(db, int(legacy_ds.id))
        else:
            db.execute(update(DataSource).where(DataSource.id == int(legacy_ds.id)).values(is_active=False))
            db.commit()
            db.refresh(legacy_ds)

    return {
        'synced': True,
        'legacy_data_source_id': int(legacy_ds.id),
        'legacy_name': legacy_name,
        'legacy_type': legacy_type,
        'legacy_active': bool(getattr(legacy_ds, 'is_active', False)),
        'role': role,
    }


def _legacy_binding_runtime_status(db: Session, source_key: str, cfg: SourceConfig | None) -> dict:
    meta = _source_binding_meta(source_key, cfg)
    if not meta.get('bound'):
        return {'bound': False}
    legacy_name = str(meta.get('legacy_name') or '').strip()
    rows = list_data_sources(db)
    ds = next((x for x in rows if (x.name or '').strip() == legacy_name), None)
    return {
        'bound': True,
        'legacy_exists': bool(ds is not None),
        'legacy_data_source_id': (int(ds.id) if ds is not None else None),
        'legacy_is_active': (bool(ds.is_active) if ds is not None else False),
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


@app.get('/api/admin/sources')
def admin_list_sources_api(
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    defs = list(db.scalars(select(SourceDefinition).order_by(SourceDefinition.source_key.asc())).all())
    cfg_map = {x.source_key: x for x in db.scalars(select(SourceConfig)).all()}
    items = []
    for d in defs:
        cfg = cfg_map.get(d.source_key)
        row = _source_item(d, cfg)
        row['compat'] = {**_source_binding_meta(d.source_key, cfg), **_legacy_binding_runtime_status(db, d.source_key, cfg)}
        items.append(row)
    return _ok({'items': items, 'count': len(items)})


@app.post('/api/admin/sources')
def admin_create_source_config_api(
    payload: dict,
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    source_key = str(payload.get('source_key') or '').strip().upper()
    if not source_key:
        raise HTTPException(status_code=400, detail='source_key is required')

    defn = db.get(SourceDefinition, source_key)
    if defn is None:
        # Allow creating new source definition from admin payload to reduce code touch for new sources.
        display_name = str(payload.get('display_name') or '').strip()
        entity_scope = str(payload.get('entity_scope') or '').strip().upper()
        parser_key = str(payload.get('parser_key') or '').strip()
        default_grade = str(payload.get('default_evidence_grade') or 'C').strip().upper()
        if not display_name or not entity_scope or not parser_key:
            raise HTTPException(
                status_code=404,
                detail='source definition not found; provide display_name/entity_scope/parser_key to create one',
            )
        if default_grade not in {'A', 'B', 'C', 'D'}:
            default_grade = 'C'
        defn = SourceDefinition(
            source_key=source_key,
            display_name=display_name,
            entity_scope=entity_scope,
            default_evidence_grade=default_grade,
            parser_key=parser_key,
            enabled_by_default=bool(payload.get('enabled_by_default', True)),
        )
        db.add(defn)
        db.flush()

    exists = db.scalar(select(SourceConfig).where(SourceConfig.source_key == source_key))
    if exists is not None:
        raise HTTPException(status_code=409, detail='source config already exists; use PATCH')

    enabled = bool(payload.get('enabled', defn.enabled_by_default))
    schedule_cron = str(payload.get('schedule_cron')).strip() if payload.get('schedule_cron') not in {None, ''} else None
    fetch_params = _json_dict_or_400(payload.get('fetch_params'), field='fetch_params')
    parse_params = _json_dict_or_400(payload.get('parse_params'), field='parse_params')
    upsert_policy = _json_dict_or_400(payload.get('upsert_policy'), field='upsert_policy')

    cfg = SourceConfig(
        source_key=source_key,
        enabled=enabled,
        schedule_cron=schedule_cron,
        fetch_params=fetch_params,
        parse_params=parse_params,
        upsert_policy=upsert_policy,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    compat = _sync_source_config_to_legacy_data_source(db, defn=defn, cfg=cfg)
    item = _source_item(defn, cfg)
    item['compat'] = {**_source_binding_meta(defn.source_key, cfg), **compat}
    return _ok({'item': item})


@app.patch('/api/admin/sources')
def admin_patch_source_config_api(
    payload: dict,
    _admin: User = Depends(_require_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    source_key = str(payload.get('source_key') or '').strip().upper()
    if not source_key:
        raise HTTPException(status_code=400, detail='source_key is required')

    defn = db.get(SourceDefinition, source_key)
    if defn is None:
        raise HTTPException(status_code=404, detail='source definition not found')

    cfg = db.scalar(select(SourceConfig).where(SourceConfig.source_key == source_key))
    if cfg is None:
        cfg = SourceConfig(
            source_key=source_key,
            enabled=bool(defn.enabled_by_default),
            fetch_params={},
            parse_params={},
            upsert_policy={},
        )
        db.add(cfg)
        db.flush()

    if 'enabled' in payload:
        cfg.enabled = bool(payload.get('enabled'))
    if 'schedule_cron' in payload:
        cfg.schedule_cron = (str(payload.get('schedule_cron')).strip() if payload.get('schedule_cron') not in {None, ''} else None)
    if 'fetch_params' in payload:
        cfg.fetch_params = _json_dict_or_400(payload.get('fetch_params'), field='fetch_params')
    if 'parse_params' in payload:
        cfg.parse_params = _json_dict_or_400(payload.get('parse_params'), field='parse_params')
    if 'upsert_policy' in payload:
        cfg.upsert_policy = _json_dict_or_400(payload.get('upsert_policy'), field='upsert_policy')
    if 'last_status' in payload:
        cfg.last_status = (str(payload.get('last_status')).strip() if payload.get('last_status') not in {None, ''} else None)
    if 'last_error' in payload:
        cfg.last_error = (str(payload.get('last_error')).strip() if payload.get('last_error') not in {None, ''} else None)
    if 'last_run_at' in payload:
        raw = payload.get('last_run_at')
        if raw in {None, ''}:
            cfg.last_run_at = None
        else:
            try:
                cfg.last_run_at = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
            except Exception:
                raise HTTPException(status_code=400, detail='last_run_at must be ISO datetime')

    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    compat = _sync_source_config_to_legacy_data_source(db, defn=defn, cfg=cfg)
    item = _source_item(defn, cfg)
    item['compat'] = {**_source_binding_meta(defn.source_key, cfg), **compat}
    return _ok({'item': item})


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
