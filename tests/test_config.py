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
            },
            "strategy": {
                "name": "moving_average_crossover",
                "fast_window": 5,
                "slow_window": 20,
            },
            "report": {
                "output_dir": "reports/test_run",
            },
        }
    )

    assert config.data.daily_bar_path == "data/raw/daily_bars.csv"
    assert config.data.price_adjustment == "forward"
    assert config.backtest.max_names == 10
    assert config.backtest.position_sizing_method == "signal_weight"
    assert config.backtest.rebalance_frequency == "weekly"
    assert config.strategy.name == "moving_average_crossover"
    assert config.report.output_dir == "reports/test_run"
