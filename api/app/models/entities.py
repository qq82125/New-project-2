from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, func
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


class CompanyAlias(Base):
    __tablename__ = 'company_aliases'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alias_name: Mapped[str] = mapped_column(Text, nullable=False, index=True, unique=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('companies.id'), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.80)
    source: Mapped[str] = mapped_column(Text, nullable=False, default='rule')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Registration(Base):
    __tablename__ = 'registrations'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    filing_no: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    approval_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    field_meta: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
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
    superseded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('products.id'), nullable=True, index=True
    )
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
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
    archive_status: Mapped[str] = mapped_column(String(20), nullable=False, default='active', index=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    archive_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class RawSourceRecord(Base):
    __tablename__ = 'raw_source_records'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source_run_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('source_runs.id'), nullable=True, index=True
    )
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_grade: Mapped[str] = mapped_column(String(1), nullable=False, default='C')
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    parse_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    parse_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    archive_status: Mapped[str] = mapped_column(String(20), nullable=False, default='active', index=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    archive_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProductUdiMap(Base):
    __tablename__ = 'product_udi_map'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_no: Mapped[str] = mapped_column(
        String(120), ForeignKey('registrations.registration_no'), nullable=False, index=True
    )
    di: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    match_type: Mapped[str] = mapped_column(String(20), nullable=False, default='direct', index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.80)
    match_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reversible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    linked_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_source_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('raw_source_records.id'), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UdiDiMaster(Base):
    __tablename__ = 'udi_di_master'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    di: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    payload_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    has_cert: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    registration_no_norm: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    packaging_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    storage_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    raw_source_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('raw_source_records.id'), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PendingUdiLink(Base):
    __tablename__ = 'pending_udi_links'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    di: Mapped[str] = mapped_column(String(128), ForeignKey('udi_di_master.di'), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    match_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.80, index=True)
    reversible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    linked_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='PENDING', index=True)
    raw_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('raw_source_records.id'), nullable=True
    )
    raw_source_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('raw_source_records.id'), nullable=True, index=True
    )
    candidate_company_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    candidate_product_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PendingRecord(Base):
    __tablename__ = 'pending_records'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('source_runs.id'), nullable=False, index=True)
    raw_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('raw_documents.id'), nullable=False, index=False
    )
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=False)
    registration_no_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    candidate_registry_no: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    candidate_company: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    candidate_product_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='open', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PendingDocument(Base):
    __tablename__ = 'pending_documents'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('raw_documents.id'), nullable=False, unique=True, index=True
    )
    source_run_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('source_runs.id'), nullable=True, index=True
    )
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MethodologyMaster(Base):
    __tablename__ = 'methodology_master'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    name_cn: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    aliases: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProductMethodologyMap(Base):
    __tablename__ = 'product_methodology_map'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True
    )
    methodology_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('methodology_master.id'), nullable=False, index=True
    )
    evidence_raw_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('raw_documents.id'), nullable=True
    )
    evidence_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.80)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LriScore(Base):
    __tablename__ = 'lri_scores'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('registrations.id'), nullable=False, index=True
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('products.id'), nullable=True)
    methodology_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('methodology_master.id'), nullable=True
    )

    tte_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    renewal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    competitive_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gp_new_12m: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    tte_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rh_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cd_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gp_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lri_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lri_norm: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=0)

    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False, default='lri_v1', index=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    source_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey('source_runs.id'), nullable=True)


class ProductVariant(Base):
    __tablename__ = 'product_variants'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    di: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    registry_no: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    registration_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('registrations.id'), nullable=True, index=True
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('products.id'), nullable=True)
    product_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_spec: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    packaging: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSONB (UDI packingList): stored as a JSON array or object; keep typing loose for ORM compatibility.
    packaging_json: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_raw_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('raw_documents.id'), nullable=True, index=True
    )
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
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey('products.id'), nullable=True, index=True)
    param_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    value_num: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    range_low: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    range_high: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    conditions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    evidence_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    raw_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('raw_documents.id'), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.5)
    extract_version: Mapped[str] = mapped_column(String(40), nullable=False)
    param_key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)
    observed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
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


class NhsaCode(Base):
    __tablename__ = 'nhsa_codes'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    snapshot_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # YYYY-MM
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    spec: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    raw_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('raw_documents.id'), nullable=False, index=True)
    source_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('source_runs.id'), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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


class ChangeLogArchive(Base):
    __tablename__ = 'change_log_archive'

    archive_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    change_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    changed_fields: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    before_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    before_raw: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    after_raw: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    source_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    change_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class NmpaSnapshot(Base):
    __tablename__ = 'nmpa_snapshots'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('registrations.id'), nullable=False, index=True
    )
    raw_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('raw_documents.id'), nullable=True, index=False
    )
    source_run_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('source_runs.id'), nullable=True, index=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FieldDiff(Base):
    __tablename__ = 'field_diffs'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('nmpa_snapshots.id'), nullable=False, index=True
    )
    registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('registrations.id'), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.80)
    source_run_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('source_runs.id'), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShadowDiffError(Base):
    __tablename__ = 'shadow_diff_errors'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('raw_documents.id'), nullable=True, index=True
    )
    raw_source_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('raw_source_records.id'), nullable=True, index=True
    )
    source_run_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('source_runs.id'), nullable=True, index=True
    )
    registration_no: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    reason_code: Mapped[str] = mapped_column(Text, nullable=False, default='UNKNOWN', index=True)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class MethodologyNode(Base):
    __tablename__ = 'methodology_nodes'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('methodology_nodes.id'), nullable=True, index=True
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)
    synonyms: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RegistrationMethodology(Base):
    __tablename__ = 'registration_methodologies'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('registrations.id'), nullable=False, index=True
    )
    methodology_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('methodology_nodes.id'), nullable=False, index=True
    )
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.80)
    source: Mapped[str] = mapped_column(Text, nullable=False, default='rule')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RegistrationEvent(Base):
    __tablename__ = 'registration_events'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('registrations.id'), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_seq: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=False)
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey('source_runs.id'), nullable=True, index=True)
    raw_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('raw_documents.id'), nullable=True, index=False
    )
    diff_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snapshot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('nmpa_snapshots.id'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cleanup_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    archive_batch_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    archive_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class RegistrationConflictAudit(Base):
    __tablename__ = 'registration_conflict_audit'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('registrations.id'), nullable=False, index=True
    )
    registration_no: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    incoming_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    final_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    existing_meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    incoming_meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    source_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey('source_runs.id'), nullable=True, index=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConflictQueue(Base):
    __tablename__ = 'conflicts_queue'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_no: Mapped[str] = mapped_column(
        String(120), ForeignKey('registrations.registration_no'), nullable=False, index=True
    )
    registration_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('registrations.id'), nullable=True, index=False
    )
    field_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='open', index=True)
    winner_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    winner_source_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    source_run_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey('source_runs.id'), nullable=True, index=True
    )
    resolved_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProcurementProject(Base):
    __tablename__ = 'procurement_projects'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    province: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    publish_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('raw_documents.id'), nullable=False, index=True
    )
    source_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('source_runs.id'), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcurementLot(Base):
    __tablename__ = 'procurement_lots'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('procurement_projects.id'), nullable=False, index=True
    )
    lot_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    catalog_item_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    catalog_item_std: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcurementResult(Base):
    __tablename__ = 'procurement_results'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('procurement_lots.id'), nullable=False, index=True
    )
    win_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('companies.id'), nullable=True, index=True
    )
    win_company_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bid_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    publish_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    raw_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('raw_documents.id'), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcurementRegistrationMap(Base):
    __tablename__ = 'procurement_registration_map'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('procurement_lots.id'), nullable=False, index=True
    )
    registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('registrations.id'), nullable=False, index=True
    )
    match_type: Mapped[str] = mapped_column(Text, nullable=False, default='rule')
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.80)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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


class ParamDictionaryCandidate(Base):
    __tablename__ = 'param_dictionary_candidates'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    xml_tag: Mapped[str] = mapped_column(Text, nullable=False)
    count_total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    count_non_empty: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    empty_rate: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    sample_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    sample_meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    source_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey('source_runs.id'), nullable=True, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UdiJobCheckpoint(Base):
    __tablename__ = 'udi_jobs_checkpoint'

    job_name: Mapped[str] = mapped_column(String(120), primary_key=True)
    cursor: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UdiOutlier(Base):
    __tablename__ = 'udi_outliers'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    reg_no: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    di_count: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    status: Mapped[str] = mapped_column(Text, nullable=False, default='open', index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class UdiQuarantineEvent(Base):
    __tablename__ = 'udi_quarantine_events'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    reg_no: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    di: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class DataSource(Base):
    __tablename__ = 'data_sources'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(20), index=True)
    config_encrypted: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SourceDefinition(Base):
    __tablename__ = 'source_definitions'

    source_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    entity_scope: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    default_evidence_grade: Mapped[str] = mapped_column(String(1), nullable=False, default='C')
    parser_key: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled_by_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SourceConfig(Base):
    __tablename__ = 'source_configs'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_key: Mapped[str] = mapped_column(String(80), ForeignKey('source_definitions.source_key'), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    schedule_cron: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fetch_params: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    parse_params: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    upsert_policy: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    pending_count: Mapped[int] = mapped_column(Integer, default=0)
    lri_computed_count: Mapped[int] = mapped_column(Integer, default=0)
    lri_missing_methodology_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_level_distribution: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    # UDI operational + enrichment value-add metrics (stored as JSON to avoid schema churn).
    # Keys are defined in app.services.metrics._compute_udi_value_add_metrics().
    udi_metrics: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    source_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey('source_runs.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DailyUdiMetric(Base):
    __tablename__ = 'daily_udi_metrics'

    metric_date: Mapped[date] = mapped_column(Date, primary_key=True)
    total_di_count: Mapped[int] = mapped_column(Integer, default=0)
    mapped_di_count: Mapped[int] = mapped_column(Integer, default=0)
    unmapped_di_count: Mapped[int] = mapped_column(Integer, default=0)
    coverage_ratio: Mapped[float] = mapped_column(Numeric(8, 6), default=0)
    source_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey('source_runs.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DailyQualityMetric(Base):
    __tablename__ = 'daily_quality_metrics'

    metric_date: Mapped[date] = mapped_column('date', Date, primary_key=True)
    metric_key: Mapped[str] = mapped_column('key', Text, primary_key=True)
    value: Mapped[float] = mapped_column(Numeric(14, 6), nullable=False, default=0)
    meta: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
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
