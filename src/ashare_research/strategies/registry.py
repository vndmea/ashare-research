from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd

StrategyRunner = Callable[[pd.DataFrame, dict[str, Any]], pd.DataFrame]


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, StrategyRunner] = {}

    def register(self, name: str, runner: StrategyRunner) -> None:
        self._strategies[name] = runner

    def get(self, name: str) -> StrategyRunner:
        if name not in self._strategies:
            raise ValueError(f"Unsupported strategy: {name}")
        return self._strategies[name]


registry = StrategyRegistry()
