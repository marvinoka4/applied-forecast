# Cleaning report

Snapshot: neso_generation_mix_to_2026-09-30.csv (SHA256 44198a5f54f4ace4441a76face62c24e1ae909faec826d28ab4ba5bd266febc8)

## Time zone
- Timestamps carry no offset: True. Parsed as UTC.
- Rows per UTC day: min 48, max 48, days not equal to 48: 0.
- Rows on the 35 GB clock-change Sundays: [48]. 48 on every one is consistent with UTC.

## Duplicates and gaps (half-hourly)
- Rows out of chronological order in the file: 1. Action: sorted by timestamp.
- Duplicate timestamps: 0 rows. Action: none needed.
- Expected half-hours 311136, present 311136, missing 0.
- Missing WIND values after reindexing: 0. Action: left missing, not filled.

## WIND column
- GENERATION equals the sum of GAS, COAL, NUCLEAR, WIND, WIND_EMB, HYDRO, IMPORTS, BIOMASS, OTHER, SOLAR, STORAGE (within 1 MW) in 99.9846% of rows. WIND and WIND_EMB are separate addends, so WIND excludes embedded wind.
- WIND range: 0 to 18439 MW; negative values: 0; exact zeros: 29.
- Test period (2025-10-01 to 2026-09-30) range: 391 to 18439 MW, mean 8716 MW.

## Possible outliers and imputation artefacts (flagged, not changed)
- Flat runs of 6+ identical half-hours: 9 overall, 0 in the test period.
  - 2009-03-28 00:30:00+00:00 for 10 half-hours at 815 MW
  - 2009-06-02 02:00:00+00:00 for 10 half-hours at 4 MW
  - 2009-07-15 04:30:00+00:00 for 8 half-hours at 24 MW
  - 2009-10-12 08:30:00+00:00 for 9 half-hours at 57 MW
  - 2010-03-08 03:30:00+00:00 for 8 half-hours at 6 MW
  - 2010-04-11 01:00:00+00:00 for 8 half-hours at 9 MW
  - 2010-05-04 00:30:00+00:00 for 6 half-hours at 100 MW
  - 2010-09-01 00:00:00+00:00 for 10 half-hours at 6 MW
  - 2014-10-11 02:00:00+00:00 for 6 half-hours at 0 MW
- Half-hour changes above 2000 MW (the 99.99th percentile of all changes is 1595 MW): 5 overall, 0 in the test period.
  - 2018-12-11 12:00:00+00:00: change of 2123 MW, value 2123 MW
  - 2019-03-24 18:00:00+00:00: change of 2268 MW, value 9699 MW
  - 2021-11-23 10:30:00+00:00: change of 2996 MW, value 592 MW
  - 2023-06-07 12:30:00+00:00: change of 2420 MW, value 2420 MW
  - 2023-07-15 23:00:00+00:00: change of 2324 MW, value 7777 MW
- Half-hours at exactly 0 MW that are followed by another 0: 17, last at 2023-06-07 11:30:00+00:00. These look like metering outages (for example 2021-11-23 10:30 to 12:00).
- Action: none of these are changed. NESO states that it already applies seasonal decomposition to correct missing or irregular points, so flat runs may be its imputation.
- Earliest data used by the backtest: 2024-09-24 00:00:00+00:00. Latest flagged point: 2023-07-15 23:00:00+00:00. Flagged points inside the data used: none.

## Hourly aggregation
- Hourly value = mean of the two half-hourly MW values starting in that hour (average power over the hour, MW), labelled by hour start in UTC.
- Hours: 155568, missing (any half-hour missing): 0.
- First hour 2009-01-01 00:00:00+00:00, last hour 2026-09-30 23:00:00+00:00.
