from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.settings import Settings
from app.schemas import ExchangeConfigUpdateRequest, ExchangeConfigView


class ExchangeConfigRecord(BaseModel):
    """交易所连接配置（含敏感字段，仅服务端使用）。"""

    grvt_env: str = "prod"
    grvt_api_key: str = ""
    grvt_api_secret: str = ""
    grvt_trading_account_id: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("grvt_env")
    @classmethod
    def validate_env(cls, value: str) -> str:
        env = value.strip().lower()
        if env == "production":
            env = "prod"
        if env not in {"testnet", "prod", "staging", "dev"}:
            raise ValueError("grvt_env 仅支持 testnet/prod/staging/dev")
        return env

    @field_validator("grvt_api_key", "grvt_api_secret", "grvt_trading_account_id")
    @classmethod
    def normalize_secret_text(cls, value: str) -> str:
        return value.strip()


class ExchangeConfigStore:
    """交易所配置持久化。"""

    def __init__(self, path: Path, settings: Settings) -> None:
        self._path = path
        self._settings = settings
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._config = self._load_or_default()

    def _default(self) -> ExchangeConfigRecord:
        return ExchangeConfigRecord(
            grvt_env="prod",
            grvt_api_key=self._settings.grvt_api_key,
            grvt_api_secret=self._settings.grvt_api_secret,
            grvt_trading_account_id=self._settings.grvt_trading_account_id,
        )

    def _normalize_env(self, config: ExchangeConfigRecord) -> ExchangeConfigRecord:
        if config.grvt_env == "prod":
            return config
        normalized = config.model_copy(
            update={
                "grvt_env": "prod",
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._save(normalized)
        return normalized

    def _load_or_default(self) -> ExchangeConfigRecord:
        if not self._path.exists():
            config = self._default()
            self._save(config)
            return config
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            config = ExchangeConfigRecord.model_validate(raw)
            config = self._normalize_env(config)
            if isinstance(raw, dict):
                allowed_keys = {
                    "grvt_env",
                    "grvt_api_key",
                    "grvt_api_secret",
                    "grvt_trading_account_id",
                    "updated_at",
                }
                if any(key not in allowed_keys for key in raw.keys()):
                    self._save(config)
            return config
        except (json.JSONDecodeError, ValidationError, OSError):
            config = self._default()
            self._save(config)
            return config

    def _save(self, config: ExchangeConfigRecord) -> None:
        self._path.write_text(
            config.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def get(self) -> ExchangeConfigRecord:
        return self._config

    def _resolve_secret_value(self, current: str, incoming: str | None, clear: bool) -> str:
        if clear:
            return ""
        if incoming is None:
            return current
        value = incoming.strip()
        if value == "":
            # 空字符串视为“保持原值”，避免 UI 空输入误覆盖。
            return current
        return value

    def update(self, payload: ExchangeConfigUpdateRequest) -> ExchangeConfigRecord:
        merged = self._config.model_dump()

        merged["grvt_api_key"] = self._resolve_secret_value(
            current=self._config.grvt_api_key,
            incoming=payload.grvt_api_key,
            clear=payload.clear_grvt_api_key,
        )
        merged["grvt_api_secret"] = self._resolve_secret_value(
            current=self._config.grvt_api_secret,
            incoming=payload.grvt_api_secret,
            clear=payload.clear_grvt_api_secret,
        )
        merged["grvt_trading_account_id"] = self._resolve_secret_value(
            current=self._config.grvt_trading_account_id,
            incoming=payload.grvt_trading_account_id,
            clear=payload.clear_grvt_trading_account_id,
        )
        merged["updated_at"] = datetime.now(timezone.utc)

        cfg = ExchangeConfigRecord.model_validate(merged)
        self._config = cfg
        self._save(cfg)
        return cfg

    def to_view(self) -> ExchangeConfigView:
        cfg = self._config
        return ExchangeConfigView(
            grvt_env=cfg.grvt_env,
            grvt_api_key_configured=bool(cfg.grvt_api_key),
            grvt_api_secret_configured=bool(cfg.grvt_api_secret),
            grvt_trading_account_id_configured=bool(cfg.grvt_trading_account_id),
            updated_at=cfg.updated_at,
        )
