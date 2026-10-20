"""Rolling-origin backtest splitter, as fixed in PROTOCOL.md.

Forecast origin: 00:00 UTC on each test day. Horizon h (1 to 24) is the
hour that starts at origin + (h - 1) hours. Only data strictly before the
origin may be used to forecast it.
"""

import pandas as pd

from src.config import (
    CALIBRATION_DAYS,
    HORIZON,
    HOURLY,
    REFIT_EVERY_DAYS,
    SARIMA_FIT_DAYS,
    TEST_END,
    TEST_START,
    TRAIN_WINDOW_DAYS,
)


def load_hourly(path=HOURLY):
    frame = pd.read_csv(path, index_col="timestamp_utc", parse_dates=["timestamp_utc"])
    series = frame["wind_mw"].astype(float)
    if series.index.tz is None:
        series.index = series.index.tz_localize("UTC")
    return series.asfreq("1h")


def origins(start=TEST_START, end=TEST_END):
    return pd.date_range(start, end, freq="1D", tz="UTC")


def target_index(origin, horizon=HORIZON):
    return pd.date_range(origin, periods=horizon, freq="1h")


def history(series, origin):
    """Everything observed before the origin. The origin hour itself is excluded."""
    return series[series.index < origin]


def refit_dates(start=TEST_START, end=TEST_END, every=REFIT_EVERY_DAYS):
    return pd.date_range(start, end, freq=f"{every}D", tz="UTC")


def refit_for(origin, refits=None):
    """The latest refit date on or before the origin."""
    refits = refit_dates() if refits is None else refits
    eligible = refits[refits <= origin]
    if len(eligible) == 0:
        raise ValueError(f"No refit date on or before {origin}")
    return eligible[-1]


def windows(refit):
    """Training, calibration and SARIMA fit windows for one weekly refit.

    Each is a half-open interval [start, end) that ends at the refit date,
    so none overlaps the test week that starts at the refit date.
    """
    day = pd.Timedelta(days=1)
    train_start = refit - TRAIN_WINDOW_DAYS * day
    calib_start = refit - CALIBRATION_DAYS * day
    return {
        "train": (train_start, refit),
        "fit": (train_start, calib_start),
        "calibration": (calib_start, refit),
        "sarima": (refit - SARIMA_FIT_DAYS * day, refit),
    }
