from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
import logging

from sqlalchemy import desc, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Company, Product, Registration, RegistrationEvent, SignalScore
from app.services.time_semantics import detect_time_columns, get_registration_start_date, get_registration_start_date_map

DEFAULT_WINDOW = '12m'
DEFAULT_BATCH_SIZE = 500

logger = logging.getLogger(__name__)


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in {'1', 'true', 'yes', 'y'}


def _is_active_status(status: str | None) -> bool:
    s = str(status or '').strip().lower()
    if not s:
        return True
    blocked = {'cancelled', 'canceled', 'expired', 'inactive', '注销', '已注销', '失效', '过期', '作废'}
    return s not in blocked


def _dominant_anchor_by_registration(db: Session) -> dict[str, dict[str, str | None]]:
    rows = db.execute(
        text(
            """
            SELECT DISTINCT ON (p.registration_id)
              p.registration_id::text AS registration_id,
              btrim(p.ivd_category) AS track_id,
              p.company_id::text AS company_id,
              c.country AS country
            FROM products p
            LEFT JOIN companies c ON c.id = p.company_id
            WHERE p.registration_id IS NOT NULL
            ORDER BY p.registration_id, p.updated_at DESC NULLS LAST, p.created_at DESC, p.id
            """
        )
    ).mappings().all()
    out: dict[str, dict[str, str | None]] = {}
    for r in rows:
        rid = str(r.get('registration_id') or '').strip()
        if not rid:
            continue
        track_id = str(r.get('track_id') or '').strip() or None
        company_id = str(r.get('company_id') or '').strip() or None
        country = str(r.get('country') or '').strip() or None
        out[rid] = {'track_id': track_id, 'company_id': company_id, 'country': country}
    return out


def _active_track_counts(db: Session, reg_track_map: dict[str, str]) -> dict[str, int]:
    if not reg_track_map:
        return {}
    reg_ids = list(reg_track_map.keys())
    out: dict[str, int] = {}
    chunk = 1000
    for i in range(0, len(reg_ids), chunk):
        part = reg_ids[i : i + chunk]
        rows = db.execute(
            select(Registration.id, Registration.status).where(Registration.id.in_(part))
        ).all()
        for reg_id, status in rows:
            rid = str(reg_id)
            track = reg_track_map.get(rid)
            if not track:
                continue
            if _is_active_status(status):
                out[track] = int(out.get(track, 0) or 0) + 1
    return out


def _level_score_registration(days_to_expiry: int | None, has_renewal: bool, competition_density: int) -> tuple[str, float]:
    if days_to_expiry is None:
        level = 'medium'
    elif days_to_expiry <= 90:
        level = 'high'
    elif days_to_expiry <= 180:
        level = 'medium'
    else:
        level = 'low'

    if has_renewal and level == 'high':
        level = 'medium'
    elif has_renewal and level == 'medium':
        level = 'low'

    if competition_density >= 300 and level == 'low':
        level = 'medium'
    elif competition_density >= 300 and level == 'medium':
        level = 'high'

    score = {'low': 25.0, 'medium': 55.0, 'high': 85.0}.get(level, 50.0)
    return level, score


def _is_domestic_country(country: str | None) -> bool:
    s = str(country or '').strip().lower()
    if not s:
        return False
    if s == 'cn':
        return True
    return ('china' in s) or ('中国' in s)


def _format_source_distribution(source_counts: dict[str, int]) -> str:
    total = sum(int(v or 0) for v in source_counts.values())
    if total <= 0:
        return 'missing:100%'
    parts: list[str] = []
    for key, cnt in sorted(source_counts.items(), key=lambda x: (-int(x[1] or 0), str(x[0]))):
        pct = (float(cnt) / float(total)) * 100.0
        parts.append(f'{key}:{pct:.1f}%')
    return ', '.join(parts)


def _level_score_track(total_count: int, new_rate_12m: float) -> tuple[str, float]:
    if total_count > 200 or new_rate_12m > 0.5:
        return 'red', 85.0
    if (50 <= total_count <= 200) or (0.2 <= new_rate_12m <= 0.5):
        return 'moderate', 55.0
    return 'blue', 25.0


def _level_score_company(new_regs_12m: int, new_tracks_12m: int) -> tuple[str, float]:
    if new_regs_12m >= 30 or new_tracks_12m >= 3:
        return 'strong', 85.0
    if (10 <= new_regs_12m <= 29) or (1 <= new_tracks_12m <= 2):
        return 'medium_growth', 55.0
    return 'weak', 25.0


def _upsert_signals_bulk(
    db: Session,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        return
    base_stmt = insert(SignalScore).values(rows)
    stmt = base_stmt.on_conflict_do_update(
        constraint='uq_signal_scores_entity_window_date',
        set_={
            'level': base_stmt.excluded.level,
            'score': base_stmt.excluded.score,
            'factors': base_stmt.excluded.factors,
            'computed_at': base_stmt.excluded.computed_at,
        },
    )
    db.execute(stmt)


def _compute_registration_signals(
    db: Session,
    *,
    as_of: date,
    window: str,
    batch_size: int,
    reg_track_map: dict[str, str],
    track_counts: dict[str, int],
) -> int:
    wrote = 0
    cursor: str | None = None
    since_12m = as_of - timedelta(days=365)

    while True:
        stmt = (
            select(
                Registration.id,
                Registration.registration_no,
                Registration.expiry_date,
                Registration.status,
            )
            .order_by(Registration.registration_no.asc())
            .limit(batch_size)
        )
        if cursor:
            stmt = stmt.where(Registration.registration_no > cursor)
        rows = db.execute(stmt).all()
        if not rows:
            break

        reg_ids = [r[0] for r in rows]
        renew_rows = db.execute(
            select(RegistrationEvent.registration_id, func.count(RegistrationEvent.id))
            .where(
                RegistrationEvent.registration_id.in_(reg_ids),
                func.lower(RegistrationEvent.event_type).in_(['renew', 'renewal']),
                RegistrationEvent.event_date >= since_12m,
                RegistrationEvent.event_date <= as_of,
            )
            .group_by(RegistrationEvent.registration_id)
        ).all()
        renew_map = {str(rid): int(cnt or 0) for rid, cnt in renew_rows}
        upsert_rows: list[dict[str, Any]] = []
        computed_at = datetime.now(timezone.utc)

        for reg_id, reg_no, expiry_date, _status in rows:
            rid = str(reg_id)
            days_to_expiry = None
            if expiry_date is not None:
                days_to_expiry = int((expiry_date - as_of).days)
            has_renewal = renew_map.get(rid, 0) > 0
            track_id = reg_track_map.get(rid)
            competition_density = int(track_counts.get(track_id, 0) or 0) if track_id else 0
            level, score = _level_score_registration(days_to_expiry, has_renewal, competition_density)

            factors: list[dict[str, Any]] = [
                {
                    'name': 'days_to_expiry',
                    'value': (days_to_expiry if days_to_expiry is not None else 'unknown'),
                    'unit': 'days',
                    'explanation': '基于 registrations.expiry_date 与 as_of_date 计算。',
                },
                {
                    'name': 'has_renewal_history',
                    'value': bool(has_renewal),
                    'explanation': '基于 registration_events(event_type in renew/renewal) 的近12个月记录。',
                },
                {
                    'name': 'competition_density',
                    'value': competition_density,
                    'explanation': (
                        f'同赛道有效注册证数，赛道来源于 products.ivd_category={track_id}.'
                        if track_id
                        else '缺少赛道锚点（products.ivd_category），按 0 处理。'
                    ),
                },
            ]

            upsert_rows.append(
                {
                    'entity_type': 'registration',
                    'entity_id': str(reg_no),
                    'window': window,
                    'as_of_date': as_of,
                    'level': level,
                    'score': score,
                    'factors': factors,
                    'computed_at': computed_at,
                }
            )
            wrote += 1

        _upsert_signals_bulk(db, upsert_rows)
        cursor = str(rows[-1][1])

    return wrote


def _compute_track_signals(
    db: Session,
    *,
    as_of: date,
    window: str,
    batch_size: int,
    anchor_map: dict[str, dict[str, str | None]],
    start_date_map: dict[str, tuple[date | None, str]],
) -> int:
    wrote = 0
    since_12m = as_of - timedelta(days=365)
    cursor: str | None = None
    track_total: dict[str, int] = {}
    track_new: dict[str, int] = {}
    track_domestic: dict[str, int] = {}
    track_source_stats: dict[str, dict[str, int]] = {}
    track_missing_start: dict[str, int] = {}

    while True:
        stmt = (
            select(
                Registration.id,
                Registration.registration_no,
                Registration.status,
            )
            .order_by(Registration.registration_no.asc())
            .limit(batch_size)
        )
        if cursor:
            stmt = stmt.where(Registration.registration_no > cursor)
        rows = db.execute(stmt).all()
        if not rows:
            break

        for reg_id, reg_no, status in rows:
            rid = str(reg_id)
            meta = anchor_map.get(rid) or {}
            track_id = str(meta.get('track_id') or '').strip()
            if not track_id:
                continue
            if not _is_active_status(status):
                continue
            track_total[track_id] = int(track_total.get(track_id, 0) or 0) + 1
            if _is_domestic_country(meta.get('country')):  # type: ignore[arg-type]
                track_domestic[track_id] = int(track_domestic.get(track_id, 0) or 0) + 1

            reg_no_key = str(reg_no)
            if reg_no_key in start_date_map:
                start_date, source_key = start_date_map.get(reg_no_key, (None, 'missing'))
            else:
                start_date, source_key = get_registration_start_date(db, reg_no_key, as_of)
            source_bucket = track_source_stats.setdefault(track_id, {})
            source_bucket[source_key] = int(source_bucket.get(source_key, 0) or 0) + 1

            if start_date is None:
                track_missing_start[track_id] = int(track_missing_start.get(track_id, 0) or 0) + 1
            elif since_12m <= start_date <= as_of:
                track_new[track_id] = int(track_new.get(track_id, 0) or 0) + 1

        cursor = str(rows[-1][1])

    track_ids = sorted(track_total.keys())
    upsert_rows: list[dict[str, Any]] = []
    computed_at = datetime.now(timezone.utc)
    for track_id in track_ids:
        total_count = int(track_total.get(track_id, 0) or 0)
        new_count_12m = int(track_new.get(track_id, 0) or 0)
        domestic_count = int(track_domestic.get(track_id, 0) or 0)
        source_dist = _format_source_distribution(track_source_stats.get(track_id, {}))
        missing_cnt = int(track_missing_start.get(track_id, 0) or 0)

        new_rate_12m = (float(new_count_12m) / float(total_count)) if total_count > 0 else 0.0
        domestic_ratio = (float(domestic_count) / float(total_count)) if total_count > 0 else 0.0
        level, score = _level_score_track(total_count, new_rate_12m)

        factors = [
            {
                'name': 'total_count',
                'value': total_count,
                'explanation': '该赛道下有效注册证数量（赛道来源 products.ivd_category）。',
            },
            {
                'name': 'new_rate_12m',
                'value': round(new_rate_12m, 4),
                'explanation': (
                    '近12个月新增注册证 / 当前有效总数，新增以统一 start_date 口径计算。'
                    f' source_dist=[{source_dist}] missing_start_date={missing_cnt}'
                ),
            },
            {
                'name': 'domestic_ratio',
                'value': round(domestic_ratio, 4),
                'explanation': '公司国家字段中中国/CN 占比（基于 companies.country 近似）。',
            },
        ]

        upsert_rows.append(
            {
                'entity_type': 'track',
                'entity_id': track_id,
                'window': window,
                'as_of_date': as_of,
                'level': level,
                'score': score,
                'factors': factors,
                'computed_at': computed_at,
            }
        )
        wrote += 1
        if len(upsert_rows) >= batch_size:
            _upsert_signals_bulk(db, upsert_rows)
            upsert_rows = []
    _upsert_signals_bulk(db, upsert_rows)

    return wrote


def _compute_company_signals(
    db: Session,
    *,
    as_of: date,
    window: str,
    batch_size: int,
    anchor_map: dict[str, dict[str, str | None]],
    start_date_map: dict[str, tuple[date | None, str]],
) -> int:
    wrote = 0
    since_12m = as_of - timedelta(days=365)
    company_new_regs: dict[str, int] = {}
    company_new_tracks: dict[str, set[str]] = {}
    company_source_stats: dict[str, dict[str, int]] = {}
    company_missing_start: dict[str, int] = {}

    reg_cursor: str | None = None
    while True:
        stmt = (
            select(
                Registration.id,
                Registration.registration_no,
            )
            .order_by(Registration.registration_no.asc())
            .limit(batch_size)
        )
        if reg_cursor:
            stmt = stmt.where(Registration.registration_no > reg_cursor)
        rows = db.execute(stmt).all()
        if not rows:
            break

        for reg_id, reg_no in rows:
            rid = str(reg_id)
            meta = anchor_map.get(rid) or {}
            company_id = str(meta.get('company_id') or '').strip()
            if not company_id:
                continue
            source_bucket = company_source_stats.setdefault(company_id, {})
            reg_no_key = str(reg_no)
            if reg_no_key in start_date_map:
                start_date, source_key = start_date_map.get(reg_no_key, (None, 'missing'))
            else:
                start_date, source_key = get_registration_start_date(db, reg_no_key, as_of)
            source_bucket[source_key] = int(source_bucket.get(source_key, 0) or 0) + 1
            if start_date is None:
                company_missing_start[company_id] = int(company_missing_start.get(company_id, 0) or 0) + 1
                continue
            if since_12m <= start_date <= as_of:
                company_new_regs[company_id] = int(company_new_regs.get(company_id, 0) or 0) + 1
                track_id = str(meta.get('track_id') or '').strip()
                if track_id:
                    company_new_tracks.setdefault(company_id, set()).add(track_id)
        reg_cursor = str(rows[-1][1])

    cancel_rows = db.execute(
        select(RegistrationEvent.registration_id)
        .where(
            func.lower(RegistrationEvent.event_type).in_(['cancel', 'cancelled', 'canceled', '注销']),
            RegistrationEvent.event_date >= since_12m,
            RegistrationEvent.event_date <= as_of,
        )
        .distinct()
    ).all()
    company_cancel_count: dict[str, int] = {}
    for (reg_id,) in cancel_rows:
        rid = str(reg_id)
        meta = anchor_map.get(rid) or {}
        company_id = str(meta.get('company_id') or '').strip()
        if not company_id:
            continue
        company_cancel_count[company_id] = int(company_cancel_count.get(company_id, 0) or 0) + 1

    company_cursor: str | None = None
    while True:
        stmt = select(Company.id).order_by(Company.id.asc()).limit(batch_size)
        if company_cursor:
            stmt = stmt.where(Company.id > company_cursor)
        rows = db.execute(stmt).all()
        if not rows:
            break
        company_ids = [str(r[0]) for r in rows]

        upsert_rows: list[dict[str, Any]] = []
        computed_at = datetime.now(timezone.utc)

        for cid in company_ids:
            new_regs_12m = int(company_new_regs.get(cid, 0) or 0)
            new_tracks_12m = int(len(company_new_tracks.get(cid, set())))
            cancel_count_12m = int(company_cancel_count.get(cid, 0) or 0)
            source_dist = _format_source_distribution(company_source_stats.get(cid, {}))
            missing_cnt = int(company_missing_start.get(cid, 0) or 0)
            growth_slope = round((new_regs_12m - cancel_count_12m) / 12.0, 4)
            level, score = _level_score_company(new_regs_12m, new_tracks_12m)

            factors = [
                {
                    'name': 'new_registrations_12m',
                    'value': new_regs_12m,
                    'explanation': (
                        '近12个月新增注册证数（统一 start_date 口径）。'
                        f' source_dist=[{source_dist}] missing_start_date={missing_cnt}'
                    ),
                },
                {
                    'name': 'new_tracks_12m',
                    'value': new_tracks_12m,
                    'explanation': '近12个月新增进入赛道数（distinct products.ivd_category；时间口径同 start_date）。',
                },
                {
                    'name': 'growth_slope',
                    'value': growth_slope,
                    'explanation': '用 (近12月新增 - 近12月注销) / 12 近似月度线性斜率。',
                },
            ]

            upsert_rows.append(
                {
                    'entity_type': 'company',
                    'entity_id': cid,
                    'window': window,
                    'as_of_date': as_of,
                    'level': level,
                    'score': score,
                    'factors': factors,
                    'computed_at': computed_at,
                }
            )
            wrote += 1

        _upsert_signals_bulk(db, upsert_rows)
        company_cursor = company_ids[-1]

    return wrote


@dataclass
class SignalsComputeResult:
    ok: bool
    window: str
    as_of: str
    dry_run: bool
    batch_size: int
    registration_count: int
    track_count: int
    company_count: int
    wrote_total: int
    error: str | None = None


def compute_signals_v1(
    db: Session,
    *,
    as_of: date | None = None,
    window: str = DEFAULT_WINDOW,
    dry_run: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> SignalsComputeResult:
    target = as_of or _today_utc()
    if window != DEFAULT_WINDOW:
        raise ValueError(f'Unsupported window: {window}. only {DEFAULT_WINDOW} is implemented in MVP.')

    time_columns = detect_time_columns(db.get_bind())
    logger.warning('Time semantics columns: %s', {k: sorted(list(v)) for k, v in time_columns.items()})
    start_date_map, start_source_stats = get_registration_start_date_map(
        db,
        as_of_date=target,
        registration_nos=None,
        columns_map=time_columns,
    )
    logger.warning('Time semantics source distribution: %s', start_source_stats)

    anchor_map = _dominant_anchor_by_registration(db)
    reg_track_map = {
        rid: str(meta.get('track_id'))
        for rid, meta in anchor_map.items()
        if meta.get('track_id') is not None and str(meta.get('track_id')).strip()
    }
    track_counts = _active_track_counts(db, reg_track_map)

    reg_count = _compute_registration_signals(
        db,
        as_of=target,
        window=window,
        batch_size=batch_size,
        reg_track_map=reg_track_map,
        track_counts=track_counts,
    )
    track_count = _compute_track_signals(
        db,
        as_of=target,
        window=window,
        batch_size=batch_size,
        anchor_map=anchor_map,
        start_date_map=start_date_map,
    )
    company_count = _compute_company_signals(
        db,
        as_of=target,
        window=window,
        batch_size=batch_size,
        anchor_map=anchor_map,
        start_date_map=start_date_map,
    )

    wrote_total = int(reg_count + track_count + company_count)
    if dry_run:
        db.rollback()
        wrote_total = 0
    else:
        db.commit()

    return SignalsComputeResult(
        ok=True,
        window=window,
        as_of=target.isoformat(),
        dry_run=bool(dry_run),
        batch_size=int(batch_size),
        registration_count=int(reg_count),
        track_count=int(track_count),
        company_count=int(company_count),
        wrote_total=int(wrote_total),
    )
