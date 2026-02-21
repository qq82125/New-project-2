from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import Select, or_, select, text
from sqlalchemy.orm import Session

from app.models import Company, Product, ProductParam, RawSourceRecord, Registration
from app.services.normalize_keys import normalize_registration_no
from app.services.registration_no_parser import parse_registration_no


LEGACY_SOURCE_KEY = "nmpa_legacy_dump"

_COMMON_COLUMN_MAP: dict[str, tuple[str, ...]] = {
    "registration_no_raw": ("注册证编号", "注册证号", "备案编号", "备案号", "证号"),
    "company_name": ("注册人名称",),
    "product_name": ("产品名称中文", "产品名称"),
    "model": ("型号",),
    "structure_and_composition": ("结构及组成",),
    "intended_use_scope": ("适用范围",),
    "other_content": ("其他内容",),
    "remarks": ("备注",),
    "approval_date": ("批准日期",),
    "expiry_date": ("有效期至",),
    "product_standard": ("产品标准",),
    "change_date": ("变更日期",),
    "main_components": ("主要组成成分",),
    "intended_use": ("预期用途",),
    "storage_conditions": ("储存条件及有效期", "产品储存条件"),
    "approval_department": ("审批部门",),
    "change_summary": ("变更情况",),
    "management_class_raw": ("管理类别",),
    "country_or_region": ("生产国或地区",),
    "country_or_region_en": ("生产国或地区英文",),
    "manufacturer_name_cn": ("生产厂商名称中文",),
}

_LEGACY_PARAM_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "结构及组成": ("structure_and_composition", "STRUCTURE_COMPOSITION", "composition", "MAIN_STRUCTURE"),
    "适用范围": ("intended_use_scope", "APPLICABLE_SCOPE", "scope_of_application"),
    "预期用途": ("intended_use", "INTENDED_USE", "usage"),
    "储存条件及有效期": ("storage_conditions", "STORAGE", "STORAGE_CONDITION"),
    "产品储存条件": ("storage_conditions", "STORAGE", "STORAGE_CONDITION"),
    "产品标准": ("product_standard", "PRODUCT_STANDARD"),
    "主要组成成分": ("main_components", "MAIN_COMPONENTS"),
    "生产国或地区": ("country_or_region", "COUNTRY_OR_REGION"),
    "生产国或地区英文": ("country_or_region", "COUNTRY_OR_REGION"),
}


def _pick_text(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        if key not in data:
            continue
        val = data.get(key)
        if val is None:
            continue
        txt = str(val).strip()
        if txt:
            return txt
    return None


def _clip_text(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    txt = str(value).strip()
    if not txt:
        return None
    if len(txt) <= max_len:
        return txt
    return txt[:max_len]


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    txt = str(value).strip()
    if not txt:
        return None
    txt = txt.replace("/", "-").replace(".", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y%m%d", "%Y年%m月%d日"):
        try:
            d = datetime.strptime(txt, fmt)
            return d.date()
        except ValueError:
            continue
    return None


def _extract_fields_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    row = data if isinstance(data, dict) else {}
    out: dict[str, Any] = {}
    for target, candidates in _COMMON_COLUMN_MAP.items():
        out[target] = _pick_text(row, *candidates)
    return out


def _canonical_from_payload(payload: dict[str, Any], extracted: dict[str, Any]) -> tuple[str | None, str, str | None]:
    payload_norm_raw = str(payload.get("registration_no_norm") or "").strip()
    payload_norm = payload_norm_raw or None
    reg_raw = extracted.get("registration_no_raw")
    normalized_from_raw = normalize_registration_no(reg_raw) if reg_raw else None

    if payload_norm:
        return payload_norm, "payload", normalized_from_raw
    if normalized_from_raw:
        return normalized_from_raw, "normalized_fallback", normalized_from_raw
    return None, "none", normalized_from_raw


def _ensure_company(db: Session, company_name: str | None) -> Company | None:
    company_name = _clip_text(company_name, 255)
    if not company_name:
        return None
    existing = db.scalar(select(Company).where(Company.name == company_name).limit(1))
    if existing is not None:
        return existing
    c = Company(name=company_name, raw_json={"source_hint": LEGACY_SOURCE_KEY})
    db.add(c)
    db.flush()
    return c


def _stub_udi_di(registration_no: str) -> str:
    digest = hashlib.sha1(registration_no.encode("utf-8")).hexdigest()[:24]
    return f"LEGACY-{digest}"


def _select_raw_rows(
    source_key: str,
    source_run_id: int | None,
    *,
    offset: int,
    limit: int,
) -> Select[tuple[RawSourceRecord]]:
    stmt: Select[tuple[RawSourceRecord]] = (
        select(RawSourceRecord)
        .where(RawSourceRecord.source == source_key, RawSourceRecord.payload.is_not(None))
        .order_by(RawSourceRecord.created_at.asc(), RawSourceRecord.id.asc())
        .offset(offset)
        .limit(limit)
    )
    if source_run_id is not None:
        stmt = stmt.where(RawSourceRecord.source_run_id == source_run_id)
    return stmt


@dataclass
class LegacyPromoteReport:
    scanned: int = 0
    promoted: int = 0
    skipped: int = 0
    failed: int = 0
    reason_codes: Counter[str] | None = None
    parse_levels: Counter[str] | None = None
    canonical_source_distribution: Counter[str] | None = None

    def __post_init__(self) -> None:
        if self.reason_codes is None:
            self.reason_codes = Counter()
        if self.parse_levels is None:
            self.parse_levels = Counter()
        if self.canonical_source_distribution is None:
            self.canonical_source_distribution = Counter()

    @property
    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": int(self.scanned),
            "promoted": int(self.promoted),
            "skipped": int(self.skipped),
            "failed": int(self.failed),
            "reason_codes": dict(self.reason_codes or {}),
            "parse_level_distribution": dict(self.parse_levels or {}),
            "canonical_source_distribution": dict(self.canonical_source_distribution or {}),
        }


@dataclass
class LegacyProductStubReport:
    scanned: int = 0
    created: int = 0
    existing: int = 0
    failed: int = 0

    @property
    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": int(self.scanned),
            "created": int(self.created),
            "existing": int(self.existing),
            "failed": int(self.failed),
        }


@dataclass
class LegacyParamsBackfillReport:
    scanned: int = 0
    written: int = 0
    skipped_existing: int = 0
    skipped_invalid_key: int = 0
    failed: int = 0
    per_key_written_counts: Counter[str] | None = None
    candidates_top10: Counter[str] | None = None

    def __post_init__(self) -> None:
        if self.per_key_written_counts is None:
            self.per_key_written_counts = Counter()
        if self.candidates_top10 is None:
            self.candidates_top10 = Counter()

    @property
    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": int(self.scanned),
            "written": int(self.written),
            "skipped_existing": int(self.skipped_existing),
            "skipped_invalid_key": int(self.skipped_invalid_key),
            "failed": int(self.failed),
            "per_key_written_counts": dict(self.per_key_written_counts or {}),
            "candidates_top10": dict((self.candidates_top10 or Counter()).most_common(10)),
        }


def promote_nmpa_legacy_raw_to_registrations(
    db: Session,
    *,
    dry_run: bool,
    limit: int | None = None,
    offset: int = 0,
    batch_size: int = 1000,
    only_missing: bool = True,
    source_run_id: int | None = None,
) -> LegacyPromoteReport:
    rep = LegacyPromoteReport()
    scanned_total = 0
    local_offset = offset
    hard_limit = int(limit) if limit is not None else None
    seen_canonical_in_run: set[str] = set()

    while True:
        chunk = batch_size
        if hard_limit is not None:
            remain = hard_limit - scanned_total
            if remain <= 0:
                break
            chunk = min(chunk, remain)
        rows = list(
            db.scalars(
                _select_raw_rows(LEGACY_SOURCE_KEY, source_run_id, offset=local_offset, limit=chunk)
            ).all()
        )
        if not rows:
            break
        local_offset += len(rows)
        scanned_total += len(rows)

        for rec in rows:
            rep.scanned += 1
            payload = rec.payload if isinstance(rec.payload, dict) else {}
            extracted = _extract_fields_from_payload(payload)
            canonical, canonical_src, normalized_from_raw = _canonical_from_payload(payload, extracted)
            rep.canonical_source_distribution[canonical_src] += 1

            if not canonical:
                rep.failed += 1
                rep.reason_codes["REGNO_MISSING"] += 1
                rep.parse_levels["FAIL"] += 1
                continue

            if canonical_src == "payload":
                if normalized_from_raw and normalized_from_raw != canonical:
                    rep.reason_codes["REGNO_CANONICAL_MISMATCH"] += 1

            parse_level = str(payload.get("regno_parse_level") or "").strip().upper()
            if not parse_level:
                parse_level = parse_registration_no(canonical).parse_level
            rep.parse_levels[parse_level] += 1
            if parse_level not in {"FULL", "PARTIAL", "CLASSIFIED"}:
                rep.failed += 1
                rep.reason_codes["REGNO_PARSE_FAILED"] += 1
                continue

            if canonical in seen_canonical_in_run and only_missing:
                rep.skipped += 1
                rep.reason_codes["DUP_IN_BATCH"] += 1
                continue

            existing = db.scalar(select(Registration).where(Registration.registration_no == canonical).limit(1))
            if existing is not None and only_missing:
                rep.skipped += 1
                rep.reason_codes["ALREADY_EXISTS"] += 1
                continue

            approval_date = _as_date(extracted.get("approval_date"))
            expiry_date = _as_date(extracted.get("expiry_date"))
            raw_meta = {
                "source_key": LEGACY_SOURCE_KEY,
                "source_run_id": rec.source_run_id,
                "raw_source_record_id": str(rec.id),
                "storage_uri": payload.get("storage_uri"),
                "file_sha256": payload.get("file_sha256"),
                "row_index": payload.get("row_index"),
                "registration_no_raw": extracted.get("registration_no_raw"),
                "registration_no_norm": canonical,
                "company_name": extracted.get("company_name"),
                "product_name": extracted.get("product_name"),
                "model": extracted.get("model"),
                "parse_level": parse_level,
                "parse_reason": payload.get("regno_parse_reason"),
                "parse_confidence": payload.get("regno_parse_confidence"),
            }
            field_meta = {
                "source_hint": LEGACY_SOURCE_KEY,
                "is_stub": True,
                "company_name": extracted.get("company_name"),
                "product_name": extracted.get("product_name"),
                "management_class_raw": extracted.get("management_class_raw"),
            }

            if dry_run:
                rep.promoted += 1
                continue

            if existing is None:
                existing = Registration(
                    registration_no=canonical,
                    approval_date=approval_date,
                    expiry_date=expiry_date,
                    field_meta=field_meta,
                    raw_json=raw_meta,
                )
                db.add(existing)
                rep.promoted += 1
                seen_canonical_in_run.add(canonical)
            else:
                if not existing.approval_date and approval_date:
                    existing.approval_date = approval_date
                if not existing.expiry_date and expiry_date:
                    existing.expiry_date = expiry_date
                existing.field_meta = {**(existing.field_meta or {}), **field_meta}
                existing.raw_json = {**(existing.raw_json or {}), **raw_meta}
                rep.promoted += 1
                seen_canonical_in_run.add(canonical)

    return rep


def create_legacy_product_stubs(
    db: Session,
    *,
    dry_run: bool,
    limit: int | None = None,
    offset: int = 0,
    source_key: str = LEGACY_SOURCE_KEY,
) -> LegacyProductStubReport:
    rep = LegacyProductStubReport()
    stmt = (
        select(Registration)
        .where(
            or_(
                Registration.field_meta["source_hint"].astext == source_key,
                Registration.raw_json["source_key"].astext == source_key,
            )
        )
        .order_by(Registration.created_at.asc())
        .offset(offset)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    regs = list(db.scalars(stmt).all())

    for reg in regs:
        rep.scanned += 1
        reg_no = str(reg.registration_no or "").strip()
        if not reg_no:
            rep.failed += 1
            continue
        product = db.scalar(select(Product).where(Product.reg_no == reg_no).limit(1))
        if product is not None:
            rep.existing += 1
            continue
        if dry_run:
            rep.created += 1
            continue

        raw = reg.raw_json if isinstance(reg.raw_json, dict) else {}
        company_name = _clip_text(str(raw.get("company_name") or "").strip() or None, 255)
        product_name = _clip_text(str(raw.get("product_name") or "").strip() or f"Legacy-{reg_no}", 500) or f"Legacy-{reg_no}"
        company = _ensure_company(db, company_name)

        stub = Product(
            udi_di=_stub_udi_di(reg_no),
            reg_no=reg_no,
            registration_id=reg.id,
            company_id=company.id if company is not None else None,
            name=product_name,
            model=_clip_text(str(raw.get("model") or "").strip() or None, 255),
            status="ACTIVE",
            is_ivd=True,
            ivd_category="legacy",
            raw_json={
                "_stub": {
                    "source_hint": source_key,
                    "verified_by_nmpa": True,
                },
                "registration_no_raw": raw.get("registration_no_raw"),
                "registration_no_norm": reg_no,
            },
            raw={
                "source_hint": source_key,
                "registration_raw_meta": {
                    "storage_uri": raw.get("storage_uri"),
                    "file_sha256": raw.get("file_sha256"),
                    "row_index": raw.get("row_index"),
                },
            },
        )
        # HARD-2: product.reg_no must equal registrations.registration_no
        if stub.reg_no != reg_no:
            rep.failed += 1
            continue
        db.add(stub)
        rep.created += 1
    return rep


def _resolve_param_code_aliases(db: Session) -> tuple[dict[str, str], Counter[str]]:
    existing_codes = {str(x) for x in db.scalars(select(ProductParam.param_code).distinct()).all() if x}
    mapping: dict[str, str] = {}
    candidate_counter: Counter[str] = Counter()
    for src_field, candidates in _LEGACY_PARAM_FIELD_CANDIDATES.items():
        target = None
        for code in candidates:
            if code in existing_codes:
                target = code
                break
        if target is None and src_field in {"生产国或地区", "生产国或地区英文"}:
            target = "country_or_region"
        if target is None:
            candidate_counter[src_field] += 1
            continue
        mapping[src_field] = target
    return mapping, candidate_counter


def _latest_params_for_regnos(db: Session, reg_nos: list[str], param_codes: list[str]) -> dict[tuple[str, str], tuple[str | None, str]]:
    if not reg_nos or not param_codes:
        return {}
    rows = db.execute(
        text(
            """
            SELECT DISTINCT ON (registry_no, param_code)
                   id::text AS id,
                   registry_no,
                   param_code,
                   value_text
            FROM product_params
            WHERE registry_no = ANY(:reg_nos)
              AND param_code = ANY(:param_codes)
            ORDER BY registry_no, param_code, created_at DESC
            """
        ),
        {"reg_nos": reg_nos, "param_codes": param_codes},
    ).mappings().all()
    out: dict[tuple[str, str], tuple[str | None, str]] = {}
    for r in rows:
        k = (str(r["registry_no"]), str(r["param_code"]))
        out[k] = ((str(r["value_text"]).strip() if r["value_text"] is not None else None), str(r["id"]))
    return out


def backfill_legacy_params(
    db: Session,
    *,
    dry_run: bool,
    limit: int | None = None,
    offset: int = 0,
    source_key: str = LEGACY_SOURCE_KEY,
    batch_size: int = 1000,
    only_missing: bool = True,
) -> LegacyParamsBackfillReport:
    rep = LegacyParamsBackfillReport()
    param_mapping, initial_candidates = _resolve_param_code_aliases(db)
    rep.candidates_top10.update(initial_candidates)
    if not param_mapping:
        rep.skipped_invalid_key += 1
        return rep

    scanned = 0
    local_offset = offset
    hard_limit = int(limit) if limit is not None else None

    raw_doc_cache: dict[str, str | None] = {}
    while True:
        chunk = batch_size
        if hard_limit is not None:
            remain = hard_limit - scanned
            if remain <= 0:
                break
            chunk = min(chunk, remain)
        rows = list(db.scalars(_select_raw_rows(source_key, None, offset=local_offset, limit=chunk)).all())
        if not rows:
            break
        local_offset += len(rows)
        scanned += len(rows)

        pending_rows: list[tuple[RawSourceRecord, str, dict[str, Any], str, str, str]] = []
        reg_nos: set[str] = set()
        for rec in rows:
            rep.scanned += 1
            payload = rec.payload if isinstance(rec.payload, dict) else {}
            extracted = _extract_fields_from_payload(payload)
            canonical, _, _ = _canonical_from_payload(payload, extracted)
            if not canonical:
                rep.failed += 1
                continue
            for src_field, code in param_mapping.items():
                val = _pick_text(payload.get("data") or {}, src_field)
                if not val:
                    continue
                pending_rows.append((rec, canonical, extracted, src_field, code, val))
                reg_nos.add(canonical)

        existing_map = _latest_params_for_regnos(db, sorted(reg_nos), sorted(set(param_mapping.values())))
        product_map = {
            str(p.reg_no): str(p.id)
            for p in db.scalars(select(Product).where(Product.reg_no.in_(sorted(reg_nos)))).all()
            if p.reg_no
        }

        for rec, canonical, extracted, src_field, code, value_text in pending_rows:
            key = (canonical, code)
            existing = existing_map.get(key)
            if existing:
                existing_value, existing_id = existing
                if existing_value and only_missing:
                    rep.skipped_existing += 1
                    continue
                if dry_run:
                    rep.written += 1
                    rep.per_key_written_counts[code] += 1
                    continue
                db.execute(
                    text(
                        """
                        UPDATE product_params
                        SET value_text = :value_text,
                            conditions = CAST(:conditions AS jsonb),
                            evidence_json = CAST(:evidence_json AS jsonb),
                            evidence_text = :evidence_text,
                            confidence = :confidence,
                            extract_version = :extract_version,
                            param_key_version = 1,
                            observed_at = NOW()
                        WHERE id = CAST(:id AS uuid)
                        """
                    ),
                    {
                        "id": existing_id,
                        "value_text": value_text,
                        "conditions": json.dumps({"source_key": source_key, "mode": "legacy_backfill_only_missing"}, ensure_ascii=False),
                        "evidence_json": json.dumps(
                            {
                                "source_key": source_key,
                                "storage_uri": (rec.payload or {}).get("storage_uri"),
                                "file_sha256": (rec.payload or {}).get("file_sha256"),
                                "row_index": (rec.payload or {}).get("row_index"),
                            },
                            ensure_ascii=False,
                        ),
                        "evidence_text": f"{source_key}: {canonical}/{code}",
                        "confidence": 0.82,
                        "extract_version": "legacy_backfill_v1",
                    },
                )
                rep.written += 1
                rep.per_key_written_counts[code] += 1
                continue

            if dry_run:
                rep.written += 1
                rep.per_key_written_counts[code] += 1
                continue

            file_sha = str((rec.payload or {}).get("file_sha256") or "").strip()
            if file_sha not in raw_doc_cache:
                raw_id = db.execute(
                    text(
                        """
                        SELECT id::text
                        FROM raw_documents
                        WHERE source = :source
                          AND sha256 = :sha
                        ORDER BY fetched_at DESC
                        LIMIT 1
                        """
                    ),
                    {"source": source_key, "sha": file_sha},
                ).scalar_one_or_none()
                raw_doc_cache[file_sha] = str(raw_id) if raw_id else None
            raw_doc_id = raw_doc_cache.get(file_sha)
            if raw_doc_id is None:
                rep.failed += 1
                continue
            db.execute(
                text(
                    """
                    INSERT INTO product_params (
                        di, registry_no, product_id, param_code, value_num, value_text, unit,
                        range_low, range_high, conditions, evidence_json, evidence_text, evidence_page,
                        raw_document_id, confidence, extract_version, param_key_version, observed_at
                    ) VALUES (
                        NULL, :registry_no, CAST(:product_id AS uuid), :param_code, NULL, :value_text, NULL,
                        NULL, NULL, CAST(:conditions AS jsonb), CAST(:evidence_json AS jsonb), :evidence_text, NULL,
                        CAST(:raw_document_id AS uuid), :confidence, :extract_version, 1, NOW()
                    )
                    ON CONFLICT (product_id, param_code, extract_version)
                    WHERE product_id IS NOT NULL
                    DO UPDATE
                    SET value_text = EXCLUDED.value_text,
                        conditions = EXCLUDED.conditions,
                        evidence_json = EXCLUDED.evidence_json,
                        evidence_text = EXCLUDED.evidence_text,
                        confidence = EXCLUDED.confidence,
                        param_key_version = EXCLUDED.param_key_version,
                        observed_at = EXCLUDED.observed_at
                    WHERE product_params.value_text IS NULL
                       OR btrim(COALESCE(product_params.value_text, '')) = ''
                    """
                ),
                {
                    "registry_no": canonical,
                    "product_id": product_map.get(canonical),
                    "param_code": code,
                    "value_text": value_text,
                    "conditions": json.dumps({"source_key": source_key, "mode": "legacy_backfill_insert"}, ensure_ascii=False),
                    "evidence_json": json.dumps(
                        {
                            "source_key": source_key,
                            "storage_uri": (rec.payload or {}).get("storage_uri"),
                            "file_sha256": file_sha,
                            "row_index": (rec.payload or {}).get("row_index"),
                            "raw_field_name": src_field,
                        },
                        ensure_ascii=False,
                    ),
                    "evidence_text": f"{source_key}: {canonical}/{code}",
                    "raw_document_id": raw_doc_id,
                    "confidence": 0.82,
                    "extract_version": "legacy_backfill_v1",
                },
            )
            rep.written += 1
            rep.per_key_written_counts[code] += 1
    return rep
