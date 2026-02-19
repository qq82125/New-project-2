from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

TIME_TABLES = ('registrations', 'nmpa_snapshots', 'registration_events', 'products')

REG_APPROVAL_CANDIDATES = ('approved_at', 'approval_date', 'approved_date')
REG_CREATED_CANDIDATES = ('created_at',)
SNAPSHOT_TIME_CANDIDATES = ('snapshot_date', 'snapshot_at', 'observed_at', 'created_at')
EVENT_TIME_CANDIDATES = ('event_date', 'observed_at', 'created_at')
EVENT_TYPE_CANDIDATES = ('event_type',)
PRODUCT_APPROVAL_CANDIDATES = ('approved_at', 'approved_date')
PRODUCT_REG_LINK_CANDIDATES = ('registration_id', 'registration_no', 'reg_no')


def month_bucket(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        value = value.date()
    return f'{value.year:04d}-{value.month:02d}'


def detect_time_columns(engine) -> dict[str, set[str]]:
    insp = inspect(engine)
    table_names = set(insp.get_table_names())
    out: dict[str, set[str]] = {}
    for table in TIME_TABLES:
        if table not in table_names:
            out[table] = set()
            continue
        cols = {str(col.get('name')) for col in insp.get_columns(table)}
        out[table] = cols
    return out


def _pick_first_existing(columns: set[str], candidates: tuple[str, ...]) -> str | None:
    for c in candidates:
        if c in columns:
            return c
    return None


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def _build_start_date_query(
    *,
    columns_map: dict[str, set[str]],
    registration_nos: list[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    reg_cols = columns_map.get('registrations') or set()
    reg_approval_col = _pick_first_existing(reg_cols, REG_APPROVAL_CANDIDATES)
    reg_created_col = _pick_first_existing(reg_cols, REG_CREATED_CANDIDATES)

    snap_cols = columns_map.get('nmpa_snapshots') or set()
    snap_date_col = _pick_first_existing(snap_cols, SNAPSHOT_TIME_CANDIDATES)
    has_snap_reg_id = 'registration_id' in snap_cols

    evt_cols = columns_map.get('registration_events') or set()
    evt_date_col = _pick_first_existing(evt_cols, EVENT_TIME_CANDIDATES)
    evt_type_col = _pick_first_existing(evt_cols, EVENT_TYPE_CANDIDATES)
    has_evt_reg_id = 'registration_id' in evt_cols

    prod_cols = columns_map.get('products') or set()
    prod_date_col = _pick_first_existing(prod_cols, PRODUCT_APPROVAL_CANDIDATES)
    prod_link_col = _pick_first_existing(prod_cols, PRODUCT_REG_LINK_CANDIDATES)

    approval_expr = f"(r.{reg_approval_col})::date" if reg_approval_col else 'NULL::date'
    created_expr = f"(r.{reg_created_col})::date" if reg_created_col else 'NULL::date'

    snap_join = ''
    if snap_date_col and has_snap_reg_id:
        snap_join = f"""
        LEFT JOIN (
          SELECT s.registration_id::text AS registration_id, MIN((s.{snap_date_col})::date) AS dt
          FROM nmpa_snapshots s
          WHERE (s.{snap_date_col})::date <= :as_of_date
          GROUP BY s.registration_id
        ) snap ON snap.registration_id = r.id::text
        """

    evt_join = ''
    if evt_date_col and has_evt_reg_id:
        evt_filter = ''
        if evt_type_col:
            evt_filter = (
                f" AND lower(coalesce(e.{evt_type_col}, '')) IN "
                "('create','created','issue','issued','approve','approved','grant','granted')"
            )
        evt_join = f"""
        LEFT JOIN (
          SELECT e.registration_id::text AS registration_id, MIN((e.{evt_date_col})::date) AS dt
          FROM registration_events e
          WHERE (e.{evt_date_col})::date <= :as_of_date
          {evt_filter}
          GROUP BY e.registration_id
        ) evt ON evt.registration_id = r.id::text
        """

    prod_join = ''
    if prod_date_col and prod_link_col:
        if prod_link_col == 'registration_id':
            prod_join = f"""
            LEFT JOIN (
              SELECT p.registration_id::text AS registration_id, MIN((p.{prod_date_col})::date) AS dt
              FROM products p
              WHERE p.registration_id IS NOT NULL AND (p.{prod_date_col})::date <= :as_of_date
              GROUP BY p.registration_id
            ) prod ON prod.registration_id = r.id::text
            """
        else:
            prod_join = f"""
            LEFT JOIN (
              SELECT p.{prod_link_col}::text AS registration_no, MIN((p.{prod_date_col})::date) AS dt
              FROM products p
              WHERE p.{prod_link_col} IS NOT NULL AND (p.{prod_date_col})::date <= :as_of_date
              GROUP BY p.{prod_link_col}
            ) prod ON prod.registration_no = r.registration_no
            """

    where_clause = ''
    params: dict[str, Any] = {}
    if registration_nos:
        where_clause = 'WHERE r.registration_no = ANY(:registration_nos)'
        params['registration_nos'] = registration_nos

    sql = f"""
    SELECT
      r.registration_no::text AS registration_no,
      {approval_expr} AS reg_approval_date,
      {"snap.dt" if snap_join else "NULL::date"} AS snapshot_first_date,
      {"evt.dt" if evt_join else "NULL::date"} AS event_first_date,
      {"prod.dt" if prod_join else "NULL::date"} AS product_first_date,
      {created_expr} AS reg_created_date
    FROM registrations r
    {snap_join}
    {evt_join}
    {prod_join}
    {where_clause}
    """
    return sql, params


def get_registration_start_date_map(
    db: Session,
    *,
    as_of_date: date,
    registration_nos: list[str] | None = None,
    columns_map: dict[str, set[str]] | None = None,
) -> tuple[dict[str, tuple[date | None, str]], dict[str, int]]:
    cols = columns_map or detect_time_columns(db.get_bind())
    sql, params = _build_start_date_query(columns_map=cols, registration_nos=registration_nos)
    params['as_of_date'] = as_of_date
    rows = db.execute(text(sql), params).mappings().all()

    result: dict[str, tuple[date | None, str]] = {}
    source_stats: dict[str, int] = defaultdict(int)
    for row in rows:
        reg_no = str(row.get('registration_no') or '').strip()
        if not reg_no:
            continue
        approval_dt = _to_date(row.get('reg_approval_date'))
        snapshot_dt = _to_date(row.get('snapshot_first_date'))
        event_dt = _to_date(row.get('event_first_date'))
        product_dt = _to_date(row.get('product_first_date'))
        created_dt = _to_date(row.get('reg_created_date'))

        chosen_date: date | None = None
        source_key = 'missing'
        if approval_dt is not None:
            chosen_date = approval_dt
            source_key = 'registrations.approval_date'
        elif snapshot_dt is not None:
            chosen_date = snapshot_dt
            source_key = 'nmpa_snapshots.first_observed'
        elif event_dt is not None:
            chosen_date = event_dt
            source_key = 'registration_events.first_create_issue_approve'
        elif product_dt is not None:
            chosen_date = product_dt
            source_key = 'products.approved_date'
        elif created_dt is not None:
            chosen_date = created_dt
            source_key = 'registrations.created_at'

        if chosen_date is not None and chosen_date > as_of_date:
            chosen_date = None
            source_key = 'missing'

        result[reg_no] = (chosen_date, source_key)
        source_stats[source_key] = int(source_stats.get(source_key, 0) or 0) + 1
    return result, dict(source_stats)


def get_registration_start_date(
    db: Session,
    registration_no: str,
    as_of_date: date,
    *,
    columns_map: dict[str, set[str]] | None = None,
) -> tuple[date | None, str]:
    reg_no = str(registration_no or '').strip()
    if not reg_no:
        return None, 'missing'
    data, _stats = get_registration_start_date_map(
        db,
        as_of_date=as_of_date,
        registration_nos=[reg_no],
        columns_map=columns_map,
    )
    return data.get(reg_no, (None, 'missing'))


def audit_time_semantics(
    db: Session,
    *,
    as_of_date: date,
    limit: int = 200,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 200), 5000))
    rows = db.execute(
        text(
            """
            SELECT r.registration_no::text AS registration_no
            FROM registrations r
            ORDER BY r.registration_no ASC
            LIMIT :limit
            """
        ),
        {'limit': limit},
    ).mappings().all()
    registration_nos = [str(r.get('registration_no') or '').strip() for r in rows if r.get('registration_no')]
    cols = detect_time_columns(db.get_bind())
    mapped, source_stats = get_registration_start_date_map(
        db,
        as_of_date=as_of_date,
        registration_nos=registration_nos,
        columns_map=cols,
    )

    hit = 0
    missing_samples: list[str] = []
    sample_rows: list[dict[str, Any]] = []
    for no in registration_nos[:10]:
        d, s = mapped.get(no, (None, 'missing'))
        sample_rows.append({'registration_no': no, 'start_date': (d.isoformat() if d else None), 'source_key': s})
    for no in registration_nos:
        d, _s = mapped.get(no, (None, 'missing'))
        if d is not None:
            hit += 1
        elif len(missing_samples) < 20:
            missing_samples.append(no)

    total = len(registration_nos)
    hit_rate = (float(hit) / float(total)) if total > 0 else 0.0
    return {
        'as_of_date': as_of_date.isoformat(),
        'limit': total,
        'hit_count': hit,
        'missing_count': int(total - hit),
        'hit_rate': round(hit_rate, 4),
        'source_stats': source_stats,
        'missing_samples': missing_samples,
        'sample_rows': sample_rows,
        'time_columns': {k: sorted(list(v)) for k, v in cols.items()},
    }
