"""Naive baselines. Each takes the history before an origin and returns
HORIZON point forecasts for the hours starting at the origin.

Missing inputs give missing forecasts; nothing is filled.
"""

import numpy as np
import pandas as pd

from src.backtest import target_index
from src.config import HORIZON


def _lookup(past, stamps, origin):
    if stamps.max() >= origin:
        raise ValueError("Baseline lookup reaches the origin or later")
    return past.reindex(stamps).to_numpy(dtype=float)


def persistence(past, origin, horizon=HORIZON):
    """Last value before the origin, held flat over the horizon."""
    last = origin - pd.Timedelta(hours=1)
    value = past.get(last, np.nan)
    return np.full(horizon, value, dtype=float)


def seasonal_naive(past, origin, lag_hours, horizon=HORIZON):
    """Value at the same hour lag_hours earlier. Needs lag_hours >= horizon."""
    if lag_hours < horizon:
        raise ValueError("lag_hours must be at least the horizon to avoid leakage")
    stamps = target_index(origin, horizon) - pd.Timedelta(hours=lag_hours)
    return _lookup(past, stamps, origin)


def seasonal_naive_day(past, origin, horizon=HORIZON):
    return seasonal_naive(past, origin, 24, horizon)


def seasonal_naive_week(past, origin, horizon=HORIZON):
    return seasonal_naive(past, origin, 168, horizon)


BASELINES = {
    "persistence": persistence,
    "seasonal_naive_day": seasonal_naive_day,
    "seasonal_naive_week": seasonal_naive_week,
}
