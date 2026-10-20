# Forecasting protocol

Fixed on 2026-10-20, before any model was fitted. Any later change is recorded in the change log at the end with its date and reason. Choices are made on data before 1 Oct 2025 only; nothing is tuned on the test period.

## Data
- Source: NESO Data Portal, "Historic GB Generation Mix", half-hourly, frozen at 30 Sep 2026 23:30 UTC. See data/SNAPSHOT.md for the URL, download time, row count and SHA256.
- Target: GB wind generation, hourly, from the `WIND` column. Unit: MW (average power over the hour).
- Hourly value: mean of the two half-hourly values that start in the hour, labelled by hour start in UTC. An hour with either half-hour missing is missing; nothing is filled.
- All timestamps are UTC, so GB clock changes do not create gaps or duplicate hours.

## Forecast task
- Origin: 00:00 UTC on each day of the test period.
- Horizon: hours 1 to 24 of that day. Horizon h is the hour starting at origin + (h - 1) hours.
- Information set: a forecast for an origin may use only values for hours that start before the origin. The last usable value is the hour 23:00 to 00:00 of the previous day.

## Backtest
- Test period: 1 Oct 2025 to 30 Sep 2026 (365 origins, 8,760 origin and horizon pairs).
- Refits: every 7 days, on 1 Oct 2025 and every 7th day after (53 refits). A model fitted at a refit date is used, with its parameters fixed, for the origins from that date until the next refit. Between refits, forecasts are conditioned on all data before each origin.
- Training window: the 365 days before each refit date. Reason: one full year covers every season of the strongly seasonal wind regime, so no refit is trained without winter or summer conditions, and the window length is the same for every refit.
- Every window is a half-open interval that ends at the refit date, so no training or calibration target falls in the test week.

## Models
1. Persistence: the last value before the origin, held flat for all 24 hours.
2. Seasonal naive, daily: the value at the same hour on the previous day (lag 24 hours).
3. Seasonal naive, weekly: the value at the same hour one week earlier (lag 168 hours).
4. SARIMA with daily seasonality (period 24 hours), statsmodels SARIMAX.
5. LightGBM on lag and calendar features, direct multi-horizon: one model per horizon h = 1 to 24.

Models 1 to 3 have no parameters and are not refitted.

### SARIMA details
- Fit window: the most recent 56 days of each training window. Reason: a seasonal state-space model with period 24 on a full year of hourly data is slow to fit 53 times on CPU, and its short-memory dynamics gain little from older data.
- Order: chosen once, before the test period, by AIC on the 56 days before 1 Oct 2025, then fixed for all refits. Differencing d is fixed first by a KPSS test on that window (d = 1 if stationarity is rejected at 5%, else d = 0), with D = 0. The grid is p in {1, 2, 3}, q in {0, 1, 2}, P in {0, 1}, Q in {0, 1}, with P + Q at least 1. Reason: AIC comparisons are valid only at a fixed differencing order.
- If a refit fails to converge, the previous refit's parameters are kept for that week and the failure is logged.

### LightGBM details
- Training rows: one row per hourly origin in the first 309 days of the training window (all hours of day, not just 00:00), keeping only rows whose target hour ends before the calibration window starts. Reason: daily origins alone would give about 300 rows per horizon model.
- Features, all computed from values before the origin: the last 24 hourly values; the values 48 and 168 hours before the origin; the target hour's value 24 and 168 hours earlier; means of the last 6, 24 and 168 hours; the standard deviation of the last 24 hours; hour of day of the origin; hour of day, day of week, and sine and cosine of day of year of the target hour.
- Hyperparameters, fixed a priori and not tuned: objective L2, 400 trees, learning rate 0.05, 31 leaves, minimum 20 rows per leaf, row subsampling 0.8 every iteration, feature subsampling 0.8, seed 42, deterministic mode, 1 thread.

## Prediction intervals
- Nominal levels: 80% and 95%.
- SARIMA: the model's native Gaussian prediction intervals.
- LightGBM: split conformal, per horizon. At each refit, the calibration window is the last 56 days of the training window, immediately before the test week. Scores are absolute errors of the model on the 56 daily 00:00 origins in that window. The interval is the point forecast plus or minus the ceil((n + 1)(1 - alpha))-th smallest score, with n = 56. Reason: calibrating on 00:00 origins only matches the test origins, so scores and test errors are exchangeable as far as possible; 56 days balances calibration size against staying close to the test week.
- Baselines have no intervals.

## Metrics
- Point: MAE, RMSE, and MAE relative to the daily seasonal naive (model MAE divided by daily seasonal naive MAE on the same pairs). MAE relative to the weekly seasonal naive is also reported.
- Interval (SARIMA and LightGBM): empirical coverage and mean interval width at 80% and 95%.
- Each metric is reported overall and for each horizon 1 to 24.
- Scoring set: every test origin and horizon pair whose target is observed and whose persistence and seasonal naive inputs are observed. All models are scored on this same set, and its size is reported.

## Other choices
- Target column `WIND` excludes embedded (distribution-connected) wind, which NESO publishes separately as `WIND_EMB`. Reason: `WIND` is metered transmission outturn, while `WIND_EMB` is an estimate; forecasting the metered series avoids mixing in a modelled quantity.
- Seeds: 42 for every random component. Reason: results must be reproducible from a clean clone plus the data snapshot.
- Software: Python 3.12.10 with the pinned versions in requirements.txt, CPU only.

## Known limitations fixed in advance
- No weather forecasts are used, although operational day-ahead wind forecasts depend on them. Results measure what history alone can do.
- The backtest assumes outturn up to the origin is available at the origin. In practice publication lags slightly.
- NESO applies its own correction to missing or irregular points before publishing, so some values may already be imputed.
- One test year is a single realisation of weather; results may differ in another year.

## Change log
- 2026-10-20: protocol fixed.
