"""LightGBM features, as fixed in PROTOCOL.md (LightGBM details).

Each row is one origin. Every value-based feature is computed from hours
that start before the origin; calendar features come from timestamps only.
"""

import numpy as np
import pandas as pd

LAGS = list(range(1, 25)) + [48, 168]
MEAN_WINDOWS = [6, 24, 168]


def feature_names():
    names = [f"lag_{k}" for k in LAGS]
    names += ["target_lag_24", "target_lag_168"]
    names += [f"mean_{w}" for w in MEAN_WINDOWS]
    names += ["std_24", "origin_hour", "target_hour", "target_dow",
              "target_doy_sin", "target_doy_cos"]
    return names


def build(series, origins, horizon):
    """Features for forecasting the hour origin + (horizon - 1) hours.

    series: hourly values on a regular UTC index. origins: timestamps in
    that index. Values at or after each origin are never read.
    """
    if not 1 <= horizon <= 24:
        raise ValueError("horizon must be between 1 and 24")
    origins = pd.DatetimeIndex(origins)
    # shifted.loc[o] = value of the hour starting at o - k hours.
    def at(k):
        return series.shift(k).reindex(origins).to_numpy(dtype=float)

    cols = {f"lag_{k}": at(k) for k in LAGS}
    # Target hour t = o + h - 1; its values 24 and 168 hours earlier are
    # o + h - 25 and o + h - 169, both before o because h <= 24.
    cols["target_lag_24"] = at(25 - horizon)
    cols["target_lag_168"] = at(169 - horizon)
    past = series.shift(1)
    for w in MEAN_WINDOWS:
        cols[f"mean_{w}"] = past.rolling(w, min_periods=w).mean().reindex(origins).to_numpy()
    cols["std_24"] = past.rolling(24, min_periods=24).std().reindex(origins).to_numpy()
    target = origins + pd.Timedelta(hours=horizon - 1)
    doy = target.dayofyear.to_numpy(dtype=float)
    cols["origin_hour"] = origins.hour.to_numpy(dtype=float)
    cols["target_hour"] = target.hour.to_numpy(dtype=float)
    cols["target_dow"] = target.dayofweek.to_numpy(dtype=float)
    cols["target_doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    cols["target_doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    frame = pd.DataFrame(cols, index=origins)
    return frame[feature_names()]


def targets(series, origins, horizon):
    stamps = pd.DatetimeIndex(origins) + pd.Timedelta(hours=horizon - 1)
    return series.reindex(stamps).to_numpy(dtype=float)
