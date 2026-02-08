from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any

import requests
import smtplib
from sqlalchemy import and_, desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ChangeLog, DailyDigestRun, Product, Subscription


def _fetch_changes(db: Session, digest_date: date) -> list[tuple[ChangeLog, Product]]:
    start = datetime.combine(digest_date, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    stmt = (
        select(ChangeLog, Product)
        .join(Product, and_(ChangeLog.product_id == Product.id, ChangeLog.entity_type == 'product'))
        .where(ChangeLog.change_date >= start, ChangeLog.change_date < end)
        .order_by(desc(ChangeLog.change_date))
    )
    return list(db.execute(stmt).all())


def _match_subscription(subscription: Subscription, product: Product) -> bool:
    target = (subscription.target_value or '').strip().lower()
    if not target:
        return False

    if subscription.subscription_type == 'company':
        company_name = (product.company.name if product.company else '') or ''
        return target in company_name.lower()

    if subscription.subscription_type == 'product':
        return target in (product.name or '').lower() or target in (product.udi_di or '').lower() or target in (
            product.reg_no or ''
        ).lower()

    if subscription.subscription_type == 'keyword':
        text = ' '.join(
            [
                product.name or '',
                product.udi_di or '',
                product.reg_no or '',
                (product.company.name if product.company else '') or '',
            ]
        ).lower()
        return target in text

    return False


def _dedupe_changes(changes: list[tuple[ChangeLog, Product]]) -> list[dict[str, Any]]:
    by_product: dict[str, dict[str, Any]] = {}
    for change, product in changes:
        key = str(product.id)
        if key in by_product:
            continue
        by_product[key] = {
            'product_id': str(product.id),
            'product_name': product.name,
            'change_type': change.change_type,
            'change_date': change.change_date.isoformat(),
            'changed_fields': change.changed_fields,
        }
    return list(by_product.values())


def _send_webhook(url: str, payload: dict) -> bool:
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code < 400
    except Exception:
        return False


def _send_email(email_to: str, payload: dict) -> bool:
    settings = get_settings()
    if not settings.smtp_host or not settings.email_from:
        return False

    message = EmailMessage()
    message['Subject'] = f"NMPA IVD Daily Digest {payload['digest_date']}"
    message['From'] = settings.email_from
    message['To'] = email_to

    lines = [f"subscriber: {payload['subscriber_key']}", f"total_matches: {payload['total_matches']}", '']
    for item in payload['changes']:
        lines.append(f"- {item['product_name']} ({item['change_type']}) @ {item['change_date']}")
    message.set_content('\n'.join(lines))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
        return True
    except Exception:
        return False


def _send_by_channel(channel: str, destination: str, payload: dict) -> bool:
    if channel == 'webhook':
        return _send_webhook(destination, payload)
    if channel == 'email':
        return _send_email(destination, payload)
    return False


def dispatch_daily_subscription_digest(
    db: Session,
    digest_date: date | None = None,
    force: bool = False,
) -> dict[str, int]:
    target_date = digest_date or date.today()
    active_subs = list(db.scalars(select(Subscription).where(Subscription.is_active.is_(True))))

    grouped: dict[tuple[str, str], list[Subscription]] = defaultdict(list)
    for sub in active_subs:
        channel = (sub.channel or 'webhook').lower()
        grouped[(sub.subscriber_key, channel)].append(sub)

    changes = _fetch_changes(db, target_date)

    sent = 0
    skipped = 0
    failed = 0

    for (subscriber_key, channel), subs in grouped.items():
        destination = None
        if channel == 'webhook':
            destination = next((s.webhook_url for s in subs if s.webhook_url), None)
        elif channel == 'email':
            destination = next((s.email_to for s in subs if s.email_to), None) or (
                subscriber_key if '@' in subscriber_key else None
            )

        if not destination:
            skipped += 1
            continue

        exists_stmt = select(DailyDigestRun).where(
            DailyDigestRun.digest_date == target_date,
            DailyDigestRun.subscriber_key == subscriber_key,
            DailyDigestRun.channel == channel,
        )
        existing = db.scalar(exists_stmt)
        if existing and existing.status == 'sent' and not force:
            skipped += 1
            continue

        matched = []
        for change, product in changes:
            if any(_match_subscription(sub, product) for sub in subs):
                matched.append((change, product))

        payload = {
            'digest_date': target_date.isoformat(),
            'subscriber_key': subscriber_key,
            'channel': channel,
            'total_matches': 0,
            'changes': [],
        }

        deduped = _dedupe_changes(matched)
        payload['changes'] = deduped
        payload['total_matches'] = len(deduped)

        ok = _send_by_channel(channel, destination, payload)
        status = 'sent' if ok else 'failed'

        upsert_stmt = insert(DailyDigestRun).values(
            digest_date=target_date,
            subscriber_key=subscriber_key,
            channel=channel,
            status=status,
            payload=payload,
            sent_at=datetime.now(timezone.utc) if ok else None,
        )
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=[DailyDigestRun.digest_date, DailyDigestRun.subscriber_key, DailyDigestRun.channel],
            set_={
                'status': status,
                'payload': payload,
                'sent_at': datetime.now(timezone.utc) if ok else None,
            },
        )
        db.execute(upsert_stmt)
        db.commit()

        if ok:
            sent += 1
        else:
            failed += 1

    return {'sent': sent, 'failed': failed, 'skipped': skipped}
