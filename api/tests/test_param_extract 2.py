from __future__ import annotations

from app.ivd.param_extract import extract_from_text


def test_extract_lod_from_text() -> None:
    text = "本试剂盒检出限(LOD)为 0.12 ng/mL。"
    items = extract_from_text(text)
    assert items
    lod = [x for x in items if x['param_code'] == 'LOD']
    assert lod
    assert lod[0]['value_num'] == 0.12
