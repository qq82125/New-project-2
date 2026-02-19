from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import String, and_, cast, desc, func, select
from sqlalchemy.orm import Session

from app.models import Company, Product, Registration
from app.models.signal_score import SignalScore
from app.schemas.signal import (
    BatchSignalItem,
    BatchSignalsResponse,
    SignalFactor,
    SignalResponse,
    TopCompetitiveTrackItem,
    TopCompetitiveTracksResponse,
    TopGrowthCompaniesResponse,
    TopGrowthCompanyItem,
    TopRiskRegistrationItem,
    TopRiskRegistrationsResponse,
)

DEFAULT_WINDOW = '12m'
DEFAULT_LEVEL = 'medium'
DEFAULT_EXPLANATION = '未计算/请运行 signals-compute'


def _to_float(v) -> float:
    if isinstance(v, Decimal):
        return float(v)
    if v is None:
        return 0.0
    try:
        return float(v)
    except Exception:
        return 0.0


def _normalize_factors(raw) -> list[SignalFactor]:
    if not isinstance(raw, list):
        return []
    out: list[SignalFactor] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if 'name' not in item or 'explanation' not in item:
            continue
        out.append(
            SignalFactor(
                name=str(item.get('name')),
                value=item.get('value'),
                unit=(str(item.get('unit')) if item.get('unit') is not None else None),
                explanation=str(item.get('explanation')),
                drill_link=(str(item.get('drill_link')) if item.get('drill_link') is not None else None),
            )
        )
    return out


def _factor_value(raw_factors: Any, factor_name: str) -> Any:
    if not isinstance(raw_factors, list):
        return None
    for item in raw_factors:
        if not isinstance(item, dict):
            continue
        if str(item.get('name') or '') == factor_name:
            return item.get('value')
    return None


def _to_int(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, Decimal):
        return int(v)
    try:
        return int(float(v))
    except Exception:
        return None


def _resolve_as_of_date(db: Session, *, entity_type: str, window: str, as_of_date: date | None) -> date | None:
    if as_of_date is not None:
        return as_of_date
    return db.scalar(
        select(func.max(SignalScore.as_of_date)).where(
            SignalScore.entity_type == entity_type,
            SignalScore.window == window,
        )
    )


def _entity_signal_map(
    db: Session,
    *,
    entity_type: str,
    entity_ids: list[str],
    as_of_date: date | None,
    window: str,
) -> dict[str, SignalScore]:
    ids = [str(x).strip() for x in entity_ids if str(x).strip()]
    if not ids:
        return {}

    exact_map: dict[str, SignalScore] = {}
    if as_of_date is not None:
        exact_rows = db.scalars(
            select(SignalScore)
            .where(
                SignalScore.entity_type == entity_type,
                SignalScore.window == window,
                SignalScore.as_of_date == as_of_date,
                SignalScore.entity_id.in_(ids),
            )
            .order_by(SignalScore.entity_id.asc(), desc(SignalScore.computed_at))
        ).all()
        for row in exact_rows:
            rid = str(row.entity_id)
            if rid not in exact_map:
                exact_map[rid] = row
        if len(exact_map) == len(set(ids)):
            return exact_map

    missing_ids = [x for x in ids if x not in exact_map]
    if not missing_ids:
        return exact_map

    latest_rows = db.scalars(
        select(SignalScore)
        .where(
            SignalScore.entity_type == entity_type,
            SignalScore.window == window,
            SignalScore.entity_id.in_(missing_ids),
        )
        .order_by(SignalScore.entity_id.asc(), desc(SignalScore.as_of_date), desc(SignalScore.computed_at))
    ).all()
    latest_map: dict[str, SignalScore] = {}
    for row in latest_rows:
        rid = str(row.entity_id)
        if rid not in latest_map:
            latest_map[rid] = row

    merged = dict(exact_map)
    merged.update(latest_map)
    return merged


def _lifecycle_summary(raw_factors: Any) -> str | None:
    days = _factor_value(raw_factors, 'days_to_expiry')
    renew = _factor_value(raw_factors, 'has_renewal_history')
    density = _factor_value(raw_factors, 'competition_density')
    parts: list[str] = []
    if days is not None:
        if isinstance(days, (int, float, Decimal)):
            parts.append(f'expiry:{int(days)}d')
        else:
            parts.append(f'expiry:{days}')
    if renew is not None:
        parts.append(f'renew:{str(renew).lower()}')
    if density is not None:
        parts.append(f'density:{density}')
    if not parts:
        return None
    return '; '.join(parts)


def _default_signal() -> SignalResponse:
    return SignalResponse(
        level=DEFAULT_LEVEL,
        score=0.0,
        factors=[SignalFactor(name='not_computed', value=0, explanation=DEFAULT_EXPLANATION)],
        updated_at=datetime.now(timezone.utc),
    )


def get_entity_signal(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    as_of_date: date | None = None,
    window: str = DEFAULT_WINDOW,
) -> SignalResponse:
    target_date = as_of_date or date.today()

    stmt_exact = (
        select(SignalScore)
        .where(
            SignalScore.entity_type == entity_type,
            SignalScore.entity_id == entity_id,
            SignalScore.window == window,
            SignalScore.as_of_date == target_date,
        )
        .order_by(desc(SignalScore.computed_at))
        .limit(1)
    )
    row = db.scalar(stmt_exact)

    if row is None:
        stmt_latest = (
            select(SignalScore)
            .where(
                SignalScore.entity_type == entity_type,
                SignalScore.entity_id == entity_id,
                SignalScore.window == window,
            )
            .order_by(desc(SignalScore.as_of_date), desc(SignalScore.computed_at))
            .limit(1)
        )
        row = db.scalar(stmt_latest)

    if row is None:
        return _default_signal()

    factors = _normalize_factors(getattr(row, 'factors', None))
    return SignalResponse(
        level=str(getattr(row, 'level', DEFAULT_LEVEL) or DEFAULT_LEVEL),
        score=_to_float(getattr(row, 'score', 0)),
        factors=factors,
        updated_at=(getattr(row, 'computed_at', None) or datetime.now(timezone.utc)),
    )


def get_top_risk_registrations(
    db: Session,
    *,
    limit: int = 10,
    as_of_date: date | None = None,
    window: str = DEFAULT_WINDOW,
) -> TopRiskRegistrationsResponse:
    target = _resolve_as_of_date(db, entity_type='registration', window=window, as_of_date=as_of_date)
    if target is None:
        return TopRiskRegistrationsResponse(items=[])

    dominant_company_subq = (
        select(
            Product.registration_id.label('registration_id'),
            Company.name.label('company_name'),
            func.row_number()
            .over(
                partition_by=Product.registration_id,
                order_by=(Product.updated_at.desc(), Product.created_at.desc(), Product.id.desc()),
            )
            .label('rn'),
        )
        .join(Company, Company.id == Product.company_id, isouter=True)
        .where(Product.registration_id.is_not(None))
        .subquery()
    )

    stmt = (
        select(
            SignalScore.entity_id,
            SignalScore.level,
            SignalScore.score,
            SignalScore.factors,
            dominant_company_subq.c.company_name,
        )
        .join(Registration, Registration.registration_no == SignalScore.entity_id, isouter=True)
        .join(
            dominant_company_subq,
            and_(
                dominant_company_subq.c.registration_id == Registration.id,
                dominant_company_subq.c.rn == 1,
            ),
            isouter=True,
        )
        .where(
            SignalScore.entity_type == 'registration',
            SignalScore.window == window,
            SignalScore.as_of_date == target,
        )
        .order_by(SignalScore.computed_at.desc())
        .limit(max(1, min(int(limit or 10), 100)) * 4)
    )
    rows = db.execute(stmt).all()

    parsed: list[tuple[float, int | None, TopRiskRegistrationItem]] = []
    for entity_id, level, _score, factors, company_name in rows:
        days = _to_int(_factor_value(factors, 'days_to_expiry'))
        parsed.append(
            (
                _to_float(_score),
                days,
                TopRiskRegistrationItem(
                    registration_no=str(entity_id),
                    company=(str(company_name) if company_name else None),
                    level=str(level or DEFAULT_LEVEL),
                    days_to_expiry=days,
                ),
            )
        )

    def _risk_sort_key(row: tuple[float, int | None, TopRiskRegistrationItem]) -> tuple[int, float, int]:
        score, days, _item = row
        if score > 0:
            return (0, -score, days if days is not None else 10**9)
        return (1, 0.0, days if days is not None else 10**9)

    parsed.sort(key=_risk_sort_key)
    items: list[TopRiskRegistrationItem] = []
    for _score, _days, item in parsed[: max(1, min(int(limit or 10), 100))]:
        items.append(item)

    return TopRiskRegistrationsResponse(items=items)


def get_top_competitive_tracks(
    db: Session,
    *,
    limit: int = 10,
    as_of_date: date | None = None,
    window: str = DEFAULT_WINDOW,
) -> TopCompetitiveTracksResponse:
    target = _resolve_as_of_date(db, entity_type='track', window=window, as_of_date=as_of_date)
    if target is None:
        return TopCompetitiveTracksResponse(items=[])

    stmt = (
        select(
            SignalScore.entity_id,
            SignalScore.level,
            SignalScore.score,
            SignalScore.factors,
        )
        .where(
            SignalScore.entity_type == 'track',
            SignalScore.window == window,
            SignalScore.as_of_date == target,
        )
        .order_by(SignalScore.computed_at.desc())
        .limit(max(1, min(int(limit or 10), 100)) * 4)
    )
    rows = db.execute(stmt).all()

    parsed: list[tuple[float, int, TopCompetitiveTrackItem]] = []
    for entity_id, level, _score, factors in rows:
        total_count = _to_int(_factor_value(factors, 'total_count'))
        new_rate = _to_float(_factor_value(factors, 'new_rate_12m'))
        parsed.append(
            (
                _to_float(_score),
                int(total_count or 0),
                TopCompetitiveTrackItem(
                    track_id=str(entity_id),
                    track_name=str(entity_id),
                    level=str(level or 'moderate'),
                    total_count=total_count,
                    new_rate_12m=new_rate,
                ),
            )
        )

    parsed.sort(key=lambda x: ((0, -x[0]) if x[0] > 0 else (1, -x[1])))
    items = [item for _score, _total, item in parsed[: max(1, min(int(limit or 10), 100))]]
    return TopCompetitiveTracksResponse(items=items)


def get_top_growth_companies(
    db: Session,
    *,
    limit: int = 10,
    as_of_date: date | None = None,
    window: str = DEFAULT_WINDOW,
) -> TopGrowthCompaniesResponse:
    target = _resolve_as_of_date(db, entity_type='company', window=window, as_of_date=as_of_date)
    if target is None:
        return TopGrowthCompaniesResponse(items=[])

    stmt = (
        select(
            SignalScore.entity_id,
            SignalScore.level,
            SignalScore.score,
            SignalScore.factors,
            Company.name,
        )
        .join(Company, cast(Company.id, String) == SignalScore.entity_id, isouter=True)
        .where(
            SignalScore.entity_type == 'company',
            SignalScore.window == window,
            SignalScore.as_of_date == target,
        )
        .order_by(SignalScore.computed_at.desc())
        .limit(max(1, min(int(limit or 10), 100)) * 4)
    )
    rows = db.execute(stmt).all()

    parsed: list[tuple[float, int, TopGrowthCompanyItem]] = []
    for entity_id, level, _score, factors, company_name in rows:
        new_regs = _to_int(_factor_value(factors, 'new_registrations_12m'))
        new_tracks = _to_int(_factor_value(factors, 'new_tracks_12m'))
        parsed.append(
            (
                _to_float(_score),
                int(new_regs or 0),
                TopGrowthCompanyItem(
                    company_id=str(entity_id),
                    company_name=(str(company_name) if company_name else None),
                    level=str(level or 'medium_growth'),
                    new_registrations_12m=new_regs,
                    new_tracks_12m=new_tracks,
                ),
            )
        )

    parsed.sort(key=lambda x: ((0, -x[0]) if x[0] > 0 else (1, -x[1])))
    items = [item for _score, _new_regs, item in parsed[: max(1, min(int(limit or 10), 100))]]
    return TopGrowthCompaniesResponse(items=items)


def get_batch_registration_signals(
    db: Session,
    *,
    registration_nos: list[str],
    as_of_date: date | None = None,
    window: str = DEFAULT_WINDOW,
) -> BatchSignalsResponse:
    ordered_nos = [str(x).strip() for x in registration_nos if str(x).strip()]
    if not ordered_nos:
        return BatchSignalsResponse(items=[])

    unique_nos = list(dict.fromkeys(ordered_nos))
    reg_signal_map = _entity_signal_map(
        db,
        entity_type='registration',
        entity_ids=unique_nos,
        as_of_date=as_of_date,
        window=window,
    )

    dominant_anchor_subq = (
        select(
            Product.registration_id.label('registration_id'),
            Product.ivd_category.label('track_id'),
            cast(Product.company_id, String).label('company_id'),
            func.row_number()
            .over(
                partition_by=Product.registration_id,
                order_by=(Product.updated_at.desc(), Product.created_at.desc(), Product.id.desc()),
            )
            .label('rn'),
        )
        .where(Product.registration_id.is_not(None))
        .subquery()
    )
    anchor_rows = db.execute(
        select(
            Registration.registration_no,
            dominant_anchor_subq.c.track_id,
            dominant_anchor_subq.c.company_id,
        )
        .join(
            dominant_anchor_subq,
            and_(
                dominant_anchor_subq.c.registration_id == Registration.id,
                dominant_anchor_subq.c.rn == 1,
            ),
            isouter=True,
        )
        .where(Registration.registration_no.in_(unique_nos))
    ).all()
    anchor_map = {
        str(reg_no): {
            'track_id': (str(track_id).strip() if track_id is not None and str(track_id).strip() else None),
            'company_id': (str(company_id).strip() if company_id is not None and str(company_id).strip() else None),
        }
        for reg_no, track_id, company_id in anchor_rows
    }

    track_ids = list({str(v['track_id']) for v in anchor_map.values() if v.get('track_id')})
    company_ids = list({str(v['company_id']) for v in anchor_map.values() if v.get('company_id')})
    track_signal_map = _entity_signal_map(
        db,
        entity_type='track',
        entity_ids=track_ids,
        as_of_date=as_of_date,
        window=window,
    )
    company_signal_map = _entity_signal_map(
        db,
        entity_type='company',
        entity_ids=company_ids,
        as_of_date=as_of_date,
        window=window,
    )

    items: list[BatchSignalItem] = []
    for reg_no in ordered_nos:
        reg_row = reg_signal_map.get(reg_no)
        lifecycle_level = str(getattr(reg_row, 'level', DEFAULT_LEVEL) or DEFAULT_LEVEL)
        lifecycle_summary = _lifecycle_summary(getattr(reg_row, 'factors', None)) if reg_row else None

        anchor = anchor_map.get(reg_no) or {}
        track_id = anchor.get('track_id')
        company_id = anchor.get('company_id')
        track_level = None
        company_level = None
        if track_id and track_id in track_signal_map:
            track_level = str(getattr(track_signal_map[track_id], 'level', '') or '')
        if company_id and company_id in company_signal_map:
            company_level = str(getattr(company_signal_map[company_id], 'level', '') or '')

        items.append(
            BatchSignalItem(
                registration_no=reg_no,
                lifecycle_level=lifecycle_level,
                lifecycle_factors_summary=lifecycle_summary,
                track_id=track_id,
                track_level=(track_level or None),
                company_id=company_id,
                company_level=(company_level or None),
            )
        )

    return BatchSignalsResponse(items=items)
