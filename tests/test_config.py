from __future__ import annotations

from ashare_research.config import parse_config


def test_parse_config_builds_typed_models() -> None:
    config = parse_config(
        {
            "data": {
                "daily_bar_path": "data/raw/daily_bars.csv",
                "price_adjustment": "forward",
            },
            "backtest": {
                "max_names": 10,
                "position_sizing_method": "signal_weight",
                "rebalance_frequency": "weekly",
                "min_holding_days": 3,
                "slippage_rate": 0.0002,
                "max_volume_participation": 0.15,
            },
            "strategy": {
                "name": "moving_average_crossover",
                "fast_window": 5,
                "slow_window": 20,
            },
            "report": {
                "output_dir": "reports/test_run",
            },
            "technical_analysis": {
                "symbols": ["300059.SZ", "603986.SH"],
                "buy_score_threshold": 7,
                "hold_score_threshold": 4,
            },
        }
    )

    assert config.data.daily_bar_path == "data/raw/daily_bars.csv"
    assert config.data.price_adjustment == "forward"
    assert config.backtest.max_names == 10
    assert config.backtest.position_sizing_method == "signal_weight"
    assert config.backtest.rebalance_frequency == "weekly"
    assert config.backtest.slippage_rate == 0.0002
    assert config.backtest.max_volume_participation == 0.15
    assert config.strategy.name == "moving_average_crossover"
    assert config.strategy.parameters["fast_window"] == 5
    assert config.strategy.parameters["slow_window"] == 20
    assert config.report.output_dir == "reports/test_run"
    assert config.technical_analysis.symbols == ("300059.SZ", "603986.SH")
    assert config.technical_analysis.buy_score_threshold == 7
    assert config.technical_analysis.hold_score_threshold == 4


def test_parse_config_supports_generic_strategy_parameters() -> None:
    config = parse_config(
        {
            "data": {
                "daily_bar_path": "data/raw/daily_bars.csv",
            },
            "backtest": {},
            "strategy": {
                "name": "relative_strength",
                "lookback_window": 30,
                "min_positive_return": 0.02,
            },
        }
    )

    assert config.strategy.name == "relative_strength"
    assert config.strategy.parameters == {
        "lookback_window": 30,
        "min_positive_return": 0.02,
    }
