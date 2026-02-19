from __future__ import annotations

import logging

import httpx

from app.services.telegram_config import TelegramConfigStore


class AlertService:
    """告警分发服务。"""

    def __init__(self, telegram_config_store: TelegramConfigStore) -> None:
        self._telegram_config_store = telegram_config_store
        self._logger = logging.getLogger("alert")

    async def send(self, title: str, message: str) -> None:
        telegram_cfg = self._telegram_config_store.get()
        if not telegram_cfg.telegram_bot_token or not telegram_cfg.telegram_chat_id:
            self._logger.warning("Telegram 未配置，跳过告警: %s %s", title, message)
            return
        text = f"[{title}]\n{message}"
        url = f"https://api.telegram.org/bot{telegram_cfg.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": telegram_cfg.telegram_chat_id,
            "text": text,
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                await client.post(url, json=payload)
        except Exception as exc:
            self._logger.exception("发送 Telegram 告警失败: %s", exc)
