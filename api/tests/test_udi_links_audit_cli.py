from __future__ import annotations

from types import SimpleNamespace

from app.workers import cli


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeDB:
    def execute(self, stmt):
        sql = str(stmt)
        if "FROM product_udi_map" in sql and "match_type = 'direct'" in sql:
            return _ScalarResult(6)
        if "FROM product_udi_map" in sql and "reversible = TRUE" in sql:
            return _ScalarResult(4)
        if "FROM product_udi_map" in sql and "COUNT(1)" in sql:
            return _ScalarResult(10)
        if "FROM change_log" in sql:
            return _ScalarResult(2)
        if "FROM pending_udi_links" in sql:
            return _ScalarResult(7200.0)
        return _ScalarResult(0)

    def close(self):
        return None


def test_udi_links_audit_cli_outputs_metrics(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "SessionLocal", lambda: _FakeDB())

    rc = cli._run_udi_links_audit(SimpleNamespace())  # type: ignore[attr-defined]
    assert rc == 0

    out = capsys.readouterr().out
    assert '"auto_link_rate": 0.6' in out
    assert '"rollback_rate": 0.5' in out
    assert '"pending_age_p95": 7200' in out
