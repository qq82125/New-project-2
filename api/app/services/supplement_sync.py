from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.models import DataSource, Product, SourceConfig
from app.repositories.radar import get_admin_config, upsert_admin_config
from app.repositories.source_runs import finish_source_run, start_source_run
from app.services.crypto import decrypt_json
from app.services.local_registry_supplement import run_local_registry_supplement
from app.services.normalize_keys import normalize_registration_no
from app.services.source_contract import upsert_registration_with_contract, write_udi_contract_record

SUPPLEMENT_SCHEDULE_KEY = 'source_supplement_schedule'
SUPPLEMENT_LAST_KEY = 'source_supplement_last_run'
NMPA_QUERY_LAST_KEY = 'source_nmpa_query_last_run'
DEFAULT_SUPPLEMENT_SOURCE_NAME = 'UDI注册证关联增强源（DI/GTIN/包装）'
DEFAULT_SUPPLEMENT_SOURCE_KEY = 'UDI_DI'
DEFAULT_NMPA_QUERY_URL = 'https://www.nmpa.gov.cn/datasearch/home-index.html?itemId=2c9ba384759c957701759ccef50f032b#category=ylqx'


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _pick_supplement_source(db: Session, source_name: str | None = None) -> DataSource | None:
    rows = list(db.scalars(select(DataSource).order_by(DataSource.id.asc())).all())
    if not rows:
        return None
    if source_name:
        for ds in rows:
            if (ds.name or '').strip() == source_name.strip():
                return ds
    for ds in rows:
        if '补全' in (ds.name or '') or '纠错' in (ds.name or '') or 'UDI' in (ds.name or '').upper():
            return ds
    return None


def _pick_supplement_source_by_key(db: Session, source_key: str | None = None) -> DataSource | None:
    key = str(source_key or '').strip().upper()
    if not key:
        return None
    cfg = db.scalar(select(SourceConfig).where(SourceConfig.source_key == key))
    if cfg is None:
        return None
    fp = cfg.fetch_params if isinstance(getattr(cfg, 'fetch_params', None), dict) else {}
    if not isinstance(fp, dict):
        fp = {}
    legacy = fp.get('legacy_data_source') if isinstance(fp.get('legacy_data_source'), dict) else {}
    name = str(legacy.get('name') or '').strip()
    if not name:
        return None
    return db.scalar(select(DataSource).where(DataSource.name == name))


def _dsn_from_config(cfg: dict[str, Any]) -> URL:
    query = {}
    sslmode = cfg.get('sslmode')
    if sslmode:
        query['sslmode'] = str(sslmode)
    return URL.create(
        'postgresql+psycopg',
        username=str(cfg.get('username') or ''),
        password=str(cfg.get('password') or ''),
        host=str(cfg.get('host') or ''),
        port=int(cfg.get('port') or 5432),
        database=str(cfg.get('database') or ''),
        query=query,
    )


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ''
    return False


def _ensure_supplement_query_columns(columns: set[str]) -> None:
    """Validate minimum contract for supplement source_query results.

    Contract:
    - Must expose `updated_at` (for recent-window semantics and observability).
    - Must expose at least one DI identifier: `udi_di` or `di`.
    - Must expose at least one registration identifier: `reg_no` or `registry_no`.
    """
    cols = {str(c).strip().lower() for c in columns if str(c).strip()}
    if 'updated_at' not in cols:
        raise RuntimeError("supplement source_query must include column: updated_at")
    if not ({'udi_di', 'di'} & cols):
        raise RuntimeError("supplement source_query must include one of: udi_di, di")
    if not ({'reg_no', 'registry_no'} & cols):
        raise RuntimeError("supplement source_query must include one of: reg_no, registry_no")


def _plan_config(db: Session) -> dict[str, Any]:
    cfg = get_admin_config(db, SUPPLEMENT_SCHEDULE_KEY)
    raw = cfg.config_value if cfg and isinstance(cfg.config_value, dict) else {}
    return {
        'enabled': bool(raw.get('enabled', False)),
        'interval_hours': max(1, int(raw.get('interval_hours', 24) or 24)),
        'batch_size': max(50, min(5000, int(raw.get('batch_size', 1000) or 1000))),
        'recent_hours': max(1, int(raw.get('recent_hours', 72) or 72)),
        'source_key': str(raw.get('source_key') or '').strip().upper() or DEFAULT_SUPPLEMENT_SOURCE_KEY,
        'source_name': str(raw.get('source_name') or '').strip() or DEFAULT_SUPPLEMENT_SOURCE_NAME,
        'nmpa_query_enabled': bool(raw.get('nmpa_query_enabled', True)),
        'nmpa_query_interval_hours': max(1, int(raw.get('nmpa_query_interval_hours', 24) or 24)),
        'nmpa_query_batch_size': max(10, min(2000, int(raw.get('nmpa_query_batch_size', 200) or 200))),
        'nmpa_query_url': str(raw.get('nmpa_query_url') or '').strip() or DEFAULT_NMPA_QUERY_URL,
        'nmpa_query_timeout_seconds': max(5, min(60, int(raw.get('nmpa_query_timeout_seconds', 20) or 20))),
    }


def _last_run_started_at(db: Session, key: str = SUPPLEMENT_LAST_KEY) -> datetime | None:
    cfg = get_admin_config(db, key)
    if not cfg or not isinstance(cfg.config_value, dict):
        return None
    raw = cfg.config_value.get('started_at')
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
    except Exception:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def should_run_supplement(db: Session) -> tuple[bool, dict[str, Any], str]:
    conf = _plan_config(db)
    if not conf['enabled']:
        return False, conf, 'disabled'
    last = _last_run_started_at(db)
    if last is None:
        return True, conf, 'first_run'
    due_at = last + timedelta(hours=int(conf['interval_hours']))
    if _utcnow() >= due_at:
        return True, conf, 'due'
    return False, conf, 'cooldown'


def should_run_nmpa_query_supplement(db: Session) -> tuple[bool, dict[str, Any], str]:
    conf = _plan_config(db)
    if not conf['nmpa_query_enabled']:
        return False, conf, 'disabled'
    last = _last_run_started_at(db, NMPA_QUERY_LAST_KEY)
    if last is None:
        return True, conf, 'first_run'
    due_at = last + timedelta(hours=int(conf['nmpa_query_interval_hours']))
    if _utcnow() >= due_at:
        return True, conf, 'due'
    return False, conf, 'cooldown'


_REG_NO_PAT = re.compile(r'[^\s"<>]{4,}械[^\s"<>]{0,12}\d{4,}')
_DATE_PAT = re.compile(r'(20\d{2}-\d{2}-\d{2})')


def _extract_nmpa_hints(text_blob: str) -> dict[str, str]:
    out: dict[str, str] = {}
    reg_m = _REG_NO_PAT.search(text_blob or '')
    if reg_m:
        out['reg_no'] = reg_m.group(0)
    dates = _DATE_PAT.findall(text_blob or '')
    if dates:
        out['approved_date'] = dates[0]
        if len(dates) > 1:
            out['expiry_date'] = dates[1]
    return out


def run_nmpa_query_supplement_now(db: Session, *, reason: str = 'manual') -> dict[str, Any]:
    conf = _plan_config(db)
    started_at = _utcnow()
    run = start_source_run(
        db,
        source='nmpa_query_supplement',
        package_name=None,
        package_md5=None,
        download_url=conf.get('nmpa_query_url'),
    )
    report: dict[str, Any] = {
        'reason': reason,
        'started_at': _to_iso(started_at),
        'finished_at': None,
        'status': 'failed',
        'query_url': conf.get('nmpa_query_url'),
        'scanned': 0,
        'matched': 0,
        'updated': 0,
        'blocked_412': 0,
        'failed': 0,
        'contract_raw_written': 0,
        'contract_map_written': 0,
        'contract_pending_written': 0,
        'contract_failed': 0,
        'message': '',
        'run_id': int(run.id),
    }

    batch_size = int(conf['nmpa_query_batch_size'])
    timeout_s = int(conf['nmpa_query_timeout_seconds'])
    cutoff = _utcnow() - timedelta(days=90)
    candidates = list(
        db.scalars(
            select(Product)
            .where(
                Product.is_ivd.is_(True),
                Product.updated_at >= cutoff,
                (
                    Product.reg_no.is_(None)
                    | Product.approved_date.is_(None)
                    | Product.expiry_date.is_(None)
                ),
            )
            .order_by(Product.updated_at.desc())
            .limit(batch_size)
        ).all()
    )

    headers = {'User-Agent': 'Mozilla/5.0 (compatible; IVDRadarBot/1.0)'}
    try:
        for p in candidates:
            report['scanned'] += 1
            keyword = (getattr(p, 'reg_no', None) or getattr(p, 'name', None) or '').strip()
            if not keyword:
                continue
            try:
                resp = requests.get(
                    str(conf.get('nmpa_query_url')),
                    params={'keyword': keyword},
                    headers=headers,
                    timeout=timeout_s,
                )
            except Exception:
                report['failed'] += 1
                continue
            if resp.status_code == 412:
                report['blocked_412'] += 1
                continue
            if resp.status_code >= 400:
                report['failed'] += 1
                continue
            hints = _extract_nmpa_hints(resp.text)
            if not hints:
                continue
            report['matched'] += 1
            changed = False
            if _is_blank(getattr(p, 'reg_no', None)) and hints.get('reg_no'):
                p.reg_no = hints['reg_no']
                changed = True
            if getattr(p, 'approved_date', None) is None and hints.get('approved_date'):
                try:
                    p.approved_date = datetime.fromisoformat(hints['approved_date']).date()
                    changed = True
                except Exception:
                    pass
            if getattr(p, 'expiry_date', None) is None and hints.get('expiry_date'):
                try:
                    p.expiry_date = datetime.fromisoformat(hints['expiry_date']).date()
                    changed = True
                except Exception:
                    pass
            if changed:
                db.add(p)
                report['updated'] += 1

        db.commit()
        report['status'] = 'success'
        report['finished_at'] = _to_iso(_utcnow())
        report['message'] = (
            f"nmpa-query supplement: scanned={report['scanned']} matched={report['matched']} "
            f"updated={report['updated']} blocked_412={report['blocked_412']}"
        )
        finish_source_run(
            db,
            run,
            status='success',
            message=report['message'],
            records_total=int(report['scanned']),
            records_success=int(report['updated']),
            records_failed=int(report['failed'] + report['blocked_412']),
            updated_count=int(report['updated']),
        )
        upsert_admin_config(db, NMPA_QUERY_LAST_KEY, report)
        return report
    except Exception as exc:
        db.rollback()
        report['status'] = 'failed'
        report['finished_at'] = _to_iso(_utcnow())
        report['message'] = str(exc)
        finish_source_run(
            db,
            run,
            status='failed',
            message=report['message'],
            records_total=int(report['scanned']),
            records_success=int(report['updated']),
            records_failed=max(1, int(report['failed'] + report['blocked_412'])),
            updated_count=int(report['updated']),
        )
        upsert_admin_config(db, NMPA_QUERY_LAST_KEY, report)
        return report


def run_supplement_sync_now(db: Session, *, reason: str = 'manual') -> dict[str, Any]:
    conf = _plan_config(db)
    source = _pick_supplement_source_by_key(db, conf.get('source_key')) or _pick_supplement_source(db, conf.get('source_name'))
    started_at = _utcnow()
    run = start_source_run(
        db,
        source='nmpa_supplement',
        package_name=None,
        package_md5=None,
        download_url=None,
    )

    report: dict[str, Any] = {
        'reason': reason,
        'started_at': _to_iso(started_at),
        'finished_at': None,
        'status': 'failed',
        'source_key': str(conf.get('source_key') or ''),
        'source_name': source.name if source else None,
        'source_id': int(source.id) if source else None,
        'scanned': 0,
        'matched': 0,
        'matched_by_udi_di': 0,
        'matched_by_reg_no': 0,
        'updated': 0,
        'updated_by_udi_di': 0,
        'updated_by_reg_no': 0,
        'missing_local': 0,
        'missing_identifier': 0,
        'failed': 0,
        'message': '',
        'run_id': int(run.id),
    }

    if source is None:
        msg = 'Supplement source not found. Configure source_key(UDI_DI) or source_name.'
        finish_source_run(
            db,
            run,
            status='failed',
            message=msg,
            records_total=0,
            records_success=0,
            records_failed=1,
        )
        report['finished_at'] = _to_iso(_utcnow())
        report['message'] = msg
        upsert_admin_config(db, SUPPLEMENT_LAST_KEY, report)
        return report

    source_cfg = decrypt_json(source.config_encrypted)
    if not isinstance(source_cfg, dict):
        msg = 'Supplement source config is invalid'
        finish_source_run(
            db,
            run,
            status='failed',
            message=msg,
            records_total=0,
            records_success=0,
            records_failed=1,
        )
        report['finished_at'] = _to_iso(_utcnow())
        report['message'] = msg
        upsert_admin_config(db, SUPPLEMENT_LAST_KEY, report)
        return report

    if (getattr(source, 'type', None) or '').strip() == 'local_registry':
        folder = str(source_cfg.get('folder') or '').strip()
        if not folder:
            msg = 'local_registry source requires config.folder'
            finish_source_run(
                db,
                run,
                status='failed',
                message=msg,
                records_total=0,
                records_success=0,
                records_failed=1,
            )
            report['finished_at'] = _to_iso(_utcnow())
            report['message'] = msg
            upsert_admin_config(db, SUPPLEMENT_LAST_KEY, report)
            return report
        ingest_new = bool(source_cfg.get('ingest_new', True))
        ingest_chunk_size = max(100, min(10000, int(source_cfg.get('ingest_chunk_size') or 2000)))
        try:
            result = run_local_registry_supplement(
                db,
                folder=folder,
                dry_run=False,
                source_run_id=int(run.id),
                ingest_new=ingest_new,
                ingest_chunk_size=ingest_chunk_size,
            )
            report['scanned'] = int(result.scanned_rows + result.ingested_total)
            report['matched'] = int(result.matched_products)
            report['updated'] = int(result.updated_products + result.ingested_success)
            report['missing_local'] = int(result.skipped_products)
            report['ingested_total'] = int(result.ingested_total)
            report['ingested_success'] = int(result.ingested_success)
            report['ingested_filtered'] = int(result.ingested_filtered)
            report['ingested_failed'] = int(result.ingested_failed)
            report['ingested_added'] = int(result.ingested_added)
            report['ingested_updated'] = int(result.ingested_updated)
            report['files_read'] = int(result.files_read)
            report['indexed_rows'] = int(result.indexed_rows)
            msg = (
                f"local supplement ok: scanned={report['scanned']}, matched={report['matched']}, "
                f"updated={report['updated']}, ingested_added={report['ingested_added']}"
            )
            finish_source_run(
                db,
                run,
                status='success',
                message=msg,
                records_total=int(report['scanned']),
                records_success=int(report['updated']),
                records_failed=int(result.ingested_failed),
                added_count=int(result.ingested_added),
                updated_count=int(result.updated_products + result.ingested_updated),
                removed_count=0,
                ivd_kept_count=int(result.matched_products + result.ingested_success),
                non_ivd_skipped_count=int(result.skipped_products + result.ingested_filtered),
                source_notes={
                    'mode': 'local_registry_supplement',
                    'folder': folder,
                    'ingest_new': ingest_new,
                    'ingest_chunk_size': ingest_chunk_size,
                    'files_read': int(result.files_read),
                    'indexed_rows': int(result.indexed_rows),
                    'change_logs_written': int(result.change_logs_written),
                    'company_backfilled': int(result.company_backfilled),
                },
            )
            report['status'] = 'success'
            report['message'] = msg
            report['finished_at'] = _to_iso(_utcnow())
            upsert_admin_config(db, SUPPLEMENT_LAST_KEY, report)
            return report
        except Exception as exc:
            db.rollback()
            msg = str(exc)
            finish_source_run(
                db,
                run,
                status='failed',
                message=msg,
                records_total=int(report['scanned']),
                records_success=int(report['updated']),
                records_failed=max(1, int(report['failed'])),
                updated_count=int(report['updated']),
            )
            report['status'] = 'failed'
            report['message'] = msg
            report['finished_at'] = _to_iso(_utcnow())
            upsert_admin_config(db, SUPPLEMENT_LAST_KEY, report)
            return report

    batch_size = int(conf['batch_size'])
    recent_hours = int(conf['recent_hours'])
    source_priority = int(source_cfg.get('source_priority') or 100)
    default_evidence_grade = str(source_cfg.get('default_evidence_grade') or 'C').strip().upper()
    if default_evidence_grade not in {'A', 'B', 'C', 'D'}:
        default_evidence_grade = 'C'
    source_query = str(source_cfg.get('source_query') or '').strip()
    source_table = str(source_cfg.get('source_table') or '').strip() or 'public.products'
    sql = (
        source_query
        if source_query
        else (
            """
            select udi_di, reg_no, name, model, specification, category, status,
                   approved_date, expiry_date, class, raw_json, raw, updated_at
            from public.products
            where updated_at >= :cutoff
            order by updated_at desc
            limit :batch_size
            """
        )
    )
    ext_engine = create_engine(_dsn_from_config(source_cfg), pool_pre_ping=True, poolclass=NullPool)
    cutoff = _utcnow() - timedelta(hours=recent_hours)

    try:
        with ext_engine.connect() as conn:
            result = conn.execute(text(sql), {'cutoff': cutoff, 'batch_size': batch_size})
            _ensure_supplement_query_columns(set(result.keys()))
            rows = result.mappings()

            for row in rows:
                report['scanned'] += 1
                raw_source_record_id = None
                try:
                    contract_result = write_udi_contract_record(
                        db,
                        row=dict(row),
                        source='SUPPLEMENT_POSTGRES',
                        source_run_id=int(run.id),
                        source_url=None,
                        evidence_grade=default_evidence_grade,
                        confidence=0.70,
                    )
                    raw_source_record_id = contract_result.raw_record_id
                    if contract_result.raw_record_id is not None:
                        report['contract_raw_written'] += 1
                    if contract_result.map_written:
                        report['contract_map_written'] += 1
                    if contract_result.pending_written:
                        report['contract_pending_written'] += 1
                    if contract_result.error:
                        report['contract_failed'] += 1
                except Exception:
                    report['contract_failed'] += 1

                udi_di = row.get('udi_di') or row.get('di')
                reg_no_ext = row.get('reg_no') or row.get('registry_no')
                if not _is_blank(reg_no_ext):
                    try:
                        upsert_registration_with_contract(
                            db,
                            registration_no=str(reg_no_ext),
                            incoming_fields={
                                'approval_date': row.get('approved_date'),
                                'expiry_date': row.get('expiry_date'),
                                'status': row.get('status'),
                            },
                            source='SUPPLEMENT_POSTGRES',
                            source_run_id=int(run.id),
                            evidence_grade=default_evidence_grade,
                            source_priority=source_priority,
                            observed_at=_utcnow(),
                            raw_source_record_id=raw_source_record_id,
                            raw_payload=dict(row),
                            write_change_log=True,
                        )
                    except Exception:
                        report['contract_failed'] += 1
                local = None
                match_strategy: str | None = None
                if not _is_blank(udi_di):
                    local = db.scalar(
                        select(Product).where(Product.udi_di == str(udi_di), Product.is_ivd.is_(True)).limit(1)
                    )
                    if local is not None:
                        match_strategy = 'udi_di'
                if local is None and not _is_blank(reg_no_ext):
                    reg_no_norm = normalize_registration_no(str(reg_no_ext))
                    if reg_no_norm:
                        local = db.scalar(
                            select(Product)
                            .where(
                                Product.is_ivd.is_(True),
                                text(
                                    "regexp_replace(upper(coalesce(reg_no, '')), '[^0-9A-Z一-龥]+', '', 'g') = :n"
                                ),
                            )
                            .params(n=reg_no_norm)
                            .order_by(Product.updated_at.desc())
                            .limit(1)
                        )
                        if local is not None:
                            match_strategy = 'reg_no'
                if local is None:
                    if _is_blank(udi_di) and _is_blank(reg_no_ext):
                        report['missing_identifier'] += 1
                        continue
                    report['missing_local'] += 1
                    continue
                report['matched'] += 1
                if match_strategy == 'udi_di':
                    report['matched_by_udi_di'] += 1
                elif match_strategy == 'reg_no':
                    report['matched_by_reg_no'] += 1

                changed = False
                fill_map = {
                    'reg_no': reg_no_ext,
                    'model': row.get('model') or row.get('model_spec'),
                    'specification': row.get('specification') or row.get('model_spec'),
                    'category': row.get('category'),
                    'status': row.get('status'),
                    'approved_date': row.get('approved_date'),
                    'expiry_date': row.get('expiry_date'),
                    'class_name': row.get('class'),
                    'name': row.get('name'),
                }

                for field, ext_value in fill_map.items():
                    if _is_blank(ext_value):
                        continue
                    current = getattr(local, field, None)
                    if _is_blank(current):
                        setattr(local, field, ext_value)
                        changed = True

                ext_raw = row.get('raw')
                if isinstance(ext_raw, dict) and (not isinstance(local.raw, dict) or len(local.raw) == 0):
                    local.raw = ext_raw
                    changed = True
                ext_raw_json = row.get('raw_json')
                if isinstance(ext_raw_json, dict) and (not isinstance(local.raw_json, dict) or len(local.raw_json) == 0):
                    local.raw_json = ext_raw_json
                    changed = True

                if changed:
                    db.add(local)
                    report['updated'] += 1
                    if match_strategy == 'udi_di':
                        report['updated_by_udi_di'] += 1
                    elif match_strategy == 'reg_no':
                        report['updated_by_reg_no'] += 1

        db.commit()
        msg = (
            f"supplement sync ok: scanned={report['scanned']}, matched={report['matched']}, "
            f"updated={report['updated']}, missing_local={report['missing_local']}, "
            f"match_by_udi={report['matched_by_udi_di']}, match_by_reg={report['matched_by_reg_no']}"
        )
        finish_source_run(
            db,
            run,
            status='success',
            message=msg,
            records_total=int(report['scanned']),
            records_success=int(report['matched']),
            records_failed=int(report['failed'] + report['missing_identifier']),
            updated_count=int(report['updated']),
            source_notes={
                'source_name': report.get('source_name'),
                'source_id': report.get('source_id'),
                'source_table': source_table,
                'source_query_used': bool(source_query),
                'matched_by_udi_di': int(report['matched_by_udi_di']),
                'matched_by_reg_no': int(report['matched_by_reg_no']),
                'updated_by_udi_di': int(report['updated_by_udi_di']),
                'updated_by_reg_no': int(report['updated_by_reg_no']),
                'missing_identifier': int(report['missing_identifier']),
                'missing_local': int(report['missing_local']),
                'source_priority': source_priority,
                'default_evidence_grade': default_evidence_grade,
                'contract_raw_written': int(report['contract_raw_written']),
                'contract_map_written': int(report['contract_map_written']),
                'contract_pending_written': int(report['contract_pending_written']),
                'contract_failed': int(report['contract_failed']),
            },
        )
        report['status'] = 'success'
        report['message'] = msg
        report['source_table'] = source_table
        report['source_query_used'] = bool(source_query)
        report['finished_at'] = _to_iso(_utcnow())
        upsert_admin_config(db, SUPPLEMENT_LAST_KEY, report)
        return report
    except Exception as exc:
        db.rollback()
        msg = str(exc)
        finish_source_run(
            db,
            run,
            status='failed',
            message=msg,
            records_total=int(report['scanned']),
            records_success=int(report['matched']),
            records_failed=max(1, int(report['failed'] + report['missing_identifier'])),
            updated_count=int(report['updated']),
            source_notes={
                'source_name': report.get('source_name'),
                'source_id': report.get('source_id'),
                'source_table': source_table,
                'source_query_used': bool(source_query),
                'matched_by_udi_di': int(report.get('matched_by_udi_di', 0)),
                'matched_by_reg_no': int(report.get('matched_by_reg_no', 0)),
                'updated_by_udi_di': int(report.get('updated_by_udi_di', 0)),
                'updated_by_reg_no': int(report.get('updated_by_reg_no', 0)),
                'missing_identifier': int(report.get('missing_identifier', 0)),
                'missing_local': int(report.get('missing_local', 0)),
                'source_priority': source_priority,
                'default_evidence_grade': default_evidence_grade,
                'contract_raw_written': int(report.get('contract_raw_written', 0)),
                'contract_map_written': int(report.get('contract_map_written', 0)),
                'contract_pending_written': int(report.get('contract_pending_written', 0)),
                'contract_failed': int(report.get('contract_failed', 0)),
            },
        )
        report['status'] = 'failed'
        report['message'] = msg
        report['finished_at'] = _to_iso(_utcnow())
        upsert_admin_config(db, SUPPLEMENT_LAST_KEY, report)
        return report
    finally:
        ext_engine.dispose()
