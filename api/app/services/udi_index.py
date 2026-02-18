from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID
import xml.etree.ElementTree as ET

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.normalize_keys import normalize_registration_no
from app.services.udi_parse import parse_packing_list, parse_storage_list


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
    total_devices: int
    di_present: int
    reg_present: int
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
    def packing_rate(self) -> float:
        return (self.packing_present / self.total_devices) if self.total_devices else 0.0

    @property
    def storage_rate(self) -> float:
        return (self.storage_present / self.total_devices) if self.total_devices else 0.0


def iter_devices_from_xml_files(paths: Iterable[Path]) -> Iterable[ET.Element]:
    for p in paths:
        if not p.is_file() or p.suffix.lower() != ".xml":
            continue
        # Stream parse to avoid loading full UDI exports into memory.
        for _event, elem in ET.iterparse(str(p), events=("end",)):
            if elem.tag != "device":
                continue
            yield elem
            elem.clear()


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
) -> UdiIndexReport:
    xml_files = sorted([p for p in staging_dir.rglob("*.xml") if p.is_file()])

    report = UdiIndexReport(
        total_devices=0,
        di_present=0,
        reg_present=0,
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
            raw_document_id = COALESCE(EXCLUDED.raw_document_id, udi_device_index.raw_document_id),
            source_run_id = COALESCE(EXCLUDED.source_run_id, udi_device_index.source_run_id),
            updated_at = NOW()
        """
    )

    for dev in iter_devices_from_xml_files(xml_files):
        if limit is not None and report.total_devices >= limit:
            break
        report.total_devices += 1
        row = _extract_device_row(dev, raw_document_id=raw_document_id, source_run_id=source_run_id)
        if row is None:
            continue
        report.di_present += 1
        if row.get("registration_no_norm"):
            report.reg_present += 1

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
                report.sample_packing_json.append({"di_norm": str(row.get("di_norm")), "packing_json": packings})
        if isinstance(storages, list) and len(storages) > 0:
            report.storage_present += 1
            if len(report.sample_storage_json) < 2:
                report.sample_storage_json.append({"di_norm": str(row.get("di_norm")), "storage_json": storages})

        if dry_run:
            continue
        db.execute(upsert_sql, row)
        report.upserted += 1

    if not dry_run:
        db.commit()
    return report

