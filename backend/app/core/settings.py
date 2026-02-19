from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "GRVT AS 做市系统"
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    cors_origins: list[str] = ["*"]

    app_jwt_secret: str = Field(default="change-me", alias="APP_JWT_SECRET")
    app_token_expire_minutes: int = 60 * 12

    app_admin_user: str = Field(default="admin", alias="APP_ADMIN_USER")
    app_admin_password_hash: str = Field(default="$pbkdf2-sha256$29000$vDem1FpLiRECIKSUsjYGoA$18PFiYxoPnnIz2EFPTAy.RpuVX9c8FCexDibwe7.Uok", alias="APP_ADMIN_PASSWORD_HASH")

    grvt_env: str = Field(default="testnet", alias="GRVT_ENV")
    grvt_api_key: str = Field(default="", alias="GRVT_API_KEY")
    grvt_api_secret: str = Field(default="", alias="GRVT_API_SECRET")
    grvt_trading_account_id: str = Field(default="", alias="GRVT_TRADING_ACCOUNT_ID")
    grvt_use_mock: bool = Field(default=True, alias="GRVT_USE_MOCK")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")

    runtime_config_path: str = Field(default="data/runtime_config.json", alias="RUNTIME_CONFIG_PATH")
    data_dir: str = Field(default="data", alias="DATA_DIR")

    stream_queue_size: int = 1024

    @property
    def runtime_config_file(self) -> Path:
        return Path(self.runtime_config_path)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


