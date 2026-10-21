"""Clean the frozen NESO snapshot and aggregate the wind series to hourly.

With the raw snapshot present: checks its hash, works in UTC, reports gaps,
duplicates, flat runs and outliers to results/cleaning_report.md, writes the
hourly series, and rebuilds the committed hourly slice. Nothing is filled
or removed silently.

Without the raw snapshot (a clean clone): checks the committed slice
against the SHA256 in data/SNAPSHOT.md and writes the hourly series from it.

Usage: python -m src.prepare
"""

import gzip
import hashlib
import io
import json
import re

import numpy as np
import pandas as pd

from src.config import (
    DATA_PROCESSED,
    HOURLY,
    RAW_SNAPSHOT,
    RESULTS,
    SLICE,
    SLICE_END,
    SLICE_START,
    SNAPSHOT_JSON,
    SNAPSHOT_MD,
    TARGET_COLUMN,
    TEST_END,
    TRAIN_WINDOW_DAYS,
    TEST_START,
)

REPORT = RESULTS / "cleaning_report.md"
COMPONENTS = ["GAS", "COAL", "NUCLEAR", "WIND", "WIND_EMB", "HYDRO", "IMPORTS",
              "BIOMASS", "OTHER", "SOLAR", "STORAGE"]
FLAT_RUN_HALF_HOURS = 6
RAMP_MW = 2000.0


def expected_slice_sha():
    """The slice SHA256 recorded in data/SNAPSHOT.md, or None if absent."""
    match = re.search(r"Slice SHA256: `([0-9a-f]{64})`", SNAPSHOT_MD.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def slice_bytes(hourly):
    """Deterministic gzip of the hourly slice: LF endings, no name, mtime 0."""
    part = hourly[pd.Timestamp(SLICE_START, tz="UTC"):pd.Timestamp(SLICE_END, tz="UTC")]
    frame = part.rename("wind_mw").to_frame()
    frame.index.name = "timestamp_utc"
    text = frame.to_csv(float_format="%.1f", lineterminator="\n")
    return gzip.compress(text.encode("utf-8"), compresslevel=9, mtime=0)


def from_slice():
    """Clean-clone path: verify the committed slice and write the hourly series."""
    data = SLICE.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    expected = expected_slice_sha()
    if digest != expected:
        raise SystemExit(f"Slice hash mismatch: {digest} != {expected}")
    text = gzip.decompress(data)
    hourly = pd.read_csv(io.BytesIO(text), index_col="timestamp_utc",
                         parse_dates=["timestamp_utc"])["wind_mw"]
    gaps = pd.date_range(hourly.index.min(), hourly.index.max(), freq="1h").difference(hourly.index)
    if len(gaps) or hourly.isna().any():
        raise SystemExit("Slice has gaps or missing values")
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    HOURLY.write_bytes(text)
    print(f"Raw snapshot absent. Used committed slice {SLICE.name} (SHA256 {digest}), "
          f"{len(hourly)} hours from {hourly.index.min()} to {hourly.index.max()}.")


def check_hash():
    facts = json.loads(SNAPSHOT_JSON.read_text(encoding="utf-8"))
    digest = hashlib.sha256(RAW_SNAPSHOT.read_bytes()).hexdigest()
    if digest != facts["snapshot_sha256"]:
        raise SystemExit(f"Snapshot hash mismatch: {digest} != {facts['snapshot_sha256']}")
    return facts


def load_raw():
    raw = pd.read_csv(RAW_SNAPSHOT)
    stamps = raw["DATETIME"].astype(str)
    has_offset = stamps.str.contains(r"[+Z]|-\d\d:\d\d$", regex=True).any()
    raw["ts"] = pd.to_datetime(stamps, format="%Y-%m-%dT%H:%M:%S").dt.tz_localize("UTC")
    return raw, has_offset


def flat_runs(series, min_len):
    """Return (start, length) for runs of identical consecutive values."""
    values = series.to_numpy()
    change = np.r_[True, values[1:] != values[:-1]]
    run_id = np.cumsum(change)
    lengths = np.bincount(run_id)[run_id]
    starts = series.index[change & (lengths >= min_len)]
    return [(start, int(lengths[series.index.get_loc(start)])) for start in starts]


def ramps(series, threshold):
    """Half-hour changes larger than threshold MW, on chronologically sorted data."""
    change = series.diff().abs()
    return change[change > threshold]


def main():
    if not RAW_SNAPSHOT.exists():
        from_slice()
        return
    facts = check_hash()
    raw, has_offset = load_raw()
    lines = ["# Cleaning report", "",
             f"Snapshot: {facts['snapshot_file']} (SHA256 {facts['snapshot_sha256']})", ""]
    log = lines.append

    # Time zone evidence: local GB clock time would show 46 or 50 rows on
    # clock-change days; UTC shows 48 every day.
    per_day = raw.groupby(raw["ts"].dt.date).size()
    log("## Time zone")
    log(f"- Timestamps carry no offset: {not has_offset}. Parsed as UTC.")
    log(f"- Rows per UTC day: min {per_day.min()}, max {per_day.max()}, "
        f"days not equal to 48: {(per_day != 48).sum()}.")
    dst_days = [d for d in per_day.index if (d.month in (3, 10)) and d.weekday() == 6 and d.day > 24]
    log(f"- Rows on the {len(dst_days)} GB clock-change Sundays: "
        f"{sorted(set(per_day.loc[dst_days].tolist()))}. 48 on every one is consistent with UTC.")
    log("")

    log("## Duplicates and gaps (half-hourly)")
    out_of_order = int((raw["ts"].diff() < pd.Timedelta(0)).sum())
    log(f"- Rows out of chronological order in the file: {out_of_order}. Action: sorted by timestamp.")
    dup = raw["ts"].duplicated(keep=False)
    log(f"- Duplicate timestamps: {int(dup.sum())} rows. Action: none needed." if not dup.any()
        else f"- Duplicate timestamps: {int(dup.sum())} rows. Action: kept the first of each.")
    raw = raw[~raw["ts"].duplicated(keep="first")].set_index("ts").sort_index()
    full = pd.date_range(raw.index.min(), raw.index.max(), freq="30min", tz="UTC")
    missing = full.difference(raw.index)
    log(f"- Expected half-hours {len(full)}, present {len(raw)}, missing {len(missing)}.")
    if len(missing):
        log(f"- First missing: {[str(t) for t in missing[:10]]}. Action: left missing, not filled.")
    raw = raw.reindex(full)
    wind = raw[TARGET_COLUMN].astype(float)
    log(f"- Missing {TARGET_COLUMN} values after reindexing: {int(wind.isna().sum())}. "
        "Action: left missing, not filled.")
    log("")

    log(f"## {TARGET_COLUMN} column")
    gen_sum = raw[COMPONENTS].sum(axis=1)
    match = (gen_sum - raw["GENERATION"]).abs() <= 1.0
    log(f"- GENERATION equals the sum of {', '.join(COMPONENTS)} (within 1 MW) "
        f"in {match.mean():.4%} of rows. WIND and WIND_EMB are separate addends, "
        "so WIND excludes embedded wind.")
    log(f"- {TARGET_COLUMN} range: {wind.min():.0f} to {wind.max():.0f} MW; "
        f"negative values: {int((wind < 0).sum())}; exact zeros: {int((wind == 0).sum())}.")
    test = wind[TEST_START:f"{TEST_END} 23:30"]
    log(f"- Test period ({TEST_START} to {TEST_END}) range: {test.min():.0f} to "
        f"{test.max():.0f} MW, mean {test.mean():.0f} MW.")
    log("")

    log("## Possible outliers and imputation artefacts (flagged, not changed)")
    runs = flat_runs(wind.dropna(), FLAT_RUN_HALF_HOURS)
    test_runs = [r for r in runs if pd.Timestamp(TEST_START, tz="UTC") <= r[0]
                 <= pd.Timestamp(f"{TEST_END} 23:30", tz="UTC")]
    log(f"- Flat runs of {FLAT_RUN_HALF_HOURS}+ identical half-hours: {len(runs)} overall, "
        f"{len(test_runs)} in the test period.")
    for start, length in runs[:10]:
        log(f"  - {start} for {length} half-hours at {wind.loc[start]:.0f} MW")
    ramp = ramps(wind, RAMP_MW)
    test_ramp = ramp[TEST_START:f"{TEST_END} 23:30"]
    log(f"- Half-hour changes above {RAMP_MW:.0f} MW (the 99.99th percentile of all changes "
        f"is {wind.diff().abs().quantile(0.9999):.0f} MW): {len(ramp)} overall, "
        f"{len(test_ramp)} in the test period.")
    for ts, val in ramp.items():
        log(f"  - {ts}: change of {val:.0f} MW, value {wind.loc[ts]:.0f} MW")
    zero_dips = wind[(wind == 0) & (wind.shift(-1).fillna(0) == 0)]
    log(f"- Half-hours at exactly 0 MW that are followed by another 0: {len(zero_dips)}, "
        f"last at {zero_dips.index.max() if len(zero_dips) else 'none'}. "
        "These look like metering outages (for example 2021-11-23 10:30 to 12:00).")
    log("- Action: none of these are changed. NESO states that it already applies "
        "seasonal decomposition to correct missing or irregular points, so flat runs "
        "may be its imputation.")
    # Training window start, less 168 hours for the weekly lag features.
    earliest_used = (pd.Timestamp(TEST_START, tz="UTC") - pd.Timedelta(days=TRAIN_WINDOW_DAYS)
                     - pd.Timedelta(hours=168))
    flagged = [r[0] for r in runs] + list(ramp.index) + list(zero_dips.index)
    latest_flag = max(flagged) if flagged else None
    inside = latest_flag is not None and latest_flag >= earliest_used
    log(f"- Earliest data used by the backtest: {earliest_used}. Latest flagged point: "
        f"{latest_flag}. Flagged points inside the data used: {'yes' if inside else 'none'}.")
    log("")

    # Hourly mean of the two half-hours that start in each hour. An hour with
    # either half missing becomes missing rather than half-filled.
    log("## Hourly aggregation")
    counts = wind.resample("1h").count()
    hourly = wind.resample("1h").mean().where(counts == 2)
    log("- Hourly value = mean of the two half-hourly MW values starting in that hour "
        "(average power over the hour, MW), labelled by hour start in UTC.")
    log(f"- Hours: {len(hourly)}, missing (any half-hour missing): {int(hourly.isna().sum())}.")
    log(f"- First hour {hourly.index.min()}, last hour {hourly.index.max()}.")

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = hourly.rename("wind_mw").to_frame()
    out.index.name = "timestamp_utc"
    out.to_csv(HOURLY, float_format="%.1f", lineterminator="\n")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))

    data = slice_bytes(hourly)
    digest = hashlib.sha256(data).hexdigest()
    expected = expected_slice_sha()
    if expected is not None and digest != expected:
        raise SystemExit(f"Rebuilt slice {digest} does not match SNAPSHOT.md {expected}")
    SLICE.write_bytes(data)
    print(f"\nSlice {SLICE.name}: SHA256 {digest}")


if __name__ == "__main__":
    main()
