from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from ashare_research.contracts.schemas import DatasetSchema


def validate_required_columns(frame: pd.DataFrame, schema: DatasetSchema) -> None:
    missing = schema.required_field_set.difference(frame.columns)
    if missing:
        raise ValueError(
            f"{schema.name} is missing required columns: {sorted(missing)}"
        )


def validate_non_empty_frame(frame: pd.DataFrame, schema: DatasetSchema) -> None:
    if frame.empty:
        raise ValueError(f"{schema.name} is empty.")


def validate_primary_keys_unique(frame: pd.DataFrame, schema: DatasetSchema) -> None:
    if not schema.primary_keys:
        return
    missing = set(schema.primary_keys).difference(frame.columns)
    if missing:
        raise ValueError(
            f"{schema.name} is missing primary key columns: {sorted(missing)}"
        )
    duplicated = frame.duplicated(list(schema.primary_keys))
    if duplicated.any():
        sample = frame.loc[duplicated, list(schema.primary_keys)].head().to_dict("records")
        raise ValueError(
            f"{schema.name} contains duplicate primary key rows: {sample}"
        )


def validate_columns_not_null(
    frame: pd.DataFrame,
    schema: DatasetSchema,
    columns: Sequence[str],
) -> None:
    for column in columns:
        if column not in frame.columns:
            continue
        if frame[column].isna().any():
            raise ValueError(f"{schema.name}.{column} contains null values.")


def validate_string_column_not_blank(
    frame: pd.DataFrame,
    schema: DatasetSchema,
    column: str,
) -> None:
    if column not in frame.columns:
        return
    normalized = frame[column].astype("string").str.strip()
    if normalized.isna().any() or normalized.eq("").any():
        raise ValueError(f"{schema.name}.{column} contains blank values.")


def validate_numeric_column_positive(
    frame: pd.DataFrame,
    schema: DatasetSchema,
    column: str,
) -> None:
    if column not in frame.columns:
        return
    series = pd.to_numeric(frame[column], errors="coerce")
    if series.isna().any():
        raise ValueError(f"{schema.name}.{column} contains non-numeric values.")
    if (series <= 0).any():
        raise ValueError(f"{schema.name}.{column} must be positive.")


def validate_numeric_column_non_negative(
    frame: pd.DataFrame,
    schema: DatasetSchema,
    column: str,
) -> None:
    if column not in frame.columns:
        return
    series = pd.to_numeric(frame[column], errors="coerce")
    if series.isna().any():
        raise ValueError(f"{schema.name}.{column} contains non-numeric values.")
    if (series < 0).any():
        raise ValueError(f"{schema.name}.{column} must be non-negative.")

