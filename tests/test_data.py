import gzip
import hashlib
import io

import pandas as pd

from src.config import SLICE, TEST_END, TEST_START, TRAIN_WINDOW_DAYS
from src.prepare import expected_slice_sha


def test_committed_slice_matches_snapshot_sha256():
    recorded = expected_slice_sha()
    assert recorded is not None, "data/SNAPSHOT.md has no 'Slice SHA256' line"
    assert hashlib.sha256(SLICE.read_bytes()).hexdigest() == recorded


def test_committed_slice_covers_every_protocol_window():
    text = gzip.decompress(SLICE.read_bytes())
    hourly = pd.read_csv(io.BytesIO(text), index_col="timestamp_utc",
                         parse_dates=["timestamp_utc"])["wind_mw"]
    first_train_origin = pd.Timestamp(TEST_START, tz="UTC") - pd.Timedelta(days=TRAIN_WINDOW_DAYS)
    earliest_needed = first_train_origin - pd.Timedelta(hours=168)
    assert hourly.index.min() <= earliest_needed
    assert hourly.index.max() == pd.Timestamp(f"{TEST_END} 23:00", tz="UTC")
    expected = pd.date_range(hourly.index.min(), hourly.index.max(), freq="1h")
    assert hourly.index.equals(expected)
    assert not hourly.isna().any()
