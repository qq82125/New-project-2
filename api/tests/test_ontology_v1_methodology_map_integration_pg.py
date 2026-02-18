from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import MethodologyMaster, Product, ProductMethodologyMap
from app.services.ontology_v1_methodology import map_products_methodologies_v1
from it_pg_utils import apply_sql_migrations, require_it_db_url


@pytest.mark.integration
def test_ontology_v1_maps_product_ivd_subtypes_to_methodology(monkeypatch) -> None:
    url = require_it_db_url()
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        apply_sql_migrations(conn)

    tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    di = f"DI-ONTO-{uuid.uuid4().hex[:8]}".upper()

    with Session(engine) as db:
        # Ensure seed exists (migration inserts TOP20).
        pcr = db.scalar(select(MethodologyMaster).where(MethodologyMaster.code == "PCR"))
        assert pcr is not None

        prod = Product(
            udi_di=di,
            reg_no=None,
            name=f"测试 PCR 产品 {tag}",
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
            registration_id=None,
            raw_json={},
            raw={},
        )
        db.add(prod)
        db.commit()

        res = map_products_methodologies_v1(db, dry_run=False, limit=None)
        assert res.ok
        assert res.matched_products >= 1
        assert int(res.total_ivd_products) >= 1
        assert float(res.coverage_ratio) > 0.0

        row = db.scalar(select(ProductMethodologyMap).where(ProductMethodologyMap.product_id == prod.id))
        assert row is not None
        assert row.methodology_id == pcr.id
        assert float(row.confidence) >= 0.6
