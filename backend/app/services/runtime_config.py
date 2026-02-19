from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas import RuntimeConfig


class RuntimeConfigStore:
    """运行参数持久化。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._config = self._load_or_default()

    def _load_or_default(self) -> RuntimeConfig:
        if not self._path.exists():
            config = RuntimeConfig()
            self._save(config)
            return config
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return RuntimeConfig.model_validate(raw)
        except (json.JSONDecodeError, ValidationError, OSError):
            config = RuntimeConfig()
            self._save(config)
            return config

    def _save(self, config: RuntimeConfig) -> None:
        self._path.write_text(
            config.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def get(self) -> RuntimeConfig:
        return self._config

    def update(self, data: dict) -> RuntimeConfig:
        merged = self._config.model_dump()
        merged.update(data)
        cfg = RuntimeConfig.model_validate(merged)
        self._config = cfg
        self._save(cfg)
        return cfg
