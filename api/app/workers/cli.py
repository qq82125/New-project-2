from __future__ import annotations

import argparse
import json
from datetime import date
from typing import Any

from pathlib import Path
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text

from app.db.session import SessionLocal
from app.repositories.users import get_user_by_email
from app.repositories.admin_membership import admin_grant_membership
from app.repositories.source_runs import finish_source_run, start_source_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='NMPA IVD worker entrypoint')
    sub = parser.add_subparsers(dest='cmd')

    sync_parser = sub.add_parser('sync', help='Run data sync task')
    sync_parser.add_argument('--once', action='store_true', default=True)
    sync_parser.add_argument('--package-url', default=None)
    sync_parser.add_argument('--checksum', default=None)
    sync_parser.add_argument('--checksum-algorithm', default='md5', choices=['md5', 'sha256'])
    sync_parser.add_argument('--no-clean-staging', action='store_true')

    metrics_parser = sub.add_parser('daily-metrics', help='Generate daily metrics snapshot')
    metrics_parser.add_argument('--date', dest='metric_date', default=None, help='YYYY-MM-DD')

    digest_parser = sub.add_parser('daily-digest', help='Dispatch daily subscription digest via webhook')
    digest_parser.add_argument('--date', dest='digest_date', default=None, help='YYYY-MM-DD')
    digest_parser.add_argument('--force', action='store_true', help='Resend even if already sent')

    grant_parser = sub.add_parser('grant', help='Dev: grant Pro annual membership (admin)')
    grant_parser.add_argument('--email', required=True, help='Target user email')
    grant_parser.add_argument('--months', type=int, default=12, help='Months to grant (default: 12)')
    grant_parser.add_argument('--reason', default=None)
    grant_parser.add_argument('--note', default=None)
    grant_parser.add_argument('--actor-email', default=None, help='Admin actor email (default: BOOTSTRAP_ADMIN_EMAIL)')

    reclassify_parser = sub.add_parser('reclassify_ivd', help='Reclassify historical products with current IVD rules')
    reclassify_mode = reclassify_parser.add_mutually_exclusive_group()
    reclassify_mode.add_argument('--dry-run', action='store_true', help='Preview only, no writes')
    reclassify_mode.add_argument('--execute', action='store_true', help='Persist reclassification results')

    def _add_cleanup_parser(name: str) -> None:
        cleanup_parser = sub.add_parser(name, help='Archive then delete non-IVD products')
        cleanup_mode = cleanup_parser.add_mutually_exclusive_group()
        cleanup_mode.add_argument('--dry-run', action='store_true', help='Preview only, no writes')
        cleanup_mode.add_argument('--execute', action='store_true', help='Archive and delete non-IVD rows')
        cleanup_parser.add_argument('--recompute-days', type=int, default=365, help='Days of daily_metrics to recompute')
        cleanup_parser.add_argument('--notes', default=None, help='optional notes for data_cleanup_runs')
        cleanup_parser.add_argument('--archive-batch-id', default=None, help='Optional batch id for archive/rollback traceability')

    _add_cleanup_parser('cleanup_non_ivd')
    _add_cleanup_parser('cleanup-non-ivd')  # backward-compatible alias

    # PR8 command aliases (runbook-facing)
    source_udi_parser = sub.add_parser('source:udi', help='Run UDI source sync (runbook alias)')
    source_udi_parser.add_argument('--date', default=None, help='optional logical date label YYYY-MM-DD')
    source_udi_mode = source_udi_parser.add_mutually_exclusive_group()
    source_udi_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    source_udi_mode.add_argument('--execute', action='store_true', help='Execute sync')

    ivd_classify_parser = sub.add_parser('ivd:classify', help='IVD classify backfill alias')
    ivd_classify_parser.add_argument('--version', default='ivd_v1_20260213')
    ivd_classify_mode = ivd_classify_parser.add_mutually_exclusive_group()
    ivd_classify_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    ivd_classify_mode.add_argument('--execute', action='store_true', help='Execute write-back')
    ivd_classify_parser.add_argument('--batch-size', type=int, default=1000)

    ivd_cleanup_parser = sub.add_parser('ivd:cleanup', help='Non-IVD cleanup alias')
    ivd_cleanup_mode = ivd_cleanup_parser.add_mutually_exclusive_group()
    ivd_cleanup_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    ivd_cleanup_mode.add_argument('--execute', action='store_true', help='Archive and delete')
    ivd_cleanup_parser.add_argument('--batch-size', type=int, default=1000)
    ivd_cleanup_parser.add_argument('--archive-batch-id', default=None)

    ivd_rollback_parser = sub.add_parser('ivd:rollback', help='Rollback archived cleanup batch')
    ivd_rollback_mode = ivd_rollback_parser.add_mutually_exclusive_group()
    ivd_rollback_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    ivd_rollback_mode.add_argument('--execute', action='store_true', help='Execute rollback')
    ivd_rollback_parser.add_argument('--archive-batch-id', required=True)
    ivd_rollback_parser.add_argument('--recompute-days', type=int, default=365, help='Days of daily_metrics to recompute')

    metrics_recompute_parser = sub.add_parser('metrics:recompute', help='Recompute metrics alias')
    metrics_recompute_parser.add_argument('--scope', default='ivd', choices=['ivd'])
    metrics_recompute_parser.add_argument('--since', default=None, help='YYYY-MM-DD')

    local_supp_parser = sub.add_parser('local_registry_supplement', help='Supplement local products from local registry xlsx/zip files')
    local_supp_parser.add_argument('--folder', required=True, help='Folder containing xlsx/zip files')
    local_supp_parser.add_argument('--ingest-new', action='store_true', help='Also ingest new products from local registry rows')
    local_supp_parser.add_argument('--ingest-chunk-size', type=int, default=2000, help='Batch size when ingesting new rows')
    mode = local_supp_parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='Preview only, no writes')
    mode.add_argument('--execute', action='store_true', help='Write updates to DB')

    sub.add_parser('loop', help='Run sync loop')

    params_extract_parser = sub.add_parser('params:extract', help='Extract structured params from a raw document/manual')
    params_extract_mode = params_extract_parser.add_mutually_exclusive_group()
    params_extract_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    params_extract_mode.add_argument('--execute', action='store_true', help='Write extracted params to DB')
    params_extract_parser.add_argument('--raw-document-id', default=None, help='Existing raw_documents.id UUID')
    params_extract_parser.add_argument('--file', default=None, help='Local file path to upload as raw document')
    params_extract_parser.add_argument('--source-url', default=None, help='Optional original source URL')
    params_extract_parser.add_argument('--doc-type', default=None, help='Optional doc type hint: pdf/text/html')
    params_extract_parser.add_argument('--run-id', default=None, help='Optional logical run id for traceability')
    params_extract_parser.add_argument('--di', default=None, help='UDI-DI to bind params')
    params_extract_parser.add_argument('--registry-no', default=None, help='Registration number to bind params')
    params_extract_parser.add_argument('--extract-version', default='param_v1_20260213')

    params_rb_parser = sub.add_parser('params:rollback', help='Rollback (delete) params extracted from a raw document')
    params_rb_mode = params_rb_parser.add_mutually_exclusive_group()
    params_rb_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    params_rb_mode.add_argument('--execute', action='store_true', help='Delete product_params rows for this raw document')
    params_rb_parser.add_argument('--raw-document-id', required=True, help='raw_documents.id UUID')

    nhsa_parser = sub.add_parser('nhsa:ingest', help='Ingest NHSA monthly snapshot into evidence chain + nhsa_codes')
    nhsa_mode = nhsa_parser.add_mutually_exclusive_group()
    nhsa_mode.add_argument('--dry-run', action='store_true', help='Preview only (still stores raw_documents)')
    nhsa_mode.add_argument('--execute', action='store_true', help='Write nhsa_codes')
    nhsa_parser.add_argument('--month', required=True, help='Snapshot month YYYY-MM')
    nhsa_src = nhsa_parser.add_mutually_exclusive_group(required=True)
    nhsa_src.add_argument('--url', default=None, help='CSV download URL (low frequency)')
    nhsa_src.add_argument('--file', default=None, help='Local snapshot file path (csv)')
    nhsa_parser.add_argument('--timeout', type=int, default=30, help='HTTP timeout seconds (when using --url)')

    nhsa_rb = sub.add_parser('nhsa:rollback', help='Rollback (delete) nhsa_codes rows inserted by a source_run_id')
    nhsa_rb_mode = nhsa_rb.add_mutually_exclusive_group()
    nhsa_rb_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    nhsa_rb_mode.add_argument('--execute', action='store_true', help='Delete nhsa_codes by source_run_id')
    nhsa_rb.add_argument('--source-run-id', type=int, required=True, help='source_runs.id of the nhsa ingest run')

    proc_ingest = sub.add_parser('procurement:ingest', help='Ingest procurement snapshot into evidence chain + procurement_*')
    proc_ingest_mode = proc_ingest.add_mutually_exclusive_group()
    proc_ingest_mode.add_argument('--dry-run', action='store_true', help='Preview only (still stores raw_documents)')
    proc_ingest_mode.add_argument('--execute', action='store_true', help='Write procurement structured tables')
    proc_ingest.add_argument('--file', required=True, help='Local procurement snapshot file (csv/json)')
    proc_ingest.add_argument('--province', required=True, help='Province label for this snapshot')

    proc_rb = sub.add_parser('procurement:rollback', help='Rollback procurement_* rows inserted by a source_run_id')
    proc_rb_mode = proc_rb.add_mutually_exclusive_group()
    proc_rb_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    proc_rb_mode.add_argument('--execute', action='store_true', help='Delete procurement_* by source_run_id')
    proc_rb.add_argument('--source-run-id', type=int, required=True, help='source_runs.id of the procurement ingest run')

    nmpa_snap_parser = sub.add_parser('nmpa:snapshots', help='Inspect NMPA snapshots since a date (ops/debug)')
    nmpa_snap_parser.add_argument('--since', required=True, help='YYYY-MM-DD')

    nmpa_diff_parser = sub.add_parser('nmpa:diffs', help='Summarize NMPA field diffs for a date (ops/debug)')
    nmpa_diff_parser.add_argument('--date', required=True, help='YYYY-MM-DD')

    meth_seed = sub.add_parser('methodology:seed', help='Seed methodology tree (V1) into methodology_nodes')
    meth_seed_mode = meth_seed.add_mutually_exclusive_group()
    meth_seed_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    meth_seed_mode.add_argument('--execute', action='store_true', help='Write to DB')
    meth_seed.add_argument('--file', default='docs/methodology_tree_v1.json')

    meth_map = sub.add_parser('methodology:map', help='Rule-map registrations to methodology_nodes via synonyms')
    meth_map_mode = meth_map.add_mutually_exclusive_group()
    meth_map_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    meth_map_mode.add_argument('--execute', action='store_true', help='Write to DB')
    meth_map.add_argument('--file', default=None, help='optional: seed file to load if methodology_nodes empty')
    meth_map.add_argument('--registration-no', action='append', default=None, help='optional: filter by registration_no (repeatable)')

    reg_ev = sub.add_parser('registration:events', help='Generate registration version events from snapshots/diffs')
    reg_ev_mode = reg_ev.add_mutually_exclusive_group()
    reg_ev_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    reg_ev_mode.add_argument('--execute', action='store_true', help='Write to DB')
    date_group = reg_ev.add_mutually_exclusive_group()
    date_group.add_argument('--date', default=None, help='YYYY-MM-DD (snapshot_date)')
    date_group.add_argument('--since', default=None, help='YYYY-MM-DD (snapshot_date >= since)')

    derive_ev = sub.add_parser('derive-registration-events', help='Time Engine V1: derive registration_events from field_diffs')
    derive_ev_mode = derive_ev.add_mutually_exclusive_group()
    derive_ev_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    derive_ev_mode.add_argument('--execute', action='store_true', help='Write to DB')
    derive_ev.add_argument('--since', required=True, help='YYYY-MM-DD (snapshot_date/created_at >= since)')

    source_run = sub.add_parser('source:run', help='Run unified ingest runner for one source_key')
    source_run.add_argument('--source_key', required=True, help='source_definitions.source_key')
    source_run_mode = source_run.add_mutually_exclusive_group()
    source_run_mode.add_argument('--dry-run', action='store_true', help='Preview parse/upsert counts only')
    source_run_mode.add_argument('--execute', action='store_true', help='Persist raw_source_records + upserts')

    source_run_all = sub.add_parser('source:run-all', help='Run unified ingest runner for all enabled sources')
    source_run_all_mode = source_run_all.add_mutually_exclusive_group()
    source_run_all_mode.add_argument('--dry-run', action='store_true', help='Preview parse/upsert counts only')
    source_run_all_mode.add_argument('--execute', action='store_true', help='Persist raw_source_records + upserts')

    udi_audit = sub.add_parser('udi:audit', help='Audit DI binding distribution against registration anchors')
    udi_audit_mode = udi_audit.add_mutually_exclusive_group()
    udi_audit_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    udi_audit_mode.add_argument('--execute', action='store_true', help='Alias of dry-run (read-only)')
    udi_audit.add_argument('--outlier-threshold', type=int, default=100, help='Threshold for DI count per registration_no outlier')

    udi_promote = sub.add_parser('udi:promote', help='Promote UDI device index entries into registration/product structures')
    udi_promote_mode = udi_promote.add_mutually_exclusive_group()
    udi_promote_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    udi_promote_mode.add_argument('--execute', action='store_true', help='Write registration/product bindings')
    udi_promote.add_argument('--source-run-id', type=int, default=None, help='Filter by source_runs.id')
    udi_promote.add_argument('--raw-document-id', default=None, help='Filter by udi_device_index.raw_document_id')
    udi_promote.add_argument('--limit', type=int, default=None, help='Optional max number of rows to process')
    udi_promote.add_argument('--offset', type=int, default=None, help='Optional offset for batched promote pagination')
    # Backward-compatible runbook flag: current implementation does not branch on confidence yet.
    udi_promote.add_argument('--min-confidence', type=float, default=None, help='Reserved (accepted for compatibility)')

    udi_promote_snapshot = sub.add_parser('udi:promote-snapshot', help='Snapshot udi:promote run with success-rate metrics')
    udi_promote_snapshot_mode = udi_promote_snapshot.add_mutually_exclusive_group()
    udi_promote_snapshot_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    udi_promote_snapshot_mode.add_argument('--execute', action='store_true', help='Execute and write')
    udi_promote_snapshot.add_argument('--source-run-id', type=int, default=None, help='Filter by source_runs.id')
    udi_promote_snapshot.add_argument('--raw-document-id', default=None, help='Filter by udi_device_index.raw_document_id')
    udi_promote_snapshot.add_argument('--source', default='UDI_PROMOTE', help='Source label for upsert/pending paths (default: UDI_PROMOTE)')
    udi_promote_snapshot.add_argument('--limit', type=int, default=None, help='Optional max number of rows to process')

    udi_index = sub.add_parser('udi:index', help='Build UDI device index from extracted XML (no anchor writes)')
    udi_index_mode = udi_index.add_mutually_exclusive_group()
    udi_index_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    udi_index_mode.add_argument('--execute', action='store_true', help='Write udi_device_index')
    udi_index.add_argument('--source-run-id', type=int, default=None, help='source_runs.id (used to locate staging/run_<id>/extracted)')
    udi_index.add_argument('--raw-document-id', default=None, help='raw_documents.id UUID (for traceability)')
    udi_index.add_argument('--staging-dir', default=None, help='Override: path containing extracted UDI XML files')
    udi_index.add_argument('--limit', type=int, default=None, help='Optional max number of <device> nodes to scan')
    udi_index.add_argument('--limit-files', type=int, default=None, help='Optional max number of XML files to scan (sorted)')
    udi_index.add_argument('--max-devices-per-file', type=int, default=None, help='Optional max number of <device> nodes per file')
    udi_index.add_argument('--part-from', type=int, default=None, help='Only scan PART N..M files (inclusive), based on file name')
    udi_index.add_argument('--part-to', type=int, default=None, help='Only scan PART N..M files (inclusive), based on file name')

    udi_variants = sub.add_parser('udi:variants', help='Promote udi_device_index into registration-anchored product_variants')
    udi_variants_mode = udi_variants.add_mutually_exclusive_group()
    udi_variants_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    udi_variants_mode.add_argument('--execute', action='store_true', help='Write product_variants + mark udi_device_index unbound')
    udi_variants.add_argument('--source-run-id', type=int, default=None, help='Filter by source_runs.id')
    udi_variants.add_argument('--limit', type=int, default=None, help='Optional max number of rows to process')

    udi_products_enrich = sub.add_parser('udi:products-enrich', help='Enrich products (fill-empty only) from udi_device_index')
    udi_products_enrich_mode = udi_products_enrich.add_mutually_exclusive_group()
    udi_products_enrich_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    udi_products_enrich_mode.add_argument('--execute', action='store_true', help='Write products (fill-empty) + change_log')
    udi_products_enrich.add_argument('--source-run-id', type=int, default=None, help='Filter by source_runs.id')
    udi_products_enrich.add_argument('--limit', type=int, default=None, help='Optional max number of rows to process')
    udi_products_enrich.add_argument('--description-max-len', type=int, default=2000, help='Max chars for cpms description snapshot')

    udi_params = sub.add_parser('udi:params', help='Scan UDI device index param candidates; optionally write allowlisted product_params')
    udi_params_mode = udi_params.add_mutually_exclusive_group()
    udi_params_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    udi_params_mode.add_argument('--execute', action='store_true', help='Write product_params (and optional candidates snapshot)')
    udi_params.add_argument('--source-run-id', type=int, default=None, help='Filter by source_runs.id')
    udi_params.add_argument('--limit', type=int, default=None, help='Optional max number of index rows to scan (for execute)')
    udi_params.add_argument('--top', type=int, default=50, help='Top N fields to print in dry-run (default 50)')
    udi_params.add_argument('--sample-rows', type=int, default=20000, help='Full-scan: sample size for sample_values (default 20000)')
    udi_params.add_argument('--sample-limit', type=int, default=200000, help='Dry-run sampling rows (default 200000)')
    udi_params.add_argument('--full-scan', action='store_true', help='Dry-run/execute candidates: use full scan instead of sampling')
    udi_params.add_argument('--with-candidates', action='store_true', help='Execute: also compute+upsert candidates snapshot (can be expensive)')
    udi_params.add_argument('--only-allowlisted', action='store_true', help='Execute: only write params from admin_configs[udi_params_allowlist]')
    udi_params.add_argument('--batch-size', type=int, default=50000, help='Execute: rows per batch for allowlist write (default 50000)')
    udi_params.add_argument('--resume', dest='resume', action='store_true', help='Execute: continue from checkpoint (default)')
    udi_params.add_argument('--no-resume', dest='resume', action='store_false', help='Execute: ignore checkpoint and start fresh')
    udi_params.add_argument('--start-cursor', default=None, help='Execute: start from this di_norm cursor (overrides checkpoint)')
    udi_params.set_defaults(resume=True)

    prod_meth = sub.add_parser('methodology:map-products', help='Ontology V1: map products to methodology_master (rules-based)')
    prod_meth_mode = prod_meth.add_mutually_exclusive_group()
    prod_meth_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    prod_meth_mode.add_argument('--execute', action='store_true', help='Write to DB')
    prod_meth.add_argument('--limit', type=int, default=None, help='Optional limit of products to scan')

    lri = sub.add_parser('lri-compute', help='Compute LRI V1 scores into lri_scores')
    lri_mode = lri.add_mutually_exclusive_group()
    lri_mode.add_argument('--dry-run', action='store_true', help='Preview only')
    lri_mode.add_argument('--execute', action='store_true', help='Write to DB')
    lri.add_argument('--date', default=None, help='YYYY-MM-DD (default: today UTC)')
    lri.add_argument('--model-version', default='lri_v1')
    lri.add_argument('--upsert', action='store_true', help='Delete existing scores for the same day+model before insert')
    return parser


def _run_sync(args: argparse.Namespace) -> int:
    from app.workers.sync import sync_nmpa_ivd

    result = sync_nmpa_ivd(
        package_url=args.package_url,
        checksum=args.checksum,
        checksum_algorithm=args.checksum_algorithm,
        clean_staging=not args.no_clean_staging,
    )
    print(json.dumps(result.__dict__, ensure_ascii=True))
    return 0 if result.status == 'success' else 1


def _run_daily_metrics(metric_date: str | None) -> int:
    target = date.fromisoformat(metric_date) if metric_date else None
    db = SessionLocal()
    try:
        from app.services.metrics import generate_daily_metrics

        row = generate_daily_metrics(db, target)
        print(
            json.dumps(
                {
                    'metric_date': row.metric_date.isoformat(),
                    'new_products': int(row.new_products or 0),
                    'updated_products': int(row.updated_products or 0),
                    'cancelled_products': int(row.cancelled_products or 0),
                    'expiring_in_90d': int(row.expiring_in_90d or 0),
                    'pending_count': int(getattr(row, 'pending_count', 0) or 0),
                    'lri_computed_count': int(getattr(row, 'lri_computed_count', 0) or 0),
                    'lri_missing_methodology_count': int(getattr(row, 'lri_missing_methodology_count', 0) or 0),
                    'udi_metrics': (getattr(row, 'udi_metrics', None) or {}),
                },
                ensure_ascii=False,
                default=str,
            )
        )
        return 0
    finally:
        db.close()


def _run_daily_digest(digest_date: str | None, force: bool) -> int:
    target = date.fromisoformat(digest_date) if digest_date else None
    db = SessionLocal()
    try:
        from app.services.subscriptions import dispatch_daily_subscription_digest

        res = dispatch_daily_subscription_digest(db, target, force=force)
        print(json.dumps(res, ensure_ascii=True))
        return 0 if res['failed'] == 0 else 1
    finally:
        db.close()


def _run_grant(email: str, months: int, reason: str | None, note: str | None, actor_email: str | None) -> int:
    if months <= 0:
        raise SystemExit('months must be > 0')

    db = SessionLocal()
    try:
        target = get_user_by_email(db, email)
        if not target:
            raise SystemExit(f'user not found: {email}')

        from app.core.config import get_settings

        cfg = get_settings()
        actor_lookup = actor_email or getattr(cfg, 'bootstrap_admin_email', None) or ''
        actor = get_user_by_email(db, actor_lookup) if actor_lookup else None
        if not actor or getattr(actor, 'role', None) != 'admin':
            # Fallback: first admin user.
            from sqlalchemy import select
            from app.models import User

            actor = db.scalars(select(User).where(User.role == 'admin').limit(1)).first()
        if not actor:
            raise SystemExit('admin actor not found; create bootstrap admin first')

        user = admin_grant_membership(
            db,
            user_id=target.id,
            actor_user_id=actor.id,
            plan='pro_annual',
            months=months,
            start_at=None,
            reason=reason,
            note=note,
        )
        if not user:
            raise SystemExit('grant failed: user not found')
        print(
            json.dumps(
                {
                    'ok': True,
                    'user_id': user.id,
                    'email': user.email,
                    'plan': getattr(user, 'plan', None),
                    'plan_status': getattr(user, 'plan_status', None),
                    'plan_expires_at': getattr(user, 'plan_expires_at', None).isoformat()
                    if getattr(user, 'plan_expires_at', None)
                    else None,
                },
                ensure_ascii=True,
            )
        )
        return 0
    finally:
        db.close()


def _run_cleanup_non_ivd(*, dry_run: bool, recompute_days: int, notes: str | None) -> int:
    db = SessionLocal()
    try:
        from app.services.data_cleanup import run_non_ivd_cleanup

        # Backward-compat call signature; archive_batch_id is passed by newer commands (ivd:cleanup, cleanup_non_ivd).
        result = run_non_ivd_cleanup(db, dry_run=dry_run, recompute_days=recompute_days, notes=notes)
        print(
            json.dumps(
                {
                    'ok': True,
                    'run_id': result.run_id,
                    'archive_batch_id': result.archive_batch_id,
                    'dry_run': result.dry_run,
                    'target_count': result.target_count,
                    'archived_count': result.archived_count,
                    'deleted_count': result.deleted_count,
                    'recomputed_days': result.recomputed_days,
                    'notes': result.notes,
                },
                ensure_ascii=True,
            )
        )
        return 0
    finally:
        db.close()


def _run_cleanup_non_ivd_v2(*, dry_run: bool, recompute_days: int, notes: str | None, archive_batch_id: str | None) -> int:
    db = SessionLocal()
    try:
        from app.services.data_cleanup import run_non_ivd_cleanup

        result = run_non_ivd_cleanup(
            db,
            dry_run=dry_run,
            recompute_days=recompute_days,
            notes=notes,
            archive_batch_id=archive_batch_id,
        )
        print(
            json.dumps(
                {
                    'ok': True,
                    'run_id': result.run_id,
                    'archive_batch_id': result.archive_batch_id,
                    'dry_run': result.dry_run,
                    'target_count': result.target_count,
                    'archived_count': result.archived_count,
                    'deleted_count': result.deleted_count,
                    'recomputed_days': result.recomputed_days,
                    'notes': result.notes,
                },
                ensure_ascii=True,
            )
        )
        return 0
    finally:
        db.close()


def _run_ivd_rollback(*, archive_batch_id: str, dry_run: bool, recompute_days: int = 365) -> int:
    db = SessionLocal()
    try:
        from app.services.data_cleanup import rollback_non_ivd_cleanup

        result = rollback_non_ivd_cleanup(
            db,
            archive_batch_id=archive_batch_id,
            dry_run=dry_run,
            recompute_days=int(recompute_days),
        )
        print(
            json.dumps(
                {
                    'ok': True,
                    'archive_batch_id': result.archive_batch_id,
                    'dry_run': result.dry_run,
                    'target_count': result.target_count,
                    'restored_count': result.restored_count,
                    'skipped_existing': result.skipped_existing,
                    'recomputed_days': (int(recompute_days) if not bool(dry_run) else 0),
                },
                ensure_ascii=True,
            )
        )
        return 0
    finally:
        db.close()


def _run_metrics_recompute(*, scope: str, since: str | None) -> int:
    if scope != 'ivd':
        raise SystemExit('only --scope ivd is supported')
    from datetime import timedelta

    target_since = date.fromisoformat(since) if since else (date.today() - timedelta(days=365))
    days = max(1, (date.today() - target_since).days + 1)
    db = SessionLocal()
    try:
        from app.services.metrics import regenerate_daily_metrics

        rows = regenerate_daily_metrics(db, days=days)
        print(json.dumps({'ok': True, 'scope': scope, 'since': target_since.isoformat(), 'days': days, 'rows': len(rows)}, ensure_ascii=True))
        return 0
    finally:
        db.close()


def _run_nmpa_snapshots(*, since: str) -> int:
    target = date.fromisoformat(since)
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT snapshot_date, count(*) AS cnt, count(DISTINCT source_run_id) AS runs
                FROM nmpa_snapshots
                WHERE snapshot_date >= :since
                GROUP BY snapshot_date
                ORDER BY snapshot_date ASC
                """
            ),
            {"since": target},
        ).fetchall()
        total = sum(int(r[1]) for r in rows)
        out = {
            "ok": True,
            "since": target.isoformat(),
            "total_snapshots": total,
            "by_date": [{"date": r[0].isoformat(), "count": int(r[1]), "source_runs": int(r[2])} for r in rows],
        }
        print(json.dumps(out, ensure_ascii=True))
        return 0
    finally:
        db.close()


def _run_nmpa_diffs(*, target_date: str) -> int:
    d = date.fromisoformat(target_date)
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT
                  fd.source_run_id,
                  fd.severity,
                  fd.field_name,
                  count(*) AS cnt
                FROM field_diffs fd
                JOIN nmpa_snapshots ns ON ns.id = fd.snapshot_id
                WHERE ns.snapshot_date = :d
                GROUP BY fd.source_run_id, fd.severity, fd.field_name
                ORDER BY fd.source_run_id ASC, fd.severity DESC, cnt DESC
                """
            ),
            {"d": d},
        ).fetchall()
        total = sum(int(r[3]) for r in rows)
        out = {
            "ok": True,
            "date": d.isoformat(),
            "total_diffs": total,
            "rows": [
                {
                    "source_run_id": (int(r[0]) if r[0] is not None else None),
                    "severity": r[1],
                    "field_name": r[2],
                    "count": int(r[3]),
                }
                for r in rows
            ],
        }
        print(json.dumps(out, ensure_ascii=True))
        return 0
    finally:
        db.close()


def _run_methodology_seed(*, dry_run: bool, file_path: str) -> int:
    db = SessionLocal()
    try:
        from app.services.methodology_v1 import seed_methodology_tree

        res = seed_methodology_tree(db, seed_path=str(file_path), dry_run=bool(dry_run))
        print(json.dumps(res, ensure_ascii=True))
        return 0
    finally:
        db.close()


def _run_methodology_map(*, dry_run: bool, file_path: str | None, registration_nos: list[str] | None) -> int:
    db = SessionLocal()
    try:
        from sqlalchemy import select
        from app.models import MethodologyNode
        from app.services.methodology_v1 import map_methodologies_v1, seed_methodology_tree

        # Convenience: if empty, allow seeding from file (optional).
        has_nodes = bool(db.scalar(select(MethodologyNode.id).limit(1)))
        if not has_nodes and file_path:
            seed_methodology_tree(db, seed_path=str(file_path), dry_run=False)

        res = map_methodologies_v1(db, registration_nos=registration_nos, dry_run=bool(dry_run))
        print(json.dumps(res, ensure_ascii=True))
        return 0 if res.get('ok') else 1
    finally:
        db.close()


def _run_registration_events(*, dry_run: bool, date_str: str | None, since_str: str | None) -> int:
    from datetime import date

    target_date = date.fromisoformat(date_str) if date_str else None
    since = date.fromisoformat(since_str) if since_str else None
    db = SessionLocal()
    try:
        from app.services.version_events import generate_registration_events

        res = generate_registration_events(db, target_date=target_date, since=since, dry_run=bool(dry_run))
        print(json.dumps(res.__dict__, ensure_ascii=True))
        return 0 if res.ok else 1
    finally:
        db.close()


def _run_derive_registration_events(*, dry_run: bool, since_str: str) -> int:
    from datetime import date as dt_date

    since = dt_date.fromisoformat(str(since_str).strip())
    db = SessionLocal()
    try:
        from app.services.time_engine_v1 import derive_registration_events_v1

        res = derive_registration_events_v1(db, since=since, dry_run=bool(dry_run))
        print(json.dumps(res.__dict__, ensure_ascii=True, default=str))
        return 0 if res.ok else 1
    finally:
        db.close()


def _run_source_udi(*, execute: bool, date_label: str | None) -> int:
    from app.workers.sync import sync_nmpa_ivd

    if not execute:
        print(json.dumps({'ok': True, 'dry_run': True, 'source': 'udi', 'date': date_label, 'message': 'no side effects'}))
        return 0
    result = sync_nmpa_ivd(clean_staging=True)
    print(json.dumps({'ok': result.status == 'success', 'source': 'udi', 'date': date_label, **result.__dict__}, ensure_ascii=True))
    return 0 if result.status == 'success' else 1


def _run_reclassify_ivd(*, dry_run: bool) -> int:
    db = SessionLocal()
    try:
        from app.services.reclassify_ivd import run_reclassify_ivd

        result = run_reclassify_ivd(db, dry_run=dry_run)
        print(
            json.dumps(
                {
                    'ok': True,
                    'dry_run': result.dry_run,
                    'scanned': result.scanned,
                    'would_update': result.would_update,
                    'updated': result.updated,
                    'ivd_true': result.ivd_true,
                    'ivd_false': result.ivd_false,
                    'ivd_version': result.ivd_version,
                },
                ensure_ascii=True,
            )
        )
        return 0
    finally:
        db.close()


def _run_local_registry_supplement(*, folder: str, dry_run: bool, ingest_new: bool, ingest_chunk_size: int) -> int:
    db = SessionLocal()
    run = None
    try:
        from app.services.local_registry_supplement import run_local_registry_supplement
        from app.services.metrics import generate_daily_metrics

        if not dry_run:
            run = start_source_run(
                db,
                source='local_registry_supplement',
                package_name='local-registry-folder',
                package_md5=None,
                download_url=folder,
            )
        result = run_local_registry_supplement(
            db,
            folder=folder,
            dry_run=dry_run,
            source_run_id=(int(run.id) if run is not None else None),
            ingest_new=bool(ingest_new),
            ingest_chunk_size=int(ingest_chunk_size),
        )
        if run is not None:
            finish_source_run(
                db,
                run,
                status='success',
                message='local registry supplement finished',
                records_total=result.scanned_rows + result.ingested_total,
                records_success=result.updated_products + result.ingested_success,
                records_failed=result.ingested_failed,
                added_count=result.ingested_added,
                updated_count=result.updated_products + result.ingested_updated,
                removed_count=0,
                ivd_kept_count=result.matched_products,
                non_ivd_skipped_count=result.skipped_products,
                source_notes={
                    'mode': 'local_registry_supplement',
                    'files_read': result.files_read,
                    'indexed_rows': result.indexed_rows,
                    'change_logs_written': result.change_logs_written,
                    'company_backfilled': result.company_backfilled,
                    'ingest_new': bool(ingest_new),
                    'ingested_total': result.ingested_total,
                    'ingested_success': result.ingested_success,
                    'ingested_filtered': result.ingested_filtered,
                },
            )
            generate_daily_metrics(db)
        print(
            json.dumps(
                {
                    'ok': True,
                    'dry_run': dry_run,
                    'folder': folder,
                    'files_read': result.files_read,
                    'scanned_rows': result.scanned_rows,
                    'indexed_rows': result.indexed_rows,
                    'matched_products': result.matched_products,
                    'updated_products': result.updated_products,
                    'change_logs_written': result.change_logs_written,
                    'ingested_total': result.ingested_total,
                    'ingested_success': result.ingested_success,
                    'ingested_filtered': result.ingested_filtered,
                    'ingested_failed': result.ingested_failed,
                    'ingested_added': result.ingested_added,
                    'ingested_updated': result.ingested_updated,
                    'company_backfilled': result.company_backfilled,
                    'skipped_products': result.skipped_products,
                    'source_run_id': (int(run.id) if run is not None else None),
                },
                ensure_ascii=True,
            )
        )
        return 0
    except Exception as exc:
        if run is not None:
            try:
                db.rollback()
            except Exception:
                pass
            finish_source_run(
                db,
                run,
                status='failed',
                message=str(exc),
                records_total=0,
                records_success=0,
                records_failed=0,
                added_count=0,
                updated_count=0,
                removed_count=0,
                ivd_kept_count=0,
                non_ivd_skipped_count=0,
                source_notes={'mode': 'local_registry_supplement', 'folder': folder},
            )
        raise
    finally:
        db.close()


def _infer_doc_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == '.pdf':
        return 'pdf'
    if ext in {'.htm', '.html'}:
        return 'html'
    return 'text'


def _run_params_extract(
    *,
    dry_run: bool,
    raw_document_id: str | None,
    file_path: str | None,
    source_url: str | None,
    doc_type: str | None,
    run_id: str | None,
    di: str | None,
    registry_no: str | None,
    extract_version: str,
) -> int:
    db = SessionLocal()
    try:
        from app.pipeline.ingest import save_raw_document_from_path
        from app.services.product_params_extract import extract_params_for_raw_document

        rid: UUID | None = None
        if raw_document_id:
            rid = UUID(str(raw_document_id))
        elif file_path:
            p = Path(str(file_path))
            if not p.exists() or not p.is_file():
                raise SystemExit(f'file not found: {file_path}')
            dtype = (doc_type or _infer_doc_type(p)).strip().lower()
            rid = save_raw_document_from_path(
                db,
                source='MANUAL',
                url=source_url,
                file_path=p,
                doc_type=dtype,
                run_id=(run_id or f'manual_params:{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}'),
            )
        else:
            raise SystemExit('either --raw-document-id or --file is required')

        res = extract_params_for_raw_document(
            db,
            raw_document_id=rid,
            di=(str(di).strip() or None) if di else None,
            registry_no=(str(registry_no).strip() or None) if registry_no else None,
            extract_version=str(extract_version),
            dry_run=bool(dry_run),
        )
        print(
            json.dumps(
                {
                    'ok': True,
                    'dry_run': res.dry_run,
                    'raw_document_id': str(res.raw_document_id),
                    'di': res.di,
                    'registry_no': res.registry_no,
                    'bound_product_id': res.bound_product_id,
                    'pages': res.pages,
                    'deleted_existing': res.deleted_existing,
                    'extracted': res.extracted,
                    'extract_version': res.extract_version,
                    'parse_log': res.parse_log,
                },
                ensure_ascii=True,
            )
        )
        return 0
    finally:
        db.close()


def _run_params_rollback(*, dry_run: bool, raw_document_id: str) -> int:
    db = SessionLocal()
    try:
        from app.services.product_params_extract import rollback_params_for_raw_document

        rid = UUID(str(raw_document_id))
        res = rollback_params_for_raw_document(db, raw_document_id=rid, dry_run=bool(dry_run))
        print(json.dumps({'ok': True, 'dry_run': res.dry_run, 'raw_document_id': str(res.raw_document_id), 'deleted': res.deleted}, ensure_ascii=True))
        return 0
    finally:
        db.close()


def _run_nhsa_ingest(args: argparse.Namespace) -> int:
    dry_run = bool(args.dry_run) or not bool(args.execute)
    db = SessionLocal()
    try:
        from app.services.nhsa_ingest import ingest_nhsa_from_file, ingest_nhsa_from_url

        if getattr(args, 'url', None):
            res = ingest_nhsa_from_url(
                db,
                snapshot_month=str(args.month),
                url=str(args.url),
                timeout_seconds=int(getattr(args, 'timeout', 30)),
                dry_run=dry_run,
            )
        else:
            res = ingest_nhsa_from_file(
                db,
                snapshot_month=str(args.month),
                file_path=str(args.file),
                dry_run=dry_run,
            )
        print(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": bool(dry_run),
                    "source_run_id": int(res.source_run_id),
                    "raw_run_id": str(res.raw_run_id),
                    "raw_document_id": str(res.raw_document_id),
                    "snapshot_month": str(res.snapshot_month),
                    "fetched_count": int(res.fetched_count),
                    "parsed_count": int(res.parsed_count),
                    "failed_count": int(res.failed_count),
                    "upserted": int(res.upserted),
                },
                ensure_ascii=True,
            )
        )
        return 0 if int(res.failed_count) == 0 else 1
    finally:
        db.close()


def _run_nhsa_rollback(args: argparse.Namespace) -> int:
    dry_run = bool(args.dry_run) or not bool(args.execute)
    db = SessionLocal()
    try:
        from app.services.nhsa_ingest import rollback_nhsa_ingest

        res = rollback_nhsa_ingest(db, source_run_id=int(args.source_run_id), dry_run=dry_run)
        print(json.dumps(res, ensure_ascii=True))
        return 0
    finally:
        db.close()


def _run_procurement_ingest(args: argparse.Namespace) -> int:
    dry_run = bool(args.dry_run) or not bool(args.execute)
    db = SessionLocal()
    try:
        from app.services.procurement_ingest import ingest_procurement_from_file

        res = ingest_procurement_from_file(
            db,
            province=str(args.province),
            file_path=str(args.file),
            dry_run=dry_run,
        )
        print(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": bool(dry_run),
                    "province": str(args.province),
                    "source_run_id": int(res.source_run_id),
                    "raw_run_id": str(res.raw_run_id),
                    "raw_document_id": str(res.raw_document_id),
                    "fetched_count": int(res.fetched_count),
                    "parsed_count": int(res.parsed_count),
                    "failed_count": int(res.failed_count),
                    "projects": int(res.projects),
                    "lots": int(res.lots),
                    "results": int(res.results),
                    "maps": int(res.maps),
                    "sample_mappings": res.sample_mappings[:10],
                },
                ensure_ascii=True,
            )
        )
        return 0 if int(res.failed_count) == 0 else 1
    finally:
        db.close()


def _run_procurement_rollback(args: argparse.Namespace) -> int:
    dry_run = bool(args.dry_run) or not bool(args.execute)
    db = SessionLocal()
    try:
        from app.services.procurement_ingest import rollback_procurement_ingest

        res = rollback_procurement_ingest(db, source_run_id=int(args.source_run_id), dry_run=dry_run)
        print(json.dumps(res.__dict__, ensure_ascii=True))
        return 0
    finally:
        db.close()


def _run_source_runner(args: argparse.Namespace) -> int:
    dry_run = bool(args.dry_run) or not bool(args.execute)
    db = SessionLocal()
    try:
        from app.services.ingest_runner import run_source_by_key

        try:
            stats = run_source_by_key(db, source_key=str(args.source_key), execute=(not dry_run))
            print(json.dumps(stats.to_dict(), ensure_ascii=True, default=str))
            return 0 if stats.status in {"success", "skipped"} else 1
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "source_key": str(args.source_key),
                        "dry_run": dry_run,
                        "status": "failed",
                        "error": str(exc),
                    },
                    ensure_ascii=True,
                    default=str,
                )
            )
            return 1
    finally:
        db.close()


def _run_source_runner_all(args: argparse.Namespace) -> int:
    dry_run = bool(args.dry_run) or not bool(args.execute)
    db = SessionLocal()
    try:
        from app.services.ingest_runner import run_all_enabled_sources

        rows = run_all_enabled_sources(db, execute=(not dry_run))
        body = {
            "count": len(rows),
            "failed": sum(1 for x in rows if x.status == "failed"),
            "skipped": sum(1 for x in rows if x.status == "skipped"),
            "items": [x.to_dict() for x in rows],
        }
        print(json.dumps(body, ensure_ascii=True, default=str))
        return 0 if int(body["failed"]) == 0 else 1
    finally:
        db.close()


def _run_udi_audit(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        threshold = int(getattr(args, 'outlier_threshold', 100) or 100)
        dist = db.execute(
            text(
                """
                WITH per_reg AS (
                  SELECT registry_no, COUNT(1)::bigint AS di_count
                  FROM product_variants
                  WHERE registry_no IS NOT NULL AND btrim(registry_no) <> ''
                  GROUP BY registry_no
                )
                SELECT
                  COALESCE(COUNT(1), 0)::bigint AS registration_count,
                  COALESCE(SUM(di_count), 0)::bigint AS total_di_bound,
                  COALESCE(MIN(di_count), 0)::bigint AS min_di,
                  COALESCE(MAX(di_count), 0)::bigint AS max_di,
                  COALESCE(percentile_cont(0.5) WITHIN GROUP (ORDER BY di_count), 0)::numeric AS p50,
                  COALESCE(percentile_cont(0.9) WITHIN GROUP (ORDER BY di_count), 0)::numeric AS p90,
                  COALESCE(percentile_cont(0.99) WITHIN GROUP (ORDER BY di_count), 0)::numeric AS p99
                FROM per_reg
                """
            )
        ).mappings().one()
        unbound_di = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM product_variants
                    WHERE registry_no IS NULL OR btrim(registry_no) = ''
                    """
                )
            ).scalar()
            or 0
        )
        outliers = db.execute(
            text(
                """
                SELECT registry_no, COUNT(1)::bigint AS di_count
                FROM product_variants
                WHERE registry_no IS NOT NULL AND btrim(registry_no) <> ''
                GROUP BY registry_no
                HAVING COUNT(1) > :threshold
                ORDER BY di_count DESC, registry_no ASC
                LIMIT 100
                """
            ),
            {"threshold": threshold},
        ).mappings().all()

        print(
            json.dumps(
                {
                    "ok": True,
                    "mode": "dry_run",
                    "outlier_threshold": threshold,
                    "distribution": {
                        "registration_count": int(dist.get("registration_count") or 0),
                        "total_di_bound": int(dist.get("total_di_bound") or 0),
                        "min": int(dist.get("min_di") or 0),
                        "max": int(dist.get("max_di") or 0),
                        "p50": float(dist.get("p50") or 0),
                        "p90": float(dist.get("p90") or 0),
                        "p99": float(dist.get("p99") or 0),
                    },
                    "di_unbound_registration_count": unbound_di,
                    "outlier_registrations": [
                        {"registration_no": str(r.get("registry_no") or ""), "di_count": int(r.get("di_count") or 0)}
                        for r in outliers
                    ],
                },
                ensure_ascii=True,
            )
        )
        return 0
    finally:
        db.close()


def _run_udi_promote(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        from app.services.udi_promote import promote_udi_from_device_index

        source_run_id = int(args.source_run_id) if getattr(args, "source_run_id", None) is not None else None
        raw_document_id = UUID(str(args.raw_document_id)) if getattr(args, "raw_document_id", None) else None

        rep = promote_udi_from_device_index(
            db,
            source_run_id=source_run_id,
            raw_document_id=raw_document_id,
            dry_run=(not bool(getattr(args, "execute", False))),
            limit=(int(args.limit) if getattr(args, "limit", None) else None),
            offset=(int(args.offset) if getattr(args, "offset", None) else None),
        )

        print(json.dumps(rep.to_dict, ensure_ascii=True, default=str))
        return 0
    finally:
        db.close()


def _run_udi_promote_snapshot(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        from app.services.udi_promote import promote_udi_from_device_index

        source_run_id = int(args.source_run_id) if getattr(args, "source_run_id", None) is not None else None
        raw_document_id = UUID(str(args.raw_document_id)) if getattr(args, "raw_document_id", None) else None
        source = str(getattr(args, "source", "UDI_PROMOTE"))
        execute = bool(getattr(args, "execute", False))

        rep = promote_udi_from_device_index(
            db,
            source_run_id=source_run_id,
            raw_document_id=raw_document_id,
            source=source,
            dry_run=(not execute),
            limit=(int(args.limit) if getattr(args, "limit", None) else None),
        )

        scanned = int(rep.scanned or 0)
        with_registration = int(rep.with_registration_no or 0)
        missing = int(rep.missing_registration_no or 0)
        pending = int(rep.pending_written or 0)
        promoted = int(rep.promoted or 0)
        failed = int(rep.failed or 0)

        def _pct(n: int, t: int) -> float:
            return round((float(n) * 100.0) / float(t), 2) if t > 0 else 0.0

        snapshot = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "source_run_id": source_run_id,
            "raw_document_id": str(raw_document_id) if raw_document_id else None,
            "execute": bool(execute),
            "limit": int(args.limit) if getattr(args, "limit", None) else None,
            "metrics": {
                "promoted_rate_pct": _pct(promoted, scanned),
                "reg_no_hit_rate_pct": _pct(with_registration, scanned),
                "missing_reg_no_rate_pct": _pct(missing, scanned),
                "pending_rate_pct": _pct(pending, scanned),
                "failure_rate_pct": _pct(failed, scanned),
                "with_registration_no": with_registration,
                "missing_registration_no": missing,
                "pending_written": pending,
                "failed": failed,
            },
        }

        out = rep.to_dict
        out["snapshot"] = snapshot
        print(json.dumps(out, ensure_ascii=True, default=str))
        return 0
    finally:
        db.close()


def _run_udi_index(args: argparse.Namespace) -> int:
    from app.core.config import Settings

    settings = Settings()
    db = SessionLocal()
    try:
        from app.services.udi_index import run_udi_device_index, refresh_udi_registration_index

        execute = bool(getattr(args, "execute", False))
        source_run_id = int(args.source_run_id) if getattr(args, "source_run_id", None) is not None else None
        raw_document_id = UUID(str(args.raw_document_id)) if getattr(args, "raw_document_id", None) else None

        if getattr(args, "staging_dir", None):
            staging = Path(str(args.staging_dir))
        elif source_run_id is not None:
            staging = Path(str(settings.staging_dir)) / f"run_{source_run_id}" / "extracted"
        else:
            raise SystemExit("require --staging-dir or --source-run-id")

        # Standardized import rule: all writes must have source_run_id.
        run = None
        if execute and source_run_id is None:
            part_from = getattr(args, "part_from", None)
            part_to = getattr(args, "part_to", None)
            pkg = "UDID_FULL_RELEASE_20260205"
            if part_from is not None or part_to is not None:
                pkg = f"{pkg}:PART{part_from or ''}-{part_to or ''}"
            run = start_source_run(db, "UDI_INDEX", package_name=pkg, package_md5=None, download_url=str(staging))
            source_run_id = int(run.id)

        try:
            rep = run_udi_device_index(
                db,
                staging_dir=staging,
                raw_document_id=raw_document_id,
                source_run_id=source_run_id,
                dry_run=(not execute),
                limit=(int(args.limit) if getattr(args, "limit", None) else None),
                limit_files=(int(args.limit_files) if getattr(args, "limit_files", None) is not None else None),
                max_devices_per_file=(
                    int(args.max_devices_per_file) if getattr(args, "max_devices_per_file", None) is not None else None
                ),
                part_from=(int(args.part_from) if getattr(args, "part_from", None) is not None else None),
                part_to=(int(args.part_to) if getattr(args, "part_to", None) is not None else None),
            )
        except Exception as e:
            db.rollback()
            if run is not None:
                finish_source_run(
                    db,
                    run,
                    status="FAILED",
                    message=f"udi:index failed: {type(e).__name__}: {e}",
                    records_total=0,
                    records_success=0,
                    records_failed=0,
                    source_notes={"error": str(e), "staging_dir": str(staging), "source_run_id": source_run_id},
                )
            raise

        out = {
            # Required counters/rates for runbook validation.
            "files_seen": int(getattr(rep, "files_seen", 0)),
            "files_total": int(getattr(rep, "files_total", 0)),
            "files_failed": int(getattr(rep, "files_failed", 0)),
            "file_errors": list(getattr(rep, "file_errors", []) or []),
            "devices_parsed": int(rep.total_devices),
            "di_non_empty_rate": float(rep.di_non_empty_rate),
            "reg_no_non_empty_rate": float(rep.reg_non_empty_rate),
            "has_cert_yes_rate": float(getattr(rep, "has_cert_yes_rate", 0.0)),
            "packing_present_rate": float(rep.packing_rate),
            "storage_present_rate": float(rep.storage_rate),
            "sample_packaging_json": rep.sample_packing_json,
            "sample_storage_json": rep.sample_storage_json,
            # Backward-compatible fields (kept stable for existing scripts).
            "total_devices": int(rep.total_devices),
            "di_present": int(rep.di_present),
            "reg_present": int(rep.reg_present),
            "packing_present": int(rep.packing_present),
            "storage_present": int(rep.storage_present),
            "upserted": int(rep.upserted),
            "source_run_id": source_run_id,
        }

        print(json.dumps(out, ensure_ascii=False, default=str))

        # Hard guard: never "silent success" when nothing was scanned.
        if out["files_total"] == 0:
            if run is not None:
                finish_source_run(
                    db,
                    run,
                    status="FAILED",
                    message="files_total=0 (no XML found under staging-dir)",
                    records_total=0,
                    records_success=0,
                    records_failed=0,
                    source_notes=out,
                )
            raise SystemExit(1)
        if execute and out["devices_parsed"] == 0:
            if run is not None:
                finish_source_run(
                    db,
                    run,
                    status="FAILED",
                    message="devices_parsed=0 in execute mode",
                    records_total=0,
                    records_success=0,
                    records_failed=0,
                    source_notes=out,
                )
            raise SystemExit(1)

        if execute and source_run_id is not None:
            # Build/refresh registration-level aggregation for this batch.
            try:
                refreshed = refresh_udi_registration_index(db, source_run_id=int(source_run_id))
            except Exception as e:
                if run is not None:
                    finish_source_run(
                        db,
                        run,
                        status="FAILED",
                        message=f"refresh_udi_registration_index failed: {e}",
                        records_total=int(out["devices_parsed"]),
                        records_success=int(out["upserted"]),
                        records_failed=int(out["devices_parsed"]) - int(out["upserted"]),
                        source_notes=out,
                    )
                raise
            out["udi_registration_index_refreshed"] = int(refreshed)
            print(json.dumps({"udi_registration_index_refreshed": int(refreshed)}, ensure_ascii=False, default=str))

        if run is not None:
            msg = None
            if int(out.get("files_failed") or 0) > 0:
                msg = f"completed with {int(out.get('files_failed') or 0)} XML parse error file(s)"
            finish_source_run(
                db,
                run,
                status="SUCCESS",
                message=msg,
                records_total=int(out["devices_parsed"]),
                records_success=int(out["upserted"]),
                records_failed=max(0, int(out["devices_parsed"]) - int(out["upserted"])),
                source_notes=out,
            )
        return 0
    finally:
        db.close()


def _run_udi_variants(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        from app.services.udi_variants import upsert_udi_variants_from_device_index

        source_run_id = int(args.source_run_id) if getattr(args, "source_run_id", None) is not None else None
        rep = upsert_udi_variants_from_device_index(
            db,
            source_run_id=source_run_id,
            limit=(int(args.limit) if getattr(args, "limit", None) else None),
            dry_run=(not bool(getattr(args, "execute", False))),
        )
        print(json.dumps(rep.to_dict, ensure_ascii=True, default=str))
        return 0 if int(rep.failed or 0) == 0 else 1
    finally:
        db.close()

def _run_udi_products_enrich(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        from app.services.udi_products_enrich import enrich_products_from_udi_device_index

        source_run_id = int(args.source_run_id) if getattr(args, "source_run_id", None) is not None else None
        rep = enrich_products_from_udi_device_index(
            db,
            source_run_id=source_run_id,
            limit=(int(args.limit) if getattr(args, "limit", None) else None),
            dry_run=(not bool(getattr(args, "execute", False))),
            description_max_len=int(getattr(args, "description_max_len", 2000) or 2000),
        )
        print(json.dumps(rep.to_dict, ensure_ascii=True, default=str))
        return 0 if int(rep.failed or 0) == 0 else 1
    finally:
        db.close()

def _run_udi_params(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        from app.services.udi_params import (
            compute_udi_candidates_full,
            compute_udi_candidates_sample,
            upsert_candidates,
            write_allowlisted_params,
        )

        source_run_id = int(args.source_run_id) if getattr(args, "source_run_id", None) is not None else None
        dry_run = not bool(getattr(args, "execute", False))
        topn = max(1, int(getattr(args, "top", 50) or 50))
        sample_rows = max(100, int(getattr(args, "sample_rows", 20000) or 20000))
        sample_limit = max(1000, int(getattr(args, "sample_limit", 200000) or 200000))
        with_candidates = bool(getattr(args, "with_candidates", False))
        full_scan = bool(getattr(args, "full_scan", False))
        raw_start = getattr(args, "start_cursor", None)
        start_cursor = str(raw_start).strip() if isinstance(raw_start, str) else None
        if start_cursor == "":
            start_cursor = None

        if not dry_run:
            def _progress(batch: Any) -> None:
                print(
                    json.dumps(
                        {
                            "type": "batch",
                            "batch_no": int(batch.batch_no),
                            "rows_scanned": int(batch.rows_scanned),
                            "rows_written": int(batch.rows_written),
                            "elapsed_ms": int(batch.elapsed_ms),
                            "cursor": str(batch.cursor),
                        },
                        ensure_ascii=False,
                    )
                )

            rep = write_allowlisted_params(
                db,
                source_run_id=source_run_id,
                limit=(int(args.limit) if getattr(args, "limit", None) else None),
                only_allowlisted=bool(getattr(args, "only_allowlisted", False)),
                dry_run=False,
                batch_size=max(1000, int(getattr(args, "batch_size", 50000) or 50000)),
                resume=bool(getattr(args, "resume", True)),
                start_cursor=start_cursor,
                progress_cb=_progress,
            )
            out: dict[str, object] = {"write": rep.to_dict}
            if with_candidates:
                if full_scan:
                    candidates_rows, candidate_meta = compute_udi_candidates_full(
                        db,
                        source="UDI",
                        source_run_id=source_run_id,
                        top=topn,
                        sample_rows=sample_rows,
                    )
                else:
                    candidates_rows, candidate_meta = compute_udi_candidates_sample(
                        db,
                        source="UDI",
                        source_run_id=source_run_id,
                        top=topn,
                        sample_limit=sample_limit,
                        start_cursor=start_cursor,
                    )
                wrote = upsert_candidates(db, rows=candidates_rows)
                rep.candidates_written = wrote
                out["candidates_top"] = candidates_rows[:topn]
                out["total_fields"] = len(candidates_rows)
                out["candidates_meta"] = candidate_meta
                db.commit()
            print(json.dumps(out, ensure_ascii=False, default=str))
            return 0 if int(rep.failed or 0) == 0 else 1

        if full_scan:
            top_rows, candidate_meta = compute_udi_candidates_full(
                db,
                source="UDI",
                source_run_id=source_run_id,
                top=topn,
                sample_rows=sample_rows,
            )
        else:
            top_rows, candidate_meta = compute_udi_candidates_sample(
                db,
                source="UDI",
                source_run_id=source_run_id,
                top=topn,
                sample_limit=sample_limit,
                start_cursor=start_cursor,
            )
        wrote = upsert_candidates(db, rows=top_rows)
        db.commit()
        out = {
            "candidates_top": top_rows,
            "total_fields": len(top_rows),
            "candidates_written": wrote,
            "candidates_meta": candidate_meta,
        }
        print(json.dumps(out, ensure_ascii=False, default=str))
        return 0
    finally:
        db.close()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.cmd == 'sync':
        raise SystemExit(_run_sync(args))
    if args.cmd == 'daily-metrics':
        raise SystemExit(_run_daily_metrics(args.metric_date))
    if args.cmd == 'daily-digest':
        raise SystemExit(_run_daily_digest(args.digest_date, args.force))
    if args.cmd == 'grant':
        raise SystemExit(_run_grant(args.email, args.months, args.reason, args.note, args.actor_email))
    if args.cmd == 'reclassify_ivd':
        raise SystemExit(_run_reclassify_ivd(dry_run=(not bool(args.execute))))
    if args.cmd == 'ivd:classify':
        raise SystemExit(_run_reclassify_ivd(dry_run=(not bool(args.execute))))
    if args.cmd in {'cleanup_non_ivd', 'cleanup-non-ivd'}:
        if bool(args.execute) and not (getattr(args, 'archive_batch_id', None) or '').strip():
            raise SystemExit('--archive-batch-id is required when using --execute (for rollback traceability)')
        raise SystemExit(
            _run_cleanup_non_ivd_v2(
                dry_run=(not bool(args.execute)),
                recompute_days=int(args.recompute_days),
                notes=args.notes,
                archive_batch_id=getattr(args, 'archive_batch_id', None),
            )
        )
    if args.cmd == 'ivd:cleanup':
        if bool(args.execute) and not (getattr(args, 'archive_batch_id', None) or '').strip():
            raise SystemExit('--archive-batch-id is required when using --execute (for rollback traceability)')
        raise SystemExit(
            _run_cleanup_non_ivd_v2(
                dry_run=(not bool(args.execute)),
                recompute_days=365,
                notes=(f"archive_batch_id={args.archive_batch_id}" if args.archive_batch_id else None),
                archive_batch_id=(str(args.archive_batch_id).strip() if args.archive_batch_id else None),
            )
        )
    if args.cmd == 'ivd:rollback':
        raise SystemExit(
            _run_ivd_rollback(
                archive_batch_id=str(args.archive_batch_id),
                dry_run=(not bool(args.execute)),
                recompute_days=int(getattr(args, 'recompute_days', 365)),
            )
        )
    if args.cmd == 'metrics:recompute':
        raise SystemExit(_run_metrics_recompute(scope=str(args.scope), since=args.since))
    if args.cmd == 'source:udi':
        raise SystemExit(_run_source_udi(execute=bool(args.execute), date_label=args.date))
    if args.cmd == 'local_registry_supplement':
        raise SystemExit(
            _run_local_registry_supplement(
                folder=str(args.folder),
                dry_run=(not bool(args.execute)),
                ingest_new=bool(args.ingest_new),
                ingest_chunk_size=int(args.ingest_chunk_size),
            )
        )
    if args.cmd == 'params:extract':
        raise SystemExit(
            _run_params_extract(
                dry_run=(not bool(args.execute)),
                raw_document_id=getattr(args, 'raw_document_id', None),
                file_path=getattr(args, 'file', None),
                source_url=getattr(args, 'source_url', None),
                doc_type=getattr(args, 'doc_type', None),
                run_id=getattr(args, 'run_id', None),
                di=getattr(args, 'di', None),
                registry_no=getattr(args, 'registry_no', None),
                extract_version=str(getattr(args, 'extract_version', 'param_v1_20260213')),
            )
        )
    if args.cmd == 'params:rollback':
        raise SystemExit(_run_params_rollback(dry_run=(not bool(args.execute)), raw_document_id=str(args.raw_document_id)))
    if args.cmd == 'nhsa:ingest':
        raise SystemExit(_run_nhsa_ingest(args))
    if args.cmd == 'nhsa:rollback':
        raise SystemExit(_run_nhsa_rollback(args))
    if args.cmd == 'procurement:ingest':
        raise SystemExit(_run_procurement_ingest(args))
    if args.cmd == 'procurement:rollback':
        raise SystemExit(_run_procurement_rollback(args))
    if args.cmd == 'nmpa:snapshots':
        raise SystemExit(_run_nmpa_snapshots(since=str(args.since)))
    if args.cmd == 'nmpa:diffs':
        raise SystemExit(_run_nmpa_diffs(target_date=str(args.date)))
    if args.cmd == 'methodology:seed':
        raise SystemExit(_run_methodology_seed(dry_run=(not bool(args.execute)), file_path=str(args.file)))
    if args.cmd == 'methodology:map':
        raise SystemExit(
            _run_methodology_map(
                dry_run=(not bool(args.execute)),
                file_path=(str(args.file) if getattr(args, 'file', None) else None),
                registration_nos=(list(args.registration_no) if getattr(args, 'registration_no', None) else None),
            )
        )
    if args.cmd == 'registration:events':
        raise SystemExit(
            _run_registration_events(
                dry_run=(not bool(args.execute)),
                date_str=(str(args.date).strip() if getattr(args, 'date', None) else None),
                since_str=(str(args.since).strip() if getattr(args, 'since', None) else None),
            )
        )
    if args.cmd == 'derive-registration-events':
        raise SystemExit(
            _run_derive_registration_events(
                dry_run=(not bool(args.execute)),
                since_str=str(args.since),
            )
        )
    if args.cmd == 'source:run':
        raise SystemExit(_run_source_runner(args))
    if args.cmd == 'source:run-all':
        raise SystemExit(_run_source_runner_all(args))
    if args.cmd == 'udi:audit':
        raise SystemExit(_run_udi_audit(args))
    if args.cmd == 'udi:promote':
        raise SystemExit(_run_udi_promote(args))
    if args.cmd == 'udi:promote-snapshot':
        raise SystemExit(_run_udi_promote_snapshot(args))
    if args.cmd == 'udi:index':
        raise SystemExit(_run_udi_index(args))
    if args.cmd == 'udi:variants':
        raise SystemExit(_run_udi_variants(args))
    if args.cmd == 'udi:products-enrich':
        raise SystemExit(_run_udi_products_enrich(args))
    if args.cmd == 'udi:params':
        raise SystemExit(_run_udi_params(args))
    if args.cmd == 'methodology:map-products':
        db = SessionLocal()
        try:
            from app.services.ontology_v1_methodology import map_products_methodologies_v1

            res = map_products_methodologies_v1(db, dry_run=(not bool(args.execute)), limit=(int(args.limit) if args.limit else None))
            print(json.dumps(res.__dict__, ensure_ascii=True, default=str))
            raise SystemExit(0 if res.ok else 1)
        finally:
            db.close()
    if args.cmd == 'lri-compute':
        from datetime import date as dt_date

        target = dt_date.fromisoformat(str(args.date)) if getattr(args, 'date', None) else None
        db = SessionLocal()
        try:
            from app.services.lri_v1 import compute_lri_v1

            res = compute_lri_v1(
                db,
                asof=target,
                dry_run=(not bool(args.execute)),
                model_version=str(getattr(args, 'model_version', 'lri_v1')),
                upsert_mode=bool(getattr(args, 'upsert', False)),
            )
            print(json.dumps(res.__dict__, ensure_ascii=True, default=str))
            raise SystemExit(0 if res.ok else 1)
        finally:
            db.close()
    if args.cmd == 'loop':
        from app.workers.loop import main as loop_main

        loop_main()
        return

    # backward compatible default behavior
    raise SystemExit(_run_sync(argparse.Namespace(package_url=None, checksum=None, checksum_algorithm='md5', no_clean_staging=False)))


if __name__ == '__main__':
    main()
