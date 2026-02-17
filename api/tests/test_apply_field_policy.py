from __future__ import annotations

from datetime import datetime, timezone

from app.services.source_contract import apply_field_policy


def test_apply_field_policy_prefers_higher_evidence_grade() -> None:
    observed = datetime(2026, 2, 17, 1, 0, 0, tzinfo=timezone.utc)
    decision = apply_field_policy(
        None,  # type: ignore[arg-type]
        field_name="status",
        old_value="ACTIVE",
        new_value="CANCELLED",
        source_key="NMPA_REG",
        observed_at=observed,
        existing_meta={
            "source_key": "LEGACY",
            "evidence_grade": "C",
            "source_priority": 100,
            "observed_at": "2026-02-16T00:00:00+00:00",
        },
        policy_evidence_grade="A",
        policy_source_priority=10,
    )
    assert decision.action == "apply"
    assert decision.value_to_store == "CANCELLED"


def test_apply_field_policy_marks_unresolved_tie_as_conflict() -> None:
    observed = datetime(2026, 2, 17, 1, 0, 0, tzinfo=timezone.utc)
    decision = apply_field_policy(
        None,  # type: ignore[arg-type]
        field_name="status",
        old_value="ACTIVE",
        new_value="CANCELLED",
        source_key="NMPA_REG",
        observed_at=observed,
        existing_meta={
            "source_key": "NMPA_REG",
            "evidence_grade": "A",
            "source_priority": 10,
            "observed_at": observed.isoformat(),
        },
        policy_evidence_grade="A",
        policy_source_priority=10,
    )
    assert decision.action == "conflict"
    assert decision.value_to_store == "ACTIVE"

