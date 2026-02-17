from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import (
    Company,
    CompanyAlias,
    MethodologyNode,
    ProcurementLot,
    ProcurementProject,
    ProcurementRegistrationMap,
    ProcurementResult,
    Product,
    RawDocument,
    RegistrationMethodology,
)
from app.pipeline.ingest import save_raw_document
from app.pipeline.source_run_context import source_run
from app.repositories.procurement import ProcurementRollbackResult, rollback_procurement_by_source_run
from app.services.company_resolution import normalize_company_name


def _pick(row: dict[str, Any], keys: list[str]) -> str | None:
    for k in keys:
        if k in row and row[k] is not None:
            v = str(row[k]).strip()
            if v:
                return v
    return None


def _parse_date(v: str | None) -> date | None:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    # Accept common date formats.
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def _parse_price(v: str | None) -> float | None:
    if not v:
        return None
    s = str(v).strip().replace(",", "")
    s = re.sub(r"[^\d.\-]", "", s)
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _norm_key(text_value: str | None) -> str:
    s = unicodedata.normalize("NFKC", str(text_value or ""))
    s = re.sub(r"\s+", "", s).upper()
    out: list[str] = []
    for ch in s:
        o = ord(ch)
        if "0" <= ch <= "9" or "A" <= ch <= "Z" or (0x4E00 <= o <= 0x9FFF):
            out.append(ch)
    return "".join(out)


def _extract_rows(content: bytes, suffix_hint: str | None) -> list[dict[str, Any]]:
    suffix = (suffix_hint or "").lower().strip()
    if suffix in {"json", ".json"}:
        data = json.loads(content.decode("utf-8", errors="ignore"))
        if isinstance(data, list):
            return [dict(x) for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            if isinstance(data.get("rows"), list):
                return [dict(x) for x in data["rows"] if isinstance(x, dict)]
            return [data]
        return []

    text_content = content.decode("utf-8", errors="ignore")
    return [dict(r) for r in csv.DictReader(io.StringIO(text_content))]


def _map_row(row: dict[str, Any], province: str) -> dict[str, Any]:
    project_title = _pick(row, ["project_title", "title", "项目", "项目名称"]) or "未命名项目"
    lot_name = _pick(row, ["lot_name", "lot", "包组", "分包", "标段"]) or "未命名分包"
    catalog_item_raw = _pick(row, ["catalog_item_raw", "catalog_item", "目录项原文", "目录项"])
    catalog_item_std = _pick(row, ["catalog_item_std", "目录项标准化", "目录项标准", "目录项"])
    win_company_text = _pick(row, ["win_company_text", "winning_company", "中标企业", "中选企业", "企业名称"])
    publish_date = _parse_date(_pick(row, ["publish_date", "发布日期", "公告日期"]))
    status = _pick(row, ["status", "状态"])
    bid_price = _parse_price(_pick(row, ["bid_price", "price", "中标价", "中选价"]))
    currency = _pick(row, ["currency", "币种"]) or "CNY"
    return {
        "province": province,
        "project_title": project_title,
        "lot_name": lot_name,
        "catalog_item_raw": catalog_item_raw,
        "catalog_item_std": catalog_item_std,
        "win_company_text": win_company_text,
        "bid_price": bid_price,
        "currency": currency,
        "publish_date": publish_date,
        "status": status,
        "raw": dict(row),
    }


def _resolve_company_id(db: Session, company_text: str | None) -> UUID | None:
    if not company_text:
        return None
    norm = normalize_company_name(company_text)
    if not norm:
        return None
    alias = db.scalar(select(CompanyAlias).where(CompanyAlias.alias_name == norm))
    if alias is not None:
        return alias.company_id
    company = db.scalar(select(Company).where(Company.name == norm))
    if company is not None:
        return company.id
    return None


def _build_methodology_keyword_map(db: Session) -> list[tuple[UUID, list[str]]]:
    rows = db.scalars(select(MethodologyNode).where(MethodologyNode.is_active.is_(True))).all()
    out: list[tuple[UUID, list[str]]] = []
    for n in rows:
        syns = getattr(n, "synonyms", None)
        vals = [str(n.name)]
        if isinstance(syns, list):
            vals.extend(str(x) for x in syns if str(x).strip())
        keys = list(dict.fromkeys([_norm_key(v) for v in vals if _norm_key(v)]))
        if keys:
            out.append((n.id, keys))
    return out


def _infer_lot_methodologies(catalog_item_std: str | None, method_keys: list[tuple[UUID, list[str]]]) -> set[UUID]:
    blob = _norm_key(catalog_item_std)
    if not blob:
        return set()
    mids: set[UUID] = set()
    for mid, keys in method_keys:
        if any(k in blob for k in keys):
            mids.add(mid)
    return mids


def _candidate_rows_for_lot(db: Session, catalog_item_std: str, limit: int = 30) -> list[dict[str, Any]]:
    if not catalog_item_std.strip():
        return []
    query = text(
        """
        SELECT
          p.registration_id AS registration_id,
          max(similarity(:q, p.name)) AS name_sim,
          max(similarity(:q, COALESCE(r.raw_json::text, ''))) AS raw_sim,
          bool_or(p.company_id IS NOT NULL) AS has_company
        FROM products p
        JOIN registrations r ON r.id = p.registration_id
        WHERE p.registration_id IS NOT NULL
          AND (
            similarity(:q, p.name) > 0.10
            OR similarity(:q, COALESCE(r.raw_json::text, '')) > 0.05
          )
        GROUP BY p.registration_id
        ORDER BY GREATEST(max(similarity(:q, p.name)), max(similarity(:q, COALESCE(r.raw_json::text, '')))) DESC
        LIMIT :lim
        """
    )
    rows = db.execute(query, {"q": catalog_item_std, "lim": int(limit)}).mappings().all()
    return [dict(r) for r in rows]


def _registration_methodologies(db: Session, registration_id: UUID) -> set[UUID]:
    mids = db.scalars(
        select(RegistrationMethodology.methodology_id).where(RegistrationMethodology.registration_id == registration_id)
    ).all()
    return set(mids)


def _company_match_for_registration(db: Session, registration_id: UUID, win_company_id: UUID | None) -> bool:
    if win_company_id is None:
        return False
    q = select(func.count()).select_from(Product).where(
        Product.registration_id == registration_id,
        Product.company_id == win_company_id,
    )
    return int(db.scalar(q) or 0) > 0


def _upsert_rule_maps_for_lot(
    db: Session,
    *,
    lot_id: UUID,
    catalog_item_std: str | None,
    win_company_id: UUID | None,
    method_keys: list[tuple[UUID, list[str]]],
    dry_run: bool,
) -> tuple[int, list[dict[str, Any]]]:
    if not catalog_item_std or not catalog_item_std.strip():
        return 0, []

    candidates = _candidate_rows_for_lot(db, catalog_item_std.strip(), limit=30)
    if not candidates:
        return 0, []

    lot_mids = _infer_lot_methodologies(catalog_item_std, method_keys)
    ranked: list[dict[str, Any]] = []
    for c in candidates:
        rid = c.get("registration_id")
        if rid is None:
            continue
        registration_id = UUID(str(rid))
        name_sim = float(c.get("name_sim") or 0.0)
        raw_sim = float(c.get("raw_sim") or 0.0)
        base = max(name_sim, raw_sim * 0.8)
        method_bonus = 0.0
        company_bonus = 0.0

        if lot_mids:
            reg_mids = _registration_methodologies(db, registration_id)
            if reg_mids and (reg_mids & lot_mids):
                method_bonus = 0.15

        if _company_match_for_registration(db, registration_id, win_company_id):
            company_bonus = 0.12

        final_score = min(0.99, base + method_bonus + company_bonus)
        if final_score < 0.20:
            continue
        ranked.append(
            {
                "registration_id": registration_id,
                "confidence": round(final_score, 2),
                "explain": {
                    "name_similarity": round(name_sim, 4),
                    "raw_similarity": round(raw_sim, 4),
                    "methodology_bonus": method_bonus,
                    "company_bonus": company_bonus,
                },
            }
        )

    ranked.sort(key=lambda x: float(x["confidence"]), reverse=True)
    top = ranked[:3]
    if dry_run:
        return 0, top

    upserted = 0
    for r in top:
        stmt = insert(ProcurementRegistrationMap).values(
            lot_id=lot_id,
            registration_id=r["registration_id"],
            match_type="rule",
            confidence=float(r["confidence"]),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ProcurementRegistrationMap.lot_id, ProcurementRegistrationMap.registration_id],
            set_={
                "match_type": "rule",
                "confidence": stmt.excluded.confidence,
            },
        )
        db.execute(stmt)
        upserted += 1
    return upserted, top


@dataclass(frozen=True)
class ProcurementIngestResult:
    source_run_id: int
    raw_run_id: str
    raw_document_id: UUID
    fetched_count: int
    parsed_count: int
    failed_count: int
    projects: int
    lots: int
    results: int
    maps: int
    sample_mappings: list[dict[str, Any]]


def ingest_procurement_snapshot(
    db: Session,
    *,
    province: str,
    content: bytes,
    source_url: str | None,
    doc_type: str,
    dry_run: bool,
) -> ProcurementIngestResult:
    province_clean = str(province or "").strip()
    if not province_clean:
        raise ValueError("--province is required")

    with source_run(
        db,
        source="procurement",
        download_url=source_url,
        source_notes={"province": province_clean, "dry_run": bool(dry_run)},
    ) as (run, raw_run_id, stats):
        raw_document_id = save_raw_document(
            db,
            source="PROCUREMENT",
            url=source_url,
            content=content,
            doc_type=doc_type,
            run_id=raw_run_id,
        )

        fetched_count = 1
        failed_count = 0
        mapped_rows: list[dict[str, Any]] = []
        try:
            suffix = (Path(source_url).suffix.lower().lstrip(".") if source_url else doc_type)
            rows = _extract_rows(content, suffix_hint=suffix)
            mapped_rows = [_map_row(r, province_clean) for r in rows]
        except Exception as exc:
            failed_count = 1
            doc = db.get(RawDocument, raw_document_id)
            if doc is not None:
                doc.parse_status = "FAILED"
                doc.error = str(exc)
                doc.parse_log = {
                    "kind": "procurement_snapshot",
                    "province": province_clean,
                    "error": str(exc),
                    "parsed_at": datetime.now(timezone.utc).isoformat(),
                }
                db.add(doc)
                db.commit()
            raise

        projects_cnt = 0
        lots_cnt = 0
        results_cnt = 0
        maps_cnt = 0
        sample_mappings: list[dict[str, Any]] = []
        method_keys = _build_methodology_keyword_map(db)
        project_cache: dict[tuple[str, str, date | None], UUID] = {}

        if not dry_run:
            for r in mapped_rows:
                pkey = (r["province"], r["project_title"], r["publish_date"])
                project_id = project_cache.get(pkey)
                if project_id is None:
                    project = ProcurementProject(
                        province=r["province"],
                        title=r["project_title"],
                        publish_date=r["publish_date"],
                        status=r["status"],
                        raw_document_id=raw_document_id,
                        source_run_id=int(run.id),
                    )
                    db.add(project)
                    db.flush()
                    project_id = project.id
                    project_cache[pkey] = project_id
                    projects_cnt += 1

                lot = ProcurementLot(
                    project_id=project_id,
                    lot_name=r["lot_name"],
                    catalog_item_raw=r["catalog_item_raw"],
                    catalog_item_std=r["catalog_item_std"],
                )
                db.add(lot)
                db.flush()
                lots_cnt += 1

                win_company_id = _resolve_company_id(db, r["win_company_text"])
                result = ProcurementResult(
                    lot_id=lot.id,
                    win_company_id=win_company_id,
                    win_company_text=r["win_company_text"],
                    bid_price=r["bid_price"],
                    currency=r["currency"],
                    publish_date=r["publish_date"],
                    raw_document_id=raw_document_id,
                )
                db.add(result)
                db.flush()
                results_cnt += 1

                m_upserted, top = _upsert_rule_maps_for_lot(
                    db,
                    lot_id=lot.id,
                    catalog_item_std=r["catalog_item_std"],
                    win_company_id=win_company_id,
                    method_keys=method_keys,
                    dry_run=False,
                )
                maps_cnt += int(m_upserted)
                if top and len(sample_mappings) < 20:
                    sample_mappings.append(
                        {
                            "lot_id": str(lot.id),
                            "catalog_item_std": r["catalog_item_std"],
                            "matches": [
                                {
                                    "registration_id": str(x["registration_id"]),
                                    "confidence": float(x["confidence"]),
                                    "explain": x["explain"],
                                }
                                for x in top
                            ],
                        }
                    )
            db.commit()
        else:
            # dry-run: evaluate mapping explainability on synthetic lot ids.
            for r in mapped_rows[:200]:
                win_company_id = _resolve_company_id(db, r["win_company_text"])
                _, top = _upsert_rule_maps_for_lot(
                    db,
                    lot_id=UUID("00000000-0000-0000-0000-000000000000"),
                    catalog_item_std=r["catalog_item_std"],
                    win_company_id=win_company_id,
                    method_keys=method_keys,
                    dry_run=True,
                )
                if top and len(sample_mappings) < 20:
                    sample_mappings.append(
                        {
                            "catalog_item_std": r["catalog_item_std"],
                            "matches": [
                                {
                                    "registration_id": str(x["registration_id"]),
                                    "confidence": float(x["confidence"]),
                                    "explain": x["explain"],
                                }
                                for x in top
                            ],
                        }
                    )

        parsed_count = len(mapped_rows)
        doc = db.get(RawDocument, raw_document_id)
        if doc is not None:
            doc.parse_status = "PARSED"
            doc.parse_log = {
                "kind": "procurement_snapshot",
                "province": province_clean,
                "dry_run": bool(dry_run),
                "rows_total": parsed_count,
                "projects": projects_cnt,
                "lots": lots_cnt,
                "results": results_cnt,
                "maps": maps_cnt,
                "source_run_id": int(run.id),
                "sample_mappings": sample_mappings[:10],
                "parsed_at": datetime.now(timezone.utc).isoformat(),
            }
            db.add(doc)
            db.commit()

        stats.update(
            {
                "fetched_count": fetched_count,
                "parsed_count": parsed_count,
                "failed_count": failed_count,
                "added": projects_cnt + lots_cnt + results_cnt + maps_cnt,
                "projects": projects_cnt,
                "lots": lots_cnt,
                "results": results_cnt,
                "maps": maps_cnt,
            }
        )

        return ProcurementIngestResult(
            source_run_id=int(run.id),
            raw_run_id=raw_run_id,
            raw_document_id=raw_document_id,
            fetched_count=fetched_count,
            parsed_count=parsed_count,
            failed_count=failed_count,
            projects=projects_cnt,
            lots=lots_cnt,
            results=results_cnt,
            maps=maps_cnt,
            sample_mappings=sample_mappings,
        )


def ingest_procurement_from_file(
    db: Session,
    *,
    province: str,
    file_path: str | Path,
    dry_run: bool,
) -> ProcurementIngestResult:
    fp = Path(file_path)
    content = fp.read_bytes()
    return ingest_procurement_snapshot(
        db,
        province=province,
        content=content,
        source_url=str(fp),
        doc_type=(fp.suffix.lstrip(".").lower() or "csv"),
        dry_run=dry_run,
    )


def rollback_procurement_ingest(
    db: Session,
    *,
    source_run_id: int,
    dry_run: bool,
) -> ProcurementRollbackResult:
    return rollback_procurement_by_source_run(db, source_run_id=int(source_run_id), dry_run=bool(dry_run))
