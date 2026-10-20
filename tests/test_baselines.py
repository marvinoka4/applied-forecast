import numpy as np
import pandas as pd
import pytest

from src import baselines
from src.backtest import history, target_index

ORIGIN = pd.Timestamp("2026-01-15", tz="UTC")


def ramp():
    """Value equals hours since the start, so lookups are easy to check."""
    idx = pd.date_range("2025-12-01", "2026-01-31", freq="1h", tz="UTC")
    return pd.Series(np.arange(len(idx), dtype=float), index=idx)


def position(series, stamp):
    return float(series.index.get_loc(stamp))


def test_persistence_holds_last_value_flat():
    series = ramp()
    fc = baselines.persistence(history(series, ORIGIN), ORIGIN)
    expected = position(series, ORIGIN - pd.Timedelta(hours=1))
    assert fc.shape == (24,)
    assert np.all(fc == expected)


@pytest.mark.parametrize("name,lag", [("seasonal_naive_day", 24), ("seasonal_naive_week", 168)])
def test_seasonal_naive_uses_same_hour_lag(name, lag):
    series = ramp()
    fc = baselines.BASELINES[name](history(series, ORIGIN), ORIGIN)
    expected = [position(series, t - pd.Timedelta(hours=lag)) for t in target_index(ORIGIN)]
    assert fc.tolist() == expected


@pytest.mark.parametrize("name", list(baselines.BASELINES))
def test_no_leakage_from_origin_onwards(name):
    series = ramp()
    changed = series.copy()
    changed[changed.index >= ORIGIN] = -1e9
    fn = baselines.BASELINES[name]
    np.testing.assert_array_equal(fn(history(series, ORIGIN), ORIGIN),
                                  fn(history(changed, ORIGIN), ORIGIN))
    # Passing the full series must not change the answer either.
    np.testing.assert_array_equal(fn(series, ORIGIN), fn(history(series, ORIGIN), ORIGIN))


def test_seasonal_lag_shorter_than_horizon_is_rejected():
    series = ramp()
    with pytest.raises(ValueError):
        baselines.seasonal_naive(history(series, ORIGIN), ORIGIN, lag_hours=12)


def test_missing_inputs_give_missing_forecasts():
    series = ramp()
    gap = ORIGIN - pd.Timedelta(hours=24)
    series[gap] = np.nan
    series[ORIGIN - pd.Timedelta(hours=1)] = np.nan
    past = history(series, ORIGIN)
    assert np.isnan(baselines.persistence(past, ORIGIN)).all()
    day = baselines.seasonal_naive_day(past, ORIGIN)
    # Horizon 1 needs origin - 24h; horizon 24 needs origin - 1h. Both are missing.
    assert np.isnan(day[0]) and np.isnan(day[23])
    assert not np.isnan(day[1:23]).any()
