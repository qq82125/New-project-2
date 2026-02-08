from pathlib import Path

from app.services.crawler import parse_daily_packages, pick_latest_package, verify_md5


def test_parse_daily_packages_extracts_md5_and_url() -> None:
    html = '''
    <html><body>
      <div><a href="/files/UDI_daily_20260207.zip">每日更新包</a> d41d8cd98f00b204e9800998ecf8427e</div>
      <div><a href="/files/UDI_weekly_20260201.zip">每周包</a></div>
    </body></html>
    '''
    items = parse_daily_packages(html, 'https://udi.nmpa.gov.cn')
    assert len(items) == 1
    assert items[0].filename == 'UDI_daily_20260207.zip'
    assert items[0].md5 == 'd41d8cd98f00b204e9800998ecf8427e'
    assert items[0].download_url == 'https://udi.nmpa.gov.cn/files/UDI_daily_20260207.zip'


def test_pick_latest_package_raises_on_empty() -> None:
    try:
        pick_latest_package([])
    except ValueError:
        assert True
    else:
        assert False


def test_verify_md5(tmp_path: Path) -> None:
    file_path = tmp_path / 'x.txt'
    file_path.write_text('', encoding='utf-8')
    assert verify_md5(file_path, 'd41d8cd98f00b204e9800998ecf8427e')
