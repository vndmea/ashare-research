from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TradeConstraints:
    exclude_suspended: bool = True
    exclude_st: bool = True
    block_limit_up_buys: bool = True
    block_limit_down_sells: bool = True
    min_amount: float = 0.0
    max_volume_participation: float = 0.0


@dataclass(frozen=True)
class ExecutionResult:
    positions: pd.DataFrame
    execution_diagnostics: pd.DataFrame


def filter_signals_for_universe(
    signals: pd.DataFrame,
    universe: pd.DataFrame | None,
) -> pd.DataFrame:
    """Keep only signals that are in the date-aware research universe."""
    if universe is None or universe.empty:
        return signals
    return signals.merge(universe[["date", "symbol"]].drop_duplicates(), on=["date", "symbol"])


def filter_signals_for_eligibility(
    signals: pd.DataFrame,
    bars: pd.DataFrame,
    constraints: TradeConstraints,
) -> pd.DataFrame:
    """Remove names that should not be selected as target holdings."""
    eligibility = bars[["date", "symbol"]].drop_duplicates().copy()
    eligibility["eligible"] = True

    if constraints.exclude_suspended and "is_suspended" in bars.columns:
        eligibility = eligibility.merge(
            bars[["date", "symbol", "is_suspended"]],
            on=["date", "symbol"],
            how="left",
        )
        eligibility["eligible"] &= ~eligibility["is_suspended"].fillna(False)
        eligibility = eligibility.drop(columns=["is_suspended"])

    if "tradable" in bars.columns:
        eligibility = eligibility.merge(
            bars[["date", "symbol", "tradable"]],
            on=["date", "symbol"],
            how="left",
        )
        eligibility["eligible"] &= eligibility["tradable"].fillna(False)
        eligibility = eligibility.drop(columns=["tradable"])

    if constraints.exclude_st and "st_status" in bars.columns:
        eligibility = eligibility.merge(
            bars[["date", "symbol", "st_status"]],
            on=["date", "symbol"],
            how="left",
        )
        eligibility["eligible"] &= ~eligibility["st_status"].map(_is_st_status)
        eligibility = eligibility.drop(columns=["st_status"])

    if constraints.min_amount > 0.0 and "amount" in bars.columns:
        eligibility = eligibility.merge(
            bars[["date", "symbol", "amount"]],
            on=["date", "symbol"],
            how="left",
        )
        eligibility["eligible"] &= eligibility["amount"].fillna(0.0) >= constraints.min_amount
        eligibility = eligibility.drop(columns=["amount"])

    eligible_pairs = eligibility.loc[eligibility["eligible"], ["date", "symbol"]]
    return signals.merge(eligible_pairs, on=["date", "symbol"])


def apply_trade_constraints(
    target_weights: pd.DataFrame,
    bars: pd.DataFrame,
    trading_dates: pd.DatetimeIndex,
    constraints: TradeConstraints,
    *,
    reference_cash: float,
) -> ExecutionResult:
    """Apply suspension, price-limit, and participation constraints to target weights."""
    if target_weights.empty:
        return ExecutionResult(
            positions=pd.DataFrame(columns=["date", "symbol", "weight"]),
            execution_diagnostics=_empty_execution_diagnostics(),
        )

    dates = pd.DatetimeIndex(pd.to_datetime(trading_dates).drop_duplicates().sort_values())
    if dates.empty:
        return ExecutionResult(
            positions=pd.DataFrame(columns=["date", "symbol", "weight"]),
            execution_diagnostics=_empty_execution_diagnostics(),
        )

    weights = target_weights.copy()
    weights["date"] = pd.to_datetime(weights["date"])
    symbols = sorted(weights["symbol"].drop_duplicates())
    targets = (
        weights.pivot(index="date", columns="symbol", values="weight")
        .reindex(index=dates, columns=symbols)
        .fillna(0.0)
    )

    available = _availability_matrix(bars, dates, symbols)
    tradable = available.copy()
    if constraints.exclude_suspended and "is_suspended" in bars.columns:
        tradable &= ~_flag_matrix(bars, "is_suspended", dates, symbols, default=False)
    if "tradable" in bars.columns:
        tradable &= _flag_matrix(bars, "tradable", dates, symbols, default=False)

    limit_up = _flag_matrix(bars, "limit_up", dates, symbols, default=False)
    limit_down = _flag_matrix(bars, "limit_down", dates, symbols, default=False)
    liquidity = _liquidity_matrix(bars, dates, symbols)

    rows: list[pd.DataFrame] = []
    diagnostics_rows: list[pd.DataFrame] = []
    previous = pd.Series(0.0, index=targets.columns, dtype=float)
    for date in targets.index:
        desired = targets.loc[date].astype(float)
        current = desired.copy()
        reasons = pd.Series("", index=current.index, dtype="string")

        unavailable_mask = ~available.loc[date]
        blocked = unavailable_mask.copy()
        reasons.loc[unavailable_mask] = _append_reason(reasons.loc[unavailable_mask], "missing_bar")

        untradable_mask = ~tradable.loc[date]
        blocked |= untradable_mask
        reasons.loc[untradable_mask] = _append_reason(
            reasons.loc[untradable_mask],
            "not_tradable",
        )

        if constraints.block_limit_up_buys:
            limit_up_block = limit_up.loc[date] & (desired > previous)
            blocked |= limit_up_block
            reasons.loc[limit_up_block] = _append_reason(
                reasons.loc[limit_up_block],
                "limit_up_buy_blocked",
            )
        if constraints.block_limit_down_sells:
            limit_down_block = limit_down.loc[date] & (desired < previous)
            blocked |= limit_down_block
            reasons.loc[limit_down_block] = _append_reason(
                reasons.loc[limit_down_block],
                "limit_down_sell_blocked",
            )

        current.loc[blocked] = previous.loc[blocked]

        max_trade_weight = pd.Series(float("inf"), index=current.index, dtype=float)
        if constraints.max_volume_participation > 0.0 and reference_cash > 0.0:
            max_trade_weight = (
                liquidity.loc[date].astype(float) * constraints.max_volume_participation / reference_cash
            )
            max_trade_weight = max_trade_weight.fillna(0.0).clip(lower=0.0)
            desired_trade = current - previous
            limited_trade = desired_trade.clip(lower=-max_trade_weight, upper=max_trade_weight)
            capacity_limited = limited_trade.ne(desired_trade)
            reasons.loc[capacity_limited] = _append_reason(
                reasons.loc[capacity_limited],
                "capacity_limited",
            )
            current = previous + limited_trade

        current = current.clip(lower=0.0)

        locked_weight = float(current.loc[blocked].sum())
        free = ~blocked
        free_weight = float(current.loc[free].sum())
        capacity = max(0.0, 1.0 - locked_weight)
        if free_weight > capacity and free_weight > 0.0:
            before_scale = current.copy()
            current.loc[free] *= capacity / free_weight
            scaled = free & current.ne(before_scale)
            reasons.loc[scaled] = _append_reason(
                reasons.loc[scaled],
                "gross_exposure_scaled",
            )

        positive = current[current > 0.0]
        if not positive.empty:
            rows.append(
                pd.DataFrame(
                    {
                        "date": date,
                        "symbol": positive.index,
                        "weight": positive.to_numpy(),
                    }
                )
            )

        diagnostics_rows.append(
            pd.DataFrame(
                {
                    "date": date,
                    "symbol": current.index,
                    "previous_weight": previous.to_numpy(),
                    "target_weight": desired.to_numpy(),
                    "executed_weight": current.to_numpy(),
                    "desired_trade_weight": (desired - previous).to_numpy(),
                    "executed_trade_weight": (current - previous).to_numpy(),
                    "available": available.loc[date].to_numpy(),
                    "tradable": tradable.loc[date].to_numpy(),
                    "limit_up": limit_up.loc[date].to_numpy(),
                    "limit_down": limit_down.loc[date].to_numpy(),
                    "liquidity_amount": liquidity.loc[date].to_numpy(),
                    "max_trade_weight": max_trade_weight.to_numpy(),
                    "blocked_reason": reasons.fillna("").to_numpy(),
                }
            )
        )
        previous = current

    positions = (
        pd.concat(rows, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)
        if rows
        else pd.DataFrame(columns=["date", "symbol", "weight"])
    )
    diagnostics = (
        pd.concat(diagnostics_rows, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)
        if diagnostics_rows
        else _empty_execution_diagnostics()
    )
    diagnostics["is_blocked"] = diagnostics["blocked_reason"].fillna("").ne("")
    return ExecutionResult(positions=positions, execution_diagnostics=diagnostics)


def _availability_matrix(
    bars: pd.DataFrame,
    dates: pd.DatetimeIndex,
    symbols: list[str],
) -> pd.DataFrame:
    state = bars[["date", "symbol"]].drop_duplicates().copy()
    state["available"] = True
    return (
        state.pivot(index="date", columns="symbol", values="available")
        .reindex(index=dates, columns=symbols)
        .fillna(False)
        .astype(bool)
    )


def _flag_matrix(
    bars: pd.DataFrame,
    column: str,
    dates: pd.DatetimeIndex,
    symbols: list[str],
    *,
    default: bool,
) -> pd.DataFrame:
    if column not in bars.columns:
        return pd.DataFrame(default, index=dates, columns=symbols)
    return (
        bars.pivot(index="date", columns="symbol", values=column)
        .reindex(index=dates, columns=symbols)
        .fillna(default)
        .astype(bool)
    )


def _liquidity_matrix(
    bars: pd.DataFrame,
    dates: pd.DatetimeIndex,
    symbols: list[str],
) -> pd.DataFrame:
    frame = bars[["date", "symbol"]].copy()
    if "amount" in bars.columns:
        frame["liquidity_amount"] = pd.to_numeric(bars["amount"], errors="coerce").fillna(0.0)
    else:
        volume = pd.to_numeric(bars.get("volume"), errors="coerce").fillna(0.0)
        close = pd.to_numeric(bars.get("close"), errors="coerce").fillna(0.0)
        frame["liquidity_amount"] = volume * close
    return (
        frame.pivot(index="date", columns="symbol", values="liquidity_amount")
        .reindex(index=dates, columns=symbols)
        .fillna(0.0)
    )


def _append_reason(series: pd.Series, reason: str) -> pd.Series:
    return series.fillna("").apply(lambda value: reason if value == "" else f"{value}|{reason}")


def _empty_execution_diagnostics() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "date",
            "symbol",
            "previous_weight",
            "target_weight",
            "executed_weight",
            "desired_trade_weight",
            "executed_trade_weight",
            "available",
            "tradable",
            "limit_up",
            "limit_down",
            "liquidity_amount",
            "max_trade_weight",
            "blocked_reason",
            "is_blocked",
        ]
    )


def _is_st_status(value: object) -> bool:
    if pd.isna(value):
        return False
    text = str(value).strip().lower()
    return text not in {"", "0", "false", "none", "normal", "nan"}
