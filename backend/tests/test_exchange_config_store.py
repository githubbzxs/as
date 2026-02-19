from app.core.settings import Settings
from app.schemas import ExchangeConfigUpdateRequest
from app.services.exchange_config import ExchangeConfigStore


def build_settings() -> Settings:
    return Settings(
        grvt_env="testnet",
        grvt_use_mock=True,
        grvt_api_key="",
        grvt_api_secret="",
        grvt_trading_account_id="",
    )


def test_exchange_config_store_update_and_persist(tmp_path):
    path = tmp_path / "exchange.json"
    store = ExchangeConfigStore(path, build_settings())

    updated = store.update(
        ExchangeConfigUpdateRequest(
            grvt_env="prod",
            grvt_use_mock=False,
            grvt_api_key="key-A",
            grvt_api_secret="secret-A",
            grvt_trading_account_id="acc-A",
        )
    )
    assert updated.grvt_env == "prod"
    assert updated.grvt_use_mock is False
    assert updated.grvt_api_key == "key-A"

    restored = ExchangeConfigStore(path, build_settings()).get()
    assert restored.grvt_api_key == "key-A"
    assert restored.grvt_trading_account_id == "acc-A"


def test_exchange_config_store_empty_not_override_and_clear(tmp_path):
    path = tmp_path / "exchange.json"
    store = ExchangeConfigStore(path, build_settings())
    store.update(ExchangeConfigUpdateRequest(grvt_api_key="key-A"))

    keep = store.update(ExchangeConfigUpdateRequest(grvt_api_key=""))
    assert keep.grvt_api_key == "key-A"

    cleared = store.update(ExchangeConfigUpdateRequest(clear_grvt_api_key=True))
    assert cleared.grvt_api_key == ""
