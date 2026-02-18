from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID
import xml.etree.ElementTree as ET
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.normalize_keys import normalize_registration_no
from app.services.udi_parse import parse_packing_list, parse_storage_list


_PART_RE = re.compile(r"PART(\d+)_Of_(\d+)", re.IGNORECASE)


class UdiXmlParseError(RuntimeError):
    def __init__(self, path: Path, err: Exception):
        super().__init__(f"{path.name}: {err}")
        self.path = path
        self.err = err


def _extract_part_no(path: Path) -> int | None:
    m = _PART_RE.search(path.name)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _t(dev: ET.Element, tag: str) -> str | None:
    el = dev.find(tag)
    if el is None or el.text is None:
        return None
    s = el.text.strip()
    return s or None


def _as_date(v: str | None) -> date | None:
    if not v:
        return None
    s = v.strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def _as_int(v: str | None) -> int | None:
    if not v:
        return None
    s = v.strip()
    if not s:
        return None
    try:
        return int(float(s))
    except Exception:
        return None


@dataclass
class UdiIndexReport:
    files_total: int
    files_seen: int
    files_failed: int
    file_errors: list[dict[str, Any]]
    total_devices: int
    di_present: int
    reg_present: int
    has_cert_yes: int
    packing_present: int
    storage_present: int
    sample_packing_json: list[dict[str, Any]]
    sample_storage_json: list[dict[str, Any]]
    upserted: int = 0

    @property
    def di_non_empty_rate(self) -> float:
        return (self.di_present / self.total_devices) if self.total_devices else 0.0

    @property
    def reg_non_empty_rate(self) -> float:
        return (self.reg_present / self.total_devices) if self.total_devices else 0.0

    @property
    def has_cert_yes_rate(self) -> float:
        return (self.has_cert_yes / self.total_devices) if self.total_devices else 0.0

    @property
    def packing_rate(self) -> float:
        return (self.packing_present / self.total_devices) if self.total_devices else 0.0

    @property
    def storage_rate(self) -> float:
        return (self.storage_present / self.total_devices) if self.total_devices else 0.0


def iter_devices_from_xml_file(path: Path, *, max_devices: int | None) -> Iterable[ET.Element]:
    if not path.is_file() or path.suffix.lower() != ".xml":
        return

    # Stream parse to avoid loading full UDI exports into memory.
    # NOTE: We open the file explicitly so we can early-break on max_devices and still close cleanly.
    seen = 0
    try:
        with path.open("rb") as f:
            for _event, elem in ET.iterparse(f, events=("end",)):
                if elem.tag != "device":
                    continue
                yield elem
                elem.clear()
                seen += 1
                if max_devices is not None and seen >= max_devices:
                    break
    except ET.ParseError as e:
        raise UdiXmlParseError(path, e) from e


def _extract_device_row(
    dev: ET.Element,
    *,
    raw_document_id: UUID | None,
    source_run_id: int | None,
) -> dict[str, Any] | None:
    di = _t(dev, "zxxsdycpbs")
    di_norm = (di or "").strip() or None
    if not di_norm:
        return None

    raw_reg = _t(dev, "zczbhhzbapzbh")
    reg_norm = normalize_registration_no(raw_reg)
    has_cert = (_t(dev, "sfyzcbayz") == "是")

    pack_obj = parse_packing_list(dev)
    stor_obj = parse_storage_list(dev)
    packings = pack_obj.get("packings") if isinstance(pack_obj, dict) else None
    storages = stor_obj.get("storages") if isinstance(stor_obj, dict) else None
    if not isinstance(packings, list):
        packings = []
    if not isinstance(storages, list):
        storages = []

    row: dict[str, Any] = {
        "di_norm": di_norm,
        "registration_no_norm": (reg_norm or None),
        "has_cert": bool(has_cert),
        "model_spec": _t(dev, "ggxh"),
        "sku_code": _t(dev, "cphhhbh"),
        "product_name": _t(dev, "cpmctymc"),
        "brand": _t(dev, "spmc"),
        "description": _t(dev, "cpms"),
        "category_big": _t(dev, "qxlb"),
        "class_code": _t(dev, "flbm"),
        "product_type": _t(dev, "cplb"),
        "issuer_standard": _t(dev, "cpbsbmtxmc"),
        "publish_date": _as_date(_t(dev, "cpbsfbrq")),
        "barcode_carrier": _t(dev, "bszt"),
        "manufacturer_cn": _t(dev, "ylqxzcrbarmc"),
        "manufacturer_en": _t(dev, "ylqxzcrbarywmc"),
        "uscc": _t(dev, "tyshxydm"),
        # Contract requirement: store packings/storages arrays in the index.
        "packing_json": json.dumps(packings, ensure_ascii=False, default=str),
        "storage_json": json.dumps(storages, ensure_ascii=False, default=str),
        "mjfs": _t(dev, "mjfs"),
        "tscchcztj": _t(dev, "tscchcztj"),
        "tsccsm": _t(dev, "tsccsm"),
        "version_number": _as_int(_t(dev, "versionNumber")),
        "version_time": _as_date(_t(dev, "versionTime")),
        "version_status": _t(dev, "versionStauts"),
        "correction_number": _as_int(_t(dev, "correctionNumber")),
        "correction_remark": _t(dev, "correctionRemark"),
        "correction_time": _t(dev, "correctionTime"),
        "device_record_key": _t(dev, "deviceRecordKey"),
        # Label codes (write into index so later stages don't need to re-read XML).
        "scbssfbhxlh": _t(dev, "scbssfbhxlh"),
        "scbssfbhscrq": _t(dev, "scbssfbhscrq"),
        "scbssfbhsxrq": _t(dev, "scbssfbhsxrq"),
        "scbssfbhph": _t(dev, "scbssfbhph"),
        "raw_document_id": (str(raw_document_id) if raw_document_id else None),
        "source_run_id": (int(source_run_id) if source_run_id is not None else None),
    }
    return row


def run_udi_device_index(
    db: Session,
    *,
    staging_dir: Path,
    raw_document_id: UUID | None,
    source_run_id: int | None,
    dry_run: bool,
    limit: int | None = None,
    limit_files: int | None = None,
    max_devices_per_file: int | None = None,
    part_from: int | None = None,
    part_to: int | None = None,
) -> UdiIndexReport:
    xml_files = sorted([p for p in staging_dir.rglob("*.xml") if p.is_file()])
    files_total = len(xml_files)

    # Part-range filter (by file name). Intended for standardized full-release imports.
    if part_from is not None or part_to is not None:
        lo = int(part_from) if part_from is not None else 1
        hi = int(part_to) if part_to is not None else 10**9
        filtered: list[Path] = []
        for p in xml_files:
            n = _extract_part_no(p)
            if n is None:
                continue
            if lo <= n <= hi:
                filtered.append(p)
        xml_files = sorted(filtered)
    elif limit_files is not None and limit_files >= 0:
        xml_files = xml_files[:limit_files]
    files_seen = len(xml_files)

    report = UdiIndexReport(
        files_total=files_total,
        files_seen=files_seen,
        files_failed=0,
        file_errors=[],
        total_devices=0,
        di_present=0,
        reg_present=0,
        has_cert_yes=0,
        packing_present=0,
        storage_present=0,
        sample_packing_json=[],
        sample_storage_json=[],
        upserted=0,
    )

    upsert_sql = text(
        """
        INSERT INTO udi_device_index (
            di_norm, registration_no_norm, has_cert,
            model_spec, sku_code, product_name, brand, description,
            category_big, class_code, product_type,
            issuer_standard, publish_date, barcode_carrier,
            manufacturer_cn, manufacturer_en, uscc,
            packing_json, storage_json,
            mjfs, tscchcztj, tsccsm,
            version_number, version_time, version_status,
            correction_number, correction_remark, correction_time,
            device_record_key,
            scbssfbhxlh, scbssfbhscrq, scbssfbhsxrq, scbssfbhph,
            raw_document_id, source_run_id,
            updated_at
        ) VALUES (
            :di_norm, :registration_no_norm, :has_cert,
            :model_spec, :sku_code, :product_name, :brand, :description,
            :category_big, :class_code, :product_type,
            :issuer_standard, :publish_date, :barcode_carrier,
            :manufacturer_cn, :manufacturer_en, :uscc,
            CAST(:packing_json AS jsonb), CAST(:storage_json AS jsonb),
            :mjfs, :tscchcztj, :tsccsm,
            :version_number, :version_time, :version_status,
            :correction_number, :correction_remark, :correction_time,
            :device_record_key,
            :scbssfbhxlh, :scbssfbhscrq, :scbssfbhsxrq, :scbssfbhph,
            CAST(:raw_document_id AS uuid), :source_run_id,
            NOW()
        )
        ON CONFLICT (di_norm) DO UPDATE SET
            registration_no_norm = EXCLUDED.registration_no_norm,
            has_cert = EXCLUDED.has_cert,
            model_spec = EXCLUDED.model_spec,
            sku_code = EXCLUDED.sku_code,
            product_name = EXCLUDED.product_name,
            brand = EXCLUDED.brand,
            description = EXCLUDED.description,
            category_big = EXCLUDED.category_big,
            class_code = EXCLUDED.class_code,
            product_type = EXCLUDED.product_type,
            issuer_standard = EXCLUDED.issuer_standard,
            publish_date = EXCLUDED.publish_date,
            barcode_carrier = EXCLUDED.barcode_carrier,
            manufacturer_cn = EXCLUDED.manufacturer_cn,
            manufacturer_en = EXCLUDED.manufacturer_en,
            uscc = EXCLUDED.uscc,
            packing_json = EXCLUDED.packing_json,
            storage_json = EXCLUDED.storage_json,
            mjfs = EXCLUDED.mjfs,
            tscchcztj = EXCLUDED.tscchcztj,
            tsccsm = EXCLUDED.tsccsm,
            version_number = EXCLUDED.version_number,
            version_time = EXCLUDED.version_time,
            version_status = EXCLUDED.version_status,
            correction_number = EXCLUDED.correction_number,
            correction_remark = EXCLUDED.correction_remark,
            correction_time = EXCLUDED.correction_time,
            device_record_key = EXCLUDED.device_record_key,
            scbssfbhxlh = EXCLUDED.scbssfbhxlh,
            scbssfbhscrq = EXCLUDED.scbssfbhscrq,
            scbssfbhsxrq = EXCLUDED.scbssfbhsxrq,
            scbssfbhph = EXCLUDED.scbssfbhph,
            raw_document_id = COALESCE(EXCLUDED.raw_document_id, udi_device_index.raw_document_id),
            -- Always stamp the latest run id so we can batch-aggregate touched registrations.
            source_run_id = EXCLUDED.source_run_id,
            updated_at = NOW()
        """
    )

    for xml_path in xml_files:
        try:
            for dev in iter_devices_from_xml_file(xml_path, max_devices=max_devices_per_file):
                if limit is not None and report.total_devices >= limit:
                    break
                report.total_devices += 1
                row = _extract_device_row(dev, raw_document_id=raw_document_id, source_run_id=source_run_id)
                if row is None:
                    continue
                report.di_present += 1
                if row.get("registration_no_norm"):
                    report.reg_present += 1
                if bool(row.get("has_cert")):
                    report.has_cert_yes += 1

                try:
                    packings = json.loads(str(row.get("packing_json") or "[]"))
                except Exception:
                    packings = []
                try:
                    storages = json.loads(str(row.get("storage_json") or "[]"))
                except Exception:
                    storages = []

                if isinstance(packings, list) and len(packings) > 0:
                    report.packing_present += 1
                    if len(report.sample_packing_json) < 2:
                        report.sample_packing_json.append(
                            {"di_norm": str(row.get("di_norm")), "packaging_json": packings}
                        )
                if isinstance(storages, list) and len(storages) > 0:
                    report.storage_present += 1
                    if len(report.sample_storage_json) < 2:
                        report.sample_storage_json.append({"di_norm": str(row.get("di_norm")), "storage_json": storages})

                if dry_run:
                    continue
                db.execute(upsert_sql, row)
                report.upserted += 1
        except UdiXmlParseError as e:
            report.files_failed += 1
            if len(report.file_errors) < 10:
                report.file_errors.append({"file": e.path.name, "error": str(e.err)})

        if limit is not None and report.total_devices >= limit:
            break

    if not dry_run:
        db.commit()
    return report


def refresh_udi_registration_index(db: Session, *, source_run_id: int) -> int:
    """Refresh udi_registration_index for registrations touched in this source_run_id.

    This keeps the batch acceptance check cheap, while still converging on correct global counts.
    """
    sql = text(
        """
        WITH touched AS (
          SELECT DISTINCT registration_no_norm
          FROM udi_device_index
          WHERE source_run_id = :run_id
            AND registration_no_norm IS NOT NULL
            AND registration_no_norm <> ''
        ),
        agg AS (
          SELECT u.registration_no_norm,
                 COUNT(*)::bigint AS di_count,
                 BOOL_OR(COALESCE(u.has_cert, FALSE)) AS has_cert_yes
          FROM udi_device_index u
          JOIN touched t ON t.registration_no_norm = u.registration_no_norm
          GROUP BY u.registration_no_norm
        )
        INSERT INTO udi_registration_index (
          registration_no_norm, di_count, has_cert_yes, source_run_id, updated_at
        )
        SELECT registration_no_norm, di_count, has_cert_yes, :run_id, NOW()
        FROM agg
        ON CONFLICT (registration_no_norm) DO UPDATE SET
          di_count = EXCLUDED.di_count,
          has_cert_yes = EXCLUDED.has_cert_yes,
          source_run_id = EXCLUDED.source_run_id,
          updated_at = NOW()
        """
    )
    res = db.execute(sql, {"run_id": int(source_run_id)})
    db.commit()
    return int(getattr(res, "rowcount", 0) or 0)
