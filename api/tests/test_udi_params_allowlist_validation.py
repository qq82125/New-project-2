from __future__ import annotations

import pytest

from app.services import udi_params


class _DummyDb:
    def scalar(self, _stmt):  # pragma: no cover - should not be called when monkeypatched
        return None


def test_validate_allowlist_keys_case_insensitive() -> None:
    valid, invalid = udi_params._validate_allowlist_keys(
        ["STORAGE", "LABEL_LOT", "NOT_IN_CORE"],
        {"storage", "label_lot"},
    )
    assert valid == ["STORAGE", "LABEL_LOT"]
    assert invalid == ["NOT_IN_CORE"]


def test_execute_fails_on_invalid_allowlist_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        udi_params,
        "_get_allowlist_config",
        lambda _db: udi_params.UdiAllowlistConfig(
            allowlist=["STORAGE", "NOT_IN_CORE"],
            allowlist_version=2,
            changed_by="admin",
            changed_at=None,
            change_reason="test",
        ),
    )
    monkeypatch.setattr(udi_params, "_load_core_param_keys", lambda: {"storage"})

    with pytest.raises(ValueError) as exc:
        udi_params.write_allowlisted_params(
            _DummyDb(),
            source_run_id=None,
            limit=1,
            only_allowlisted=True,
            dry_run=False,
        )
    assert "invalid allowlist keys" in str(exc.value)
