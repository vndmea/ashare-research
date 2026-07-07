from __future__ import annotations

from dataclasses import dataclass, field
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
    slippage_rate: float = 0.0
    max_volume_participation: float = 0.0


@dataclass(frozen=True)
class StrategyConfig:
    name: str = "moving_average_crossover"
    parameters: dict[str, Any] = field(default_factory=dict)

    @property
    def fast_window(self) -> int:
        return int(self.parameters.get("fast_window", 20))

    @property
    def slow_window(self) -> int:
        return int(self.parameters.get("slow_window", 60))

    def resolved_parameters(self, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
        merged = dict(defaults or {})
        merged.update(self.parameters)
        return merged


@dataclass(frozen=True)
class ReportConfig:
    output_dir: str = "reports/example_run"


@dataclass(frozen=True)
class TechnicalAnalysisConfig:
    symbols: tuple[str, ...] = ()
    short_window: int = 20
    medium_window: int = 60
    long_window: int = 120
    trend_window: int = 250
    volume_window: int = 20
    baseline_volume_window: int = 120
    peak_lookback_window: int = 20
    buy_score_threshold: int = 6
    hold_score_threshold: int = 3
    peak_drawdown_threshold: float = 0.15


@dataclass(frozen=True)
class ResearchConfig:
    data: DataConfig
    backtest: BacktestConfig
    strategy: StrategyConfig
    report: ReportConfig
    technical_analysis: TechnicalAnalysisConfig


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
    technical_analysis_section = _mapping(
        data.get("technical_analysis"),
        section="technical_analysis",
        allow_empty=True,
    )

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
            slippage_rate=float(backtest_section.get("slippage_rate", 0.0)),
            max_volume_participation=float(
                backtest_section.get("max_volume_participation", 0.0)
            ),
        ),
        strategy=StrategyConfig(
            name=str(strategy_section.get("name", "moving_average_crossover")),
            parameters={
                key: value
                for key, value in strategy_section.items()
                if key != "name"
            },
        ),
        report=ReportConfig(
            output_dir=str(report_section.get("output_dir", "reports/example_run")),
        ),
        technical_analysis=TechnicalAnalysisConfig(
            symbols=tuple(_string_list(technical_analysis_section.get("symbols", ()))),
            short_window=int(technical_analysis_section.get("short_window", 20)),
            medium_window=int(technical_analysis_section.get("medium_window", 60)),
            long_window=int(technical_analysis_section.get("long_window", 120)),
            trend_window=int(technical_analysis_section.get("trend_window", 250)),
            volume_window=int(technical_analysis_section.get("volume_window", 20)),
            baseline_volume_window=int(
                technical_analysis_section.get("baseline_volume_window", 120)
            ),
            peak_lookback_window=int(
                technical_analysis_section.get("peak_lookback_window", 20)
            ),
            buy_score_threshold=int(
                technical_analysis_section.get("buy_score_threshold", 6)
            ),
            hold_score_threshold=int(
                technical_analysis_section.get("hold_score_threshold", 3)
            ),
            peak_drawdown_threshold=float(
                technical_analysis_section.get("peak_drawdown_threshold", 0.15)
            ),
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


def _string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if not isinstance(value, list | tuple):
        raise ValueError("Config field must be a list of strings")
    return [str(item) for item in value if str(item).strip()]
