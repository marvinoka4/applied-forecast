# Data snapshot

Raw files live in data/raw/ and are not committed. Rebuild them with `python -m src.download_data`; data/snapshot.json holds the same facts in machine-readable form, and `src.prepare` refuses to run if the snapshot hash does not match.

## Source
- Dataset: NESO Data Portal, "Historic GB Generation Mix" (dataset id historic-generation-mix), NESO Open Data Licence.
- URL: https://api.neso.energy/dataset/88313ae5-94e4-4ddc-a790-593554d8c6b9/resource/f93d1835-75bc-43e5-84ad-12472b180a98/download/df_fuel_ckan.csv
- Downloaded: 2026-10-20T11:12:55Z
- Coverage: Great Britain only (Northern Ireland is not included).

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
- Target column: `WIND`.
- `WIND` does not include embedded (distribution-connected) wind. Embedded wind is the separate column `WIND_EMB`. Evidence: GENERATION equals the sum of GAS, COAL, NUCLEAR, WIND, WIND_EMB, HYDRO, IMPORTS, BIOMASS, OTHER, SOLAR and STORAGE to within 1 MW in 99.98% of rows, so WIND and WIND_EMB are separate addends.
- NESO publishes embedded generation as an estimate, while `WIND` is transmission-metered outturn.

## Facts that affect cleaning
- DATETIME has no time zone offset. Every UTC day, including all 35 GB clock-change Sundays, has exactly 48 rows, which is consistent with UTC; a local-time series would show 46 or 50 rows on those days.
- The file is not in strict chronological order (3 rows out of order). Cleaning sorts by timestamp.
- NESO's dataset notes state that seasonal decomposition is applied to correct missing or irregular data points, and that net-negative values are curtailed at zero.
- Full cleaning results: results/cleaning_report.md.
