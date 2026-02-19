from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RiskInput:
    equity: float
    drawdown_pct: float
    sigma_zscore: float
    consecutive_failures: int


@dataclass(slots=True)
class RiskResult:
    triggered: bool
    reason: str | None = None


class RiskGuard:
    """风控与熔断状态机。"""

    def __init__(self) -> None:
        self._peak_equity: float | None = None

    def update_drawdown(self, equity: float) -> float:
        if self._peak_equity is None:
            self._peak_equity = equity
            return 0.0
        self._peak_equity = max(self._peak_equity, equity)
        if self._peak_equity <= 0:
            return 0.0
        dd = max(0.0, (self._peak_equity - equity) / self._peak_equity * 100)
        return dd

    def reset_peak(self, equity: float) -> None:
        self._peak_equity = equity

    def evaluate(
        self,
        risk_input: RiskInput,
        drawdown_kill_pct: float,
        volatility_kill_zscore: float,
        max_consecutive_failures: int,
    ) -> RiskResult:
        if risk_input.consecutive_failures >= max_consecutive_failures:
            return RiskResult(True, f"连续下单失败达到阈值({risk_input.consecutive_failures})")
        if risk_input.drawdown_pct >= drawdown_kill_pct:
            return RiskResult(True, f"回撤触发熔断({risk_input.drawdown_pct:.2f}%)")
        if abs(risk_input.sigma_zscore) >= volatility_kill_zscore:
            return RiskResult(True, f"异常波动触发熔断(z={risk_input.sigma_zscore:.2f})")
        return RiskResult(False, None)
