#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


MIG_RE = re.compile(r"^(\d{4})_(.+)\.sql$")


def _iter_migrations(mig_dir: Path) -> list[Path]:
    files = []
    for fp in mig_dir.glob("*.sql"):
        # macOS Finder copies; never part of canonical runner ordering.
        if " 2.sql" in fp.name or " 2." in fp.name:
            continue
        m = MIG_RE.match(fp.name)
        if not m:
            continue
        files.append(fp)
    return sorted(files, key=lambda p: p.name)


def _expected_down_name(migration_name: str) -> str | None:
    m = MIG_RE.match(migration_name)
    if not m:
        return None
    return f"{m.group(1)}_{m.group(2)}_down.sql"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Verify each migration has a matching rollback SQL under scripts/rollback/."
    )
    ap.add_argument("--repo-root", default=None, help="Repo root (defaults to this file's grandparent).")
    ap.add_argument(
        "--min",
        type=int,
        default=11,
        help="Only require rollback for migrations with number >= MIN (default: 11).",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Also fail when rollback directory contains unexpected *_down.sql files with no matching migration.",
    )
    args = ap.parse_args()

    repo_root = Path(args.repo_root) if args.repo_root else Path(__file__).resolve().parents[1]
    mig_dir = repo_root / "migrations"
    rb_dir = repo_root / "scripts" / "rollback"

    if not mig_dir.is_dir():
        print(f"ERROR: missing migrations dir: {mig_dir}", file=sys.stderr)
        return 2
    if not rb_dir.is_dir():
        print(f"ERROR: missing rollback dir: {rb_dir}", file=sys.stderr)
        return 2

    migrations = _iter_migrations(mig_dir)
    rollback_files = {p.name for p in rb_dir.glob("*.sql")}

    required: list[tuple[str, str]] = []
    for fp in migrations:
        m = MIG_RE.match(fp.name)
        if not m:
            continue
        n = int(m.group(1))
        if n < int(args.min):
            continue
        down = _expected_down_name(fp.name)
        if down:
            required.append((fp.name, down))

    missing: list[tuple[str, str]] = [(mig, down) for (mig, down) in required if down not in rollback_files]

    unexpected: list[str] = []
    if args.strict:
        expected_downs = {down for (_mig, down) in required}
        unexpected = sorted([f for f in rollback_files if f.endswith("_down.sql") and f not in expected_downs])

    if missing:
        print("FAIL: missing rollback scripts:", file=sys.stderr)
        for mig, down in missing:
            print(f"- {mig} -> {down}", file=sys.stderr)
        print(f"Hint: create files under {rb_dir} matching the pattern <migration>_down.sql.", file=sys.stderr)
        return 1

    if unexpected:
        print("FAIL: unexpected rollback scripts (no matching migration in scope):", file=sys.stderr)
        for f in unexpected:
            print(f"- {f}", file=sys.stderr)
        return 1

    print(f"OK: rollback coverage verified for {len(required)} migrations (min={args.min}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

