from __future__ import annotations

from typing import Any
from xml.etree.ElementTree import Element


def _text(node: Element | None, tag: str) -> str | None:
    if node is None:
        return None
    child = node.find(tag)
    if child is None or child.text is None:
        return None
    s = child.text.strip()
    return s or None


def _int(v: str | None) -> int | None:
    if v is None:
        return None
    s = v.strip()
    if not s:
        return None
    try:
        return int(float(s))
    except Exception:
        return None


def _float(v: str | None) -> float | None:
    if v is None:
        return None
    s = v.strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _parsed_at_from_device(device_xml: Element) -> str | None:
    # Keep the functions deterministic: prefer timestamps present in XML.
    # `versionTime` is commonly present in NMPA UDI delta exports; otherwise fallback to publish date.
    for tag in ("versionTime", "cpbsfbrq", "creationDate"):
        v = _text(device_xml, tag)
        if v:
            return v
    return None


def parse_packing_list(device_xml: Element) -> dict[str, Any]:
    """Parse <packingList> under a <device> node into canonical JSON.

    Output schema:
    {
      "packings": [
        {"package_di": str, "package_level": str|null, "contains_qty": int|null, "child_di": str|null}
      ],
      "source": "UDI",
      "parsed_at": str|null
    }
    """
    packings: list[dict[str, Any]] = []
    pl = device_xml.find("packingList")
    if pl is not None:
        for p in pl.findall("packing"):
            package_di = _text(p, "bzcpbs")
            if not package_di:
                continue
            packings.append(
                {
                    "package_di": package_di,
                    "package_level": _text(p, "cpbzjb"),
                    "contains_qty": _int(_text(p, "bznhxyjcpbssl")),
                    "child_di": _text(p, "bznhxyjbzcpbs"),
                }
            )
    return {"packings": packings, "source": "UDI", "parsed_at": _parsed_at_from_device(device_xml)}


def parse_storage_list(device_xml: Element) -> dict[str, Any]:
    """Parse <storageList> under a <device> node into canonical JSON.

    Output schema:
    {
      "storages": [
        {"type": str|null, "min": float|null, "max": float|null, "unit": str|null, "range": str|null}
      ],
      "source": "UDI",
      "parsed_at": str|null
    }
    """
    storages: list[dict[str, Any]] = []
    sl = device_xml.find("storageList")
    if sl is not None:
        for s in sl.findall("storage"):
            t = _text(s, "cchcztj")
            mn = _float(_text(s, "zdz"))
            mx = _float(_text(s, "zgz"))
            unit = _text(s, "jldw")

            rng: str | None = None
            if mn is not None and mx is not None and unit:
                # Use "~" to match how temperature ranges are commonly expressed in CN materials.
                rng = f"{mn:g}~{mx:g}{unit}"
            elif mn is not None and mx is not None:
                rng = f"{mn:g}~{mx:g}"
            elif mn is not None and unit:
                rng = f"{mn:g}{unit}"
            elif mx is not None and unit:
                rng = f"{mx:g}{unit}"
            elif mn is not None:
                rng = f"{mn:g}"
            elif mx is not None:
                rng = f"{mx:g}"

            storages.append({"type": t, "min": mn, "max": mx, "unit": unit, "range": rng})

    return {"storages": storages, "source": "UDI", "parsed_at": _parsed_at_from_device(device_xml)}
