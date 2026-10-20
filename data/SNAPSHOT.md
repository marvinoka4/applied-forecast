# Data snapshot

Raw files live in data/raw/ and are not committed. A committed hourly slice of the target (below) lets the backtest run from a clean clone without them. Rebuild the raw files with `python -m src.download_data`; data/snapshot.json holds the same facts in machine-readable form, and `src.prepare` refuses to run if the snapshot hash does not match.

## Source
- Dataset: NESO Data Portal, "Historic GB Generation Mix" (dataset id historic-generation-mix).
- URL: https://api.neso.energy/dataset/88313ae5-94e4-4ddc-a790-593554d8c6b9/resource/f93d1835-75bc-43e5-84ad-12472b180a98/download/df_fuel_ckan.csv
- Downloaded: 2026-10-20T11:12:55Z
- Coverage: Great Britain only (Northern Ireland is not included).

## Licence and attribution
- Licence: NESO Open Data Licence (licence id ESO on the NESO data portal), https://www.neso.energy/data-portal/ngeso-open-licence. Based on the Open Government Licence v3.0 with NESO amendments. It permits copying, publishing, distributing, transmitting and adapting the data, including commercially, provided the source is acknowledged.
- Attribution: Supported by National Energy SO Open Data.

## Files
| File | Rows | SHA256 |
|------|------|--------|
| neso_generation_mix_download.csv (full download, changes as NESO updates) | 312,067 | d86d1d197e0b50a8407dbb3d5f1293ba10020dc15ba18f7f249a136741e77ab3 |
| neso_generation_mix_to_2026-09-30.csv (frozen snapshot, used by every step) | 311,136 | 44198a5f54f4ace4441a76face62c24e1ae909faec826d28ab4ba5bd266febc8 |

- Snapshot rule: keep rows with DATETIME before 2026-10-01T00:00:00, so the last half-hour is 2026-09-30 23:30 UTC.
- Snapshot span: 2009-01-01T00:00:00 to 2026-09-30T23:30:00, half-hourly.
- A rebuilt snapshot reproduces this hash only if NESO has not revised historical values. NESO states that its data is subject to change through a cleansing process; if the hash differs, the snapshot has been revised upstream.

## Columns
DATETIME, GAS, COAL, NUCLEAR, WIND, WIND_EMB, HYDRO, IMPORTS, BIOMASS, OTHER, SOLAR, STORAGE, GENERATION, CARBON_INTENSITY, LOW_CARBON, ZERO_CARBON, RENEWABLE, FOSSIL, and a `_perc` share column for each of GAS through FOSSIL. Generation columns are in MW.

## Wind series
- Target: GB transmission-metered wind generation (NESO WIND column, excludes embedded wind).
- `WIND` does not include embedded (distribution-connected) wind. Embedded wind is the separate column `WIND_EMB`. Evidence: GENERATION equals the sum of GAS, COAL, NUCLEAR, WIND, WIND_EMB, HYDRO, IMPORTS, BIOMASS, OTHER, SOLAR and STORAGE to within 1 MW in 99.98% of rows, so WIND and WIND_EMB are separate addends.
- NESO publishes embedded generation as an estimate, while `WIND` is transmission-metered outturn.

## Facts that affect cleaning
- DATETIME has no time zone offset. Every UTC day, including all 35 GB clock-change Sundays, has exactly 48 rows, which is consistent with UTC; a local-time series would show 46 or 50 rows on those days.
- The file is not in strict chronological order (3 rows out of order). Cleaning sorts by timestamp.
- NESO's dataset notes state that seasonal decomposition is applied to correct missing or irregular data points, and that net-negative values are curtailed at zero.
- Full cleaning results: results/cleaning_report.md.

## Committed hourly slice
- File: data/wind_hourly_2024-09-01_2026-09-30.csv.gz (tracked). Columns: timestamp_utc (hour start, UTC) and wind_mw (hourly mean of the NESO WIND column, MW). Derived from the frozen snapshot by src.prepare; values are unchanged apart from hourly averaging.
- Range: 2024-09-01 00:00 to 2026-09-30 23:00 UTC, 18,240 hours, no gaps.
- Why this range: the earliest value the protocol needs is 2024-09-24 00:00 UTC (168 hours before the first training origin, 2024-10-01 00:00, for the weekly lag features). The slice starts 23 days earlier. SARIMA order selection (from 2025-08-06), calibration windows and baseline lags all fall later.
- Written deterministically (gzip with no file name and mtime 0, LF line endings), so it rebuilds to the same bytes from the raw snapshot.
- Slice SHA256: `a19c31ad552c138a7fbefd89261f141f0ebaaec57783b420912b8fa7826e5056`
- Attribution for this file: Supported by National Energy SO Open Data.
