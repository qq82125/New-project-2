from __future__ import annotations

import argparse
import json
from datetime import date

from app.db.session import SessionLocal
from app.services.metrics import generate_daily_metrics
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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.cmd == 'sync':
        raise SystemExit(_run_sync(args))
    if args.cmd == 'daily-metrics':
        raise SystemExit(_run_daily_metrics(args.metric_date))
    if args.cmd == 'daily-digest':
        raise SystemExit(_run_daily_digest(args.digest_date, args.force))
    if args.cmd == 'loop':
        loop_main()
        return

    # backward compatible default behavior
    raise SystemExit(_run_sync(argparse.Namespace(package_url=None, checksum=None, checksum_algorithm='md5', no_clean_staging=False)))


if __name__ == '__main__':
    main()
