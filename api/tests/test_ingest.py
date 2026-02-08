from app.services.mapping import UnifiedRecord


def test_unified_record_dataclass() -> None:
    rec = UnifiedRecord(
        udi_di='1',
        product_name='n',
        model=None,
        specification=None,
        category=None,
        company_name=None,
        company_country=None,
        registration_no=None,
        filing_no=None,
        registration_status=None,
        approval_date=None,
        expiry_date=None,
        raw_json={'x': 1},
    )
    assert rec.raw_json['x'] == 1
