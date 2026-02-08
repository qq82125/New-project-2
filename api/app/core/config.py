from __future__ import annotations

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    database_url: str = 'postgresql+psycopg://nmpa:nmpa@localhost:5432/nmpa'
    api_host: str = '0.0.0.0'
    api_port: int = 8000

    nmpa_udi_download_page: str = 'https://udi.nmpa.gov.cn/download.html'
    download_base_url: str = 'https://udi.nmpa.gov.cn'
    staging_dir: str = './staging'
    sync_interval_seconds: int = 86400
    webhook_url: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
