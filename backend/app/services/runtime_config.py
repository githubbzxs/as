from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.schemas import GoalConfig, RuntimeConfig, StrategyConfig
from app.services.goal_mapper import goal_to_runtime_config, runtime_to_goal_config
from app.services.strategy_mapper import runtime_to_strategy_config, strategy_to_runtime_config


class RuntimeConfigDocument(BaseModel):
    runtime_config: RuntimeConfig
    strategy_config: StrategyConfig
    goal_config: GoalConfig | None = None


class RuntimeConfigStore:
    """运行参数持久化。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._config, self._strategy = self._load_or_default()

    def _build_default(self) -> tuple[RuntimeConfig, StrategyConfig]:
        strategy = StrategyConfig()
        runtime = strategy_to_runtime_config(strategy, RuntimeConfig())
        return runtime, strategy

    def _load_or_default(self) -> tuple[RuntimeConfig, StrategyConfig]:
        if not self._path.exists():
            runtime, strategy = self._build_default()
            self._save(runtime, strategy)
            return runtime, strategy
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "runtime_config" in raw:
                runtime = RuntimeConfig.model_validate(raw["runtime_config"])
                strategy_raw = raw.get("strategy_config")
                if strategy_raw is None:
                    strategy = runtime_to_strategy_config(runtime)
                    self._save(runtime, strategy)
                    return runtime, strategy
                strategy = StrategyConfig.model_validate(strategy_raw)
                return runtime, strategy

            runtime = RuntimeConfig.model_validate(raw)
            strategy = runtime_to_strategy_config(runtime)
            self._save(runtime, strategy)
            return runtime, strategy
        except (json.JSONDecodeError, ValidationError, OSError):
            runtime, strategy = self._build_default()
            self._save(runtime, strategy)
            return runtime, strategy

    def _save(self, config: RuntimeConfig, strategy: StrategyConfig) -> None:
        payload = RuntimeConfigDocument(runtime_config=config, strategy_config=strategy).model_dump(mode="json")
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get(self) -> RuntimeConfig:
        return self._config

    def get_strategy(self) -> StrategyConfig:
        return self._strategy

    def set_strategy(self, strategy: StrategyConfig) -> StrategyConfig:
        self._strategy = StrategyConfig.model_validate(strategy)
        self._config = strategy_to_runtime_config(self._strategy, self._config)
        self._save(self._config, self._strategy)
        return self._strategy

    def get_goal(self) -> GoalConfig:
        return runtime_to_goal_config(self._config)

    def set_goal(self, goal: GoalConfig) -> GoalConfig:
        normalized = GoalConfig.model_validate(goal)
        self._config = goal_to_runtime_config(normalized, self._config)
        self._strategy = runtime_to_strategy_config(self._config)
        self._save(self._config, self._strategy)
        return normalized

    def update(self, data: dict) -> RuntimeConfig:
        merged = self._config.model_dump()
        merged.update(data)
        cfg = RuntimeConfig.model_validate(merged)
        self._config = cfg
        self._strategy = runtime_to_strategy_config(cfg)
        self._save(cfg, self._strategy)
        return cfg
