#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

SOURCE_RUN_ID = 41
THRESHOLD = 100
SAMPLE_PER_REGNO = 10

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"
CSV_PATH = REPORTS_DIR / "outlier_triage_run41.csv"
MD_PATH = REPORTS_DIR / "outlier_triage_run41.md"


@dataclass
class OutlierRow:
    reg_no: str
    di_count: int


@dataclass
class TriageRow:
    reg_no: str
    di_count: int
    triage_type: str
    evidence_notes: str
    sample_dis: str
    sample_count: int
    sample_source: str


def _run_psql_csv(sql: str) -> list[dict[str, str]]:
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "db",
        "psql",
        "-U",
        "nmpa",
        "-d",
        "nmpa",
        "-A",
        "-F",
        ",",
        "--csv",
        "-c",
        sql,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    text = res.stdout.strip()
    if not text:
        return []
    rows: list[dict[str, str]] = []
    reader = csv.DictReader(text.splitlines())
    for row in reader:
        rows.append({k: (v or "") for k, v in row.items()})
    return rows


def _sql_str(v: str) -> str:
    return "'" + v.replace("'", "''") + "'"


def _table_has_columns(table: str, cols: list[str]) -> bool:
    col_list = ", ".join(_sql_str(c) for c in cols)
    sql = f"""
    SELECT COUNT(*)::int AS cnt
    FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name={_sql_str(table)}
      AND column_name IN ({col_list})
    """
    rows = _run_psql_csv(sql)
    if not rows:
        return False
    return int(rows[0].get("cnt") or 0) == len(cols)


def load_outliers() -> list[OutlierRow]:
    sql = f"""
    SELECT reg_no, di_count
    FROM udi_outliers
    WHERE source_run_id={SOURCE_RUN_ID}
      AND status='open'
    ORDER BY di_count DESC, reg_no ASC
    """
    rows = _run_psql_csv(sql)
    return [OutlierRow(reg_no=r["reg_no"], di_count=int(r["di_count"])) for r in rows]


def sample_from_product_variants(reg_no: str) -> list[str]:
    sql = f"""
    SELECT di
    FROM product_variants
    WHERE registry_no={_sql_str(reg_no)}
      AND di IS NOT NULL
      AND btrim(di) <> ''
    ORDER BY di ASC
    LIMIT {SAMPLE_PER_REGNO}
    """
    return [r["di"] for r in _run_psql_csv(sql) if r.get("di")]


def sample_from_udi_device_index(reg_no: str) -> list[str]:
    sql = f"""
    SELECT di_norm AS di
    FROM udi_device_index
    WHERE source_run_id={SOURCE_RUN_ID}
      AND registration_no_norm={_sql_str(reg_no)}
      AND di_norm IS NOT NULL
      AND btrim(di_norm) <> ''
    ORDER BY di_norm ASC
    LIMIT {SAMPLE_PER_REGNO}
    """
    return [r["di"] for r in _run_psql_csv(sql) if r.get("di")]


def sample_from_udi_registration_index(reg_no: str) -> list[str]:
    sql = f"""
    SELECT di_norm AS di
    FROM udi_registration_index
    WHERE source_run_id={SOURCE_RUN_ID}
      AND registration_no_norm={_sql_str(reg_no)}
      AND di_norm IS NOT NULL
      AND btrim(di_norm) <> ''
    ORDER BY di_norm ASC
    LIMIT {SAMPLE_PER_REGNO}
    """
    return [r["di"] for r in _run_psql_csv(sql) if r.get("di")]


def classify(reg_no: str, di_count: int, samples: list[str]) -> tuple[str, str]:
    placeholder_reg = reg_no.strip().upper() in {"", "-", "UNKNOWN", "N/A", "NULL"}
    if placeholder_reg:
        return "B", "reg_no looks placeholder/missing; fallback anomaly evidence"

    if di_count >= 1000:
        return "A", "extreme di_count>=1000; high risk of canonical aggregation issue"

    if samples:
        prefixes = {s[:6] for s in samples if s}
        prefix_ratio = len(prefixes) / max(len(samples), 1)
        if di_count >= 300 and prefix_ratio > 0.8:
            return "A", f"high di_count with diverse DI prefixes (ratio={prefix_ratio:.2f})"

    return "C", "limited evidence; treated as long-tail and keep quarantine"


def suggest_action(t: str) -> str:
    if t == "A":
        return "修 canonical / 多证号映射，再解除隔离"
    if t == "B":
        return "人工核验原始证号字段，修复 fallback 后再放开"
    return "继续隔离并抽检，确认后标记 ignored/resolved"


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    has_pv = _table_has_columns("product_variants", ["registry_no", "di"])
    has_udi_idx = _table_has_columns("udi_device_index", ["registration_no_norm", "di_norm", "source_run_id"])
    has_udi_reg_idx = _table_has_columns("udi_registration_index", ["registration_no_norm", "di_norm", "source_run_id"])

    outliers = load_outliers()
    triaged: list[TriageRow] = []

    for row in outliers:
        samples: list[str] = []
        sample_source = "none"

        if has_pv:
            samples = sample_from_product_variants(row.reg_no)
            if samples:
                sample_source = "product_variants"

        if not samples and has_udi_idx:
            samples = sample_from_udi_device_index(row.reg_no)
            if samples:
                sample_source = "udi_device_index"

        if not samples and has_udi_reg_idx:
            samples = sample_from_udi_registration_index(row.reg_no)
            if samples:
                sample_source = "udi_registration_index"

        triage_type, notes = classify(row.reg_no, row.di_count, samples)
        if len(samples) < SAMPLE_PER_REGNO:
            suffix = f"insufficient samples ({len(samples)}/{SAMPLE_PER_REGNO})"
            notes = f"{notes}; {suffix}" if notes else suffix

        triaged.append(
            TriageRow(
                reg_no=row.reg_no,
                di_count=row.di_count,
                triage_type=triage_type,
                evidence_notes=f"{notes}; source={sample_source}",
                sample_dis="|".join(samples),
                sample_count=len(samples),
                sample_source=sample_source,
            )
        )

    # CSV
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["reg_no", "di_count", "type", "evidence_notes", "sample_dis"])
        for r in triaged:
            w.writerow([r.reg_no, r.di_count, r.triage_type, r.evidence_notes, r.sample_dis])

    # Markdown
    counts = {"A": 0, "B": 0, "C": 0}
    for r in triaged:
        counts[r.triage_type] = counts.get(r.triage_type, 0) + 1

    top5 = sorted(triaged, key=lambda x: (-x.di_count, x.reg_no))[:5]

    lines: list[str] = []
    lines.append("# Outlier Triage Report (run=41)")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- source_run_id: `{SOURCE_RUN_ID}`")
    lines.append(f"- threshold: `{THRESHOLD}`")
    lines.append(f"- total_outliers: `{len(triaged)}`")
    lines.append(f"- Type A: `{counts.get('A', 0)}`")
    lines.append(f"- Type B: `{counts.get('B', 0)}`")
    lines.append(f"- Type C: `{counts.get('C', 0)}`")
    lines.append("")
    lines.append("## Top5 (by di_count)")
    lines.append("| reg_no | di_count | type |")
    lines.append("|---|---:|---|")
    for r in top5:
        lines.append(f"| {r.reg_no} | {r.di_count} | {r.triage_type} |")

    lines.append("")
    lines.append("## Per Regno Detail")
    for r in sorted(triaged, key=lambda x: (-x.di_count, x.reg_no)):
        lines.append("")
        lines.append(f"### {r.reg_no}")
        lines.append(f"- di_count: `{r.di_count}`")
        lines.append(f"- sample_source: `{r.sample_source}`")
        lines.append(f"- sample_count: `{r.sample_count}`")
        lines.append(f"- sample_di: `{r.sample_dis if r.sample_dis else '-'}`")
        lines.append(f"- type: `{r.triage_type}`")
        lines.append(f"- evidence_notes: {r.evidence_notes}")
        lines.append(f"- suggested_action: {suggest_action(r.triage_type)}")

    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "source_run_id": SOURCE_RUN_ID,
                "threshold": THRESHOLD,
                "total_outliers": len(triaged),
                "type_counts": counts,
                "top5": [
                    {"reg_no": x.reg_no, "di_count": x.di_count, "type": x.triage_type}
                    for x in top5
                ],
                "csv": str(CSV_PATH),
                "md": str(MD_PATH),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
