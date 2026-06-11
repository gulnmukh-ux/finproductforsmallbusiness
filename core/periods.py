"""Weekly / Monthly / Quarterly / Yearly period handling."""

from __future__ import annotations

import pandas as pd

FREQ_CODES = {"Weekly": "W", "Monthly": "M", "Quarterly": "Q", "Yearly": "Y"}
FREQ_NOUN = {"Weekly": "week", "Monthly": "month", "Quarterly": "quarter", "Yearly": "year"}


def to_period(dates: pd.Series, freq_name: str) -> pd.Series:
    return pd.to_datetime(dates).dt.to_period(FREQ_CODES[freq_name])


def period_label(p: pd.Period, freq_name: str) -> str:
    if freq_name == "Weekly":
        return f"Week of {p.start_time:%b %d, %Y}"
    if freq_name == "Monthly":
        return f"{p.start_time:%B %Y}"
    if freq_name == "Quarterly":
        return f"Q{p.quarter} {p.year}"
    return str(p.year)


def available_periods(df: pd.DataFrame, freq_name: str, date_col: str = "date") -> list[pd.Period]:
    if df is None or df.empty:
        return []
    return sorted(to_period(df[date_col], freq_name).dropna().unique())


def filter_period(df: pd.DataFrame, period: pd.Period, freq_name: str, date_col: str = "date") -> pd.DataFrame:
    if df is None or df.empty:
        return df
    mask = to_period(df[date_col], freq_name) == period
    return df.loc[mask]


def pct_change(current: float, previous: float) -> float | None:
    if previous in (0, None) or pd.isna(previous):
        return None
    return (current - previous) / abs(previous) * 100
