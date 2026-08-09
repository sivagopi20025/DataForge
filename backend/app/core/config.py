from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    api_key: str | None = Field(default=None, alias="DATAFORGE_API_KEY")
    database_url: str = Field(
        default="postgresql+psycopg://dataforge:dataforge123@127.0.0.1:55434/dataforge",
        alias="DATABASE_URL",
    )
    output_dir: Path = Field(default=Path("output/backend"), alias="OUTPUT_DIR")
    max_batch_records: int = Field(default=500_000, ge=0, alias="MAX_BATCH_RECORDS")
    generated_file_retention_days: int = Field(default=7, alias="GENERATED_FILE_RETENTION_DAYS")
    storage_backend: str = Field(default="local", alias="STORAGE_BACKEND")
    object_storage_bucket: str | None = Field(default=None, alias="OBJECT_STORAGE_BUCKET")
    object_storage_base_url: str | None = Field(default=None, alias="OBJECT_STORAGE_BASE_URL")
    object_storage_endpoint_url: str | None = Field(default=None, alias="OBJECT_STORAGE_ENDPOINT_URL")
    object_storage_region: str = Field(default="us-east-1", alias="OBJECT_STORAGE_REGION")
    object_storage_access_key_id: str | None = Field(default=None, alias="OBJECT_STORAGE_ACCESS_KEY_ID")
    object_storage_secret_access_key: str | None = Field(default=None, alias="OBJECT_STORAGE_SECRET_ACCESS_KEY")
    object_storage_presign_seconds: int = Field(default=300, ge=1, alias="OBJECT_STORAGE_PRESIGN_SECONDS")
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=120, ge=1, alias="RATE_LIMIT_REQUESTS")
    rate_limit_window_seconds: int = Field(default=60, ge=1, alias="RATE_LIMIT_WINDOW_SECONDS")
    stream_query_token_enabled: bool = Field(default=True, alias="STREAM_QUERY_TOKEN_ENABLED")
    benchmark_detector_upload_max_bytes: int = Field(default=5_000_000, ge=1, alias="BENCHMARK_DETECTOR_UPLOAD_MAX_BYTES")
    benchmark_runs_per_period: int = Field(default=25, ge=1, alias="BENCHMARK_RUNS_PER_PERIOD")
    benchmark_run_period_seconds: int = Field(default=3600, ge=1, alias="BENCHMARK_RUN_PERIOD_SECONDS")
    benchmark_concurrent_runs: int = Field(default=2, ge=1, alias="BENCHMARK_CONCURRENT_RUNS")
    benchmark_artifact_retention_days: int = Field(default=30, ge=1, alias="BENCHMARK_ARTIFACT_RETENTION_DAYS")
    webhook_allowed_domains_raw: str = Field(default="", alias="WEBHOOK_ALLOWED_DOMAINS")
    cors_origins_raw: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def webhook_allowed_domains(self) -> list[str]:
        return [domain.strip().lower() for domain in self.webhook_allowed_domains_raw.split(",") if domain.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
