#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from typing import Iterable

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


DEFAULT_DB_URL = "postgresql+psycopg://nmpa:nmpa@127.0.0.1:5432/nmpa"
EXPECTED_STATUS_VALUES = {"open", "resolved", "ignored", "pending"}


def _norm(s: str | None) -> str:
    return str(s or "").strip()


def _extract_check_literals(check_def: str) -> set[str]:
    # Example def can be:
    # CHECK (((status)::text = ANY ((ARRAY['open'::character varying, ...])::text[])))
    return {m.group(1) for m in re.finditer(r"'([^']+)'", check_def)}


def _format_lines(lines: Iterable[str]) -> str:
    return "\n".join(f"- {x}" for x in lines)


def main() -> int:
    db_url = _norm(os.getenv("DATABASE_URL")) or DEFAULT_DB_URL
    try:
        engine = create_engine(db_url, pool_pre_ping=True)
    except Exception as exc:
        print("pending_records schema guard: FAILED")
        print(_format_lines([f"invalid DATABASE_URL: {exc}"]))
        return 1
    errors: list[str] = []

    try:
        with engine.connect() as conn:
            exists = bool(
                conn.execute(
                    text("SELECT to_regclass('public.pending_records') IS NOT NULL")
                ).scalar()
            )
            if not exists:
                errors.append("table public.pending_records does not exist")
                print("pending_records schema guard: FAILED")
                print(_format_lines(errors))
                return 1

            # a) status default must be open
            col_default = conn.execute(
                text(
                    """
                    SELECT column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'pending_records'
                      AND column_name = 'status'
                    """
                )
            ).scalar()
            default_txt = _norm(col_default)
            if "open" not in default_txt:
                errors.append(
                    "pending_records.status default is not 'open' "
                    f"(actual: {default_txt or '<NULL>'})"
                )

            # b) check constraint must allow open/resolved/ignored/pending
            check_def = conn.execute(
                text(
                    """
                    SELECT pg_get_constraintdef(c.oid)
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    JOIN pg_namespace n ON n.oid = t.relnamespace
                    WHERE n.nspname = 'public'
                      AND t.relname = 'pending_records'
                      AND c.conname = 'chk_pending_records_status'
                    """
                )
            ).scalar()
            if check_def is None:
                errors.append("constraint chk_pending_records_status is missing")
            else:
                actual_values = _extract_check_literals(str(check_def))
                missing = sorted(EXPECTED_STATUS_VALUES - actual_values)
                if missing:
                    errors.append(
                        "chk_pending_records_status does not allow required statuses "
                        f"(missing: {', '.join(missing)}; def: {check_def})"
                    )

            # c) uq_pending_records_run_payload unique guard exists (constraint or unique index)
            uq_constraint = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    JOIN pg_namespace n ON n.oid = t.relnamespace
                    WHERE n.nspname = 'public'
                      AND t.relname = 'pending_records'
                      AND c.conname = 'uq_pending_records_run_payload'
                      AND c.contype = 'u'
                    LIMIT 1
                    """
                )
            ).scalar()
            uq_index = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'pending_records'
                      AND indexname = 'uq_pending_records_run_payload'
                    LIMIT 1
                    """
                )
            ).scalar()
            if not uq_constraint and not uq_index:
                errors.append(
                    "uq_pending_records_run_payload unique guard is missing "
                    "(neither unique constraint nor index found)"
                )

            # d) key indexes exist
            expected_indexes = {
                "idx_pending_records_status",
                "idx_pending_records_source_key",
            }
            rows = conn.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'pending_records'
                    """
                )
            ).fetchall()
            index_names = {str(r[0]) for r in rows}
            for idx in sorted(expected_indexes):
                if idx not in index_names:
                    errors.append(f"required index missing: {idx}")
    except SQLAlchemyError as exc:
        print("pending_records schema guard: FAILED")
        print(_format_lines([f"database connection/query error: {exc}"]))
        return 1
    finally:
        engine.dispose()

    if errors:
        print("pending_records schema guard: FAILED")
        print(_format_lines(errors))
        return 1

    print("pending_records schema guard: OK")
    print("- status default: open")
    print("- status check: open/resolved/ignored/pending")
    print("- unique guard: uq_pending_records_run_payload")
    print("- indexes: idx_pending_records_status, idx_pending_records_source_key")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
