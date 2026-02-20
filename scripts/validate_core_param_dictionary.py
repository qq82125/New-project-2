#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


KEY_PATTERN = re.compile(r"^[a-z0-9_:\.\- ]+$")
REQUIRED_TOP_FIELDS = {"version", "updated_at", "owner", "keys"}
REQUIRED_KEY_FIELDS = {
    "key",
    "display_name",
    "description",
    "unit",
    "source_scopes",
    "stability",
    "deprecated",
    "replaced_by",
    "created_in_version",
}


def _fail(message: str) -> None:
    raise ValueError(message)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        _fail(f"dictionary not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _fail(f"failed to parse yaml: {exc}")
    if not isinstance(data, dict):
        _fail("yaml root must be a mapping")
    return data


def _validate_structure(data: dict[str, Any]) -> list[dict[str, Any]]:
    missing = sorted(REQUIRED_TOP_FIELDS - set(data.keys()))
    if missing:
        _fail(f"missing top-level fields: {missing}")
    if not isinstance(data.get("version"), int):
        _fail("version must be integer")
    if not isinstance(data.get("updated_at"), str) or not str(data.get("updated_at")).strip():
        _fail("updated_at must be non-empty string")
    if not isinstance(data.get("owner"), str) or not str(data.get("owner")).strip():
        _fail("owner must be non-empty string")
    keys = data.get("keys")
    if not isinstance(keys, list) or not keys:
        _fail("keys must be a non-empty list")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, item in enumerate(keys):
        where = f"keys[{idx}]"
        if not isinstance(item, dict):
            _fail(f"{where} must be mapping")
        miss = sorted(REQUIRED_KEY_FIELDS - set(item.keys()))
        if miss:
            _fail(f"{where} missing fields: {miss}")
        key = str(item.get("key") or "").strip()
        if not key:
            _fail(f"{where}.key is empty")
        if not KEY_PATTERN.match(key):
            _fail(f"{where}.key invalid format: {key!r} (must match {KEY_PATTERN.pattern})")
        if key in seen:
            _fail(f"duplicate key found: {key}")
        seen.add(key)
        if str(item.get("stability") or "").strip() != "core":
            _fail(f"{where}.stability must be 'core'")
        deprecated = item.get("deprecated")
        if not isinstance(deprecated, bool):
            _fail(f"{where}.deprecated must be boolean")
        replaced_by = str(item.get("replaced_by") or "").strip()
        if deprecated and replaced_by and replaced_by == key:
            _fail(f"{where}.replaced_by cannot point to itself")
        source_scopes = item.get("source_scopes")
        if not isinstance(source_scopes, list):
            _fail(f"{where}.source_scopes must be list")
        normalized.append({"key": key, "deprecated": deprecated, "replaced_by": replaced_by})
    key_set = {x["key"] for x in normalized}
    for item in normalized:
        if item["deprecated"] and item["replaced_by"] and item["replaced_by"] not in key_set:
            _fail(f"deprecated key {item['key']} has replaced_by={item['replaced_by']} not found in keys")
    return normalized


def _load_baseline(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _fail(f"failed to parse baseline json: {exc}")
    if not isinstance(data, dict):
        _fail("baseline json must be object")
    return data


def _baseline_key_map(data: dict[str, Any]) -> dict[str, bool]:
    rows = data.get("keys")
    if not isinstance(rows, list):
        _fail("baseline keys must be list")
    out: dict[str, bool] = {}
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail(f"baseline keys[{idx}] must be object")
        key = str(row.get("key") or "").strip()
        if not key:
            _fail(f"baseline keys[{idx}].key is empty")
        deprecated = row.get("deprecated")
        if not isinstance(deprecated, bool):
            _fail(f"baseline keys[{idx}].deprecated must be boolean")
        out[key] = deprecated
    return out


def _validate_against_baseline(current: list[dict[str, Any]], baseline: dict[str, Any]) -> None:
    current_map = {row["key"]: bool(row["deprecated"]) for row in current}
    baseline_map = _baseline_key_map(baseline)
    missing = sorted(set(baseline_map.keys()) - set(current_map.keys()))
    if missing:
        _fail(
            "breaking change: deleting/renaming core keys is forbidden. "
            f"missing historical keys: {missing}"
        )
    flipped_back = sorted([k for k, was_dep in baseline_map.items() if was_dep and not current_map.get(k, False)])
    if flipped_back:
        _fail(
            "breaking change: deprecated key cannot be re-activated (true -> false). "
            f"violations: {flipped_back}"
        )


def _build_baseline_payload(yaml_data: dict[str, Any], current: list[dict[str, Any]]) -> dict[str, Any]:
    rows = sorted([{"key": row["key"], "deprecated": bool(row["deprecated"])} for row in current], key=lambda x: x["key"])
    return {
        "version": 1,
        "dictionary_version": int(yaml_data["version"]),
        "updated_at": str(yaml_data["updated_at"]),
        "owner": str(yaml_data["owner"]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "keys": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate core parameter dictionary governance rules")
    parser.add_argument(
        "--dictionary",
        default="docs/PARAMETER_DICTIONARY_CORE_V1.yaml",
        help="Path to core dictionary yaml",
    )
    parser.add_argument(
        "--baseline",
        default="docs/PARAMETER_DICTIONARY_CORE_BASELINE.json",
        help="Path to baseline json",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Update baseline file after successful validation (release operation only)",
    )
    args = parser.parse_args()

    dictionary_path = Path(args.dictionary)
    baseline_path = Path(args.baseline)

    data = _load_yaml(dictionary_path)
    current = _validate_structure(data)
    baseline = _load_baseline(baseline_path)

    if baseline is None and not args.update_baseline:
        _fail(
            f"baseline file not found: {baseline_path}. "
            "Create baseline via --update-baseline first."
        )

    if baseline is not None:
        _validate_against_baseline(current, baseline)

    if args.update_baseline:
        payload = _build_baseline_payload(data, current)
        baseline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[OK] baseline updated: {baseline_path}")
    else:
        print(
            "[OK] core parameter dictionary validation passed. "
            f"keys={len(current)} file={dictionary_path}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1)
