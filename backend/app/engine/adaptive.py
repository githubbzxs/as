from __future__ import annotations

import math
from collections import deque
from statistics import mean, pstdev


class AdaptiveController:
    """实时参数自适应控制器。"""

    def __init__(self, maxlen: int = 600) -> None:
        self._returns: deque[float] = deque(maxlen=maxlen)
        self._depth_scores: deque[float] = deque(maxlen=maxlen)
        self._trade_intensity: deque[float] = deque(maxlen=maxlen)
        self._sigma_history: deque[float] = deque(maxlen=maxlen)
        self._last_mid: float | None = None

    def update(self, mid: float, depth_score: float, trade_intensity: float) -> tuple[float, float]:
        if self._last_mid and self._last_mid > 0:
            ret = math.log(max(mid, 1e-9) / self._last_mid)
            self._returns.append(ret)
        self._last_mid = mid

        self._depth_scores.append(depth_score)
        self._trade_intensity.append(trade_intensity)

        sigma = self.current_sigma()
        self._sigma_history.append(sigma)
        z = self.sigma_zscore(sigma)
        return sigma, z

    def current_sigma(self) -> float:
        if len(self._returns) < 4:
            return 0.001
        var = mean([r * r for r in self._returns])
        sigma = math.sqrt(max(var, 1e-12))
        return max(1e-6, sigma)

    def sigma_zscore(self, sigma_now: float | None = None) -> float:
        if sigma_now is None:
            sigma_now = self.current_sigma()
        if len(self._sigma_history) < 20:
            return 0.0
        mu = mean(self._sigma_history)
        sd = pstdev(self._sigma_history)
        if sd < 1e-12:
            return 0.0
        return (sigma_now - mu) / sd

    def depth_factor(self) -> float:
        if not self._depth_scores:
            return 1.0
        cur = self._depth_scores[-1]
        avg = mean(self._depth_scores)
        ratio = cur / max(avg, 1e-9)
        # 深度差时增大点差，深度好时减小点差。
        return max(0.7, min(1.8, 1.2 - 0.35 * (ratio - 1.0)))

    def intensity_factor(self) -> float:
        if not self._trade_intensity:
            return 1.0
        cur = self._trade_intensity[-1]
        avg = mean(self._trade_intensity)
        ratio = cur / max(avg, 1e-9)
        # 成交强度高时可以适当缩小价差，低流动性时放宽。
        return max(0.7, min(1.6, 1.15 - 0.25 * (ratio - 1.0)))

    def quote_size_factor(self) -> float:
        sigma = self.current_sigma()
        baseline = 0.001
        ratio = sigma / baseline
        if ratio <= 1:
            return 1.0
        # 波动越大，挂单量越小。
        return max(0.2, min(1.0, 1.0 / math.sqrt(ratio)))
