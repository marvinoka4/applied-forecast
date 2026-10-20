"""SARIMA order selection and backtest, as fixed in PROTOCOL.md (SARIMA details).

Usage:
  python -m src.sarima select     order selection on the 56 days before the test period
  python -m src.sarima time       time one refit (fit plus its week of forecasts)
  python -m src.sarima backtest   all 53 refits
"""

import itertools
import sys
import time
import warnings

import numpy as np
import pandas as pd
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import kpss

from src.backtest import history, load_hourly, origins, refit_dates, windows
from src.config import DATA_PROCESSED, HORIZON, RESULTS, SARIMA_FIT_DAYS, TEST_START
from src.runlog import logged

SEASON = 24
GRID = {"p": [1, 2, 3], "q": [0, 1, 2], "P": [0, 1], "Q": [0, 1]}
SELECTION_CSV = RESULTS / "sarima_order_selection.csv"
REFITS_CSV = RESULTS / "sarima_refits.csv"
FORECASTS = DATA_PROCESSED / "forecasts_sarima.csv"


def selection_window(series):
    end = pd.Timestamp(TEST_START, tz="UTC")
    start = end - pd.Timedelta(days=SARIMA_FIT_DAYS)
    return series[(series.index >= start) & (series.index < end)]


def fit(endog, order, seasonal_order):
    """Fit with statsmodels defaults. Returns (results, converged, warnings text)."""
    model = SARIMAX(endog, order=order, seasonal_order=seasonal_order)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        res = model.fit(disp=False)
    converged = bool(res.mle_retvals.get("converged", False))
    notes = sorted({str(w.message).splitlines()[0] for w in caught
                    if issubclass(w.category, ConvergenceWarning)})
    return model, res, converged, "; ".join(notes)


def choose_d(window):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        stat, pvalue, lags, crit = kpss(window.to_numpy())
    d = 1 if stat > crit["5%"] else 0
    return d, stat, pvalue, lags, crit


def select():
    series = load_hourly()
    window = selection_window(series)
    with logged("SARIMA order selection (KPSS then AIC grid)") as rec:
        d, stat, pvalue, lags, crit = choose_d(window)
        print(f"KPSS on {window.index.min()} to {window.index.max()} ({len(window)} hours): "
              f"stat {stat:.4f}, 5% critical {crit['5%']}, p {pvalue}, lags {lags} -> d = {d}")
        rows = []
        for p, q, P, Q in itertools.product(GRID["p"], GRID["q"], GRID["P"], GRID["Q"]):
            if P + Q < 1:
                continue
            t0 = time.perf_counter()
            _, res, converged, notes = fit(window, (p, d, q), (P, 0, Q, SEASON))
            secs = time.perf_counter() - t0
            rows.append({"p": p, "d": d, "q": q, "P": P, "D": 0, "Q": Q, "s": SEASON,
                         "aic": round(float(res.aic), 3), "converged": converged,
                         "fit_seconds": round(secs, 1), "warnings": notes})
            print(rows[-1])
        grid = pd.DataFrame(rows)
        ok = grid[grid["converged"]]
        best = ok.loc[ok["aic"].idxmin()] if len(ok) else None
        grid["selected"] = False
        if best is not None:
            grid.loc[best.name, "selected"] = True
        grid.attrs["kpss"] = (stat, crit["5%"])
        grid.to_csv(SELECTION_CSV, index=False, lineterminator="\n")
        if best is None:
            rec["outcome"] = "no converged fit in grid; stopped"
            raise SystemExit("No converged fit in the grid")
        rec["outcome"] = (f"d={d} (KPSS {stat:.3f} > {crit['5%']}); {len(grid)} fits, "
                          f"{int(grid['converged'].sum())} converged; selected "
                          f"({int(best.p)},{d},{int(best.q)})({int(best.P)},0,{int(best.Q)},24) "
                          f"AIC {best.aic}")
        print(rec["outcome"])


def selected_order():
    grid = pd.read_csv(SELECTION_CSV)
    best = grid[grid["selected"]].iloc[0]
    return (int(best.p), int(best.d), int(best.q)), (int(best.P), 0, int(best.Q), SEASON)


def run_refit(series, refit, order, seasonal, prev_params):
    """Fit one refit and forecast its week. Returns (rows, info, params)."""
    start, end = windows(refit)["sarima"]
    window = series[(series.index >= start) & (series.index < end)]
    t0 = time.perf_counter()
    model, res, converged, notes = fit(window, order, seasonal)
    used = "own fit"
    if not converged:
        if prev_params is None:
            raise RuntimeError(f"First refit {refit} did not converge and has no previous "
                               "parameters; the protocol does not cover this case")
        res = model.filter(prev_params)
        used = "previous refit parameters"
    fit_secs = time.perf_counter() - t0
    rows = []
    week = [o for o in origins() if refit <= o < refit + pd.Timedelta(days=7)]
    for origin in week:
        past = history(series, origin)
        data = past[past.index >= start]
        fc = res.apply(data).get_forecast(HORIZON)
        mean = fc.predicted_mean.to_numpy()
        ci80 = fc.conf_int(alpha=0.20).to_numpy()
        ci95 = fc.conf_int(alpha=0.05).to_numpy()
        for h in range(HORIZON):
            rows.append({"origin": origin, "horizon": h + 1,
                         "target_time": origin + pd.Timedelta(hours=h),
                         "yhat": mean[h], "lo80": ci80[h, 0], "hi80": ci80[h, 1],
                         "lo95": ci95[h, 0], "hi95": ci95[h, 1]})
    info = {"refit": refit, "converged": converged, "params_used": used,
            "aic": round(float(res.aic), 3) if converged else np.nan,
            "fit_seconds": round(fit_secs, 1),
            "total_seconds": round(time.perf_counter() - t0, 1), "warnings": notes}
    return rows, info, (res.params if converged else prev_params)


def time_one():
    series = load_hourly()
    order, seasonal = selected_order()
    refit = refit_dates()[0]
    with logged(f"SARIMA timing, one refit ({refit:%Y-%m-%d})") as rec:
        rows, info, _ = run_refit(series, refit, order, seasonal, None)
        rec["outcome"] = (f"converged={info['converged']}; fit {info['fit_seconds']} s; "
                          f"fit plus {len(rows) // HORIZON} origins {info['total_seconds']} s")
        print(rec["outcome"])


def backtest():
    series = load_hourly()
    order, seasonal = selected_order()
    all_rows, infos, params = [], [], None
    with logged(f"SARIMA backtest, 53 refits, order {order}{seasonal}") as rec:
        for refit in refit_dates():
            rows, info, params = run_refit(series, refit, order, seasonal, params)
            all_rows += rows
            infos.append(info)
            print(f"{refit:%Y-%m-%d} converged={info['converged']} "
                  f"{info['params_used']} {info['total_seconds']} s", flush=True)
        refits = pd.DataFrame(infos)
        refits.to_csv(REFITS_CSV, index=False, lineterminator="\n")
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(all_rows).to_csv(FORECASTS, index=False, lineterminator="\n")
        failed = refits.loc[~refits["converged"], "refit"].dt.strftime("%Y-%m-%d").tolist()
        rec["outcome"] = (f"{len(refits)} refits, {len(failed)} convergence failures"
                          + (f" ({', '.join(failed)}; previous parameters kept)" if failed else ""))
        print(rec["outcome"])


if __name__ == "__main__":
    {"select": select, "time": time_one, "backtest": backtest}[sys.argv[1]]()
