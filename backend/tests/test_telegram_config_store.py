from app.core.settings import Settings
from app.schemas import TelegramConfigUpdateRequest
from app.services.telegram_config import TelegramConfigStore


def build_settings() -> Settings:
    return Settings(
        telegram_bot_token="",
        telegram_chat_id="",
    )


def test_telegram_config_store_update_and_persist(tmp_path):
    path = tmp_path / "telegram.json"
    store = TelegramConfigStore(path, build_settings())

    updated = store.update(
        TelegramConfigUpdateRequest(
            telegram_bot_token="bot-1",
            telegram_chat_id="chat-1",
        )
    )
    assert updated.telegram_bot_token == "bot-1"
    assert updated.telegram_chat_id == "chat-1"

    restored = TelegramConfigStore(path, build_settings()).get()
    assert restored.telegram_bot_token == "bot-1"
    assert restored.telegram_chat_id == "chat-1"


def test_telegram_config_store_empty_not_override_and_clear(tmp_path):
    path = tmp_path / "telegram.json"
    store = TelegramConfigStore(path, build_settings())
    store.update(TelegramConfigUpdateRequest(telegram_bot_token="bot-1"))

    keep = store.update(TelegramConfigUpdateRequest(telegram_bot_token=""))
    assert keep.telegram_bot_token == "bot-1"

    cleared = store.update(TelegramConfigUpdateRequest(clear_telegram_bot_token=True))
    assert cleared.telegram_bot_token == ""
