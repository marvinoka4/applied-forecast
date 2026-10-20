"""Shared constants for the GB wind forecasting backtest.

Every value here is fixed in PROTOCOL.md. Change it there first.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
SNAPSHOT_JSON = ROOT / "data" / "snapshot.json"
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"

SOURCE_URL = (
    "https://api.neso.energy/dataset/88313ae5-94e4-4ddc-a790-593554d8c6b9/"
    "resource/f93d1835-75bc-43e5-84ad-12472b180a98/download/df_fuel_ckan.csv"
)
RAW_DOWNLOAD = DATA_RAW / "neso_generation_mix_download.csv"
RAW_SNAPSHOT = DATA_RAW / "neso_generation_mix_to_2026-09-30.csv"
HOURLY = DATA_PROCESSED / "wind_hourly.csv"

# Snapshot cutoff: last half-hour kept is 2026-09-30 23:30 UTC.
CUTOFF_EXCLUSIVE = "2026-10-01T00:00:00"

TARGET_COLUMN = "WIND"

# Backtest: one forecast origin at 00:00 UTC each day.
TEST_START = "2025-10-01"
TEST_END = "2026-09-30"
HORIZON = 24
REFIT_EVERY_DAYS = 7
TRAIN_WINDOW_DAYS = 365
CALIBRATION_DAYS = 56
SARIMA_FIT_DAYS = 56

SEED = 42
