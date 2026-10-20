import pandas as pd
import pytest

from src import backtest
from src.config import CALIBRATION_DAYS, HORIZON, SARIMA_FIT_DAYS, TRAIN_WINDOW_DAYS


def hourly(start="2025-01-01", end="2026-12-31"):
    idx = pd.date_range(start, end, freq="1h", tz="UTC")
    return pd.Series(range(len(idx)), index=idx, dtype=float)


def test_origins_are_daily_at_midnight_utc():
    days = backtest.origins()
    assert len(days) == 365
    assert days[0] == pd.Timestamp("2025-10-01", tz="UTC")
    assert days[-1] == pd.Timestamp("2026-09-30", tz="UTC")
    assert (days.hour == 0).all() and (days.minute == 0).all()
    assert str(days.tz) == "UTC"


def test_target_index_covers_hours_1_to_24_of_the_day():
    origin = pd.Timestamp("2026-03-29", tz="UTC")  # GB clock change day
    stamps = backtest.target_index(origin)
    assert len(stamps) == HORIZON
    assert stamps[0] == origin
    assert stamps[-1] == origin + pd.Timedelta(hours=23)
    assert stamps.to_series().diff().dropna().eq(pd.Timedelta(hours=1)).all()


@pytest.mark.parametrize("origin", ["2025-10-01", "2026-03-29", "2026-09-30"])
def test_history_stops_strictly_before_origin(origin):
    origin = pd.Timestamp(origin, tz="UTC")
    past = backtest.history(hourly(), origin)
    assert past.index.max() == origin - pd.Timedelta(hours=1)
    assert not past.index.isin(backtest.target_index(origin)).any()


def test_refit_schedule_is_weekly_from_test_start():
    refits = backtest.refit_dates()
    assert len(refits) == 53
    assert refits.to_series().diff().dropna().eq(pd.Timedelta(days=7)).all()
    for origin in backtest.origins():
        refit = backtest.refit_for(origin, refits)
        assert refit <= origin < refit + pd.Timedelta(days=7)


def test_refit_for_rejects_origin_before_first_refit():
    with pytest.raises(ValueError):
        backtest.refit_for(pd.Timestamp("2025-09-30", tz="UTC"))


def test_windows_end_at_refit_and_do_not_overlap_test_week():
    for refit in backtest.refit_dates():
        win = backtest.windows(refit)
        test_week = pd.date_range(refit, refit + pd.Timedelta(days=7), freq="1h", inclusive="left")
        for name, (start, end) in win.items():
            assert start < end <= refit
            if name != "fit":
                assert end == refit
            assert not ((test_week >= start) & (test_week < end)).any()
        day = pd.Timedelta(days=1)
        assert win["train"][1] - win["train"][0] == TRAIN_WINDOW_DAYS * day
        assert win["calibration"][1] - win["calibration"][0] == CALIBRATION_DAYS * day
        assert win["sarima"][1] - win["sarima"][0] == SARIMA_FIT_DAYS * day
        # Fit part and calibration part split the training window with no overlap.
        assert win["fit"][0] == win["train"][0]
        assert win["fit"][1] == win["calibration"][0]
