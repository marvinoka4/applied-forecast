"""Append model run records to results/run_log.md."""

from contextlib import contextmanager
from datetime import datetime, timezone

from src.config import RESULTS

RUN_LOG = RESULTS / "run_log.md"
HEADER = (
    "# Run log\n\n"
    "Every model run, with start and end time (UTC) and outcome.\n\n"
    "| Run | Start (UTC) | End (UTC) | Seconds | Outcome |\n"
    "|-----|-------------|-----------|---------|---------|\n"
)


def _now():
    return datetime.now(timezone.utc)


def append(run, start, end, outcome):
    RESULTS.mkdir(parents=True, exist_ok=True)
    if not RUN_LOG.exists():
        RUN_LOG.write_text(HEADER, encoding="utf-8", newline="\n")
    seconds = (end - start).total_seconds()
    row = (f"| {run} | {start:%Y-%m-%d %H:%M:%S} | {end:%Y-%m-%d %H:%M:%S} | "
           f"{seconds:.1f} | {outcome} |\n")
    with open(RUN_LOG, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(row)


@contextmanager
def logged(run):
    """Log a run. The body sets record["outcome"]; an exception is logged as a failure."""
    record = {"outcome": "completed"}
    start = _now()
    try:
        yield record
    except BaseException as exc:
        append(run, start, _now(), f"failed: {type(exc).__name__}: {exc}".replace("|", "/"))
        raise
    append(run, start, _now(), record["outcome"].replace("|", "/"))
