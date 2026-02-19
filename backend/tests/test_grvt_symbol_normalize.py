from app.exchange.grvt_live import GrvtLiveAdapter


def test_normalize_symbol_supports_legacy_perp_variants():
    assert GrvtLiveAdapter._normalize_symbol("BNB_USDT-PERP") == "BNB_USDT_Perp"
    assert GrvtLiveAdapter._normalize_symbol("BNB_USDT_PERP") == "BNB_USDT_Perp"
    assert GrvtLiveAdapter._normalize_symbol("BNB_USDT_Perp") == "BNB_USDT_Perp"


def test_symbol_equal_ignores_case_and_delimiter():
    assert GrvtLiveAdapter._symbol_equal("BNB_USDT-PERP", "bnb_usdt_perp")
    assert GrvtLiveAdapter._symbol_equal("BNB_USDT_Perp", "BNB_USDT_PERP")
