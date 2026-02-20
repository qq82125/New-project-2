# Data Retention Policy

## Scope
This policy covers raw ingestion artifacts:
- `raw_documents`
- `raw_source_records`

The goal is to reduce storage pressure while preserving audit traceability for ingest and source-contract decisions.

## Retention Rules

### Hot Window
- Keep full raw payload fields in primary tables for recent records.
- Default hot window: **180 days**.

### Cold Archive (>=180d)
Records older than the retention threshold are archived by `ops:archive-raw`:
- `raw_documents`
  - keep traceability fields (`id`, `source`, `source_url`, `storage_uri`, `sha256`, `run_id`, `parse_status`, timestamps)
  - set `archive_status='archived'`, `archived_at`, `archive_note`
  - compact inline large fields: replace `parse_log` with archive marker metadata, clear `error`
- `raw_source_records`
  - keep traceability fields (`id`, `source`, `source_run_id`, `source_url`, `payload_hash`, `parse_status`, timestamps)
  - set `archive_status='archived'`, `archived_at`, `archive_note`
  - clear large inline fields (`payload`, `parse_error`)

## Compliance and Auditability
- Archive is **non-destructive for identity/lineage**: row IDs and hashes remain.
- Source-run linking stays intact (`source_run_id`, `run_id`, `payload_hash`, `sha256`).
- Archive actions are idempotent: already archived rows are skipped.

## Operational Command

```bash
python -m app.workers.cli ops:archive-raw --older-than 180d --dry-run
python -m app.workers.cli ops:archive-raw --older-than 180d --execute
```

### Dry-run Output
- estimated row count to archive (`raw_documents`, `raw_source_records`)
- estimated inline bytes to compact (for targeted fields)

### Execute Output
- estimated counts/bytes (same as dry-run snapshot)
- actual updated row counts per table

## Notes
- Run during low-traffic windows.
- Start with dry-run, then execute with same threshold.
- Recommended cadence: daily or weekly.
