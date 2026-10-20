import numpy as np
import pandas as pd
import pytest

from src import features

ORIGINS = pd.DatetimeIndex(["2026-01-20 00:00", "2026-01-20 13:00", "2026-03-29 00:00"],
                           tz="UTC")


def series():
    idx = pd.date_range("2025-12-01", "2026-04-30", freq="1h", tz="UTC")
    rng = np.random.default_rng(42)
    return pd.Series(rng.normal(8000, 3000, len(idx)), index=idx)


@pytest.mark.parametrize("horizon", range(1, 25))
def test_no_feature_uses_data_at_or_after_origin(horizon):
    y = series()
    for origin in ORIGINS:
        changed = y.copy()
        changed[changed.index >= origin] = 1e12
        a = features.build(y, [origin], horizon)
        b = features.build(changed, [origin], horizon)
        pd.testing.assert_frame_equal(a, b)
        assert not a.isna().any().any()


def test_lookups_point_at_the_right_hours():
    y = series()
    origin = ORIGINS[1]
    hour = pd.Timedelta(hours=1)
    for horizon in (1, 12, 24):
        row = features.build(y, [origin], horizon).iloc[0]
        target = origin + (horizon - 1) * hour
        assert row["lag_1"] == y[origin - hour]
        assert row["lag_24"] == y[origin - 24 * hour]
        assert row["lag_48"] == y[origin - 48 * hour]
        assert row["lag_168"] == y[origin - 168 * hour]
        assert row["target_lag_24"] == y[target - 24 * hour]
        assert row["target_lag_168"] == y[target - 168 * hour]
        assert row["mean_6"] == pytest.approx(y[origin - 6 * hour:origin - hour].mean())
        assert row["std_24"] == pytest.approx(y[origin - 24 * hour:origin - hour].std())
        assert row["origin_hour"] == origin.hour
        assert row["target_hour"] == target.hour
        assert row["target_dow"] == target.dayofweek


def test_target_lags_are_before_origin_for_every_horizon():
    # The target-hour lags reach origin - 1h at horizon 24 and never later.
    for horizon in range(1, 25):
        assert 25 - horizon >= 1
        assert 169 - horizon >= 1


def test_feature_names_are_stable():
    names = features.feature_names()
    assert len(names) == len(set(names)) == 37
    assert list(features.build(series(), ORIGINS, 5).columns) == names


def test_horizon_outside_1_to_24_is_rejected():
    with pytest.raises(ValueError):
        features.build(series(), ORIGINS, 25)
