# Run log

Every model run, with start and end time (UTC) and outcome.

| Run | Start (UTC) | End (UTC) | Seconds | Outcome |
|-----|-------------|-----------|---------|---------|
| LightGBM timing, one refit (2025-10-01) | 2026-10-20 21:30:09 | 2026-10-20 21:31:00 | 51.6 | features (once per backtest) 3.7 s; one refit (24 models, conformal, 7 origins) 47.9 s; 7416 training rows at h=1, 56 calibration origins |
| SARIMA order selection (KPSS then AIC grid) | 2026-10-20 21:29:36 | 2026-10-20 21:31:10 | 94.0 | d=1 (KPSS 1.231 > 0.463); 27 fits, 25 converged; selected (1,1,0)(1,0,1,24) AIC 20013.104 |
| SARIMA timing, one refit (2025-10-01) | 2026-10-20 21:31:26 | 2026-10-20 21:31:31 | 5.4 | converged=True; fit 4.1 s; fit plus 7 origins 5.4 s |
| Runtime estimate for 53 refits | 2026-10-20 21:31:40 | 2026-10-20 21:31:40 | 0.0 | SARIMA 53 x 5.4 s = about 5 min; LightGBM 3.7 s features + 53 x 47.9 s = about 43 min; total about 48 min, under the 3 hour limit; proceeding |
| SARIMA backtest, 53 refits, order (1, 1, 0)(1, 0, 1, 24) | 2026-10-20 21:31:47 | 2026-10-20 21:34:49 | 182.4 | 53 refits, 0 convergence failures |
| LightGBM backtest, 53 refits | 2026-10-20 21:31:47 | 2026-10-20 22:06:21 | 2074.3 | 53 refits, 8760 forecast rows |
| LightGBM diagnostic fits (not part of results) | 2026-10-20 22:08:05 | 2026-10-20 22:08:05 | 0.0 | refits 2025-10-01 and 2026-04-01, horizons 1, 6, 12, 24 refitted to compare training and calibration-window MAE with persistence and to read gain importance; no protocol choice changed and no reported metric uses these fits |
| LightGBM post-hoc variant without target day-of-year features, 53 refits | 2026-10-20 22:28:17 | 2026-10-20 23:05:58 | 2260.7 | 53 refits, 8760 forecast rows |
