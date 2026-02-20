from __future__ import annotations

import pytest

from app.services import udi_params


class _DummyDb:
    class _EmptyResult:
        def mappings(self):
            return self

        def all(self):
            return []

    def get(self, *_args, **_kwargs):
        return None

    def scalar(self, _stmt):  # pragma: no cover - should not be called when monkeypatched
        return None

    def execute(self, *_args, **_kwargs):
        return self._EmptyResult()


def test_validate_allowlist_keys_case_insensitive() -> None:
    valid, invalid, core_count, approved_count = udi_params._validate_allowlist_keys(
        ["STORAGE", "LABEL_LOT", "NOT_IN_CORE"],
        {"storage": "core", "label_lot": "approved"},
    )
    assert valid == ["STORAGE", "LABEL_LOT"]
    assert invalid == ["NOT_IN_CORE"]
    assert core_count == 1
    assert approved_count == 1


def test_execute_accepts_approved_allowlist_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        udi_params,
        "_get_allowlist_config",
        lambda _db: udi_params.UdiAllowlistConfig(
            allowlist=["STORAGE", "LABEL_LOT"],
            allowlist_version=2,
            changed_by="admin",
            changed_at=None,
            change_reason="test",
        ),
    )
    monkeypatch.setattr(
        udi_params,
        "_load_allowlist_key_registry",
        lambda: {"storage": "core", "label_lot": "approved"},
    )

    out = udi_params.write_allowlisted_params(
        _DummyDb(),
        source_run_id=None,
        limit=1,
        only_allowlisted=True,
        dry_run=False,
    )
    assert out.invalid_key_count == 0
    assert out.allowlist_valid_core_count == 1
    assert out.allowlist_valid_approved_count == 1


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
    monkeypatch.setattr(udi_params, "_load_allowlist_key_registry", lambda: {"storage": "core"})

    with pytest.raises(ValueError) as exc:
        udi_params.write_allowlisted_params(
            _DummyDb(),
            source_run_id=None,
            limit=1,
            only_allowlisted=True,
            dry_run=False,
        )
    assert "invalid allowlist keys" in str(exc.value)
