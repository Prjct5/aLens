from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"
    log_level: str = "INFO"
    timezone: str = "Africa/Cairo"

    database_url: str = "postgresql://autolens:autolens_dev@localhost:5432/autolens"

    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"

    mlflow_tracking_uri: str = "http://localhost:5000"

    api_base_url: str = "http://localhost:8000"
    api_key: str = ""
    api_keys_sha256: str = ""
    api_rate_limit_per_minute: int = 60
    dashboard_origin: str = "http://localhost:8501"

    scraper_contact_email: str = "team@example.org"
    request_budget_per_second: float = 1.0

    quarantine_alert_days: int = 14
    github_repository: str = "Prjct5/aLens"
    gh_token: str = ""

    @property
    def api_key_hashes(self) -> set[str]:
        return {h.strip().lower() for h in self.api_keys_sha256.split(",") if h.strip()}

    @property
    def is_dev(self) -> bool:
        return self.environment.lower() == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
