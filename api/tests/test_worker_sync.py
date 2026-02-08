from __future__ import annotations

import zipfile
from pathlib import Path
from types import SimpleNamespace

from app.workers import sync


class FakeDB:
    def add(self, _obj) -> None:
        return None

    def commit(self) -> None:
        return None

    def close(self) -> None:
        return None


def _make_zip(path: Path) -> None:
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('mock.txt', 'ok')


def test_sync_nmpa_ivd_success_with_mock(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sync, 'get_settings', lambda: SimpleNamespace(staging_dir=str(tmp_path / 'staging')))
    monkeypatch.setattr(sync, 'SessionLocal', lambda: FakeDB())

    started = []
    finished = []

    def _start(db, source, package_name, package_md5, download_url):
        run = SimpleNamespace(id=1, package_name=package_name, package_md5=package_md5, download_url=download_url)
        started.append(run)
        return run

    def _finish(
        db, run, status, message, records_total, records_success, records_failed, added_count=0, updated_count=0, removed_count=0
    ):
        finished.append((run.id, status, message, records_total, records_success, records_failed, added_count, updated_count, removed_count))
        return run

    monkeypatch.setattr(sync, 'start_source_run', _start)
    monkeypatch.setattr(sync, 'finish_source_run', _finish)

    archive = tmp_path / 'mock.zip'
    _make_zip(archive)

    def _download(_url, destination: Path):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(archive.read_bytes())
        return destination

    monkeypatch.setattr(sync, 'download_file', _download)
    monkeypatch.setattr(sync, 'load_staging_records', lambda _p: [{'name': 'A', 'udi_di': 'U1'}])
    monkeypatch.setattr(
        sync,
        'ingest_staging_records',
        lambda _db, _records, _run_id: {'total': 1, 'success': 1, 'failed': 0, 'added': 1, 'updated': 0, 'removed': 0},
    )
    monkeypatch.setattr(sync, 'generate_daily_metrics', lambda _db: None)
    monkeypatch.setattr(sync, 'dispatch_daily_subscription_digest', lambda _db: {'sent': 0, 'failed': 0, 'skipped': 0})

    result = sync.sync_nmpa_ivd(package_url='https://example.com/mock.zip', clean_staging=True)

    assert result.status == 'success'
    assert started
    assert finished[0][1] == 'success'
    assert (tmp_path / 'staging' / 'extracted' / 'mock.txt').exists()


def test_sync_nmpa_ivd_failed_records_source_run(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sync, 'get_settings', lambda: SimpleNamespace(staging_dir=str(tmp_path / 'staging')))
    monkeypatch.setattr(sync, 'SessionLocal', lambda: FakeDB())

    finished = []

    monkeypatch.setattr(
        sync,
        'start_source_run',
        lambda db, source, package_name, package_md5, download_url: SimpleNamespace(
            id=2, package_name=package_name, package_md5=package_md5, download_url=download_url
        ),
    )

    def _finish(
        db, run, status, message, records_total, records_success, records_failed, added_count=0, updated_count=0, removed_count=0
    ):
        finished.append(status)
        return run

    monkeypatch.setattr(sync, 'finish_source_run', _finish)

    def _download(_url, _destination):
        raise RuntimeError('download error')

    monkeypatch.setattr(sync, 'download_file', _download)

    result = sync.sync_nmpa_ivd(package_url='https://example.com/mock.zip')

    assert result.status == 'failed'
    assert finished == ['failed']


def test_prepare_staging_dirs_cleanup_and_reuse(tmp_path: Path) -> None:
    staging_root = tmp_path / 'staging'
    stale_file = staging_root / 'extracted' / 'old.txt'
    stale_file.parent.mkdir(parents=True, exist_ok=True)
    stale_file.write_text('old', encoding='utf-8')

    sync.prepare_staging_dirs(staging_root, clean=True)
    assert not stale_file.exists()

    download_dir, extract_dir = sync.prepare_staging_dirs(staging_root, clean=False)
    assert download_dir.exists()
    assert extract_dir.exists()
