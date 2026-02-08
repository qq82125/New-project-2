from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import Date, cast, desc, func, select
from sqlalchemy.orm import Session

from app.models import AdminConfig, ChangeLog, ExportUsage, Product, Registration, SourceRun, Subscription, SubscriptionDelivery


def get_product_timeline(db: Session, product_id: str, limit: int = 50) -> list[ChangeLog]:
    stmt = (
        select(ChangeLog)
        .where(ChangeLog.entity_type == 'product', ChangeLog.entity_id == product_id)
        .order_by(desc(ChangeLog.changed_at))
        .limit(limit)
    )
    return list(db.scalars(stmt))


def list_subscriptions(db: Session) -> list[Subscription]:
    return list(db.scalars(select(Subscription).order_by(desc(Subscription.created_at))))


def get_active_subscriptions(db: Session) -> list[Subscription]:
    stmt = select(Subscription).where(Subscription.is_active.is_(True))
    return list(db.scalars(stmt))


def create_subscription(db: Session, subscription_type: str, target_value: str, webhook_url: str | None) -> Subscription:
    sub = Subscription(subscription_type=subscription_type, target_value=target_value, webhook_url=webhook_url)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def deactivate_subscription(db: Session, subscription_id: int) -> bool:
    sub = db.get(Subscription, subscription_id)
    if not sub:
        return False
    sub.is_active = False
    db.add(sub)
    db.commit()
    return True


def delivery_exists(db: Session, subscription_id: int, dedup_hash: str) -> bool:
    stmt = select(SubscriptionDelivery.id).where(
        SubscriptionDelivery.subscription_id == subscription_id,
        SubscriptionDelivery.dedup_hash == dedup_hash,
    )
    return db.scalar(stmt) is not None


def create_delivery(
    db: Session,
    subscription_id: int,
    dedup_hash: str,
    payload: dict,
    status: str,
) -> SubscriptionDelivery:
    delivery = SubscriptionDelivery(
        subscription_id=subscription_id,
        dedup_hash=dedup_hash,
        payload=payload,
        status=status,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery


def get_export_usage(db: Session, today: date, plan: str) -> ExportUsage | None:
    stmt = select(ExportUsage).where(ExportUsage.usage_date == today, ExportUsage.plan == plan)
    return db.scalar(stmt)


def increase_export_usage(db: Session, today: date, plan: str) -> ExportUsage:
    usage = get_export_usage(db, today, plan)
    if usage:
        usage.used_count += 1
    else:
        usage = ExportUsage(usage_date=today, plan=plan, used_count=1)
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage


def weekly_category_trends(db: Session, weeks: int = 8) -> list[tuple[date, str | None, int]]:
    since = date.today() - timedelta(days=7 * weeks)
    week_bucket = cast(func.date_trunc('week', Product.created_at), Date)
    stmt = (
        select(week_bucket, Product.category, func.count(Product.id))
        .where(cast(Product.created_at, Date) >= since)
        .group_by(week_bucket, Product.category)
        .order_by(week_bucket.desc())
    )
    return [(row[0], row[1], row[2]) for row in db.execute(stmt).all()]


def new_company_ranking(db: Session, days: int = 7, limit: int = 10) -> list[tuple[str, int]]:
    since = date.today() - timedelta(days=days)
    stmt = (
        select(func.coalesce(Product.raw_json['company_name'].astext, '未知企业').label('label'), func.count(Product.id))
        .where(cast(Product.created_at, Date) >= since)
        .group_by('label')
        .order_by(func.count(Product.id).desc())
        .limit(limit)
    )
    return [(row[0], row[1]) for row in db.execute(stmt).all()]


def expiring_registrations(db: Session, days: int = 90, limit: int = 20) -> list[tuple[str, int]]:
    until = date.today() + timedelta(days=days)
    stmt = (
        select(Registration.registration_no, func.count(Product.id))
        .join(Product, Product.registration_id == Registration.id)
        .where(Registration.expiry_date.is_not(None), Registration.expiry_date <= until)
        .group_by(Registration.registration_no)
        .order_by(Registration.expiry_date.asc())
        .limit(limit)
    )
    return [(row[0], row[1]) for row in db.execute(stmt).all()]


def get_admin_config(db: Session, key: str) -> AdminConfig | None:
    stmt = select(AdminConfig).where(AdminConfig.config_key == key)
    return db.scalar(stmt)


def list_admin_configs(db: Session) -> list[AdminConfig]:
    return list(db.scalars(select(AdminConfig).order_by(AdminConfig.config_key.asc())))


def upsert_admin_config(db: Session, key: str, value: dict) -> AdminConfig:
    cfg = get_admin_config(db, key)
    if cfg:
        cfg.config_value = value
    else:
        cfg = AdminConfig(config_key=key, config_value=value)
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def failed_runs(db: Session, limit: int = 20) -> list[SourceRun]:
    stmt = (
        select(SourceRun)
        .where(SourceRun.status == 'FAILED')
        .order_by(desc(SourceRun.started_at))
        .limit(limit)
    )
    return list(db.scalars(stmt))
