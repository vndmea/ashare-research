from __future__ import annotations

import pandas as pd

from ashare_research.backtest.engine import run_close_to_close_backtest
from ashare_research.risk.tradeability import TradeConstraints


def test_backtest_excludes_universe_membership() -> None:
    dates = pd.bdate_range("2024-01-01", periods=4)
    bars = _bars(dates, ["000001.SZ", "600000.SH"])
    signals = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "symbol": ["000001.SZ"] * len(dates) + ["600000.SH"] * len(dates),
            "signal": [1.0] * len(dates) * 2,
        }
    )
    universe = pd.DataFrame({"date": dates, "symbol": ["000001.SZ"] * len(dates)})

    result = run_close_to_close_backtest(bars, signals, max_names=2, universe=universe)

    assert set(result.positions["symbol"]) == {"000001.SZ"}


def test_backtest_excludes_suspended_rows() -> None:
    dates = pd.bdate_range("2024-01-01", periods=4)
    bars = _bars(dates, ["000001.SZ", "600000.SH"])
    bars.loc[bars["symbol"] == "000001.SZ", "is_suspended"] = True
    signals = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "symbol": ["000001.SZ"] * len(dates) + ["600000.SH"] * len(dates),
            "signal": [1.0] * len(dates) * 2,
        }
    )

    result = run_close_to_close_backtest(bars, signals, max_names=2)

    assert set(result.positions["symbol"]) == {"600000.SH"}


def test_limit_down_blocks_sell_and_keeps_position() -> None:
    dates = pd.bdate_range("2024-01-01", periods=4)
    bars = _bars(dates, ["000001.SZ"])
    bars.loc[bars["date"] == dates[1], "limit_down"] = True
    signals = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["000001.SZ"] * len(dates),
            "signal": [1.0, 0.0, 0.0, 0.0],
        }
    )

    result = run_close_to_close_backtest(
        bars,
        signals,
        trade_constraints=TradeConstraints(block_limit_down_sells=True),
    )

    day_two = result.positions[result.positions["date"] == dates[1]]
    assert day_two["weight"].sum() == 1.0


def test_limit_up_blocks_new_buy_and_keeps_cash() -> None:
    dates = pd.bdate_range("2024-01-01", periods=4)
    bars = _bars(dates, ["000001.SZ"])
    bars.loc[bars["date"] == dates[0], "limit_up"] = True
    signals = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["000001.SZ"] * len(dates),
            "signal": [1.0, 1.0, 1.0, 1.0],
        }
    )

    result = run_close_to_close_backtest(
        bars,
        signals,
        trade_constraints=TradeConstraints(block_limit_up_buys=True),
    )

    first_day = result.equity_curve[result.equity_curve["date"] == dates[0]].iloc[0]
    assert first_day["gross_exposure"] == 0.0
    assert first_day["cash_weight"] == 1.0


def test_weekly_rebalance_holds_positions_between_rebalance_days() -> None:
    dates = pd.bdate_range("2024-01-01", periods=8)
    bars = _bars(dates, ["000001.SZ", "600000.SH"])
    signals = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "symbol": ["000001.SZ"] * len(dates) + ["600000.SH"] * len(dates),
            "signal": [
                1.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            ]
            + [0.0] * len(dates),
        }
    )

    result = run_close_to_close_backtest(
        bars,
        signals,
        max_names=1,
        rebalance_frequency="weekly",
    )

    first_week = result.positions[result.positions["date"].isin(dates[:5])]
    assert set(first_week["date"]) == set(dates[:5])
    assert set(first_week["symbol"]) == {"000001.SZ"}


def test_monthly_rebalance_delays_signal_change_until_next_month() -> None:
    dates = pd.bdate_range("2024-01-29", periods=8)
    bars = _bars(dates, ["000001.SZ", "600000.SH"])
    signals = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "symbol": ["000001.SZ"] * len(dates) + ["600000.SH"] * len(dates),
            "signal": [1.0] * 3 + [0.0] * 5 + [0.0] * 3 + [1.0] * 5,
        }
    )

    result = run_close_to_close_backtest(
        bars,
        signals,
        max_names=1,
        rebalance_frequency="monthly",
    )

    january_positions = result.positions[result.positions["date"].isin(dates[:3])]
    february_positions = result.positions[result.positions["date"].isin(dates[3:])]

    assert set(january_positions["symbol"]) == {"000001.SZ"}
    assert set(february_positions["symbol"]) == {"600000.SH"}


def test_min_holding_days_prevents_early_exit() -> None:
    dates = pd.bdate_range("2024-01-01", periods=5)
    bars = _bars(dates, ["000001.SZ"])
    signals = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["000001.SZ"] * len(dates),
            "signal": [1.0, 0.0, 0.0, 0.0, 0.0],
        }
    )

    result = run_close_to_close_backtest(
        bars,
        signals,
        min_holding_days=3,
    )

    held_dates = result.positions["date"].tolist()
    assert held_dates[:3] == list(dates[:3])
    assert dates[3] in held_dates
    assert dates[4] not in held_dates


def _bars(dates: pd.DatetimeIndex, symbols: list[str]) -> pd.DataFrame:
    rows = []
    for symbol_index, symbol in enumerate(symbols):
        for index, date in enumerate(dates):
            close = 10.0 + symbol_index + index * 0.1
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "open": close,
                    "high": close + 0.1,
                    "low": close - 0.1,
                    "close": close,
                    "volume": 1_000_000,
                    "amount": close * 1_000_000,
                    "is_suspended": False,
                    "limit_up": False,
                    "limit_down": False,
                    "tradable": True,
                    "st_status": "",
                }
            )
    return pd.DataFrame(rows)
