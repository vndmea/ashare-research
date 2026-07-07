from __future__ import annotations

import pandas as pd


def daily_symbol_returns(bars: pd.DataFrame) -> pd.DataFrame:
    data = bars.sort_values(["symbol", "date"]).copy()
    data["next_close"] = data.groupby("symbol", sort=False)["close"].shift(-1)
    data["return"] = data["next_close"].div(data["close"]).sub(1.0)
    return data[["date", "symbol", "return"]].dropna(subset=["return"])


def build_portfolio_equity_curve(
    positions: pd.DataFrame,
    returns: pd.DataFrame,
    trading_dates: pd.DatetimeIndex,
    initial_cash: float,
    commission_rate: float,
    stamp_tax_rate: float,
) -> pd.DataFrame:
    portfolio = positions.merge(returns, on=["date", "symbol"], how="left").fillna({"return": 0.0})
    portfolio["weighted_return"] = portfolio["weight"] * portfolio["return"]
    portfolio_returns = portfolio.groupby("date", as_index=False).agg(
        gross_return=("weighted_return", "sum")
    )

    turnover = daily_turnover(positions)
    exposure = daily_exposure(positions)
    rebalance_flags = daily_rebalance_flags(positions)
    trading_date_frame = pd.DataFrame({"date": trading_dates})
    equity_curve = (
        trading_date_frame.merge(portfolio_returns, on="date", how="left")
        .merge(turnover, on="date", how="left")
        .merge(exposure, on="date", how="left")
        .merge(rebalance_flags, on="date", how="left")
        .fillna(0.0)
    )
    equity_curve = equity_curve.sort_values("date").reset_index(drop=True)
    equity_curve["cash_weight"] = (1.0 - equity_curve["gross_exposure"]).clip(lower=0.0)
    equity_curve["cost"] = equity_curve["turnover"] * commission_rate
    equity_curve["tax"] = equity_curve["sell_turnover"] * stamp_tax_rate
    equity_curve["net_return"] = (
        equity_curve["gross_return"] - equity_curve["cost"] - equity_curve["tax"]
    )
    equity_curve["equity"] = initial_cash * (1.0 + equity_curve["net_return"]).cumprod()
    return equity_curve


def daily_turnover(weights: pd.DataFrame) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame(columns=["date", "turnover", "sell_turnover"])

    wide = weights.pivot(index="date", columns="symbol", values="weight").fillna(0.0).sort_index()
    previous = wide.shift(1).fillna(0.0)
    changes = wide - previous
    turnover = changes.abs().sum(axis=1)
    sell_turnover = changes.clip(upper=0.0).abs().sum(axis=1)
    return pd.DataFrame(
        {
            "date": wide.index,
            "turnover": turnover.to_numpy(),
            "sell_turnover": sell_turnover.to_numpy(),
        }
    )


def daily_exposure(weights: pd.DataFrame) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame(columns=["date", "gross_exposure"])
    return weights.groupby("date", as_index=False).agg(gross_exposure=("weight", "sum"))


def daily_rebalance_flags(weights: pd.DataFrame) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame(columns=["date", "is_rebalance_day"])

    wide = weights.pivot(index="date", columns="symbol", values="weight").fillna(0.0).sort_index()
    changed = wide.ne(wide.shift(1).fillna(0.0)).any(axis=1)
    return pd.DataFrame(
        {
            "date": wide.index,
            "is_rebalance_day": changed.astype(float).to_numpy(),
        }
    )
