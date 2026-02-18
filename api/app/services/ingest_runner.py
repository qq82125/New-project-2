from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.common.errors import IngestErrorCode
from app.models import (
    PendingDocument,
    PendingRecord,
    Product,
    ProductVariant,
    RawDocument,
    RegistrationConflictAudit,
    SourceConfig,
    SourceDefinition,
    SourceRun,
)
from app.pipeline.ingest import save_raw_document
from app.repositories.source_runs import finish_source_run, start_source_run
from app.services.normalize_keys import normalize_registration_no
from app.services.pending_mode import should_enqueue_pending_documents, should_enqueue_pending_records
from app.services.source_contract import upsert_registration_with_contract


SUPPORTED_PARSER_KEYS = {"nmpa_reg_parser", "udi_di_parser", "nhsa_parser", "procurement_gd_parser"}


@dataclass(frozen=True)
class AnchorGateResult:
    ok: bool
    normalized_registration_no: str | None
    error_code: str | None
    reason_code: str | None
    reason: str | None


@dataclass
class IngestRunnerStats:
    source_key: str
    parser_key: str
    dry_run: bool
    source_run_id: int | None
    raw_written_count: int = 0
    parsed_count: int = 0
    missing_registration_no_count: int = 0
    registration_upserted_count: int = 0
    registrations_upserted_count: int = 0
    variants_upserted_count: int = 0
    conflicts_count: int = 0
    skipped_count: int = 0
    fetched_count: int = 0
    error_count: int = 0
    status: str = "success"
    message: str | None = None
    error_code_counts: dict[str, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_key": self.source_key,
            "parser_key": self.parser_key,
            "dry_run": self.dry_run,
            "source_run_id": self.source_run_id,
            "raw_written_count": self.raw_written_count,
            "parsed_count": self.parsed_count,
            "missing_registration_no_count": self.missing_registration_no_count,
            "registration_upserted_count": self.registration_upserted_count,
            "registrations_upserted_count": self.registrations_upserted_count,
            "variants_upserted_count": self.variants_upserted_count,
            "conflicts_count": self.conflicts_count,
            "skipped_count": self.skipped_count,
            "fetched_count": self.fetched_count,
            "error_count": self.error_count,
            "status": self.status,
            "message": self.message,
            "error_code_counts": (self.error_code_counts or {}),
        }


@dataclass(frozen=True)
class StructuredUpsertResult:
    registration_id: Any
    registration_no: str
    registration_created: bool
    registration_changed_fields: dict[str, Any]
    variant_upserted: bool
    di: str | None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _payload_hash(row: dict[str, Any]) -> str:
    canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _json_payload(row: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(json.dumps(row, ensure_ascii=False, default=str))
    except Exception:
        out: dict[str, Any] = {}
        for k, v in row.items():
            out[str(k)] = None if v is None else str(v)
        return out


def _pick_text(row: dict[str, Any], *keys: str) -> str | None:
    for k in keys:
        if k in row and row[k] is not None:
            s = str(row[k]).strip()
            if s:
                return s
    return None


def enforce_registration_anchor(record: dict[str, Any], source_key: str) -> AnchorGateResult:
    """Canonical anchor gate for structured writes.

    Returns a machine-readable decision. The caller must not raise for row-level gate failures.
    """
    assert isinstance(record, dict), "record must be a dict"
    _ = str(source_key or "").strip().upper()  # keep signature stable; reserved for source-specific rules.

    src = str(source_key or "").strip().upper()
    reg_a_raw = _pick_text(record, "registration_no", "reg_no")
    reg_b_raw = _pick_text(record, "registry_no")
    di = _pick_text(record, "udi_di", "di")

    reg_no_raw = reg_a_raw or reg_b_raw
    if not reg_no_raw:
        return AnchorGateResult(
            ok=False,
            normalized_registration_no=None,
            error_code=(
                IngestErrorCode.E_UDI_DI_WITHOUT_REG.value
                if (src in {"UDI_DI", "UDI"} and di)
                else IngestErrorCode.E_CANONICAL_KEY_MISSING.value
            ),
            reason_code="NO_REG_NO",
            reason="registration_no missing in payload",
        )
    reg_no = normalize_registration_no(reg_no_raw)
    if not reg_no:
        return AnchorGateResult(
            ok=False,
            normalized_registration_no=None,
            error_code=IngestErrorCode.E_REG_NO_NORMALIZE_FAILED.value,
            reason_code="PARSE_ERROR",
            reason=f"registration_no normalize failed: {reg_no_raw}",
        )

    # Detect conflicting candidate keys in the same payload (e.g. reg_no vs registry_no mismatch).
    if reg_a_raw and reg_b_raw:
        reg_a = normalize_registration_no(reg_a_raw)
        reg_b = normalize_registration_no(reg_b_raw)
        if reg_a and reg_b and reg_a != reg_b:
            return AnchorGateResult(
                ok=False,
                normalized_registration_no=None,
                error_code=IngestErrorCode.E_CANONICAL_KEY_CONFLICT.value,
                reason_code="PARSE_ERROR",
                reason=f"registration_no conflict: {reg_a_raw} != {reg_b_raw}",
            )
    return AnchorGateResult(
        ok=True,
        normalized_registration_no=reg_no,
        error_code=None,
        reason_code=None,
        reason=None,
    )


def _as_date(v: Any) -> Any:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def _dsn_from_runtime_cfg(cfg: dict[str, Any]) -> URL:
    query = {}
    sslmode = cfg.get("sslmode")
    if sslmode:
        query["sslmode"] = str(sslmode)
    return URL.create(
        "postgresql+psycopg",
        username=str(cfg.get("username") or ""),
        password=str(cfg.get("password") or ""),
        host=str(cfg.get("host") or ""),
        port=int(cfg.get("port") or 5432),
        database=str(cfg.get("database") or ""),
        query=query,
    )


def _source_runtime_connection(cfg: SourceConfig) -> tuple[str, dict[str, Any]]:
    fp = cfg.fetch_params if isinstance(cfg.fetch_params, dict) else {}
    legacy = fp.get("legacy_data_source") if isinstance(fp.get("legacy_data_source"), dict) else {}
    conn_type = str(legacy.get("type") or fp.get("type") or "postgres").strip().lower()
    conn_cfg = legacy.get("config") if isinstance(legacy.get("config"), dict) else None
    if conn_cfg is None:
        conn_cfg = fp.get("connection") if isinstance(fp.get("connection"), dict) else fp
    if not isinstance(conn_cfg, dict):
        conn_cfg = {}
    return conn_type, conn_cfg


def _resolve_runtime_fetch_controls(cfg: SourceConfig, conn_cfg: dict[str, Any]) -> tuple[int, datetime]:
    fp = cfg.fetch_params if isinstance(cfg.fetch_params, dict) else {}
    top_batch = fp.get("batch_size")
    conn_batch = conn_cfg.get("batch_size")
    try:
        batch_size = int(top_batch if top_batch not in {None, ""} else conn_batch or 2000)
    except Exception:
        batch_size = 2000
    batch_size = max(1, min(20000, batch_size))

    top_cutoff_hours = fp.get("cutoff_window_hours")
    conn_cutoff_hours = conn_cfg.get("cutoff_window_hours")
    try:
        cutoff_hours = int(top_cutoff_hours if top_cutoff_hours not in {None, ""} else conn_cutoff_hours or 72)
    except Exception:
        cutoff_hours = 72
    cutoff_hours = max(1, min(24 * 365, cutoff_hours))
    cutoff = _utcnow() - timedelta(hours=cutoff_hours)
    return batch_size, cutoff


def _fetch_rows_from_runtime(cfg: SourceConfig) -> list[dict[str, Any]]:
    conn_type, conn_cfg = _source_runtime_connection(cfg)
    if conn_type != "postgres":
        raise RuntimeError(f"unsupported fetcher type: {conn_type}")

    source_query = str(conn_cfg.get("source_query") or "").strip()
    source_table = str(conn_cfg.get("source_table") or "public.products").strip() or "public.products"
    limit, cutoff = _resolve_runtime_fetch_controls(cfg, conn_cfg)
    sql = source_query or f"SELECT * FROM {source_table} LIMIT :batch_size"

    engine = create_engine(_dsn_from_runtime_cfg(conn_cfg), pool_pre_ping=True, poolclass=NullPool)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql), {"batch_size": limit, "cutoff": cutoff}).mappings().all()
            return [dict(r) for r in rows]
    finally:
        engine.dispose()


def _write_raw_document_for_row(
    db: Session,
    *,
    source: str,
    source_run_id: int,
    source_url: str | None,
    row: dict[str, Any],
) -> Any:
    payload = _json_payload(row)
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return save_raw_document(
        db,
        source=source,
        url=source_url,
        content=content,
        doc_type="json",
        run_id=f"source_run:{int(source_run_id)}",
    )


def _set_raw_parse_log(
    db: Session,
    *,
    raw_document_id: Any,
    parse_status: str,
    parse_error: str | None,
    error_code: str | None,
    source_key: str,
    source_run_id: int,
    payload_hash: str,
) -> None:
    doc = db.get(RawDocument, raw_document_id)
    if doc is None:
        return
    doc.parse_status = parse_status
    doc.error = parse_error
    doc.parse_log = {
        "source_key": source_key,
        "source_run_id": int(source_run_id),
        "payload_hash": payload_hash,
        "error_code": error_code,
        "parse_error": parse_error,
        "updated_at": _utcnow().isoformat(),
    }
    db.add(doc)


def _enqueue_pending_record(
    db: Session,
    *,
    source_key: str,
    raw_document_id: Any,
    registration_no_raw: str | None,
    raw_row: dict[str, Any],
    payload_hash: str,
    source_run_id: int,
    reason_code: str = "NO_REG_NO",
    reason: str | None = None,
) -> None:
    stmt = insert(PendingRecord).values(
        source_key=source_key,
        source_run_id=int(source_run_id),
        raw_document_id=raw_document_id,
        payload_hash=payload_hash,
        registration_no_raw=(registration_no_raw or None),
        reason_code=reason_code,
        candidate_registry_no=(registration_no_raw or None),
        candidate_company=_pick_text(raw_row, "company_name", "manufacturer", "candidate_company"),
        candidate_product_name=_pick_text(raw_row, "product_name", "name", "candidate_product_name"),
        reason=json.dumps({"message": reason, "raw": _json_payload(raw_row)}, ensure_ascii=False),
        status="open",
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[PendingRecord.source_run_id, PendingRecord.payload_hash],
        set_={
            "raw_document_id": stmt.excluded.raw_document_id,
            "registration_no_raw": stmt.excluded.registration_no_raw,
            "reason_code": stmt.excluded.reason_code,
            "reason": stmt.excluded.reason,
            "candidate_registry_no": stmt.excluded.candidate_registry_no,
            "candidate_company": stmt.excluded.candidate_company,
            "candidate_product_name": stmt.excluded.candidate_product_name,
            "status": "open",
            "updated_at": text("NOW()"),
        },
    )
    db.execute(stmt)


def _enqueue_pending_document(
    db: Session,
    *,
    raw_document_id: Any,
    source_run_id: int | None,
    reason_code: str,
) -> None:
    """Document-level pending queue for raw_documents that failed the registration anchor gate."""
    stmt = insert(PendingDocument).values(
        raw_document_id=raw_document_id,
        source_run_id=(int(source_run_id) if source_run_id is not None else None),
        reason_code=str(reason_code or "NO_REG_NO"),
        status="pending",
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[PendingDocument.raw_document_id],
        set_={
            "source_run_id": stmt.excluded.source_run_id,
            "reason_code": stmt.excluded.reason_code,
            "status": "pending",
            "updated_at": text("NOW()"),
        },
    )
    db.execute(stmt)


def _ensure_product_snapshot_for_registration(
    db: Session,
    *,
    registration_id: Any,
    registration_no: str,
    di: str,
    row: dict[str, Any],
) -> Any:
    product = db.scalar(
        select(Product)
        .where(Product.registration_id == registration_id)
        .order_by(Product.updated_at.desc(), Product.created_at.desc())
        .limit(1)
    )
    if product is not None:
        return product.id

    name = _pick_text(row, "product_name", "name") or f"UDI-{di}"
    product = Product(
        udi_di=di,
        reg_no=registration_no,
        name=name,
        class_name=_pick_text(row, "class", "class_name"),
        approved_date=_as_date(_pick_text(row, "approval_date", "approved_date")),
        expiry_date=_as_date(_pick_text(row, "expiry_date")),
        model=_pick_text(row, "model"),
        specification=_pick_text(row, "specification", "model_spec"),
        category=_pick_text(row, "category", "ivd_category"),
        status=_pick_text(row, "status") or "ACTIVE",
        is_ivd=True,
        ivd_category=_pick_text(row, "ivd_category", "category"),
        ivd_version=1,
        ivd_source="source_runner",
        raw_json=_json_payload(row),
        raw=_json_payload(row),
        registration_id=registration_id,
    )
    db.add(product)
    db.flush()
    return product.id


def _upsert_variant_from_row_with_bindings(
    db: Session,
    *,
    row: dict[str, Any],
    registry_no: str | None,
    product_id: Any | None,
) -> bool:
    di = _pick_text(row, "udi_di", "di")
    if not di:
        return False
    stmt = insert(ProductVariant).values(
        di=di,
        registry_no=(registry_no or None),
        product_id=product_id,
        product_name=_pick_text(row, "product_name", "name"),
        model_spec=_pick_text(row, "model_spec", "model", "specification"),
        packaging=_pick_text(row, "packaging"),
        manufacturer=_pick_text(row, "manufacturer", "company_name"),
        is_ivd=True,
        ivd_category=_pick_text(row, "ivd_category", "category"),
        ivd_version="source_runner_v1",
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[ProductVariant.di],
        set_={
            "registry_no": func.coalesce(stmt.excluded.registry_no, ProductVariant.registry_no),
            "product_id": func.coalesce(stmt.excluded.product_id, ProductVariant.product_id),
            "product_name": stmt.excluded.product_name,
            "model_spec": stmt.excluded.model_spec,
            "packaging": stmt.excluded.packaging,
            "manufacturer": stmt.excluded.manufacturer,
            "is_ivd": stmt.excluded.is_ivd,
            "ivd_category": stmt.excluded.ivd_category,
            "ivd_version": stmt.excluded.ivd_version,
            "updated_at": text("NOW()"),
        },
    )
    db.execute(stmt)
    return True


def _resolve_source_policy(
    db: Session,
    *,
    source_key: str,
    default_evidence_grade: str | None = None,
    default_source_priority: int | None = None,
) -> tuple[str, int]:
    defn = db.get(SourceDefinition, str(source_key or "").strip().upper())
    cfg = db.scalar(select(SourceConfig).where(SourceConfig.source_key == str(source_key or "").strip().upper()))
    evidence_grade_raw = (
        str(default_evidence_grade or "").strip().upper()
        or (str(getattr(defn, "default_evidence_grade", "C")).strip().upper() if defn is not None else "C")
        or "C"
    )
    if default_source_priority is not None:
        source_priority_raw: Any = default_source_priority
    else:
        source_priority_raw = (
            (cfg.upsert_policy or {}).get("priority", 100)
            if (cfg is not None and isinstance(cfg.upsert_policy, dict))
            else 100
        )

    # Validate contract-level policy inputs; do not abort ingest for config errors.
    codes: list[str] = []
    evidence_grade = evidence_grade_raw if evidence_grade_raw in {"A", "B", "C"} else "C"
    if evidence_grade_raw not in {"A", "B", "C"}:
        codes.append(IngestErrorCode.E_EVIDENCE_GRADE_INVALID.value)
    try:
        source_priority = int(source_priority_raw)
        if source_priority < 0:
            raise ValueError("negative priority")
    except Exception:
        source_priority = 100
        codes.append(IngestErrorCode.E_SOURCE_PRIORITY_INVALID.value)

    # Caller may count codes into source_run notes; we only return validated values here.
    return evidence_grade, int(source_priority)


def upsert_structured_record_via_runner(
    db: Session,
    *,
    source_key: str,
    source_run_id: int | None,
    row: dict[str, Any],
    parser_key: str | None = None,
    raw_document_id: Any | None = None,
    observed_at: datetime | None = None,
    default_evidence_grade: str | None = None,
    default_source_priority: int | None = None,
) -> StructuredUpsertResult:
    gate = enforce_registration_anchor(row, str(source_key))
    reg_no = gate.normalized_registration_no
    if not gate.ok or not reg_no:
        raise ValueError(gate.error_code or IngestErrorCode.E_STRUCT_WRITE_FORBIDDEN.value)

    resolved_parser_key = str(parser_key or "").strip()
    if not resolved_parser_key:
        defn = db.get(SourceDefinition, str(source_key or "").strip().upper())
        resolved_parser_key = str(getattr(defn, "parser_key", "") or "").strip()

    evidence_grade, source_priority = _resolve_source_policy(
        db,
        source_key=str(source_key),
        default_evidence_grade=default_evidence_grade,
        default_source_priority=default_source_priority,
    )
    event_time = observed_at if observed_at is not None else _utcnow()

    incoming_fields = {
        "filing_no": _pick_text(row, "filing_no"),
        "approval_date": _as_date(_pick_text(row, "approval_date", "approved_date")),
        "expiry_date": _as_date(_pick_text(row, "expiry_date")),
        "status": _pick_text(row, "status"),
    }
    payload_for_contract = _json_payload(row)
    if raw_document_id is not None:
        payload_for_contract["_raw_document_id"] = str(raw_document_id)
    result = upsert_registration_with_contract(
        db,
        registration_no=reg_no,
        incoming_fields=incoming_fields,
        source=str(source_key),
        source_run_id=(int(source_run_id) if source_run_id is not None else None),
        evidence_grade=evidence_grade,
        source_priority=int(source_priority),
        observed_at=event_time,
        raw_source_record_id=None,
        raw_payload=payload_for_contract,
        write_change_log=True,
    )

    di = _pick_text(row, "udi_di", "di")
    variant_upserted = False
    if resolved_parser_key == "udi_di_parser":
        product_id = None
        if di:
            product_id = _ensure_product_snapshot_for_registration(
                db,
                registration_id=result.registration_id,
                registration_no=reg_no,
                di=di,
                row=row,
            )
        variant_upserted = _upsert_variant_from_row_with_bindings(
            db,
            row=row,
            registry_no=reg_no,
            product_id=product_id,
        )

    return StructuredUpsertResult(
        registration_id=result.registration_id,
        registration_no=result.registration_no,
        registration_created=bool(result.created),
        registration_changed_fields=dict(result.changed_fields or {}),
        variant_upserted=bool(variant_upserted),
        di=di,
    )


def _run_one_source(db: Session, *, defn: SourceDefinition, cfg: SourceConfig, execute: bool) -> IngestRunnerStats:
    dry_run = not bool(execute)
    parser_key = str(defn.parser_key or "").strip()
    stats = IngestRunnerStats(
        source_key=str(defn.source_key),
        parser_key=parser_key,
        dry_run=dry_run,
        source_run_id=None,
        error_code_counts={},
    )
    if parser_key not in SUPPORTED_PARSER_KEYS:
        stats.status = "skipped"
        stats.message = f"unsupported parser_key for generic runner: {parser_key}"
        return stats

    # Adapter mode: keep existing specialized ingest implementations, only unify entrypoint and summary.
    if parser_key == "nhsa_parser":
        try:
            return _run_nhsa_adapter(db, defn=defn, cfg=cfg, execute=execute)
        except Exception as exc:
            db.rollback()
            stats.status = "failed"
            stats.error_count = 1
            stats.message = str(exc)
            cfg.last_run_at = _utcnow()
            cfg.last_status = "failed"
            cfg.last_error = stats.message
            db.add(cfg)
            db.commit()
            return stats
    if parser_key == "procurement_gd_parser":
        try:
            return _run_procurement_adapter(db, defn=defn, cfg=cfg, execute=execute)
        except Exception as exc:
            db.rollback()
            stats.status = "failed"
            stats.error_count = 1
            stats.message = str(exc)
            cfg.last_run_at = _utcnow()
            cfg.last_status = "failed"
            cfg.last_error = stats.message
            db.add(cfg)
            db.commit()
            return stats

    run = start_source_run(
        db,
        source=f"source_runner:{defn.source_key}",
        package_name=None,
        package_md5=None,
        download_url=None,
    )
    stats.source_run_id = int(run.id)

    try:
        rows = _fetch_rows_from_runtime(cfg)
        stats.fetched_count = len(rows)
        seen_hashes: set[str] = set()
        for row in rows:
            row_hash = _payload_hash(row)
            if row_hash in seen_hashes:
                stats.skipped_count += 1
                continue
            seen_hashes.add(row_hash)

            di = _pick_text(row, "udi_di", "di")
            gate = enforce_registration_anchor(row, str(defn.source_key))
            reg_no = gate.normalized_registration_no
            if gate.ok and reg_no:
                stats.parsed_count += 1
            else:
                stats.missing_registration_no_count += 1
                code = str(gate.error_code or IngestErrorCode.E_PARSE_FAILED.value)
                counts = stats.error_code_counts if isinstance(stats.error_code_counts, dict) else {}
                counts[code] = int(counts.get(code, 0) or 0) + 1
                stats.error_code_counts = counts

            if dry_run:
                if not reg_no:
                    stats.skipped_count += 1
                if parser_key == "udi_di_parser" and di:
                    stats.variants_upserted_count += 1
                continue

            source_url = _pick_text(row, "source_url", "url")
            raw_document_id = _write_raw_document_for_row(
                db,
                source=str(defn.source_key),
                source_run_id=int(run.id),
                source_url=source_url,
                row=row,
            )
            stats.raw_written_count += 1

            if not reg_no:
                _set_raw_parse_log(
                    db,
                    raw_document_id=raw_document_id,
                    parse_status="FAILED",
                    parse_error=(gate.reason or "registration_no parse failed"),
                    error_code=(gate.error_code or IngestErrorCode.E_PARSE_FAILED.value),
                    source_key=str(defn.source_key),
                    source_run_id=int(run.id),
                    payload_hash=row_hash,
                )
                if should_enqueue_pending_documents():
                    _enqueue_pending_document(
                        db,
                        raw_document_id=raw_document_id,
                        source_run_id=int(run.id),
                        reason_code=str(gate.reason_code or "NO_REG_NO"),
                    )
                if should_enqueue_pending_records():
                    _enqueue_pending_record(
                        db,
                        source_key=str(defn.source_key),
                        raw_document_id=raw_document_id,
                        registration_no_raw=_pick_text(row, "registration_no", "reg_no", "registry_no"),
                        raw_row=row,
                        payload_hash=row_hash,
                        source_run_id=int(run.id),
                        reason_code=(gate.reason_code or "PARSE_ERROR"),
                        reason=(gate.reason or "registration anchor gate failed"),
                    )
                continue

            _set_raw_parse_log(
                db,
                raw_document_id=raw_document_id,
                parse_status="PARSED",
                parse_error=None,
                error_code=None,
                source_key=str(defn.source_key),
                source_run_id=int(run.id),
                payload_hash=row_hash,
            )

            result = upsert_structured_record_via_runner(
                db,
                source_key=str(defn.source_key),
                source_run_id=int(run.id),
                row=row,
                parser_key=parser_key,
                raw_document_id=raw_document_id,
                observed_at=_utcnow(),
                default_evidence_grade=str(defn.default_evidence_grade or "C").strip().upper() or "C",
                default_source_priority=(
                    int((cfg.upsert_policy or {}).get("priority", 100))
                    if isinstance(cfg.upsert_policy, dict)
                    else 100
                ),
            )
            if result.registration_created or bool(result.registration_changed_fields):
                stats.registration_upserted_count += 1
                stats.registrations_upserted_count += 1

            if result.variant_upserted:
                stats.variants_upserted_count += 1

        if not dry_run:
            stats.conflicts_count = int(
                db.scalar(
                    select(func.count(RegistrationConflictAudit.id)).where(
                        RegistrationConflictAudit.source_run_id == int(run.id),
                        RegistrationConflictAudit.resolution == "REJECTED",
                    )
                )
                or 0
            )
            db.commit()

        stats.status = "success"
        error_codes_text = ""
        if isinstance(stats.error_code_counts, dict) and stats.error_code_counts:
            error_codes_text = f" error_codes={json.dumps(stats.error_code_counts, ensure_ascii=True, sort_keys=True)}"
        stats.message = (
            f"fetched={stats.fetched_count} parsed={stats.parsed_count} missing_reg={stats.missing_registration_no_count} "
            f"reg_upserted={stats.registrations_upserted_count} variants_upserted={stats.variants_upserted_count}"
            f"{error_codes_text}"
        )
        finish_source_run(
            db,
            run,
            status="success",
            message=stats.message,
            records_total=int(stats.fetched_count),
            records_success=int(stats.parsed_count),
            records_failed=int(stats.missing_registration_no_count + stats.error_count),
            added_count=int(stats.registrations_upserted_count),
            updated_count=int(stats.variants_upserted_count),
            removed_count=0,
            source_notes=stats.to_dict(),
        )
        cfg.last_run_at = _utcnow()
        cfg.last_status = "success"
        cfg.last_error = None
        db.add(cfg)
        db.commit()
        return stats
    except Exception as exc:
        db.rollback()
        stats.status = "failed"
        stats.error_count += 1
        stats.message = str(exc)
        finish_source_run(
            db,
            run,
            status="failed",
            message=stats.message,
            records_total=int(stats.fetched_count),
            records_success=int(stats.parsed_count),
            records_failed=max(1, int(stats.missing_registration_no_count + stats.error_count)),
            added_count=int(stats.registrations_upserted_count),
            updated_count=int(stats.variants_upserted_count),
            removed_count=0,
            source_notes=stats.to_dict(),
        )
        cfg.last_run_at = _utcnow()
        cfg.last_status = "failed"
        cfg.last_error = stats.message
        db.add(cfg)
        db.commit()
        return stats


def _run_nhsa_adapter(db: Session, *, defn: SourceDefinition, cfg: SourceConfig, execute: bool) -> IngestRunnerStats:
    from app.services.nhsa_ingest import ingest_nhsa_from_file, ingest_nhsa_from_url

    dry_run = not bool(execute)
    stats = IngestRunnerStats(
        source_key=str(defn.source_key),
        parser_key=str(defn.parser_key or ""),
        dry_run=dry_run,
        source_run_id=None,
    )
    fp = cfg.fetch_params if isinstance(cfg.fetch_params, dict) else {}
    month = str(fp.get("month") or "").strip()
    url = str(fp.get("url") or "").strip()
    file_path = str(fp.get("file") or "").strip()
    if not month:
        raise ValueError("NHSA source requires fetch_params.month (YYYY-MM)")
    if not url and not file_path:
        raise ValueError("NHSA source requires fetch_params.url or fetch_params.file")

    if url:
        timeout = int(fp.get("timeout_seconds") or 30)
        res = ingest_nhsa_from_url(
            db,
            snapshot_month=month,
            url=url,
            timeout_seconds=timeout,
            dry_run=dry_run,
        )
    else:
        res = ingest_nhsa_from_file(
            db,
            snapshot_month=month,
            file_path=file_path,
            dry_run=dry_run,
        )
    stats.source_run_id = int(res.source_run_id)
    stats.fetched_count = int(res.fetched_count)
    stats.parsed_count = int(res.parsed_count)
    stats.registration_upserted_count = int(res.upserted)
    stats.registrations_upserted_count = int(res.upserted)
    stats.status = "success"
    stats.message = f"nhsa adapter ok: parsed={res.parsed_count} upserted={res.upserted}"
    _merge_runner_stats_into_source_run(db, int(res.source_run_id), stats)
    cfg.last_run_at = _utcnow()
    cfg.last_status = "success"
    cfg.last_error = None
    db.add(cfg)
    db.commit()
    return stats


def _run_procurement_adapter(db: Session, *, defn: SourceDefinition, cfg: SourceConfig, execute: bool) -> IngestRunnerStats:
    from app.services.procurement_ingest import ingest_procurement_from_file

    dry_run = not bool(execute)
    stats = IngestRunnerStats(
        source_key=str(defn.source_key),
        parser_key=str(defn.parser_key or ""),
        dry_run=dry_run,
        source_run_id=None,
    )
    fp = cfg.fetch_params if isinstance(cfg.fetch_params, dict) else {}
    province = str(fp.get("province") or "").strip()
    file_path = str(fp.get("file") or "").strip()
    if not province:
        raise ValueError("PROCUREMENT source requires fetch_params.province")
    if not file_path:
        raise ValueError("PROCUREMENT source requires fetch_params.file")

    res = ingest_procurement_from_file(
        db,
        province=province,
        file_path=file_path,
        dry_run=dry_run,
    )
    stats.source_run_id = int(res.source_run_id)
    stats.fetched_count = int(res.fetched_count)
    stats.parsed_count = int(res.parsed_count)
    stats.variants_upserted_count = int(res.results)
    stats.registration_upserted_count = int(res.maps)
    stats.registrations_upserted_count = int(res.maps)
    stats.status = "success"
    stats.message = (
        f"procurement adapter ok: projects={res.projects} lots={res.lots} results={res.results} maps={res.maps}"
    )
    _merge_runner_stats_into_source_run(db, int(res.source_run_id), stats)
    cfg.last_run_at = _utcnow()
    cfg.last_status = "success"
    cfg.last_error = None
    db.add(cfg)
    db.commit()
    return stats


def _merge_runner_stats_into_source_run(db: Session, source_run_id: int, stats: IngestRunnerStats) -> None:
    run = db.get(SourceRun, int(source_run_id))
    if run is None:
        return
    notes = run.source_notes if isinstance(run.source_notes, dict) else {}
    notes.update(
        {
            "runner_source_key": stats.source_key,
            "runner_parser_key": stats.parser_key,
            "runner_dry_run": bool(stats.dry_run),
            "raw_written_count": int(stats.raw_written_count),
            "parsed_count": int(stats.parsed_count),
            "missing_registration_no_count": int(stats.missing_registration_no_count),
            "registration_upserted_count": int(stats.registration_upserted_count),
            "registrations_upserted_count": int(stats.registrations_upserted_count),
            "variants_upserted_count": int(stats.variants_upserted_count),
            "conflicts_count": int(stats.conflicts_count),
            "skipped_count": int(stats.skipped_count),
        }
    )
    run.source_notes = notes
    db.add(run)
    db.commit()


def run_source_by_key(db: Session, *, source_key: str, execute: bool) -> IngestRunnerStats:
    key = str(source_key or "").strip().upper()
    if not key:
        raise ValueError("source_key is required")
    defn = db.get(SourceDefinition, key)
    if defn is None:
        raise ValueError(f"source definition not found: {key}")
    cfg = db.scalar(select(SourceConfig).where(SourceConfig.source_key == key))
    if cfg is None:
        raise ValueError(f"source config not found: {key}")
    return _run_one_source(db, defn=defn, cfg=cfg, execute=execute)


def run_all_enabled_sources(db: Session, *, execute: bool) -> list[IngestRunnerStats]:
    rows = list(
        db.execute(
            select(SourceDefinition, SourceConfig)
            .join(SourceConfig, SourceConfig.source_key == SourceDefinition.source_key)
            .where(SourceConfig.enabled.is_(True))
            .order_by(SourceDefinition.source_key.asc())
        ).all()
    )
    out: list[IngestRunnerStats] = []
    for defn, cfg in rows:
        out.append(_run_one_source(db, defn=defn, cfg=cfg, execute=execute))
    return out
