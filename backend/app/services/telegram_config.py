from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.settings import Settings
from app.schemas import TelegramConfigUpdateRequest, TelegramConfigView


class TelegramConfigRecord(BaseModel):
    """Telegram 告警配置（含敏感字段，仅服务端使用）。"""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("telegram_bot_token", "telegram_chat_id")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class TelegramConfigStore:
    """Telegram 告警配置持久化。"""

    def __init__(self, path: Path, settings: Settings) -> None:
        self._path = path
        self._settings = settings
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._config = self._load_or_default()

    def _default(self) -> TelegramConfigRecord:
        return TelegramConfigRecord(
            telegram_bot_token=self._settings.telegram_bot_token,
            telegram_chat_id=self._settings.telegram_chat_id,
        )

    def _load_or_default(self) -> TelegramConfigRecord:
        if not self._path.exists():
            config = self._default()
            self._save(config)
            return config
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return TelegramConfigRecord.model_validate(raw)
        except (json.JSONDecodeError, ValidationError, OSError):
            config = self._default()
            self._save(config)
            return config

    def _save(self, config: TelegramConfigRecord) -> None:
        self._path.write_text(config.model_dump_json(indent=2), encoding="utf-8")

    def get(self) -> TelegramConfigRecord:
        return self._config

    def _resolve_secret_value(self, current: str, incoming: str | None, clear: bool) -> str:
        if clear:
            return ""
        if incoming is None:
            return current
        value = incoming.strip()
        if value == "":
            return current
        return value

    def update(self, payload: TelegramConfigUpdateRequest) -> TelegramConfigRecord:
        merged = self._config.model_dump()

        merged["telegram_bot_token"] = self._resolve_secret_value(
            current=self._config.telegram_bot_token,
            incoming=payload.telegram_bot_token,
            clear=payload.clear_telegram_bot_token,
        )
        merged["telegram_chat_id"] = self._resolve_secret_value(
            current=self._config.telegram_chat_id,
            incoming=payload.telegram_chat_id,
            clear=payload.clear_telegram_chat_id,
        )
        merged["updated_at"] = datetime.now(timezone.utc)

        cfg = TelegramConfigRecord.model_validate(merged)
        self._config = cfg
        self._save(cfg)
        return cfg

    def to_view(self) -> TelegramConfigView:
        cfg = self._config
        return TelegramConfigView(
            telegram_bot_token_configured=bool(cfg.telegram_bot_token),
            telegram_chat_id_configured=bool(cfg.telegram_chat_id),
            updated_at=cfg.updated_at,
        )
