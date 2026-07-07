from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DataConfig:
    daily_bar_path: str
    benchmark_path: str | None = None
    trading_calendar_path: str | None = None
    universe_path: str | None = None
    adjustment_factor_path: str | None = None
    price_adjustment: str = "none"


@dataclass(frozen=True)
class BacktestConfig:
    start_date: str | None = None
    end_date: str | None = None
    initial_cash: float = 1_000_000.0
    commission_rate: float = 0.0003
    stamp_tax_rate: float = 0.0005
    max_names: int = 20
    position_sizing_method: str = "equal_weight"
    rebalance_frequency: str = "daily"
    min_holding_days: int = 0
    exclude_suspended: bool = True
    exclude_st: bool = True
    block_limit_up_buys: bool = True
    block_limit_down_sells: bool = True
    min_amount: float = 0.0


@dataclass(frozen=True)
class StrategyConfig:
    name: str = "moving_average_crossover"
    fast_window: int = 20
    slow_window: int = 60


@dataclass(frozen=True)
class ReportConfig:
    output_dir: str = "reports/example_run"


@dataclass(frozen=True)
class ResearchConfig:
    data: DataConfig
    backtest: BacktestConfig
    strategy: StrategyConfig
    report: ReportConfig


def load_config(path: str | Path) -> ResearchConfig:
    """Load a YAML config file into typed config models."""
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {config_path}")
    return parse_config(data)


def parse_config(data: dict[str, Any]) -> ResearchConfig:
    data_section = _mapping(data.get("data"), section="data")
    backtest_section = _mapping(data.get("backtest"), section="backtest")
    strategy_section = _mapping(data.get("strategy"), section="strategy")
    report_section = _mapping(data.get("report"), section="report", allow_empty=True)

    daily_bar_path = data_section.get("daily_bar_path")
    if not daily_bar_path:
        raise ValueError("Config data.daily_bar_path is required")

    return ResearchConfig(
        data=DataConfig(
            daily_bar_path=str(daily_bar_path),
            benchmark_path=_optional_str(data_section.get("benchmark_path")),
            trading_calendar_path=_optional_str(data_section.get("trading_calendar_path")),
            universe_path=_optional_str(data_section.get("universe_path")),
            adjustment_factor_path=_optional_str(data_section.get("adjustment_factor_path")),
            price_adjustment=str(data_section.get("price_adjustment", "none")),
        ),
        backtest=BacktestConfig(
            start_date=_optional_str(backtest_section.get("start_date")),
            end_date=_optional_str(backtest_section.get("end_date")),
            initial_cash=float(backtest_section.get("initial_cash", 1_000_000.0)),
            commission_rate=float(backtest_section.get("commission_rate", 0.0003)),
            stamp_tax_rate=float(backtest_section.get("stamp_tax_rate", 0.0005)),
            max_names=int(backtest_section.get("max_names", 20)),
            position_sizing_method=str(
                backtest_section.get("position_sizing_method", "equal_weight")
            ),
            rebalance_frequency=str(backtest_section.get("rebalance_frequency", "daily")),
            min_holding_days=int(backtest_section.get("min_holding_days", 0)),
            exclude_suspended=bool(backtest_section.get("exclude_suspended", True)),
            exclude_st=bool(backtest_section.get("exclude_st", True)),
            block_limit_up_buys=bool(backtest_section.get("block_limit_up_buys", True)),
            block_limit_down_sells=bool(backtest_section.get("block_limit_down_sells", True)),
            min_amount=float(backtest_section.get("min_amount", 0.0)),
        ),
        strategy=StrategyConfig(
            name=str(strategy_section.get("name", "moving_average_crossover")),
            fast_window=int(strategy_section.get("fast_window", 20)),
            slow_window=int(strategy_section.get("slow_window", 60)),
        ),
        report=ReportConfig(
            output_dir=str(report_section.get("output_dir", "reports/example_run")),
        ),
    )


def _mapping(
    value: Any,
    *,
    section: str,
    allow_empty: bool = False,
) -> dict[str, Any]:
    if value is None and allow_empty:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Config section must be a mapping: {section}")
    return value


def _optional_str(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    return str(value)
