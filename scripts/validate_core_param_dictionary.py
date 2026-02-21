#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
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


@dataclass(frozen=True)
class DictionarySpec:
    name: str
    stability: str
    dictionary_path: Path
    baseline_path: Path


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


def _validate_structure(data: dict[str, Any], *, spec: DictionarySpec) -> list[dict[str, Any]]:
    missing = sorted(REQUIRED_TOP_FIELDS - set(data.keys()))
    if missing:
        _fail(f"{spec.name}: missing top-level fields: {missing}")
    if not isinstance(data.get("version"), int):
        _fail(f"{spec.name}: version must be integer")
    if not isinstance(data.get("updated_at"), str) or not str(data.get("updated_at")).strip():
        _fail(f"{spec.name}: updated_at must be non-empty string")
    if not isinstance(data.get("owner"), str) or not str(data.get("owner")).strip():
        _fail(f"{spec.name}: owner must be non-empty string")

    keys = data.get("keys")
    if not isinstance(keys, list) or not keys:
        _fail(f"{spec.name}: keys must be a non-empty list")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, item in enumerate(keys):
        where = f"{spec.name}.keys[{idx}]"
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
            _fail(f"{spec.name}: duplicate key found: {key}")
        seen.add(key)

        stability = str(item.get("stability") or "").strip()
        if stability != spec.stability:
            _fail(f"{where}.stability must be '{spec.stability}'")

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
            _fail(
                f"{spec.name}: deprecated key {item['key']} has replaced_by={item['replaced_by']} not found in keys"
            )
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


def _baseline_key_map(data: dict[str, Any], *, label: str) -> dict[str, bool]:
    rows = data.get("keys")
    if not isinstance(rows, list):
        _fail(f"{label} baseline keys must be list")
    out: dict[str, bool] = {}
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail(f"{label} baseline keys[{idx}] must be object")
        key = str(row.get("key") or "").strip()
        if not key:
            _fail(f"{label} baseline keys[{idx}].key is empty")
        deprecated = row.get("deprecated")
        if not isinstance(deprecated, bool):
            _fail(f"{label} baseline keys[{idx}].deprecated must be boolean")
        out[key] = deprecated
    return out


def _validate_against_baseline(current: list[dict[str, Any]], baseline: dict[str, Any], *, label: str) -> None:
    current_map = {row["key"]: bool(row["deprecated"]) for row in current}
    baseline_map = _baseline_key_map(baseline, label=label)

    missing = sorted(set(baseline_map.keys()) - set(current_map.keys()))
    if missing:
        _fail(
            f"breaking change in {label}: deleting/renaming historical keys is forbidden. "
            f"missing keys: {missing}"
        )

    flipped_back = sorted([k for k, was_dep in baseline_map.items() if was_dep and not current_map.get(k, False)])
    if flipped_back:
        _fail(
            f"breaking change in {label}: deprecated key cannot be re-activated (true -> false). "
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


def _validate_no_overlap(core_keys: list[dict[str, Any]], approved_keys: list[dict[str, Any]]) -> None:
    core_set = {x["key"] for x in core_keys}
    approved_set = {x["key"] for x in approved_keys}
    overlap = sorted(core_set & approved_set)
    if overlap:
        _fail(f"core and approved dictionaries overlap; keys must be unique across sets: {overlap}")


def _validate_one(
    *,
    spec: DictionarySpec,
    update_baseline: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = _load_yaml(spec.dictionary_path)
    current = _validate_structure(data, spec=spec)
    baseline = _load_baseline(spec.baseline_path)

    if baseline is None and not update_baseline:
        _fail(
            f"baseline file not found for {spec.name}: {spec.baseline_path}. "
            "Create baseline via --update-baseline all|core|approved first."
        )

    if baseline is not None:
        _validate_against_baseline(current, baseline, label=spec.name)

    if update_baseline:
        payload = _build_baseline_payload(data, current)
        spec.baseline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[OK] baseline updated ({spec.name}): {spec.baseline_path}")

    return data, current


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate core/approved parameter dictionary governance rules")
    parser.add_argument(
        "--update-baseline",
        choices=["core", "approved", "all"],
        default=None,
        help="Update baseline file(s) after successful validation",
    )
    args = parser.parse_args()

    root = Path("docs")
    core = DictionarySpec(
        name="core",
        stability="core",
        dictionary_path=root / "PARAMETER_DICTIONARY_CORE_V1.yaml",
        baseline_path=root / "PARAMETER_DICTIONARY_CORE_BASELINE.json",
    )
    approved = DictionarySpec(
        name="approved",
        stability="approved",
        dictionary_path=root / "PARAMETER_DICTIONARY_APPROVED_V1.yaml",
        baseline_path=root / "PARAMETER_DICTIONARY_APPROVED_BASELINE.json",
    )

    update_core = args.update_baseline in {"core", "all"}
    update_approved = args.update_baseline in {"approved", "all"}

    _core_data, core_keys = _validate_one(spec=core, update_baseline=update_core)
    _approved_data, approved_keys = _validate_one(spec=approved, update_baseline=update_approved)
    _validate_no_overlap(core_keys, approved_keys)

    print(
        "[OK] parameter dictionary validation passed. "
        f"core_keys={len(core_keys)} approved_keys={len(approved_keys)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1)
