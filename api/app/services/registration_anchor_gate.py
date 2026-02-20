from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class RegistrationAnchorGateMetrics:
    total_regs: int
    unanchored_regs: int
    ratio: float


def collect_registration_anchor_metrics(db: Session) -> RegistrationAnchorGateMetrics:
    row = db.execute(
        text(
            """
            WITH stats AS (
              SELECT
                COUNT(*)::bigint AS total_regs,
                COUNT(*) FILTER (
                  WHERE NOT EXISTS (
                    SELECT 1 FROM products p WHERE p.registration_id = r.id
                  )
                )::bigint AS unanchored_regs
              FROM registrations r
            )
            SELECT total_regs, unanchored_regs FROM stats
            """
        )
    ).first()
    total = int((row[0] if row else 0) or 0)
    unanchored = int((row[1] if row else 0) or 0)
    ratio = (float(unanchored) / float(total)) if total > 0 else 0.0
    return RegistrationAnchorGateMetrics(
        total_regs=total,
        unanchored_regs=unanchored,
        ratio=ratio,
    )


def enforce_registration_anchor_gate(
    db: Session,
    *,
    enabled: bool,
    max_ratio: float,
    max_unanchored_count: int,
) -> RegistrationAnchorGateMetrics:
    metrics = collect_registration_anchor_metrics(db)
    if not enabled:
        return metrics
    ratio_failed = metrics.ratio > float(max_ratio)
    count_failed = int(max_unanchored_count) > 0 and metrics.unanchored_regs > int(max_unanchored_count)
    if ratio_failed or count_failed:
        raise RuntimeError(
            "registration_anchor_gate_failed: "
            f"total={metrics.total_regs} "
            f"unanchored={metrics.unanchored_regs} "
            f"ratio={metrics.ratio:.6f} "
            f"max_ratio={float(max_ratio):.6f} "
            f"max_unanchored_count={int(max_unanchored_count)}"
        )
    return metrics

