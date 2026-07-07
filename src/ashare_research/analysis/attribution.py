from __future__ import annotations

import pandas as pd


def build_strategy_attribution_report(
    positions: pd.DataFrame,
    bars: pd.DataFrame,
    equity_curve: pd.DataFrame,
) -> pd.DataFrame:
    """Build a simple daily attribution view from portfolio weights and cash."""
    if equity_curve.empty:
        return pd.DataFrame(columns=["date", "source", "contribution"])

    reports: list[pd.DataFrame] = []
    group_column = _group_column(bars)

    if not positions.empty and group_column is not None:
        grouped = positions.merge(
            bars[["date", "symbol", group_column]].drop_duplicates(),
            on=["date", "symbol"],
            how="left",
        )
        grouped["source"] = grouped[group_column].fillna("").replace("", "Unclassified")
        group_report = grouped.groupby(["date", "source"], as_index=False).agg(
            contribution=("weight", "sum")
        )
        reports.append(group_report)

    if "cash_weight" in equity_curve.columns:
        cash = equity_curve[["date", "cash_weight"]].copy()
        cash["source"] = "Cash"
        cash["contribution"] = cash["cash_weight"]
        reports.append(cash[["date", "source", "contribution"]])

    if not reports:
        return pd.DataFrame(columns=["date", "source", "contribution"])

    return pd.concat(reports, ignore_index=True).sort_values(["date", "source"]).reset_index(drop=True)


def _group_column(bars: pd.DataFrame) -> str | None:
    for column in ["industry", "sector"]:
        if column in bars.columns:
            return column
    return None
