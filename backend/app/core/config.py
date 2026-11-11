import os
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_NAME: str = "MedScope DCMS"
    DEBUG: bool = True
    TIMEZONE: str = "Asia/Dhaka"

    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    API_V1_STR: str = "/api/v1"

    DATABASE_HOST: str = "127.0.0.1"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "medscope_dcms"
    DATABASE_USER: str = "medscope_app"
    DATABASE_PASSWORD: str = Field(default="CHANGE_ME_LOCALLY")
    DATABASE_SSLMODE: str = "prefer"

    DATABASE_URL: str | None = None

    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800

    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:5173,http://127.0.0.1:5173"
    FRONTEND_URL: str = "http://localhost:5173"

    # Authentication & Session Settings (Prompt 09)
    SESSION_COOKIE_NAME: str = "medscope_session"
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: str = "lax"
    SESSION_IDLE_TIMEOUT_MINUTES: int = 120  # 2 hours idle timeout
    SESSION_ABSOLUTE_LIFETIME_HOURS: int = 24  # 24 hours absolute maximum lifetime
    AUTH_MAX_FAILED_ATTEMPTS: int = 5

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str | None, values) -> str:
        if v and isinstance(v, str) and v.startswith("postgresql"):
            return v
        data = values.data if hasattr(values, "data") else values
        host = data.get("DATABASE_HOST", "127.0.0.1")
        port = data.get("DATABASE_PORT", 5432)
        db = data.get("DATABASE_NAME", "medscope_dcms")
        user = data.get("DATABASE_USER", "medscope_app")
        pwd = data.get("DATABASE_PASSWORD", "")
        return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}"

    @property
    def cors_origin_list(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()

