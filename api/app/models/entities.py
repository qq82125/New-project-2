from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Company(Base):
    __tablename__ = 'companies'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    country: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    raw_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    raw: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    products: Mapped[List['Product']] = relationship('Product', back_populates='company')


class Registration(Base):
    __tablename__ = 'registrations'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    filing_no: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    approval_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    raw_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    products: Mapped[List['Product']] = relationship('Product', back_populates='registration')


class Product(Base):
    __tablename__ = 'products'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    udi_di: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    reg_no: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(500), index=True)
    class_name: Mapped[Optional[str]] = mapped_column('class', String(120), nullable=True)
    approved_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    specification: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='ACTIVE', index=True)
    is_ivd: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=None, index=True)
    ivd_category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ivd_subtypes: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    ivd_reason: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    ivd_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ivd_source: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ivd_confidence: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('companies.id'), nullable=True
    )
    registration_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('registrations.id'), nullable=True
    )
    raw_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    raw: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped[Optional[Company]] = relationship('Company', back_populates='products')
    registration: Mapped[Optional[Registration]] = relationship('Registration', back_populates='products')


class ProductArchive(Base):
    __tablename__ = 'products_archive'

    archive_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    udi_di: Mapped[str] = mapped_column(String(128), index=True)
    reg_no: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(500), index=True)
    class_name: Mapped[Optional[str]] = mapped_column('class', String(120), nullable=True)
    approved_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    specification: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='ACTIVE', index=True)
    is_ivd: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=None, index=True)
    ivd_category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ivd_subtypes: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    ivd_reason: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    ivd_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    registration_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    raw_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    raw: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    cleanup_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    archive_batch_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    archive_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class RawDocument(Base):
    __tablename__ = 'raw_documents'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doc_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    run_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    parse_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    parse_log: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ProductVariant(Base):
    __tablename__ = 'product_variants'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    di: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    registry_no: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('products.id'), nullable=True)
    product_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_spec: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    packaging: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_ivd: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    ivd_category: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    ivd_version: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProductParam(Base):
    __tablename__ = 'product_params'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    di: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    registry_no: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    param_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    value_num: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    range_low: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    range_high: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    conditions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    raw_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('raw_documents.id'), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.5)
    extract_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductRejected(Base):
    __tablename__ = 'products_rejected'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    source_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    raw_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('raw_documents.id'), nullable=True)
    reason: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    ivd_version: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    rejected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class SourceRun(Base):
    __tablename__ = 'source_runs'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    package_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    package_md5: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    download_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True, default='RUNNING')
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    records_total: Mapped[int] = mapped_column(Integer, default=0)
    records_success: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    added_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    removed_count: Mapped[int] = mapped_column(Integer, default=0)
    ivd_kept_count: Mapped[int] = mapped_column(Integer, default=0)
    non_ivd_skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    source_notes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ChangeLog(Base):
    __tablename__ = 'change_log'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('products.id'), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(30), index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    change_type: Mapped[str] = mapped_column(String(20), index=True)
    changed_fields: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    before_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    before_raw: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    after_raw: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    source_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey('source_runs.id'), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    change_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Subscription(Base):
    __tablename__ = 'subscriptions'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    subscriber_key: Mapped[str] = mapped_column(String(120), index=True, default='default')
    channel: Mapped[str] = mapped_column(String(20), default='webhook', index=True)
    email_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subscription_type: Mapped[str] = mapped_column(String(30), index=True)
    target_value: Mapped[str] = mapped_column(String(255), index=True)
    webhook_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_digest_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SubscriptionDelivery(Base):
    __tablename__ = 'subscription_deliveries'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey('subscriptions.id'), index=True)
    dedup_hash: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default='PENDING', index=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyDigestRun(Base):
    __tablename__ = 'daily_digest_runs'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    digest_date: Mapped[date] = mapped_column(Date, index=True)
    subscriber_key: Mapped[str] = mapped_column(String(120), index=True)
    channel: Mapped[str] = mapped_column(String(20), default='webhook')
    status: Mapped[str] = mapped_column(String(20), default='pending')
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExportUsage(Base):
    __tablename__ = 'export_usage'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    usage_date: Mapped[date] = mapped_column(Date, index=True)
    plan: Mapped[str] = mapped_column(String(30), index=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AdminConfig(Base):
    __tablename__ = 'admin_configs'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    config_value: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataSource(Base):
    __tablename__ = 'data_sources'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(20), index=True)
    config_encrypted: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DailyMetric(Base):
    __tablename__ = 'daily_metrics'

    metric_date: Mapped[date] = mapped_column(Date, primary_key=True)
    new_products: Mapped[int] = mapped_column(Integer, default=0)
    updated_products: Mapped[int] = mapped_column(Integer, default=0)
    cancelled_products: Mapped[int] = mapped_column(Integer, default=0)
    expiring_in_90d: Mapped[int] = mapped_column(Integer, default=0)
    active_subscriptions: Mapped[int] = mapped_column(Integer, default=0)
    source_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey('source_runs.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default='user', index=True)
    # Membership snapshot (current state). Historical records live in membership_grants.
    plan: Mapped[str] = mapped_column(Text, default='free', index=True)
    plan_status: Mapped[str] = mapped_column(Text, default='inactive', index=True)
    plan_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MembershipGrant(Base):
    __tablename__ = 'membership_grants'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), index=True)
    granted_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('users.id'), nullable=True, index=True
    )
    plan: Mapped[str] = mapped_column(Text, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MembershipEvent(Base):
    __tablename__ = 'membership_events'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id'), index=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey('users.id'), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(Text, index=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataCleanupRun(Base):
    __tablename__ = 'data_cleanup_runs'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    archived_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
