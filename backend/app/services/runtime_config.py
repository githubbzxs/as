from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.schemas import GoalConfig, RuntimeConfig
from app.services.goal_mapper import goal_to_runtime_config, runtime_to_goal_config


class RuntimeConfigDocument(BaseModel):
    runtime_config: RuntimeConfig
    goal_config: GoalConfig


class RuntimeConfigStore:
    """运行参数持久化。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._config, self._goal = self._load_or_default()

    def _build_default(self) -> tuple[RuntimeConfig, GoalConfig]:
        goal = GoalConfig()
        runtime = goal_to_runtime_config(goal, RuntimeConfig())
        return runtime, goal

    def _load_or_default(self) -> tuple[RuntimeConfig, GoalConfig]:
        if not self._path.exists():
            runtime, goal = self._build_default()
            self._save(runtime, goal)
            return runtime, goal
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "runtime_config" in raw:
                doc = RuntimeConfigDocument.model_validate(raw)
                return doc.runtime_config, doc.goal_config

            runtime = RuntimeConfig.model_validate(raw)
            goal = runtime_to_goal_config(runtime)
            self._save(runtime, goal)
            return runtime, goal
        except (json.JSONDecodeError, ValidationError, OSError):
            runtime, goal = self._build_default()
            self._save(runtime, goal)
            return runtime, goal

    def _save(self, config: RuntimeConfig, goal: GoalConfig) -> None:
        payload = RuntimeConfigDocument(runtime_config=config, goal_config=goal).model_dump(mode="json")
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get(self) -> RuntimeConfig:
        return self._config

    def get_goal(self) -> GoalConfig:
        return self._goal

    def set_goal(self, goal: GoalConfig) -> GoalConfig:
        self._goal = GoalConfig.model_validate(goal)
        self._save(self._config, self._goal)
        return self._goal

    def update(self, data: dict) -> RuntimeConfig:
        merged = self._config.model_dump()
        merged.update(data)
        cfg = RuntimeConfig.model_validate(merged)
        self._config = cfg
        self._save(cfg, self._goal)
        return cfg
