from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Index, Numeric, String, UniqueConstraint, desc, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SignalScore(Base):
    __tablename__ = 'signal_scores'
    __table_args__ = (
        UniqueConstraint('entity_type', 'entity_id', 'window', 'as_of_date', name='uq_signal_scores_entity_window_date'),
        Index('idx_signal_scores_entity_window_date_level', 'entity_type', 'window', 'as_of_date', 'level'),
        Index('idx_signal_scores_entity_window_date_score_desc', 'entity_type', 'window', 'as_of_date', desc('score')),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False, index=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False, index=False)
    window: Mapped[str] = mapped_column('window', String(20), nullable=False, default='12m', quote=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    level: Mapped[str] = mapped_column(String(30), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    factors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
