from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import __version__


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    auth_token: SecretStr = SecretStr("")
    user_agent: str = f"BookOrbitTurkishMetadata/{__version__}"
    source_interval_seconds: float = Field(default=2.0, ge=0, le=60)
    request_timeout_seconds: float = Field(default=5.0, gt=0, le=20)
    deadline_seconds: float = Field(default=12.0, gt=0, le=25)
    search_cache_ttl: int = Field(default=900, ge=1)
    book_cache_ttl: int = Field(default=86400, ge=1)
    cache_max_bytes: int = Field(default=16 * 1024 * 1024, ge=1024)
    api_requests_per_minute: int = Field(default=60, ge=1, le=10000)
    max_results: int = Field(default=5, ge=1, le=10)
