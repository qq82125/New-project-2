from __future__ import annotations

import xml.etree.ElementTree as ET

from app.services.udi_parse import parse_packing_list, parse_storage_list


def test_parse_packing_list_schema_and_numeric_casts() -> None:
    # De-identified example based on NMPA UDI <device> structure.
    device_xml = ET.fromstring(
        """
        <device>
          <zxxsdycpbs>06975737431158</zxxsdycpbs>
          <zczbhhzbapzbh>鄂械注准20252185501</zczbhhzbapzbh>
          <sfyzcbayz>是</sfyzcbayz>
          <versionTime>2026-02-15</versionTime>
          <packingList>
            <packing>
              <bzcpbs>26975737430209</bzcpbs>
              <cpbzjb>箱</cpbzjb>
              <bznhxyjcpbssl>10</bznhxyjcpbssl>
              <bznhxyjbzcpbs>06975737431158</bznhxyjbzcpbs>
            </packing>
            <packing>
              <bzcpbs>16975737430493</bzcpbs>
              <cpbzjb>盒</cpbzjb>
              <bznhxyjcpbssl>10</bznhxyjcpbssl>
              <bznhxyjbzcpbs>06975737431158</bznhxyjbzcpbs>
            </packing>
          </packingList>
        </device>
        """.strip()
    )

    out = parse_packing_list(device_xml)
    assert out["source"] == "UDI"
    assert out["parsed_at"] == "2026-02-15"
    assert isinstance(out["packings"], list)
    assert len(out["packings"]) == 2
    assert out["packings"][0]["package_di"] == "26975737430209"
    assert out["packings"][0]["package_level"] == "箱"
    assert out["packings"][0]["contains_qty"] == 10
    assert out["packings"][0]["child_di"] == "06975737431158"


def test_parse_storage_list_schema_and_numeric_casts() -> None:
    device_xml = ET.fromstring(
        """
        <device>
          <zxxsdycpbs>06942221705095</zxxsdycpbs>
          <versionTime>2026-02-15</versionTime>
          <storageList>
            <storage>
              <cchcztj>冷藏</cchcztj>
              <zdz>2</zdz>
              <zgz>8</zgz>
              <jldw>℃</jldw>
            </storage>
            <storage>
              <cchcztj>常温</cchcztj>
              <zdz></zdz>
              <zgz>30</zgz>
              <jldw>℃</jldw>
            </storage>
          </storageList>
        </device>
        """.strip()
    )

    out = parse_storage_list(device_xml)
    assert out["source"] == "UDI"
    assert out["parsed_at"] == "2026-02-15"
    assert isinstance(out["storages"], list)
    assert len(out["storages"]) == 2
    assert out["storages"][0]["type"] == "冷藏"
    assert out["storages"][0]["min"] == 2.0
    assert out["storages"][0]["max"] == 8.0
    assert out["storages"][0]["unit"] == "℃"
    assert out["storages"][0]["range"] == "2-8℃"
    assert out["storages"][1]["min"] is None
    assert out["storages"][1]["max"] == 30.0
    assert out["storages"][1]["range"] == "30℃"


def test_missing_lists_are_allowed() -> None:
    device_xml = ET.fromstring("<device><versionTime>2026-02-15</versionTime></device>")
    assert parse_packing_list(device_xml)["packings"] == []
    assert parse_storage_list(device_xml)["storages"] == []

