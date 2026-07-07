from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

StrategyRunner = Callable[[pd.DataFrame, dict[str, Any]], pd.DataFrame]


@dataclass(frozen=True)
class StrategyDefinition:
    name: str
    runner: StrategyRunner
    description: str
    parameter_defaults: dict[str, Any] = field(default_factory=dict)
    output_columns: tuple[str, ...] = ("date", "symbol", "signal", "signal_strength")


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, StrategyDefinition] = {}

    def register(
        self,
        name: str,
        runner: StrategyRunner,
        *,
        description: str = "",
        parameter_defaults: dict[str, Any] | None = None,
        output_columns: tuple[str, ...] = ("date", "symbol", "signal", "signal_strength"),
    ) -> None:
        self._strategies[name] = StrategyDefinition(
            name=name,
            runner=runner,
            description=description,
            parameter_defaults=dict(parameter_defaults or {}),
            output_columns=output_columns,
        )

    def get(self, name: str) -> StrategyRunner:
        return self.get_definition(name).runner

    def get_definition(self, name: str) -> StrategyDefinition:
        if name not in self._strategies:
            raise ValueError(f"Unsupported strategy: {name}")
        return self._strategies[name]

    def list_definitions(self) -> list[StrategyDefinition]:
        return [self._strategies[name] for name in sorted(self._strategies)]


registry = StrategyRegistry()
