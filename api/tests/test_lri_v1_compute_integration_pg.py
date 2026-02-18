from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.orm import Session

from app.models import (
    LriScore,
    MethodologyMaster,
    Product,
    ProductMethodologyMap,
    Registration,
    RegistrationEvent,
)
from app.services.lri_v1 import compute_lri_v1
from it_pg_utils import apply_sql_migrations, require_it_db_url


@pytest.mark.integration
def test_lri_v1_compute_writes_scores_and_has_risk_distribution() -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    di1 = f"DI-LRI-{uuid.uuid4().hex[:8]}".upper()
    di2 = f"DI-LRI-{uuid.uuid4().hex[:8]}".upper()
    asof = date(2026, 2, 17)

    with Session(engine) as db:
        meth = db.scalar(select(MethodologyMaster).where(MethodologyMaster.code == "PCR"))
        assert meth is not None

        r1 = Registration(
            registration_no=f"国械注准LRI{uuid.uuid4().hex[:8]}",
            approval_date=asof - timedelta(days=200),
            expiry_date=asof + timedelta(days=20),
            status="ACTIVE",
            raw_json={},
        )
        r2 = Registration(
            registration_no=f"国械注准LRI{uuid.uuid4().hex[:8]}",
            approval_date=asof - timedelta(days=100),
            expiry_date=asof + timedelta(days=400),
            status="ACTIVE",
            raw_json={},
        )
        db.add_all([r1, r2])
        db.flush()

        p1 = Product(
            udi_di=di1,
            reg_no=None,
            name=f"LRI 测试产品1 {tag}",
            class_name=None,
            approved_date=None,
            expiry_date=None,
            model=None,
            specification=None,
            category="reagent",
            status="ACTIVE",
            is_ivd=True,
            ivd_category="reagent",
            ivd_subtypes=["PCR"],
            ivd_reason=None,
            ivd_version=1,
            ivd_source="RULE",
            ivd_confidence=0.9,
            company_id=None,
            registration_id=r1.id,
            raw_json={},
            raw={},
        )
        p2 = Product(
            udi_di=di2,
            reg_no=None,
            name=f"LRI 测试产品2 {tag}",
            class_name=None,
            approved_date=None,
            expiry_date=None,
            model=None,
            specification=None,
            category="reagent",
            status="ACTIVE",
            is_ivd=True,
            ivd_category="reagent",
            ivd_subtypes=["PCR"],
            ivd_reason=None,
            ivd_version=1,
            ivd_source="RULE",
            ivd_confidence=0.9,
            company_id=None,
            registration_id=r2.id,
            raw_json={},
            raw={},
        )
        db.add_all([p1, p2])
        db.flush()

        db.add_all(
            [
                ProductMethodologyMap(product_id=p1.id, methodology_id=meth.id, confidence=0.9, evidence_text="token:pcr"),
                ProductMethodologyMap(product_id=p2.id, methodology_id=meth.id, confidence=0.9, evidence_text="token:pcr"),
            ]
        )

        # Renewal history for r1.
        db.add(
            RegistrationEvent(
                registration_id=r1.id,
                event_type="renew",
                event_date=asof - timedelta(days=10),
                summary="renew test",
                source_run_id=None,
                snapshot_id=None,
            )
        )
        db.commit()

        # dry-run should produce non-zero dist and no writes
        dr = compute_lri_v1(db, asof=asof, dry_run=True, upsert_mode=False)
        assert dr.ok
        assert dr.would_write >= 2
        assert dr.wrote == 0
        assert dr.risk_dist
        assert dr.missing_methodology_ratio == 0.0

        ex = compute_lri_v1(db, asof=asof, dry_run=False, upsert_mode=True)
        assert ex.ok
        assert ex.wrote >= 2
        assert ex.risk_dist

        rows = db.scalars(select(LriScore).where(LriScore.calculated_at.isnot(None)).limit(10)).all()
        assert any(x.registration_id == r1.id for x in rows)
        assert any(x.registration_id == r2.id for x in rows)
        assert all(str(x.risk_level or "") for x in rows if x.registration_id in {r1.id, r2.id})

        # Cleanup
        db.execute(delete(LriScore).where(LriScore.registration_id.in_([r1.id, r2.id])))
        db.execute(delete(ProductMethodologyMap).where(ProductMethodologyMap.product_id.in_([p1.id, p2.id])))
        db.execute(delete(Product).where(Product.id.in_([p1.id, p2.id])))
        db.execute(delete(RegistrationEvent).where(RegistrationEvent.registration_id == r1.id))
        db.execute(delete(Registration).where(Registration.id.in_([r1.id, r2.id])))
        db.commit()

