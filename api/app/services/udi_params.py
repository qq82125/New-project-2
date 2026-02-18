from __future__ import annotations

import json
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import AdminConfig, ParamDictionaryCandidate, ProductParam, UdiJobCheckpoint


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _to_dt(v: Any) -> datetime:
    if isinstance(v, datetime):
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
    if isinstance(v, str):
        try:
            # tolerate trailing Z
            parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            pass
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _get_allowlist(db: Session) -> list[str]:
    cfg = db.scalar(select(AdminConfig).where(AdminConfig.config_key == "udi_params_allowlist"))
    if cfg and isinstance(cfg.config_value, dict):
        al = cfg.config_value.get("allowlist")
        if isinstance(al, list):
            out = []
            for x in al:
                s = str(x or "").strip()
                if s:
                    out.append(s)
            if out:
                return out
    return [
        "STORAGE",
        "STERILIZATION_METHOD",
        "SPECIAL_STORAGE_COND",
        "SPECIAL_STORAGE_NOTE",
        "LABEL_SERIAL_NO",
        "LABEL_PROD_DATE",
        "LABEL_EXP_DATE",
        "LABEL_LOT",
    ]


def _is_non_empty(value: Any, data_type: str) -> bool:
    dt = (data_type or "").lower()
    if value is None:
        return False
    if "json" in dt:
        if isinstance(value, (list, dict)):
            return len(value) > 0
        s = str(value).strip()
        return s not in {"", "[]", "{}", "null", "None"}
    if "char" in dt or "text" in dt:
        return bool(str(value).strip())
    return True


def _storage_summary(storages: list[dict[str, Any]]) -> str | None:
    if not storages:
        return None
    ranges: list[str] = []
    for s in storages[:100]:
        if not isinstance(s, dict):
            continue
        r = _as_text(s.get("range"))
        if r:
            ranges.append(r)
            continue
        t = _as_text(s.get("type"))
        mn = _as_text(s.get("min"))
        mx = _as_text(s.get("max"))
        unit = _as_text(s.get("unit")) or ""
        if mn and mx:
            ranges.append(f"{mn}~{mx}{unit}")
        elif mn:
            ranges.append(f">={mn}{unit}")
        elif mx:
            ranges.append(f"<={mx}{unit}")
        elif t:
            ranges.append(t)
    uniq = []
    seen = set()
    for x in ranges:
        if x in seen:
            continue
        uniq.append(x)
        seen.add(x)
        if len(uniq) >= 10:
            break
    return "; ".join(uniq) if uniq else None


def _normalize_storages(v: Any) -> list[dict[str, Any]]:
    src = v
    if isinstance(v, dict):
        src = v.get("storages")
    if not isinstance(src, list):
        return []
    out: list[dict[str, Any]] = []
    for item in src:
        if not isinstance(item, dict):
            continue
        t = _as_text(item.get("type"))
        rng = _as_text(item.get("range"))
        mn = item.get("min")
        mx = item.get("max")
        unit = _as_text(item.get("unit"))
        if t is None and rng is None and mn is None and mx is None and unit is None:
            continue
        out.append(
            {
                "type": t,
                "min": (float(mn) if isinstance(mn, (int, float, Decimal)) else None),
                "max": (float(mx) if isinstance(mx, (int, float, Decimal)) else None),
                "unit": unit,
                "range": rng,
            }
        )
    return out


def _checkpoint_get(db: Session, job_name: str) -> str | None:
    row = db.get(UdiJobCheckpoint, job_name)
    if row is None:
        return None
    cur = str(row.cursor or "").strip()
    return cur or None


def _checkpoint_set(db: Session, *, job_name: str, cursor: str, meta: dict[str, Any] | None = None) -> None:
    stmt = insert(UdiJobCheckpoint).values(job_name=job_name, cursor=cursor, meta=(meta or {}), updated_at=_utcnow())
    stmt = stmt.on_conflict_do_update(
        index_elements=[UdiJobCheckpoint.job_name],
        set_={
            "cursor": stmt.excluded.cursor,
            "meta": stmt.excluded.meta,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    db.execute(stmt)


def _ensure_raw_document_for_run(db: Session, source_run_id: int) -> UUID:
    run_id = str(int(source_run_id))
    sha = hashlib.sha256(f"udi_params_allowlist_v1:{run_id}".encode("utf-8")).hexdigest()
    existing = db.execute(
        text(
            """
            SELECT id
            FROM raw_documents
            WHERE source = 'UDI_PARAMS'
              AND run_id = :run_id
              AND sha256 = :sha
            LIMIT 1
            """
        ),
        {"run_id": run_id, "sha": sha},
    ).scalar()
    if existing:
        return UUID(str(existing))
    new_id = db.execute(
        text(
            """
            INSERT INTO raw_documents (source, source_url, doc_type, storage_uri, sha256, fetched_at, run_id, parse_status, parse_log)
            VALUES ('UDI_PARAMS', NULL, 'JSON', :uri, :sha, NOW(), :run_id, 'PARSED', CAST(:log AS jsonb))
            ON CONFLICT (source, run_id, sha256)
            DO UPDATE SET fetched_at = EXCLUDED.fetched_at
            RETURNING id
            """
        ),
        {
            "uri": f"db://udi_params/{run_id}",
            "sha": sha,
            "run_id": run_id,
            "log": json.dumps({"job": "udi:params", "extract_version": "udi_params_allowlist_v1"}, ensure_ascii=False),
        },
    ).scalar_one()
    return UUID(str(new_id))


@dataclass
class UdiParamsBatchProgress:
    batch_no: int
    cursor: str
    rows_scanned: int
    rows_written: int
    distinct_products: int
    elapsed_ms: int

    @property
    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_no": self.batch_no,
            "cursor": self.cursor,
            "rows_scanned": self.rows_scanned,
            "rows_written": self.rows_written,
            "distinct_products": self.distinct_products,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass
class UdiParamsReport:
    scanned: int = 0
    candidates_written: int = 0
    bound_products: int = 0
    params_written: int = 0
    skipped_unbound_product: int = 0
    skipped_not_allowlisted: int = 0
    skipped_missing_value: int = 0
    failed: int = 0
    errors: list[dict[str, Any]] | None = None
    total_batches: int = 0
    final_cursor: str | None = None
    distinct_products_updated: int = 0
    storage_present_count: int = 0
    storage_non_empty_count: int = 0

    @property
    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "candidates_written": self.candidates_written,
            "bound_products": self.bound_products,
            "params_written": self.params_written,
            "skipped_unbound_product": self.skipped_unbound_product,
            "skipped_not_allowlisted": self.skipped_not_allowlisted,
            "skipped_missing_value": self.skipped_missing_value,
            "failed": self.failed,
            "errors": self.errors or [],
            "total_batches": self.total_batches,
            "final_cursor": self.final_cursor,
            "total_written": self.params_written,
            "distinct_products_updated": self.distinct_products_updated,
            "storage_present_count": self.storage_present_count,
            "storage_non_empty_count": self.storage_non_empty_count,
        }


def compute_udi_candidates_sample(
    db: Session,
    *,
    source: str = "UDI",
    source_run_id: int | None = None,
    top: int = 50,
    sample_limit: int = 200000,
    start_cursor: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cols = db.execute(
        text(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='udi_device_index'
            ORDER BY ordinal_position
            """
        )
    ).fetchall()
    fields: list[tuple[str, str]] = []
    for col_name, data_type in cols:
        col = str(col_name)
        if col in {"id", "created_at", "updated_at"}:
            continue
        fields.append((col, str(data_type)))

    if not fields:
        return [], {"sampled_rows": 0, "sample_limit": sample_limit}

    selected = ", ".join([f for f, _ in fields])
    where = ["di_norm IS NOT NULL", "btrim(di_norm) <> ''"]
    params: dict[str, Any] = {"lim": int(sample_limit)}
    if source_run_id is not None:
        where.append("source_run_id = :srid")
        params["srid"] = int(source_run_id)
    if start_cursor:
        where.append("di_norm > :cursor")
        params["cursor"] = str(start_cursor)

    sample_sql = f"""
        SELECT {selected}
        FROM udi_device_index
        WHERE {' AND '.join(where)}
        ORDER BY di_norm
        LIMIT :lim
    """
    rows = db.execute(text(sample_sql), params).mappings().all()
    sampled_rows = len(rows)

    sample_storage_present_rows = 0
    sample_packing_present_rows = 0

    counts_non_empty: dict[str, int] = {f: 0 for f, _ in fields}
    samples: dict[str, list[str]] = {f: [] for f, _ in fields}
    seen: dict[str, set[str]] = {f: set() for f, _ in fields}

    for row in rows:
        if row.get("storage_json") is not None and str(row.get("storage_json")) not in {"[]", "{}", ""}:
            sample_storage_present_rows += 1
        if row.get("packing_json") is not None and str(row.get("packing_json")) not in {"[]", "{}", ""}:
            sample_packing_present_rows += 1
        for f, dt in fields:
            val = row.get(f)
            if not _is_non_empty(val, dt):
                continue
            counts_non_empty[f] += 1
            if len(samples[f]) >= 10:
                continue
            if isinstance(val, (dict, list)):
                sval = json.dumps(val, ensure_ascii=False)
            else:
                sval = str(val).strip()
            if not sval:
                continue
            if sval in seen[f]:
                continue
            seen[f].add(sval)
            samples[f].append(sval)

    out: list[dict[str, Any]] = []
    denom = sampled_rows if sampled_rows > 0 else 1
    for f, _dt in fields:
        non_empty = int(counts_non_empty.get(f) or 0)
        out.append(
            {
                "source": source,
                "xml_tag": f,
                "count_total": sampled_rows,
                "count_non_empty": non_empty,
                "empty_rate": round(float(sampled_rows - non_empty) / float(denom), 6),
                "sample_values": samples.get(f) or [],
                "sample_meta": {
                    "mode": "sample",
                    "sample_limit": int(sample_limit),
                    "sampled_rows": sampled_rows,
                    "sample_storage_present_rows": sample_storage_present_rows,
                    "sample_packing_present_rows": sample_packing_present_rows,
                    "source_run_id": source_run_id,
                    "start_cursor": start_cursor,
                },
                "source_run_id": (int(source_run_id) if source_run_id is not None else None),
            }
        )

    topn = max(1, int(top or 50))
    out_sorted = sorted(out, key=lambda x: int(x.get("count_non_empty") or 0), reverse=True)
    return out_sorted[:topn], {
        "mode": "sample",
        "sample_limit": int(sample_limit),
        "sampled_rows": sampled_rows,
        "sample_storage_present_rows": sample_storage_present_rows,
        "sample_packing_present_rows": sample_packing_present_rows,
    }


def compute_udi_candidates_full(
    db: Session,
    *,
    source: str = "UDI",
    source_run_id: int | None = None,
    top: int = 50,
    sample_rows: int = 20000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params: dict[str, Any] = {}
    where = "WHERE 1=1"
    if source_run_id is not None:
        where += " AND source_run_id = :srid"
        params["srid"] = int(source_run_id)

    total = int(db.execute(text(f"SELECT COUNT(1) FROM udi_device_index {where}"), params).scalar() or 0)

    cols = db.execute(
        text(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='udi_device_index'
            ORDER BY ordinal_position
            """
        )
    ).fetchall()

    candidates: list[tuple[str, str]] = []
    for (col_name, data_type) in cols:
        col = str(col_name)
        dt = str(data_type)
        if col in {"id", "created_at", "updated_at"}:
            continue
        candidates.append((col, dt))

    if not candidates:
        return [], {"mode": "full", "count_total": total}

    agg_exprs: list[str] = []
    for col, dt in candidates:
        if "json" in dt.lower():
            pred = f"{col} IS NOT NULL AND {col}::text <> '[]'"
        elif "char" in dt.lower() or "text" in dt.lower():
            pred = f"{col} IS NOT NULL AND btrim({col}) <> ''"
        else:
            pred = f"{col} IS NOT NULL"
        agg_exprs.append(f"COUNT(1) FILTER (WHERE {pred}) AS ne__{col}")

    agg_sql = f"SELECT {', '.join(agg_exprs)} FROM udi_device_index {where}"
    agg_row = db.execute(text(agg_sql), params).mappings().first() or {}

    global_storage_present_rows = int(
        db.execute(text(f"SELECT COUNT(1) FROM udi_device_index {where} AND storage_json IS NOT NULL AND storage_json::text <> '[]'"), params).scalar()
        or 0
    )
    global_packing_present_rows = int(
        db.execute(text(f"SELECT COUNT(1) FROM udi_device_index {where} AND packing_json IS NOT NULL AND packing_json::text <> '[]'"), params).scalar()
        or 0
    )

    out: list[dict[str, Any]] = []
    for col, _dt in candidates:
        non_empty = int(agg_row.get(f"ne__{col}") or 0)
        empty_rate = 0.0 if total <= 0 else round(float(total - non_empty) / float(total), 6)
        out.append(
            {
                "source": source,
                "xml_tag": col,
                "count_total": total,
                "count_non_empty": non_empty,
                "empty_rate": empty_rate,
                "sample_values": [],
                "sample_meta": {
                    "mode": "full",
                    "sample_rows": int(sample_rows),
                    "global_storage_present_rows": global_storage_present_rows,
                    "global_packing_present_rows": global_packing_present_rows,
                    "source_run_id": source_run_id,
                },
                "source_run_id": (int(source_run_id) if source_run_id is not None else None),
            }
        )

    topn = max(1, int(top or 50))
    sample_n = max(100, int(sample_rows or 20000))
    top_fields = [str(x["xml_tag"]) for x in sorted(out, key=lambda x: int(x.get("count_non_empty") or 0), reverse=True)[:topn]]
    sample_storage_present_rows = 0
    sample_packing_present_rows = 0
    if top_fields:
        sample_cols = list(top_fields)
        for fixed_col in ("storage_json", "packing_json"):
            if fixed_col not in sample_cols:
                sample_cols.append(fixed_col)
        sample_sql = f"SELECT {', '.join(sample_cols)} FROM udi_device_index {where} LIMIT :srows"
        sample_params = dict(params)
        sample_params["srows"] = sample_n
        sample_data = db.execute(text(sample_sql), sample_params).mappings().all()
        sampled_rows = len(sample_data)
        sample_map: dict[str, list[str]] = {f: [] for f in top_fields}
        seen_map: dict[str, set[str]] = {f: set() for f in top_fields}
        for row in sample_data:
            if row.get("storage_json") is not None and str(row.get("storage_json")) not in {"[]", "{}", ""}:
                sample_storage_present_rows += 1
            if row.get("packing_json") is not None and str(row.get("packing_json")) not in {"[]", "{}", ""}:
                sample_packing_present_rows += 1
            for f in top_fields:
                val = row.get(f)
                if val is None:
                    continue
                sval = json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else str(val).strip()
                if not sval or sval in seen_map[f]:
                    continue
                seen_map[f].add(sval)
                if len(sample_map[f]) < 10:
                    sample_map[f].append(sval)
        for item in out:
            field = str(item["xml_tag"])
            if field in sample_map:
                item["sample_values"] = sample_map[field]
            if isinstance(item.get("sample_meta"), dict):
                item["sample_meta"]["sampled_rows"] = sampled_rows
                item["sample_meta"]["sample_storage_present_rows"] = sample_storage_present_rows
                item["sample_meta"]["sample_packing_present_rows"] = sample_packing_present_rows

    out_sorted = sorted(out, key=lambda x: int(x.get("count_non_empty") or 0), reverse=True)
    return out_sorted[:topn], {
        "mode": "full",
        "count_total": total,
        "global_storage_present_rows": global_storage_present_rows,
        "global_packing_present_rows": global_packing_present_rows,
        "sampled_rows": sampled_rows if 'sampled_rows' in locals() else 0,
        "sample_storage_present_rows": sample_storage_present_rows,
        "sample_packing_present_rows": sample_packing_present_rows,
    }


def upsert_candidates(
    db: Session,
    *,
    rows: list[dict[str, Any]],
) -> int:
    wrote = 0
    for r in rows:
        stmt = insert(ParamDictionaryCandidate).values(
            source=str(r["source"]),
            xml_tag=str(r["xml_tag"]),
            count_total=int(r["count_total"] or 0),
            count_non_empty=int(r["count_non_empty"] or 0),
            empty_rate=float(r["empty_rate"] or 0),
            sample_values={"values": list(r.get("sample_values") or [])},
            sample_meta=(r.get("sample_meta") if isinstance(r.get("sample_meta"), dict) else None),
            source_run_id=(int(r["source_run_id"]) if r.get("source_run_id") is not None else None),
            observed_at=_utcnow(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ParamDictionaryCandidate.source, ParamDictionaryCandidate.xml_tag, ParamDictionaryCandidate.source_run_id],
            set_={
                "count_total": stmt.excluded.count_total,
                "count_non_empty": stmt.excluded.count_non_empty,
                "empty_rate": stmt.excluded.empty_rate,
                "sample_values": stmt.excluded.sample_values,
                "sample_meta": stmt.excluded.sample_meta,
                "observed_at": stmt.excluded.observed_at,
            },
        )
        db.execute(stmt)
        wrote += 1
    return wrote


def write_allowlisted_params(
    db: Session,
    *,
    source_run_id: int | None,
    limit: int | None,
    only_allowlisted: bool,
    dry_run: bool,
    batch_size: int = 50000,
    resume: bool = True,
    start_cursor: str | None = None,
    job_name: str = "udi:params:allowlist",
    progress_cb: Callable[[UdiParamsBatchProgress], None] | None = None,
) -> UdiParamsReport:
    rep = UdiParamsReport(errors=[])
    allow = set(_get_allowlist(db)) if only_allowlisted else set()
    batch_size = max(1000, int(batch_size or 50000))

    effective_job_name = job_name
    if source_run_id is not None:
        effective_job_name = f"{job_name}:srid:{int(source_run_id)}"

    cursor = (str(start_cursor).strip() if start_cursor else None)
    if cursor is None and resume:
        cursor = _checkpoint_get(db, effective_job_name)

    total_limit = int(limit) if isinstance(limit, int) and limit > 0 else None
    scanned_total = 0
    batch_no = 0
    product_ids_touched: set[str] = set()
    fallback_raw_by_run: dict[int, UUID] = {}

    select_sql_base = """
    SELECT
      u.di_norm,
      u.registration_no_norm,
      u.device_record_key,
      u.storage_json,
      u.mjfs,
      u.tscchcztj,
      u.tsccsm,
      u.scbssfbhxlh,
      u.scbssfbhscrq,
      u.scbssfbhsxrq,
      u.scbssfbhph,
      u.version_number,
      u.version_time,
      u.version_status,
      u.raw_document_id,
      u.source_run_id,
      u.updated_at,
      p.id AS product_id
    FROM udi_device_index u
    JOIN registrations r ON r.registration_no = u.registration_no_norm
    JOIN products p ON p.registration_id = r.id AND p.is_ivd = true
    WHERE u.di_norm IS NOT NULL
      AND btrim(u.di_norm) <> ''
    """

    def _to_uuid(v: Any) -> UUID | None:
        try:
            return UUID(str(v)) if v else None
        except Exception:
            return None

    source_run_started_at: dict[int, datetime] = {}

    def _get_source_run_started_at(srid: int | None) -> datetime | None:
        if srid is None:
            return None
        if srid in source_run_started_at:
            return source_run_started_at[srid]
        started = db.execute(text("SELECT started_at FROM source_runs WHERE id = :id"), {"id": int(srid)}).scalar()
        dt = _to_dt(started) if started is not None else None
        if dt is not None:
            source_run_started_at[srid] = dt
        return dt

    while True:
        if total_limit is not None and scanned_total >= total_limit:
            break
        current_lim = batch_size
        if total_limit is not None:
            current_lim = min(current_lim, total_limit - scanned_total)
        if current_lim <= 0:
            break

        where_extra: list[str] = []
        params: dict[str, Any] = {"lim": int(current_lim)}
        if cursor:
            where_extra.append("u.di_norm > :cursor")
            params["cursor"] = cursor
        if source_run_id is not None:
            where_extra.append("u.source_run_id = :srid")
            params["srid"] = int(source_run_id)
        sql = select_sql_base
        if where_extra:
            sql = sql + " AND " + " AND ".join(where_extra)
        sql = sql + " ORDER BY u.di_norm LIMIT :lim"

        rows = db.execute(text(sql), params).mappings().all()
        if not rows:
            break

        t0 = time.perf_counter()
        batch_no += 1
        rep.scanned += len(rows)
        scanned_total += len(rows)
        rep.bound_products += len(rows)

        # Batch-level de-dup: one row for each (product_id, param_code)
        # Priority: non-empty > empty (filtered upstream), then latest versionTime, then DI lexical as tie-breaker.
        seen: set[tuple[UUID, str]] = set()
        per_product_param: dict[tuple[UUID, str], tuple[datetime, str, dict[str, Any]]] = {}

        for r in rows:
            product_id = _to_uuid(r.get("product_id"))
            if product_id is None:
                rep.skipped_unbound_product += 1
                continue
            product_ids_touched.add(str(product_id))
            di = _as_text(r.get("di_norm"))
            reg_no = _as_text(r.get("registration_no_norm"))
            raw_id = _to_uuid(r.get("raw_document_id"))
            if raw_id is None and r.get("source_run_id") is not None and not dry_run:
                srid = int(r.get("source_run_id"))
                cached = fallback_raw_by_run.get(srid)
                if cached is None:
                    cached = _ensure_raw_document_for_run(db, srid)
                    fallback_raw_by_run[srid] = cached
                raw_id = cached
            version_time_dt = _to_dt(r.get("version_time"))
            source_started_dt = _get_source_run_started_at(int(r.get("source_run_id"))) if r.get("source_run_id") is not None else None
            observed_at = version_time_dt if r.get("version_time") is not None else (source_started_dt or _to_dt(r.get("updated_at")) or _utcnow())
            if not reg_no:
                continue

            entries: list[tuple[str, str | None, dict[str, Any] | None, str]] = []

            storages = _normalize_storages(r.get("storage_json"))
            if r.get("storage_json") is not None:
                rep.storage_present_count += 1
            if storages:
                rep.storage_non_empty_count += 1
            entries.append(
                (
                    "STORAGE",
                    _storage_summary(storages),
                    {"storages": storages} if storages else None,
                    f"UDI storage_json (di={di or '-'}, reg_no={reg_no})",
                )
            )
            entries.append(("STERILIZATION_METHOD", _as_text(r.get("mjfs")), None, f"UDI mjfs (di={di or '-'}, reg_no={reg_no})"))
            entries.append(("SPECIAL_STORAGE_COND", _as_text(r.get("tscchcztj")), None, f"UDI tscchcztj (di={di or '-'}, reg_no={reg_no})"))
            entries.append(("SPECIAL_STORAGE_NOTE", _as_text(r.get("tsccsm")), None, f"UDI tsccsm (di={di or '-'}, reg_no={reg_no})"))
            entries.append(("LABEL_SERIAL_NO", _as_text(r.get("scbssfbhxlh")), None, f"UDI scbssfbhxlh (di={di or '-'}, reg_no={reg_no})"))
            entries.append(("LABEL_PROD_DATE", _as_text(r.get("scbssfbhscrq")), None, f"UDI scbssfbhscrq (di={di or '-'}, reg_no={reg_no})"))
            entries.append(("LABEL_EXP_DATE", _as_text(r.get("scbssfbhsxrq")), None, f"UDI scbssfbhsxrq (di={di or '-'}, reg_no={reg_no})"))
            entries.append(("LABEL_LOT", _as_text(r.get("scbssfbhph")), None, f"UDI scbssfbhph (di={di or '-'}, reg_no={reg_no})"))

            for code, value_text, conditions, evidence_text in entries:
                if only_allowlisted and code not in allow:
                    rep.skipped_not_allowlisted += 1
                    continue
                if not value_text and not conditions:
                    rep.skipped_missing_value += 1
                    continue
                if raw_id is None:
                    rep.skipped_missing_value += 1
                    continue
                key = (product_id, code)
                payload = {
                    "product_id": product_id,
                    "di": di,
                    "registry_no": reg_no,
                    "param_code": code,
                    "value_text": value_text,
                    "conditions": conditions,
                    "evidence_text": evidence_text,
                    "raw_document_id": raw_id,
                    "evidence_json": {
                        "source": "UDI",
                        "di_norm": di,
                        "deviceRecordKey": _as_text(r.get("device_record_key")),
                        "versionNumber": _as_text(r.get("version_number")),
                        "versionTime": _as_text(r.get("version_time")),
                        "versionStauts": _as_text(r.get("version_status")),
                        "raw_document_id": str(raw_id),
                    },
                    "observed_at": observed_at,
                }
                prev = per_product_param.get(key)
                if prev is None:
                    seen.add(key)
                    per_product_param[key] = (observed_at, di or "", payload)
                    continue
                prev_dt, prev_di, _prev_payload = prev
                if observed_at > prev_dt or (observed_at == prev_dt and (di or "") > prev_di):
                    per_product_param[key] = (observed_at, di or "", payload)

        values = [p for _k, (_dt, _di, p) in per_product_param.items()]

        rows_written = 0
        if dry_run:
            rows_written = len(values)
            rep.params_written += rows_written
        else:
            if values:
                product_ids = sorted({v["product_id"] for v in values})
                codes = sorted({str(v["param_code"]) for v in values})

                db.execute(
                    text(
                        """
                        DELETE FROM product_params
                        WHERE product_id = ANY(:pids)
                          AND param_code = ANY(:codes)
                          AND extract_version = 'udi_params_allowlist_v1'
                        """
                    ),
                    {"pids": product_ids, "codes": codes},
                )

                insert_rows = [
                    {
                        "product_id": v["product_id"],
                        "di": v["di"],
                        "registry_no": v["registry_no"],
                        "param_code": v["param_code"],
                        "value_num": None,
                        "value_text": v["value_text"],
                        "unit": None,
                        "range_low": None,
                        "range_high": None,
                        "conditions": v["conditions"],
                        "evidence_json": v["evidence_json"],
                        "evidence_text": v["evidence_text"],
                        "evidence_page": None,
                        "raw_document_id": v["raw_document_id"],
                        "confidence": 0.80,
                        "extract_version": "udi_params_allowlist_v1",
                        "observed_at": v["observed_at"],
                        "created_at": _utcnow(),
                    }
                    for v in values
                ]
                if insert_rows:
                    db.execute(insert(ProductParam), insert_rows)
                    rows_written = len(insert_rows)
                    rep.params_written += rows_written

            cursor = str(rows[-1].get("di_norm") or cursor or "")
            rep.final_cursor = cursor
            _checkpoint_set(
                db,
                job_name=effective_job_name,
                cursor=(cursor or ""),
                meta={
                    "source_run_id": source_run_id,
                    "batch_no": batch_no,
                    "scanned": rep.scanned,
                    "params_written": rep.params_written,
                },
            )
            db.commit()

        if dry_run:
            cursor = str(rows[-1].get("di_norm") or cursor or "")
            rep.final_cursor = cursor

        rep.total_batches = batch_no
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        progress = UdiParamsBatchProgress(
            batch_no=batch_no,
            cursor=(cursor or ""),
            rows_scanned=len(rows),
            rows_written=rows_written,
            distinct_products=len({str(v["product_id"]) for v in values}),
            elapsed_ms=elapsed_ms,
        )
        if progress_cb is not None:
            progress_cb(progress)

    rep.distinct_products_updated = len(product_ids_touched)
    return rep
