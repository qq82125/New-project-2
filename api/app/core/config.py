from __future__ import annotations

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    database_url: str = 'postgresql+psycopg://nmpa:nmpa@localhost:5432/nmpa'
    api_host: str = '0.0.0.0'
    api_port: int = 8000
    auth_secret: str = 'change-me-auth-secret'
    auth_cookie_name: str = 'ivd_session'
    auth_session_ttl_hours: int = 168
    auth_cookie_secure: bool = False
    cors_origins: str = 'http://localhost:3000,http://127.0.0.1:3000'
    bootstrap_admin_email: str = 'admin@example.com'
    bootstrap_admin_password: str = 'change-me-admin-password'
    admin_username: str = 'admin'
    admin_password: str = 'change-me'

    nmpa_udi_download_page: str = 'https://udi.nmpa.gov.cn/download.html'
    download_base_url: str = 'https://udi.nmpa.gov.cn'
    staging_dir: str = './staging'
    sync_interval_seconds: int = 86400
    sync_retry_attempts: int = 3
    sync_retry_backoff_seconds: int = 5
    sync_retry_backoff_multiplier: float = 2.0
    webhook_url: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    email_from: Optional[str] = None
    export_quota_basic_daily: int = 5
    export_quota_pro_daily: int = 50
    export_quota_enterprise_daily: int = 500


@lru_cache
def get_settings() -> Settings:
    return Settings()
