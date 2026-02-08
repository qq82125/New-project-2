from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Company(Base):
    __tablename__ = 'companies'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    products: Mapped[list[Product]] = relationship('Product', back_populates='company')


class Registration(Base):
    __tablename__ = 'registrations'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_no: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    filing_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approval_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    products: Mapped[list[Product]] = relationship('Product', back_populates='registration')


class Product(Base):
    __tablename__ = 'products'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    udi_di: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(500), index=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specification: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey('companies.id'), nullable=True
    )
    registration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey('registrations.id'), nullable=True
    )
    raw_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped[Company | None] = relationship('Company', back_populates='products')
    registration: Mapped[Registration | None] = relationship('Registration', back_populates='products')


class SourceRun(Base):
    __tablename__ = 'source_runs'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(80), index=True)
    package_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    package_md5: Mapped[str | None] = mapped_column(String(64), nullable=True)
    download_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True, default='RUNNING')
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    records_total: Mapped[int] = mapped_column(Integer, default=0)
    records_success: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChangeLog(Base):
    __tablename__ = 'change_log'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(30), index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    change_type: Mapped[str] = mapped_column(String(20), index=True)
    changed_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    before_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_run_id: Mapped[int | None] = mapped_column(ForeignKey('source_runs.id'), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
