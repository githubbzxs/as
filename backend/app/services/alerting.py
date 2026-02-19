from __future__ import annotations

import logging

import httpx

from app.core.settings import Settings


class AlertService:
    """告警分发服务。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logging.getLogger("alert")

    async def send(self, title: str, message: str) -> None:
        if not self._settings.telegram_bot_token or not self._settings.telegram_chat_id:
            self._logger.warning("Telegram 未配置，跳过告警: %s %s", title, message)
            return
        text = f"[{title}]\n{message}"
        url = f"https://api.telegram.org/bot{self._settings.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self._settings.telegram_chat_id,
            "text": text,
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                await client.post(url, json=payload)
        except Exception as exc:
            self._logger.exception("发送 Telegram 告警失败: %s", exc)
