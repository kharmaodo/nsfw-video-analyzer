from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "NSFW Video Analyzer"
    app_env: str = "development"
    app_debug: bool = False
    jwt_secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    oauth_session_secret_key: str | None = None
    oauth_google_client_id: str | None = None
    oauth_google_client_secret: str | None = None
    oauth_google_redirect_uri: str | None = None
    oauth_facebook_client_id: str | None = None
    oauth_facebook_client_secret: str | None = None
    oauth_facebook_redirect_uri: str | None = None
    oauth_facebook_graph_api_version: str = "v26.0"
    oauth_frontend_success_url: str = "http://localhost:3000/login"
    oauth_exchange_code_ttl_seconds: int = Field(default=60, ge=15, le=300)
    oauth_google_discovery_url: str = "https://accounts.google.com/.well-known/openid-configuration"
    bcrypt_rounds: int = Field(default=12, ge=10, le=15)

    auth_login_max_failures: int = Field(default=5, ge=1, le=100)
    auth_login_window_seconds: int = Field(default=900, ge=1, le=86400)
    auth_login_block_seconds: int = Field(default=900, ge=1, le=86400)
    auth_global_max_attempts: int = Field(default=100, ge=1, le=100000)
    auth_global_window_seconds: int = Field(default=60, ge=1, le=86400)

    initial_super_power_username: str | None = None
    initial_super_power_password: str | None = None
    database_url: str = "sqlite:///./storage/database/videos.db"
    sqlite_busy_timeout_ms: int = Field(default=5000, ge=1000, le=60000)
    scraper_connect_timeout_seconds: float = Field(default=5, gt=0, le=30)
    scraper_read_timeout_seconds: float = Field(default=15, gt=0, le=120)
    scraper_max_html_bytes: int = Field(default=2 * 1024 * 1024, ge=1024, le=10 * 1024 * 1024)
    scraper_max_redirects: int = Field(default=5, ge=0, le=10)
    ytdlp_cookies_file: str | None = None
    video_max_size_bytes: int = Field(default=5 * 1024 * 1024 * 1024, ge=1024)
    image_max_size_bytes: int = Field(default=25 * 1024 * 1024, ge=1024)
    media_upload_max_files: int = Field(default=10, ge=1, le=100)
    media_upload_max_total_bytes: int = Field(default=5 * 1024 * 1024 * 1024, ge=1024)
    media_upload_rate_limit_requests: int = Field(default=20, ge=1, le=1000)
    media_upload_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    media_storage_directory: str = "./storage/media"
    video_require_range_requests: bool = True
    video_allowed_content_types: Annotated[tuple[str, ...], NoDecode] = (
        "video/mp4",
        "video/webm",
        "video/x-matroska",
        "video/quicktime",
        "video/x-msvideo",
    )
    ffmpeg_binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"
    video_clip_duration_seconds: float = Field(default=300, gt=0, le=3600)
    video_frame_interval_seconds: float = Field(default=10, gt=0, le=300)
    video_frame_width: int = Field(default=384, ge=64, le=4096)
    video_process_timeout_seconds: float = Field(default=600, gt=0, le=7200)
    video_temporary_directory: str = "./storage/temporary"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_max_retries: int = Field(default=3, ge=0, le=10)
    celery_retry_delay_seconds: int = Field(default=15, ge=1, le=3600)
    nsfw_model_name: str = "Falconsai/nsfw_image_detection"
    nsfw_model_revision: str = "ea798c4a93814025af5c7befb6cbf34757ecc7b4"
    nsfw_threshold: float = Field(default=0.60, ge=0, le=1)
    nsfw_min_positive_frames: int = Field(default=1, ge=1, le=1000)
    nsfw_batch_size: int = Field(default=8, ge=1, le=128)
    nsfw_device: int = Field(default=-1, ge=-1)
    nsfw_cleanup_frames: bool = True
    api_allowed_hosts: Annotated[tuple[str, ...], NoDecode] = (
        "localhost",
        "127.0.0.1",
        "testserver",
        "api",
    )
    api_cors_allowed_origins: Annotated[tuple[str, ...], NoDecode] = (
        "http://localhost:5173",
    )

    api_max_request_bytes: int = Field(default=2 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)

    @field_validator("video_allowed_content_types", mode="before")
    @classmethod
    def parse_content_types(cls, value):  # type: ignore[no-untyped-def]
        if isinstance(value, str):
            return tuple(item.strip().lower() for item in value.split(",") if item.strip())
        return value

    @field_validator("api_allowed_hosts", "api_cors_allowed_origins", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, value):  # type: ignore[no-untyped-def]
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
