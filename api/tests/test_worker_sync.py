from __future__ import annotations

import zipfile
from pathlib import Path
from types import SimpleNamespace

from app.workers import sync


class FakeDB:
    class _ScalarsResult:
        def all(self):
            return []

        def first(self):
            return None

    def add(self, _obj) -> None:
        return None

    def commit(self) -> None:
        return None

    def close(self) -> None:
        return None

    def scalars(self, _stmt):
        return self._ScalarsResult()

    def scalar(self, _stmt):
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
        db,
        run,
        status,
        message,
        records_total,
        records_success,
        records_failed,
        added_count=0,
        updated_count=0,
        removed_count=0,
        ivd_kept_count=0,
        non_ivd_skipped_count=0,
        source_notes=None,
    ):
        finished.append(
            (
                run.id,
                status,
                message,
                records_total,
                records_success,
                records_failed,
                added_count,
                updated_count,
                removed_count,
                ivd_kept_count,
                non_ivd_skipped_count,
                source_notes,
            )
        )
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
        lambda _db, _records, _run_id: {
            'total': 3,
            'success': 1,
            'failed': 0,
            'filtered': 2,
            'added': 1,
            'updated': 0,
            'removed': 0,
        },
    )
    monkeypatch.setattr(sync, 'generate_daily_metrics', lambda _db: None)
    monkeypatch.setattr(sync, 'dispatch_daily_subscription_digest', lambda _db: {'sent': 0, 'failed': 0, 'skipped': 0})

    result = sync.sync_nmpa_ivd(package_url='https://example.com/mock.zip', clean_staging=True)

    assert result.status == 'success'
    assert started
    assert finished[0][1] == 'success'
    assert finished[0][9] == 1
    assert finished[0][10] == 2
    assert (tmp_path / 'staging' / 'run_1' / 'extracted' / 'mock.txt').exists()


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
        db,
        run,
        status,
        message,
        records_total,
        records_success,
        records_failed,
        added_count=0,
        updated_count=0,
        removed_count=0,
        ivd_kept_count=0,
        non_ivd_skipped_count=0,
        source_notes=None,
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
    stale_file = staging_root / 'run_9' / 'extracted' / 'old.txt'
    stale_file.parent.mkdir(parents=True, exist_ok=True)
    stale_file.write_text('old', encoding='utf-8')
    sibling_file = staging_root / 'run_10' / 'extracted' / 'keep.txt'
    sibling_file.parent.mkdir(parents=True, exist_ok=True)
    sibling_file.write_text('keep', encoding='utf-8')

    sync.prepare_staging_dirs(staging_root, run_id=9, clean=True)
    assert not stale_file.exists()
    assert sibling_file.exists()

    download_dir, extract_dir = sync.prepare_staging_dirs(staging_root, run_id=9, clean=False)
    assert download_dir.exists()
    assert extract_dir.exists()


def test_sync_prefers_primary_source_when_available(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sync, 'get_settings', lambda: SimpleNamespace(staging_dir=str(tmp_path / 'staging')))
    monkeypatch.setattr(sync, 'SessionLocal', lambda: FakeDB())
    monkeypatch.setattr(
        sync,
        '_pick_primary_source',
        lambda _db: SimpleNamespace(id=1, name='NMPA注册产品库（主数据源）', config_encrypted='enc'),
    )
    monkeypatch.setattr(
        sync,
        '_sync_from_primary_source',
        lambda _db, _run, _source: {
            'total': 100,
            'success': 30,
            'failed': 0,
            'filtered': 70,
            'added': 10,
            'updated': 20,
            'removed': 0,
        },
    )
    monkeypatch.setattr(sync, 'generate_daily_metrics', lambda _db: None)
    monkeypatch.setattr(sync, 'dispatch_daily_subscription_digest', lambda _db: {'sent': 0, 'failed': 0, 'skipped': 0})

    started = []
    finished = []

    def _start(db, source, package_name, package_md5, download_url):
        run = SimpleNamespace(id=3, package_name=package_name, package_md5=package_md5, download_url=download_url)
        started.append(source)
        return run

    def _finish(
        db,
        run,
        status,
        message,
        records_total,
        records_success,
        records_failed,
        added_count=0,
        updated_count=0,
        removed_count=0,
        ivd_kept_count=0,
        non_ivd_skipped_count=0,
        source_notes=None,
    ):
        finished.append((status, records_total, records_success, non_ivd_skipped_count, source_notes or {}))
        return run

    monkeypatch.setattr(sync, 'start_source_run', _start)
    monkeypatch.setattr(sync, 'finish_source_run', _finish)

    result = sync.sync_nmpa_ivd(clean_staging=True)
    assert result.status == 'success'
    assert started == ['nmpa_registry']
    assert finished[0][0] == 'success'
    assert finished[0][1] == 100
    assert finished[0][2] == 30
    assert finished[0][3] == 70
    assert finished[0][4].get('mode') == 'primary_source'
