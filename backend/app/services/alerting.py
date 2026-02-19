from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.telegram_config import TelegramConfigStore


class AlertService:
    """告警分发服务。"""

    def __init__(self, telegram_config_store: TelegramConfigStore) -> None:
        self._telegram_config_store = telegram_config_store
        self._logger = logging.getLogger("alert")
        self._last_sent_at: dict[str, datetime] = {}

    async def send(self, title: str, message: str) -> None:
        """兼容旧调用。"""
        await self.send_event(level="INFO", event=title, message=message)

    async def send_event(
        self,
        *,
        level: str,
        event: str,
        message: str,
        details: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
        min_interval_sec: float = 0.0,
    ) -> None:
        telegram_cfg = self._telegram_config_store.get()
        if not telegram_cfg.telegram_bot_token or not telegram_cfg.telegram_chat_id:
            self._logger.warning("Telegram 未配置，跳过告警: [%s][%s] %s", level, event, message)
            return

        key = dedupe_key or f"{level}:{event}"
        if self._should_skip(key, min_interval_sec):
            return

        now = datetime.now(timezone.utc)
        lines = [
            f"[MM][{level.upper()}][{event}]",
            now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            message,
        ]
        if details:
            for k, v in details.items():
                lines.append(f"{k}: {v}")

        url = f"https://api.telegram.org/bot{telegram_cfg.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": telegram_cfg.telegram_chat_id,
            "text": "\n".join(lines),
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                await client.post(url, json=payload)
        except Exception as exc:
            self._logger.exception("发送 Telegram 告警失败: %s", exc)

    def _should_skip(self, key: str, min_interval_sec: float) -> bool:
        now = datetime.now(timezone.utc)
        if min_interval_sec <= 0:
            self._last_sent_at[key] = now
            return False
        last = self._last_sent_at.get(key)
        if last is not None and (now - last).total_seconds() < min_interval_sec:
            return True
        self._last_sent_at[key] = now
        return False
