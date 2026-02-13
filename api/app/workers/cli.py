from __future__ import annotations

import argparse
import json
from datetime import date

from app.db.session import SessionLocal
from app.repositories.users import get_user_by_email
from app.repositories.admin_membership import admin_grant_membership
from app.repositories.source_runs import finish_source_run, start_source_run
from app.services.data_cleanup import rollback_non_ivd_cleanup, run_non_ivd_cleanup
from app.services.local_registry_supplement import run_local_registry_supplement
from app.services.metrics import generate_daily_metrics
from app.services.reclassify_ivd import run_reclassify_ivd
from app.services.subscriptions import dispatch_daily_subscription_digest
from app.workers.loop import main as loop_main
from app.workers.sync import sync_nmpa_ivd


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
    return parser


def _run_sync(args: argparse.Namespace) -> int:
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
        row = generate_daily_metrics(db, target)
        print(json.dumps({'metric_date': row.metric_date.isoformat(), 'new_products': row.new_products}, ensure_ascii=True))
        return 0
    finally:
        db.close()


def _run_daily_digest(digest_date: str | None, force: bool) -> int:
    target = date.fromisoformat(digest_date) if digest_date else None
    db = SessionLocal()
    try:
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
        result = run_non_ivd_cleanup(db, dry_run=dry_run, recompute_days=recompute_days, notes=notes)
        print(
            json.dumps(
                {
                    'ok': True,
                    'run_id': result.run_id,
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


def _run_ivd_rollback(*, archive_batch_id: str, dry_run: bool) -> int:
    db = SessionLocal()
    try:
        result = rollback_non_ivd_cleanup(
            db,
            archive_batch_id=archive_batch_id,
            dry_run=dry_run,
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
    target_since = date.fromisoformat(since) if since else (date.today() - date.resolution * 365)
    days = max(1, (date.today() - target_since).days + 1)
    db = SessionLocal()
    try:
        from app.services.metrics import regenerate_daily_metrics

        rows = regenerate_daily_metrics(db, days=days)
        print(json.dumps({'ok': True, 'scope': scope, 'since': target_since.isoformat(), 'days': days, 'rows': len(rows)}, ensure_ascii=True))
        return 0
    finally:
        db.close()


def _run_source_udi(*, execute: bool, date_label: str | None) -> int:
    if not execute:
        print(json.dumps({'ok': True, 'dry_run': True, 'source': 'udi', 'date': date_label, 'message': 'no side effects'}))
        return 0
    result = sync_nmpa_ivd(clean_staging=True)
    print(json.dumps({'ok': result.status == 'success', 'source': 'udi', 'date': date_label, **result.__dict__}, ensure_ascii=True))
    return 0 if result.status == 'success' else 1


def _run_reclassify_ivd(*, dry_run: bool) -> int:
    db = SessionLocal()
    try:
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
        raise SystemExit(
            _run_cleanup_non_ivd(
                dry_run=(not bool(args.execute)),
                recompute_days=int(args.recompute_days),
                notes=args.notes,
            )
        )
    if args.cmd == 'ivd:cleanup':
        raise SystemExit(
            _run_cleanup_non_ivd(
                dry_run=(not bool(args.execute)),
                recompute_days=365,
                notes=(f"archive_batch_id={args.archive_batch_id}" if args.archive_batch_id else None),
            )
        )
    if args.cmd == 'ivd:rollback':
        raise SystemExit(
            _run_ivd_rollback(
                archive_batch_id=str(args.archive_batch_id),
                dry_run=(not bool(args.execute)),
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
    if args.cmd == 'loop':
        loop_main()
        return

    # backward compatible default behavior
    raise SystemExit(_run_sync(argparse.Namespace(package_url=None, checksum=None, checksum_algorithm='md5', no_clean_staging=False)))


if __name__ == '__main__':
    main()
