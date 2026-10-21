"""Score all five models on the shared scoring set, as fixed in PROTOCOL.md (Metrics).

Writes results/model_metrics.csv (overall), results/model_metrics_by_horizon.csv,
results/figures/mae_by_horizon_all_models.png and
results/figures/coverage_by_horizon.png.

Usage:
  python -m src.evaluate           pre-specified models
  python -m src.evaluate posthoc   post-hoc LightGBM variant without the target day-of-year
                                   features, scored on the same set; writes
                                   results/posthoc_lgbm_no_doy.csv and
                                   results/posthoc_lgbm_no_doy_by_horizon.csv
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src import lgbm, sarima  # noqa: E402
from src.backtest import load_hourly  # noqa: E402
from src.baselines import BASELINES  # noqa: E402
from src.config import FIGURES, HORIZON, RESULTS  # noqa: E402
from src.metrics import coverage, mae, mean_width, rmse  # noqa: E402
from src.run_baselines import forecasts, scoring_set  # noqa: E402

MODELS = ["persistence", "seasonal_naive_day", "seasonal_naive_week", "sarima", "lightgbm"]
INTERVAL_MODELS = ["sarima", "lightgbm"]
POSTHOC = "lightgbm_no_doy"
LABELS = {"persistence": "Persistence", "seasonal_naive_day": "Seasonal naive, day",
          "seasonal_naive_week": "Seasonal naive, week", "sarima": "SARIMA",
          "lightgbm": "LightGBM"}


def load_model(path, name):
    frame = pd.read_csv(path, parse_dates=["origin"])
    frame["origin"] = pd.to_datetime(frame["origin"], utc=True)
    cols = {c: f"{name}_{c}" for c in ["yhat", "lo80", "hi80", "lo95", "hi95"]}
    return frame[["origin", "horizon", *cols]].rename(columns=cols)


def joined():
    series = load_hourly()
    base = forecasts(series)
    base["origin"] = pd.to_datetime(base["origin"], utc=True)
    scored = scoring_set(base)
    for name, path in [("sarima", sarima.FORECASTS), ("lightgbm", lgbm.FORECASTS)]:
        scored = scored.merge(load_model(path, name), on=["origin", "horizon"], how="left",
                              validate="one_to_one")
        missing = scored[f"{name}_yhat"].isna().sum()
        if missing:
            raise RuntimeError(f"{name} has no forecast for {missing} scored pairs")
    for name in BASELINES:
        scored[f"{name}_yhat"] = scored[name]
    return base, scored


def metrics(group, models=MODELS):
    out = []
    ref = {name: mae(group["y"], group[f"{name}_yhat"]) for name in BASELINES}
    for name in models:
        yhat = group[f"{name}_yhat"]
        m = mae(group["y"], yhat)
        row = {"model": name, "n": len(group), "mae_mw": round(m, 1),
               "rmse_mw": round(rmse(group["y"], yhat), 1),
               "rel_mae_vs_persistence": round(m / ref["persistence"], 4),
               "rel_mae_vs_snaive_day": round(m / ref["seasonal_naive_day"], 4),
               "rel_mae_vs_snaive_week": round(m / ref["seasonal_naive_week"], 4)}
        for lvl in ["80", "95"]:
            if name in INTERVAL_MODELS or name == POSTHOC:
                lo, hi = group[f"{name}_lo{lvl}"], group[f"{name}_hi{lvl}"]
                row[f"coverage_{lvl}"] = round(coverage(group["y"], lo, hi), 4)
                row[f"mean_width_{lvl}_mw"] = round(mean_width(lo, hi), 1)
            else:
                row[f"coverage_{lvl}"] = None
                row[f"mean_width_{lvl}_mw"] = None
        out.append(row)
    return out


def plot_mae(by_h):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for name, style in zip(MODELS, ["-o", "-s", "-^", "-D", "-v"]):
        part = by_h[by_h["model"] == name]
        ax.plot(part["horizon"], part["mae_mw"], style, ms=3, label=LABELS[name])
    ax.set_xlabel("Horizon (hours after 00:00 UTC origin)")
    ax.set_ylabel("MAE (MW)")
    ax.set_title("MAE by horizon, GB transmission-metered wind\n"
                 "test period 1 Oct 2025 to 30 Sep 2026", fontsize=10)
    ax.set_xticks(range(1, HORIZON + 1, 2))
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "mae_by_horizon_all_models.png", dpi=120, metadata={"Software": None})
    plt.close(fig)


def plot_coverage(by_h):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharex=True)
    for ax, lvl in zip(axes, ["80", "95"]):
        nominal = int(lvl) / 100
        for name, style in zip(INTERVAL_MODELS, ["-D", "-v"]):
            part = by_h[by_h["model"] == name]
            ax.plot(part["horizon"], part[f"coverage_{lvl}"], style, ms=3, label=LABELS[name])
        ax.axhline(nominal, color="black", ls="--", lw=1, label=f"Nominal {lvl}%")
        ax.axhspan(nominal - 0.03, nominal + 0.03, color="grey", alpha=0.12,
                   label="Nominal plus or minus 3 points")
        ax.set_title(f"{lvl}% intervals", fontsize=10)
        ax.set_xlabel("Horizon (hours after 00:00 UTC origin)")
        ax.set_xticks(range(1, HORIZON + 1, 2))
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Empirical coverage")
    axes[1].legend(fontsize=8, loc="lower left")
    fig.suptitle("Interval coverage by horizon, SARIMA (native) and LightGBM (split conformal)",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURES / "coverage_by_horizon.png", dpi=120, metadata={"Software": None})
    plt.close(fig)


def main():
    base, scored = joined()
    print(f"Pairs: {len(base)}, scored: {len(scored)}")
    overall = pd.DataFrame(metrics(scored))
    by_h = pd.concat([pd.DataFrame(metrics(g)).assign(horizon=h)
                      for h, g in scored.groupby("horizon")], ignore_index=True)
    by_h = by_h[["model", "horizon", *[c for c in overall.columns if c != "model"]]]
    overall.to_csv(RESULTS / "model_metrics.csv", index=False, lineterminator="\n")
    by_h.to_csv(RESULTS / "model_metrics_by_horizon.csv", index=False, lineterminator="\n")
    FIGURES.mkdir(parents=True, exist_ok=True)
    plot_mae(by_h)
    plot_coverage(by_h)
    print(overall.to_string(index=False))


def posthoc():
    _, scored = joined()
    scored = scored.merge(load_model(lgbm.FORECASTS_NO_DOY, POSTHOC), on=["origin", "horizon"],
                          how="left", validate="one_to_one")
    missing = scored[f"{POSTHOC}_yhat"].isna().sum()
    if missing:
        raise RuntimeError(f"{POSTHOC} has no forecast for {missing} scored pairs")
    overall = pd.DataFrame(metrics(scored, [POSTHOC]))
    by_h = pd.concat([pd.DataFrame(metrics(g, [POSTHOC])).assign(horizon=h)
                      for h, g in scored.groupby("horizon")], ignore_index=True)
    by_h = by_h[["model", "horizon", *[c for c in overall.columns if c != "model"]]]
    overall.to_csv(RESULTS / "posthoc_lgbm_no_doy.csv", index=False, lineterminator="\n")
    by_h.to_csv(RESULTS / "posthoc_lgbm_no_doy_by_horizon.csv", index=False,
                lineterminator="\n")
    print(overall.to_string(index=False))


if __name__ == "__main__":
    posthoc() if sys.argv[1:] == ["posthoc"] else main()
