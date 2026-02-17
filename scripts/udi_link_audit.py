#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text


REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.db.session import SessionLocal  # noqa: E402


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _percentile(sorted_values: list[int], p: float) -> int:
    if not sorted_values:
        return 0
    idx = int(math.ceil((p / 100.0) * len(sorted_values))) - 1
    idx = max(0, min(idx, len(sorted_values) - 1))
    return int(sorted_values[idx])


def run_audit(*, threshold: int, anomaly_limit: int) -> dict[str, Any]:
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT registration_no, COUNT(*)::int AS di_count
                FROM product_udi_map
                GROUP BY registration_no
                ORDER BY di_count DESC
                """
            )
        ).mappings().all()

        counts = sorted([int(r["di_count"]) for r in rows])
        p50 = _percentile(counts, 50)
        p90 = _percentile(counts, 90)
        p99 = _percentile(counts, 99)

        anomalies = [
            {
                "registration_no": str(r["registration_no"]),
                "di_count": int(r["di_count"]),
            }
            for r in rows
            if int(r["di_count"]) > int(threshold)
        ][: max(1, int(anomaly_limit))]

        di_conflicts = db.execute(
            text(
                """
                SELECT di, COUNT(DISTINCT registration_no)::int AS registration_count
                FROM product_udi_map
                GROUP BY di
                HAVING COUNT(DISTINCT registration_no) > 1
                ORDER BY registration_count DESC, di ASC
                LIMIT :lim
                """
            ),
            {"lim": max(1, int(anomaly_limit))},
        ).mappings().all()

        return {
            "generated_at": _utc_now_iso(),
            "threshold": int(threshold),
            "registration_count": len(rows),
            "di_map_count": int(sum(int(r["di_count"]) for r in rows)),
            "distribution": {
                "p50": p50,
                "p90": p90,
                "p99": p99,
                "max": (max(counts) if counts else 0),
            },
            "anomalies_over_threshold": anomalies,
            "di_multi_registration_conflicts": [
                {"di": str(r["di"]), "registration_count": int(r["registration_count"])}
                for r in di_conflicts
            ],
        }
    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="UDI link audit (registration_no -> DI distribution).")
    p.add_argument("--dry-run", action="store_true", help="No writes, print audit result (default behavior).")
    p.add_argument("--threshold", type=int, default=20, help="DI count threshold for anomalies.")
    p.add_argument("--anomaly-limit", type=int, default=200, help="Max anomaly rows to output.")
    return p


def main() -> None:
    args = build_parser().parse_args()
    report = run_audit(threshold=int(args.threshold), anomaly_limit=int(args.anomaly_limit))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

