"""LightGBM direct multi-horizon backtest with split conformal intervals,
as fixed in PROTOCOL.md (LightGBM details, Prediction intervals).

Usage:
  python -m src.lgbm time       time one refit (24 models, calibration, week of forecasts)
  python -m src.lgbm backtest   all 53 refits
"""

import sys
import time

import lightgbm as lgb
import pandas as pd

from src import features
from src.backtest import load_hourly, origins, refit_dates, windows
from src.conformal import conformal_halfwidth
from src.config import DATA_PROCESSED, HORIZON, SEED, TEST_END, TRAIN_WINDOW_DAYS, TEST_START
from src.runlog import logged

FORECASTS = DATA_PROCESSED / "forecasts_lgbm.csv"
LEVELS = {"80": 0.20, "95": 0.05}
PARAMS = {
    "objective": "regression",  # L2
    "n_estimators": 400,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 20,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "random_state": SEED,
    "deterministic": True,
    "force_row_wise": True,  # LightGBM requires a fixed histogram mode for determinism
    "n_jobs": 1,
    "verbose": -1,
}


def feature_tables(series):
    """Features and targets for every hourly origin the backtest can use, per horizon."""
    first = pd.Timestamp(TEST_START, tz="UTC") - pd.Timedelta(days=TRAIN_WINDOW_DAYS)
    last = pd.Timestamp(TEST_END, tz="UTC")
    all_origins = pd.date_range(first, last, freq="1h")
    tables = {}
    for h in range(1, HORIZON + 1):
        X = features.build(series, all_origins, h)
        y = pd.Series(features.targets(series, all_origins, h), index=all_origins)
        tables[h] = (X, y)
    return tables


def run_refit(tables, refit):
    win = windows(refit)
    fit_start, calib_start = win["fit"]
    calib_origins = pd.date_range(calib_start, refit, freq="1D", inclusive="left")
    week = [o for o in origins() if refit <= o < refit + pd.Timedelta(days=7)]
    rows, info = [], {"refit": refit}
    t0 = time.perf_counter()
    for h in range(1, HORIZON + 1):
        X, y = tables[h]
        # Training origins: target hour o + h - 1 must end by calib_start.
        last_origin = calib_start - pd.Timedelta(hours=h)
        train = X.index[(X.index >= fit_start) & (X.index <= last_origin)]
        mask = y.loc[train].notna()
        train = train[mask.to_numpy()]
        model = lgb.LGBMRegressor(**PARAMS)
        model.fit(X.loc[train], y.loc[train])
        scores = (y.loc[calib_origins] - model.predict(X.loc[calib_origins])).abs()
        if scores.isna().any():
            raise RuntimeError(f"Missing calibration target at refit {refit}, horizon {h}")
        half = {lvl: conformal_halfwidth(scores.to_numpy(), a) for lvl, a in LEVELS.items()}
        info[f"n_train_h{h}"] = len(train)
        info[f"q80_h{h}"] = round(half["80"], 1)
        info[f"q95_h{h}"] = round(half["95"], 1)
        pred = model.predict(X.loc[week]) if week else []
        for origin, yhat in zip(week, pred):
            rows.append({"origin": origin, "horizon": h,
                         "target_time": origin + pd.Timedelta(hours=h - 1), "yhat": yhat,
                         "lo80": yhat - half["80"], "hi80": yhat + half["80"],
                         "lo95": yhat - half["95"], "hi95": yhat + half["95"]})
    info["n_calibration"] = len(calib_origins)
    info["seconds"] = round(time.perf_counter() - t0, 1)
    return rows, info


def time_one():
    series = load_hourly()
    refit = refit_dates()[0]
    with logged(f"LightGBM timing, one refit ({refit:%Y-%m-%d})") as rec:
        t0 = time.perf_counter()
        tables = feature_tables(series)
        feat_secs = time.perf_counter() - t0
        rows, info = run_refit(tables, refit)
        rec["outcome"] = (f"features (once per backtest) {feat_secs:.1f} s; one refit "
                          f"(24 models, conformal, {len(rows) // HORIZON} origins) "
                          f"{info['seconds']} s; {info['n_train_h1']} training rows at h=1, "
                          f"{info['n_calibration']} calibration origins")
        print(rec["outcome"])


def backtest():
    series = load_hourly()
    with logged("LightGBM backtest, 53 refits") as rec:
        tables = feature_tables(series)
        all_rows, infos = [], []
        for refit in refit_dates():
            rows, info = run_refit(tables, refit)
            all_rows += rows
            infos.append(info)
            print(f"{refit:%Y-%m-%d} {info['seconds']} s", flush=True)
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(all_rows).to_csv(FORECASTS, index=False, lineterminator="\n")
        pd.DataFrame(infos).to_csv(DATA_PROCESSED / "lgbm_refits.csv", index=False,
                                   lineterminator="\n")
        rec["outcome"] = f"{len(infos)} refits, {len(all_rows)} forecast rows"
        print(rec["outcome"])


if __name__ == "__main__":
    {"time": time_one, "backtest": backtest}[sys.argv[1]]()
