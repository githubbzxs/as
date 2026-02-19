from __future__ import annotations

import math

from app.models import QuoteDecision


class AsMarketMakerModel:
    """Avellaneda-Stoikov 报价模型。"""

    def compute_quote(
        self,
        mid_price: float,
        sigma: float,
        inventory_base: float,
        max_inventory_base: float,
        base_gamma: float,
        gamma_min: float,
        gamma_max: float,
        liquidity_k: float,
        horizon_sec: float,
        min_spread_bps: float,
        max_spread_bps: float,
        quote_size_notional: float,
    ) -> QuoteDecision:
        # gamma 随波动增强，并做限幅。
        sigma_ref = 0.003
        gamma = base_gamma * (1.0 + min(3.0, sigma / max(1e-9, sigma_ref)))
        gamma = max(gamma_min, min(gamma_max, gamma))

        # 使用库存比例控制 reservation price 偏移。
        inventory_ratio = 0.0
        if max_inventory_base > 0:
            inventory_ratio = max(-1.0, min(1.0, inventory_base / max_inventory_base))

        reservation_shift = inventory_ratio * gamma * (sigma**2) * max(1.0, horizon_sec)
        reservation_price = mid_price * (1.0 - reservation_shift)

        # AS 半价差公式。
        k = max(1e-6, liquidity_k)
        raw_half_spread = (gamma * sigma * sigma * horizon_sec) / 2 + (1.0 / gamma) * math.log(1 + gamma / k)
        raw_spread_bps = max(0.1, raw_half_spread * 2 * 10000)
        spread_bps = max(min_spread_bps, min(max_spread_bps, raw_spread_bps))

        spread_abs = reservation_price * spread_bps / 10000
        bid = max(0.0001, reservation_price - spread_abs / 2)
        ask = max(bid + 0.0001, reservation_price + spread_abs / 2)

        quote_size_base = quote_size_notional / max(mid_price, 1e-9)

        return QuoteDecision(
            bid_price=bid,
            ask_price=ask,
            quote_size_base=quote_size_base,
            quote_size_notional=quote_size_notional,
            spread_bps=spread_bps,
            gamma=gamma,
            reservation_price=reservation_price,
        )
