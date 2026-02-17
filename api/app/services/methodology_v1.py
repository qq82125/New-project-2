from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import MethodologyNode, Product, ProductParam, Registration, RegistrationMethodology


def _norm_key(text: str | None) -> str | None:
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", "", s).upper()
    out = []
    for ch in s:
        o = ord(ch)
        if "0" <= ch <= "9":
            out.append(ch)
        elif "A" <= ch <= "Z":
            out.append(ch)
        elif 0x4E00 <= o <= 0x9FFF:
            out.append(ch)
        # else drop punctuation/separators
    return "".join(out) or None


@dataclass
class SeedNode:
    name: str
    synonyms: list[str]
    children: list["SeedNode"]


def _parse_seed_node(obj: dict[str, Any]) -> SeedNode:
    name = str(obj.get("name") or "").strip()
    if not name:
        raise ValueError("seed node missing name")
    syn = obj.get("synonyms")
    synonyms = [str(x).strip() for x in syn] if isinstance(syn, list) else []
    children_raw = obj.get("children")
    children = [_parse_seed_node(x) for x in children_raw] if isinstance(children_raw, list) else []
    return SeedNode(name=name, synonyms=[x for x in synonyms if x], children=children)


def load_methodology_seed(path: str | Path) -> list[SeedNode]:
    fp = Path(path)
    data = json.loads(fp.read_text(encoding="utf-8"))
    nodes = data.get("nodes") if isinstance(data, dict) else None
    if not isinstance(nodes, list):
        raise ValueError("methodology seed must contain top-level 'nodes' list")
    return [_parse_seed_node(x) for x in nodes if isinstance(x, dict)]


def _flatten_seed(nodes: list[SeedNode], parent: SeedNode | None = None, level: int = 1) -> Iterable[tuple[SeedNode, SeedNode | None, int]]:
    for n in nodes:
        yield (n, parent, level)
        if n.children:
            yield from _flatten_seed(n.children, parent=n, level=level + 1)


def seed_methodology_tree(db: Session, *, seed_path: str | Path, dry_run: bool) -> dict[str, Any]:
    roots = load_methodology_seed(seed_path)

    # Build existing index by (parent_id, name).
    existing = db.scalars(select(MethodologyNode)).all()
    by_key: dict[tuple[UUID | None, str], MethodologyNode] = {}
    for n in existing:
        by_key[(getattr(n, "parent_id", None), str(n.name))] = n

    # We need stable parent ids; insert level by level.
    created = 0
    updated = 0

    # Map from seed node identity to DB id (by traversing with parent DB id).
    def _upsert_node(seed: SeedNode, parent_id: UUID | None, level: int) -> MethodologyNode:
        nonlocal created, updated
        key = (parent_id, seed.name)
        synonyms = list(dict.fromkeys([seed.name] + (seed.synonyms or [])))
        if key in by_key:
            node = by_key[key]
            # Update basic fields if needed.
            changed = False
            if int(getattr(node, "level", 0) or 0) != int(level):
                node.level = int(level)
                changed = True
            if bool(getattr(node, "is_active", True)) is not True:
                node.is_active = True
                changed = True
            if isinstance(getattr(node, "synonyms", None), list):
                if node.synonyms != synonyms:
                    node.synonyms = synonyms
                    changed = True
            else:
                node.synonyms = synonyms
                changed = True
            if changed:
                updated += 1
                if not dry_run:
                    db.add(node)
            return node

        node = MethodologyNode(
            name=seed.name,
            parent_id=parent_id,
            level=int(level),
            synonyms=synonyms,
            is_active=True,
        )
        created += 1
        if not dry_run:
            db.add(node)
            db.flush()
            by_key[(parent_id, seed.name)] = node
        return node

    # Insert roots then children recursively, using DB parent ids.
    def _walk(seeds: list[SeedNode], parent_id: UUID | None, level: int) -> None:
        for s in seeds:
            node = _upsert_node(s, parent_id, level)
            if s.children:
                _walk(s.children, node.id if not dry_run else None, level + 1)

    _walk(roots, None, 1)
    if not dry_run:
        db.commit()
    return {"ok": True, "dry_run": bool(dry_run), "created": created, "updated": updated}


def _registration_text_blob(db: Session, reg: Registration) -> dict[str, str]:
    parts: dict[str, str] = {}
    try:
        if isinstance(getattr(reg, "raw_json", None), dict):
            parts["registration_raw_json"] = json.dumps(reg.raw_json, ensure_ascii=True, sort_keys=True, default=str)
    except Exception:
        parts["registration_raw_json"] = ""

    # Product names: from products linked by registration_id OR reg_no match.
    names: list[str] = []
    reg_no = str(getattr(reg, "registration_no", "") or "").strip()
    if reg_no:
        for p in db.scalars(
            select(Product.name).where(
                (Product.registration_id == reg.id) | (Product.reg_no == reg_no)
            )
        ).all():
            if p and str(p).strip():
                names.append(str(p).strip())
    parts["product_names"] = " ".join(names)[:20000]

    # Params: key+value text for registry_no match (best-effort).
    pv: list[str] = []
    if reg_no:
        rows = db.scalars(select(ProductParam).where(ProductParam.registry_no == reg_no).limit(500)).all()
        for r in rows:
            pv.append(str(getattr(r, "param_code", "") or ""))
            if getattr(r, "value_text", None):
                pv.append(str(r.value_text))
    parts["product_params"] = " ".join(pv)[:20000]
    return parts


def map_methodologies_v1(
    db: Session,
    *,
    registration_nos: list[str] | None,
    dry_run: bool,
    source: str = "rule",
) -> dict[str, Any]:
    nodes = db.scalars(select(MethodologyNode).where(MethodologyNode.is_active.is_(True))).all()
    if not nodes:
        return {"ok": False, "error": "methodology_nodes is empty; seed first"}

    # Build synonym keys per node.
    syn_map: list[tuple[UUID, str, list[str]]] = []
    for n in nodes:
        syns = []
        raw = getattr(n, "synonyms", None)
        if isinstance(raw, list):
            syns = [str(x).strip() for x in raw if str(x).strip()]
        if str(n.name).strip() not in syns:
            syns.insert(0, str(n.name).strip())
        keys = [k for k in (_norm_key(s) for s in syns) if k]
        if keys:
            syn_map.append((n.id, str(n.name), keys))

    # Pick registrations.
    q = select(Registration)
    if registration_nos:
        q = q.where(Registration.registration_no.in_(registration_nos))
    regs = db.scalars(q).all()

    scanned = 0
    matched_regs = 0
    written = 0
    samples: list[dict[str, Any]] = []

    for reg in regs:
        scanned += 1
        blobs = _registration_text_blob(db, reg)
        blob_key = _norm_key(" ".join(blobs.values())) or ""

        hits: dict[UUID, dict[str, Any]] = {}
        for mid, mname, keys in syn_map:
            for k in keys:
                if k and k in blob_key:
                    # Confidence heuristic by source field.
                    conf = 0.6
                    if k in (_norm_key(blobs.get("product_params")) or ""):
                        conf = 0.90
                    elif k in (_norm_key(blobs.get("registration_raw_json")) or ""):
                        conf = 0.75
                    elif k in (_norm_key(blobs.get("product_names")) or ""):
                        conf = 0.65
                    prev = hits.get(mid)
                    if (prev is None) or float(prev.get("confidence", 0.0)) < conf:
                        hits[mid] = {"methodology_id": mid, "methodology_name": mname, "confidence": conf}
                    break

        if not hits:
            continue
        matched_regs += 1
        if len(samples) < 20:
            samples.append(
                {
                    "registration_no": reg.registration_no,
                    "hits": [{"methodology_name": v["methodology_name"], "confidence": v["confidence"]} for v in hits.values()],
                }
            )

        if dry_run:
            continue

        for v in hits.values():
            stmt = insert(RegistrationMethodology).values(
                registration_id=reg.id,
                methodology_id=v["methodology_id"],
                confidence=float(v["confidence"]),
                source=str(source),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[RegistrationMethodology.registration_id, RegistrationMethodology.methodology_id],
                set_={
                    "confidence": stmt.excluded.confidence,
                    "source": stmt.excluded.source,
                    "updated_at": func.now(),
                },
            )
            db.execute(stmt)
            written += 1
        db.commit()

    return {
        "ok": True,
        "dry_run": bool(dry_run),
        "scanned_registrations": scanned,
        "matched_registrations": matched_regs,
        "upserts": written,
        "samples": samples,
    }
