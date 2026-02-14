from __future__ import annotations

from app.workers import cli


def test_cleanup_cli_passes_archive_batch_id(monkeypatch) -> None:
    captured = {}

    class FakeDB:
        def close(self) -> None:
            return None

    monkeypatch.setattr(cli, 'SessionLocal', lambda: FakeDB())

    def _cleanup(db, *, dry_run: bool, recompute_days: int, notes: str | None, archive_batch_id: str | None):
        captured['dry_run'] = dry_run
        captured['recompute_days'] = recompute_days
        captured['notes'] = notes
        captured['archive_batch_id'] = archive_batch_id

        return type(
            'Res',
            (),
            {
                'run_id': 1,
                'dry_run': bool(dry_run),
                'target_count': 0,
                'archived_count': 0,
                'deleted_count': 0,
                'recomputed_days': 0,
                'notes': {},
            },
        )()

    monkeypatch.setattr(cli, 'run_non_ivd_cleanup', _cleanup)

    rc = cli._run_cleanup_non_ivd_v2(  # type: ignore[attr-defined]
        dry_run=True,
        recompute_days=7,
        notes='n',
        archive_batch_id='bid1',
    )
    assert rc == 0
    assert captured['archive_batch_id'] == 'bid1'


def test_rollback_cli_passes_recompute_days(monkeypatch) -> None:
    captured = {}

    class FakeDB:
        def close(self) -> None:
            return None

    monkeypatch.setattr(cli, 'SessionLocal', lambda: FakeDB())

    def _rb(db, *, archive_batch_id: str, dry_run: bool, recompute_days: int):
        captured['archive_batch_id'] = archive_batch_id
        captured['dry_run'] = dry_run
        captured['recompute_days'] = recompute_days

        return type(
            'Res',
            (),
            {
                'archive_batch_id': str(archive_batch_id),
                'dry_run': bool(dry_run),
                'target_count': 0,
                'restored_count': 0,
                'skipped_existing': 0,
            },
        )()

    monkeypatch.setattr(cli, 'rollback_non_ivd_cleanup', _rb)

    rc = cli._run_ivd_rollback(archive_batch_id='bid2', dry_run=False, recompute_days=123)  # type: ignore[attr-defined]
    assert rc == 0
    assert captured['archive_batch_id'] == 'bid2'
    assert captured['recompute_days'] == 123
