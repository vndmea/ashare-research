from __future__ import annotations

import math

import pandas as pd

from ashare_research.config import TechnicalAnalysisConfig


def build_symbol_technical_analysis_report(
    bars: pd.DataFrame,
    technical_config: TechnicalAnalysisConfig,
    benchmark_returns: pd.DataFrame | None = None,
) -> pd.DataFrame:
    columns = [
        "date",
        "symbol",
        "latest_close",
        "return_20d",
        "return_60d",
        "return_120d",
        "return_250d",
        "max_drawdown",
        "close_vs_ma20",
        "close_vs_ma60",
        "close_vs_ma120",
        "close_vs_ma250",
        "vol20_vs_120",
        "amt20_vs_120",
        "relative_strength_250d",
        "latest_from_peak_20d",
        "trend_score",
        "volume_score",
        "relative_strength_score",
        "risk_penalty",
        "total_score",
        "decision",
        "decision_reason",
    ]
    if bars.empty:
        return pd.DataFrame(columns=columns)
    if not technical_config.symbols:
        raise ValueError("technical_analysis.symbols is empty.")

    benchmark_index = _build_benchmark_index(benchmark_returns)
    normalized_bars = bars.copy()
    normalized_bars["date"] = pd.to_datetime(normalized_bars["date"], errors="raise")
    normalized_bars["symbol"] = normalized_bars["symbol"].map(normalize_project_symbol)

    requested_symbols = tuple(normalize_project_symbol(symbol) for symbol in technical_config.symbols)
    available_symbols = set(normalized_bars["symbol"].unique())
    missing_symbols = sorted(set(requested_symbols).difference(available_symbols))
    if missing_symbols:
        raise ValueError(f"technical_analysis symbols not present in bars: {missing_symbols}")

    report_rows = [
        _build_symbol_snapshot(
            normalized_bars.loc[normalized_bars["symbol"] == symbol].copy(),
            technical_config,
            benchmark_index,
        )
        for symbol in requested_symbols
    ]
    report = pd.DataFrame(report_rows)
    return report[columns].sort_values(
        ["total_score", "date", "symbol"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def normalize_project_symbol(symbol: str) -> str:
    text = str(symbol).strip()
    if "." not in text:
        raise ValueError(f"Unexpected symbol format: {symbol}")
    left, right = text.split(".", maxsplit=1)
    if left.isdigit() and right.upper() in {"SH", "SZ", "BJ"}:
        return f"{left}.{right.upper()}"
    if left.lower() in {"sh", "sz", "bj"} and right.isdigit():
        return f"{right}.{left.upper()}"
    raise ValueError(f"Unexpected symbol format: {symbol}")


def _build_symbol_snapshot(
    symbol_bars: pd.DataFrame,
    technical_config: TechnicalAnalysisConfig,
    benchmark_index: pd.DataFrame | None,
) -> dict[str, object]:
    frame = symbol_bars.sort_values("date").reset_index(drop=True)
    for column in ["close", "volume", "amount"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["return"] = frame["close"].pct_change()

    ma_map = {
        "ma20": technical_config.short_window,
        "ma60": technical_config.medium_window,
        "ma120": technical_config.long_window,
        "ma250": technical_config.trend_window,
    }
    for label, window in ma_map.items():
        frame[label] = frame["close"].rolling(window).mean()

    latest = frame.iloc[-1]
    return_20d = _window_return(frame["close"], technical_config.short_window)
    return_60d = _window_return(frame["close"], technical_config.medium_window)
    return_120d = _window_return(frame["close"], technical_config.long_window)
    return_250d = _window_return(frame["close"], technical_config.trend_window)
    max_drawdown = _max_drawdown(frame["return"])
    vol20_vs_120 = _window_mean_ratio(
        frame["volume"],
        technical_config.volume_window,
        technical_config.baseline_volume_window,
    )
    amt20_vs_120 = _window_mean_ratio(
        frame["amount"],
        technical_config.volume_window,
        technical_config.baseline_volume_window,
    )
    recent_volume = frame.tail(technical_config.volume_window)
    avg_up_volume = recent_volume.loc[recent_volume["return"] > 0, "volume"].mean()
    avg_down_volume = recent_volume.loc[recent_volume["return"] < 0, "volume"].mean()
    relative_strength = _relative_strength_return(
        frame[["date", "close"]],
        benchmark_index,
        technical_config.trend_window,
    )
    latest_from_peak = _latest_from_peak(
        frame["close"],
        technical_config.peak_lookback_window,
    )
    trend_score = sum(
        [
            _bool_score(latest["close"] > latest["ma20"]),
            _bool_score(latest["close"] > latest["ma60"]),
            _bool_score(latest["close"] > latest["ma120"]),
            _bool_score(latest["close"] > latest["ma250"]),
            _bool_score(_is_positive(return_60d)),
            _bool_score(_is_positive(return_250d)),
        ]
    )
    volume_score = sum(
        [
            _bool_score(_is_positive(vol20_vs_120)),
            _bool_score(_is_positive(amt20_vs_120)),
            _bool_score(_safe_compare(avg_up_volume, avg_down_volume)),
        ]
    )
    relative_strength_score = _bool_score(_is_positive(relative_strength))
    risk_penalty = sum(
        [
            2 if _is_at_or_below(latest_from_peak, -technical_config.peak_drawdown_threshold) else 0,
            1 if _is_at_or_below(max_drawdown, -0.50) else 0,
            1 if _is_negative(return_20d) and _is_negative(_ratio_vs_ma(latest, "ma20")) else 0,
        ]
    )
    total_score = trend_score + volume_score + relative_strength_score - risk_penalty
    decision = _decision_from_score(total_score, technical_config)
    decision_reason = _decision_reason(
        latest,
        return_20d=return_20d,
        return_60d=return_60d,
        relative_strength=relative_strength,
        vol20_vs_120=vol20_vs_120,
        amt20_vs_120=amt20_vs_120,
        latest_from_peak=latest_from_peak,
    )

    return {
        "date": pd.Timestamp(latest["date"]).date().isoformat(),
        "symbol": str(latest["symbol"]),
        "latest_close": _maybe_float(latest["close"]),
        "return_20d": return_20d,
        "return_60d": return_60d,
        "return_120d": return_120d,
        "return_250d": return_250d,
        "max_drawdown": max_drawdown,
        "close_vs_ma20": _ratio_vs_ma(latest, "ma20"),
        "close_vs_ma60": _ratio_vs_ma(latest, "ma60"),
        "close_vs_ma120": _ratio_vs_ma(latest, "ma120"),
        "close_vs_ma250": _ratio_vs_ma(latest, "ma250"),
        "vol20_vs_120": vol20_vs_120,
        "amt20_vs_120": amt20_vs_120,
        "relative_strength_250d": relative_strength,
        "latest_from_peak_20d": latest_from_peak,
        "trend_score": trend_score,
        "volume_score": volume_score,
        "relative_strength_score": relative_strength_score,
        "risk_penalty": risk_penalty,
        "total_score": total_score,
        "decision": decision,
        "decision_reason": decision_reason,
    }


def _build_benchmark_index(benchmark_returns: pd.DataFrame | None) -> pd.DataFrame | None:
    if benchmark_returns is None or benchmark_returns.empty:
        return None
    benchmark = benchmark_returns[["date", "benchmark_return"]].copy()
    benchmark["date"] = pd.to_datetime(benchmark["date"], errors="raise")
    benchmark["benchmark_return"] = pd.to_numeric(benchmark["benchmark_return"], errors="coerce")
    benchmark["benchmark_index"] = (1.0 + benchmark["benchmark_return"].fillna(0.0)).cumprod()
    return benchmark[["date", "benchmark_index"]]


def _relative_strength_return(
    price_frame: pd.DataFrame,
    benchmark_index: pd.DataFrame | None,
    window: int,
) -> float | None:
    if benchmark_index is None or benchmark_index.empty or len(price_frame) < 2:
        return None
    aligned = price_frame.merge(benchmark_index, on="date", how="left").sort_values("date")
    aligned["benchmark_index"] = aligned["benchmark_index"].ffill()
    aligned = aligned.dropna(subset=["close", "benchmark_index"])
    if len(aligned) < 2:
        return None

    effective_window = min(window, len(aligned))
    window_frame = aligned.tail(effective_window).reset_index(drop=True)
    if len(window_frame) < 2:
        return None

    stock_return = window_frame["close"].iloc[-1] / window_frame["close"].iloc[0] - 1.0
    benchmark_return = (
        window_frame["benchmark_index"].iloc[-1] / window_frame["benchmark_index"].iloc[0] - 1.0
    )
    return _maybe_float((1.0 + stock_return) / (1.0 + benchmark_return) - 1.0)


def _window_return(series: pd.Series, window: int) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 2:
        return None
    effective_window = min(window, len(clean))
    window_series = clean.tail(effective_window)
    if len(window_series) < 2:
        return None
    return _maybe_float(window_series.iloc[-1] / window_series.iloc[0] - 1.0)


def _window_mean_ratio(series: pd.Series, short_window: int, baseline_window: int) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 2:
        return None
    short_slice = clean.tail(min(short_window, len(clean)))
    baseline_slice = clean.tail(min(baseline_window, len(clean)))
    baseline_mean = baseline_slice.mean()
    if baseline_mean == 0 or math.isnan(baseline_mean):
        return None
    return _maybe_float(short_slice.mean() / baseline_mean - 1.0)


def _latest_from_peak(series: pd.Series, lookback_window: int) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None
    recent = clean.tail(min(lookback_window, len(clean)))
    peak = recent.max()
    if peak == 0 or math.isnan(peak):
        return None
    return _maybe_float(recent.iloc[-1] / peak - 1.0)


def _max_drawdown(returns: pd.Series) -> float | None:
    clean = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    if clean.empty:
        return None
    equity = (1.0 + clean).cumprod()
    peak = equity.cummax()
    drawdown = equity.div(peak).sub(1.0)
    return _maybe_float(drawdown.min())


def _ratio_vs_ma(latest_row: pd.Series, ma_column: str) -> float | None:
    moving_average = latest_row.get(ma_column)
    close = latest_row.get("close")
    if pd.isna(moving_average) or moving_average == 0 or pd.isna(close):
        return None
    return _maybe_float(close / moving_average - 1.0)


def _decision_from_score(total_score: int, technical_config: TechnicalAnalysisConfig) -> str:
    if total_score >= technical_config.buy_score_threshold:
        return "buy"
    if total_score >= technical_config.hold_score_threshold:
        return "hold"
    return "sell"


def _decision_reason(
    latest_row: pd.Series,
    *,
    return_20d: float | None,
    return_60d: float | None,
    relative_strength: float | None,
    vol20_vs_120: float | None,
    amt20_vs_120: float | None,
    latest_from_peak: float | None,
) -> str:
    reasons: list[str] = []
    if _is_positive(_ratio_vs_ma(latest_row, "ma60")) and _is_positive(_ratio_vs_ma(latest_row, "ma120")):
        reasons.append("中期趋势已确认")
    elif _is_positive(_ratio_vs_ma(latest_row, "ma20")):
        reasons.append("短线处于反弹阶段")
    else:
        reasons.append("整体趋势仍偏弱")

    if _is_positive(vol20_vs_120) and _is_positive(amt20_vs_120):
        reasons.append("量能放大并得到确认")
    else:
        reasons.append("量能暂未形成有效确认")

    if _is_positive(relative_strength):
        reasons.append("相对强弱表现为正")
    elif relative_strength is not None:
        reasons.append("相对强弱表现为负")

    if _is_negative(return_20d):
        reasons.append("近期动量转弱")
    elif _is_positive(return_60d):
        reasons.append("中期动量保持正向")

    if _is_at_or_below(latest_from_peak, -0.15):
        reasons.append("短期高位回撤较大")

    return "；".join(reasons)


def _bool_score(condition: bool) -> int:
    return 1 if condition else 0


def _safe_compare(left: float | None, right: float | None) -> bool:
    if left is None or right is None or pd.isna(left) or pd.isna(right):
        return False
    return bool(left > right)


def _maybe_float(value: float | int | None) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _is_positive(value: float | None) -> bool:
    return value is not None and not pd.isna(value) and float(value) > 0.0


def _is_negative(value: float | None) -> bool:
    return value is not None and not pd.isna(value) and float(value) < 0.0


def _is_at_or_below(value: float | None, threshold: float) -> bool:
    return value is not None and not pd.isna(value) and float(value) <= threshold
