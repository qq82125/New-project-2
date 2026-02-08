from __future__ import annotations

import hashlib
import re
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.core.config import Settings

DAILY_PATTERN = re.compile(r'(daily|每日|update|增量)', re.IGNORECASE)
MD5_PATTERN = re.compile(r'^[a-fA-F0-9]{32}$')


@dataclass
class DailyPackage:
    filename: str
    md5: str | None
    download_url: str


def parse_daily_packages(html: str, base_url: str) -> list[DailyPackage]:
    soup = BeautifulSoup(html, 'html.parser')
    packages: list[DailyPackage] = []

    for link in soup.find_all('a', href=True):
        text = (link.get_text(strip=True) or '') + ' ' + link['href']
        if not DAILY_PATTERN.search(text):
            continue

        href = link['href']
        filename = Path(href).name
        md5: str | None = None

        parent_text = link.parent.get_text(' ', strip=True) if link.parent else text
        for token in parent_text.split():
            if MD5_PATTERN.fullmatch(token):
                md5 = token.lower()
                break

        packages.append(DailyPackage(filename=filename, md5=md5, download_url=urljoin(base_url, href)))

    dedup: dict[str, DailyPackage] = {}
    for item in packages:
        dedup[item.filename] = item
    return sorted(dedup.values(), key=lambda p: p.filename, reverse=True)


def pick_latest_package(packages: list[DailyPackage]) -> DailyPackage:
    if not packages:
        raise ValueError('No daily package found from UDI download page')
    return packages[0]


def fetch_latest_package_meta(settings: Settings) -> DailyPackage:
    response = requests.get(settings.nmpa_udi_download_page, timeout=30)
    response.raise_for_status()
    packages = parse_daily_packages(response.text, settings.download_base_url)
    return pick_latest_package(packages)


def download_file(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, timeout=120, stream=True) as response:
        response.raise_for_status()
        with destination.open('wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    return destination


def _calculate_hash(file_path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with file_path.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def calculate_md5(file_path: Path) -> str:
    return _calculate_hash(file_path, 'md5')


def calculate_sha256(file_path: Path) -> str:
    return _calculate_hash(file_path, 'sha256')


def verify_checksum(file_path: Path, expected: str | None, algorithm: str = 'md5') -> bool:
    if not expected:
        return True
    actual = _calculate_hash(file_path, algorithm)
    return actual.lower() == expected.lower()


def verify_md5(file_path: Path, expected_md5: str | None) -> bool:
    return verify_checksum(file_path, expected_md5, 'md5')


def extract_to_staging(archive_path: Path, staging_dir: Path) -> Path:
    staging_dir.mkdir(parents=True, exist_ok=True)
    if archive_path.suffix.lower() == '.zip':
        with zipfile.ZipFile(archive_path, 'r') as zf:
            zf.extractall(staging_dir)
    elif archive_path.suffix.lower() in {'.gz', '.tgz'} or archive_path.name.endswith('.tar.gz'):
        with tarfile.open(archive_path, 'r:*') as tf:
            tf.extractall(staging_dir)
    else:
        target = staging_dir / archive_path.name
        target.write_bytes(archive_path.read_bytes())
    return staging_dir
