"""Run the naive baselines over the backtest and save metrics and figures.

Writes results/baselines.csv (overall and per-horizon metrics on the
common scoring set), results/figures/wind_hourly.png and
results/figures/baseline_mae_by_horizon.png. Per-pair forecasts go to
data/processed/forecasts_baselines.csv for later comparison.

Usage: python -m src.run_baselines
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.backtest import history, load_hourly, origins, target_index  # noqa: E402
from src.baselines import BASELINES  # noqa: E402
from src.config import (  # noqa: E402
    DATA_PROCESSED,
    FIGURES,
    HORIZON,
    RESULTS,
    SEED,
    TEST_END,
    TEST_START,
    TRAIN_WINDOW_DAYS,
)
from src.metrics import mae, rmse  # noqa: E402

# Primary reference for relative MAE (PROTOCOL.md, Metrics).
REFERENCE = "persistence"


def forecasts(series):
    rows = []
    for origin in origins():
        past = history(series, origin)
        stamps = target_index(origin)
        actual = series.reindex(stamps).to_numpy(dtype=float)
        preds = {name: fn(past, origin) for name, fn in BASELINES.items()}
        for h in range(HORIZON):
            row = {"origin": origin, "horizon": h + 1, "target_time": stamps[h], "y": actual[h]}
            row.update({name: preds[name][h] for name in BASELINES})
            rows.append(row)
    return pd.DataFrame(rows)


def scoring_set(frame):
    """Pairs with an observed target and observed inputs for every baseline."""
    cols = ["y", *BASELINES]
    return frame.dropna(subset=cols)


def summarise(scored):
    out = []
    groups = [("all", scored)] + [(str(h), g) for h, g in scored.groupby("horizon")]
    for label, group in groups:
        ref_mae = mae(group["y"], group[REFERENCE])
        day_mae = mae(group["y"], group["seasonal_naive_day"])
        week_mae = mae(group["y"], group["seasonal_naive_week"])
        for name in BASELINES:
            model_mae = mae(group["y"], group[name])
            out.append({
                "model": name,
                "horizon": label,
                "n": len(group),
                "mae_mw": round(model_mae, 1),
                "rmse_mw": round(rmse(group["y"], group[name]), 1),
                "rel_mae_vs_persistence": round(model_mae / ref_mae, 4),
                "rel_mae_vs_snaive_day": round(model_mae / day_mae, 4),
                "rel_mae_vs_snaive_week": round(model_mae / week_mae, 4),
            })
    return pd.DataFrame(out)


def plot_series(series):
    start = pd.Timestamp(TEST_START, tz="UTC") - pd.Timedelta(days=TRAIN_WINDOW_DAYS)
    view = series[start:pd.Timestamp(f"{TEST_END} 23:00", tz="UTC")]
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(view.index, view.to_numpy() / 1000, lw=0.3, color="#1f4e79")
    ax.axvspan(pd.Timestamp(TEST_START, tz="UTC"), view.index.max(), color="#f2b134", alpha=0.15,
               label="Test period")
    ax.set_ylabel("Wind generation (GW, hourly mean)")
    ax.set_title("GB transmission-metered wind generation (NESO WIND column, excludes embedded "
                 "wind)\nfirst training window and test period", fontsize=10)
    ax.legend(loc="upper right")
    ax.margins(x=0)
    fig.tight_layout()
    fig.savefig(FIGURES / "wind_hourly.png", dpi=120, metadata={"Software": None})
    plt.close(fig)


def plot_mae(summary):
    by_h = summary[summary["horizon"] != "all"].copy()
    by_h["h"] = by_h["horizon"].astype(int)
    fig, ax = plt.subplots(figsize=(7, 4))
    for name, style in zip(BASELINES, ["-o", "-s", "-^"]):
        part = by_h[by_h["model"] == name]
        ax.plot(part["h"], part["mae_mw"], style, ms=3, label=name.replace("_", " "))
    ax.set_xlabel("Horizon (hours after 00:00 UTC origin)")
    ax.set_ylabel("MAE (MW)")
    ax.set_title("Baseline MAE by horizon, GB transmission-metered wind\n"
                 "test period 1 Oct 2025 to 30 Sep 2026", fontsize=10)
    ax.set_xticks(range(1, HORIZON + 1, 2))
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "baseline_mae_by_horizon.png", dpi=120, metadata={"Software": None})
    plt.close(fig)


def main():
    np.random.seed(SEED)
    series = load_hourly()
    frame = forecasts(series)
    scored = scoring_set(frame)
    print(f"Pairs: {len(frame)}, scored: {len(scored)}, dropped: {len(frame) - len(scored)}")
    summary = summarise(scored)
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    summary.to_csv(RESULTS / "baselines.csv", index=False, lineterminator="\n")
    frame.to_csv(DATA_PROCESSED / "forecasts_baselines.csv", index=False, float_format="%.1f",
                 lineterminator="\n")
    plot_series(series)
    plot_mae(summary)
    print(summary[summary["horizon"] == "all"].to_string(index=False))


if __name__ == "__main__":
    main()
