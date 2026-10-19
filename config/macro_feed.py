"""Fail-closed validation and atomic publishing of manually sourced macro CSV."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import io
import json
import math
import os
from pathlib import Path
import re
import tempfile

HEADER = (
    "timestamp_utc", "dxy_change_pct", "us10y_change_bps",
    "real_yield_change_bps", "high_impact_news_block",
)
MAX_AGE = timedelta(minutes=15)
UTC = timezone.utc
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)\Z")
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


def parse_utc(value: str) -> datetime:
    """Only UTC ISO-8601, with explicit Z or +00:00, is accepted."""
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise ValueError("timestamp must be ISO-8601 UTC with Z or +00:00")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid UTC timestamp") from exc


def _clock(now: datetime | None) -> datetime:
    now = now if now is not None else datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("validation clock must be timezone-aware UTC")
    return now


@dataclass(frozen=True)
class Snapshot:
    timestamp_utc: datetime
    dxy_change_pct: float
    us10y_change_bps: float
    real_yield_change_bps: float
    high_impact_news_block: bool

    def as_dict(self) -> dict:
        return {
            "timestamp_utc": self.timestamp_utc.isoformat().replace("+00:00", "Z"),
            "dxy_change_pct": self.dxy_change_pct,
            "us10y_change_bps": self.us10y_change_bps,
            "real_yield_change_bps": self.real_yield_change_bps,
            "high_impact_news_block": self.high_impact_news_block,
        }


def validate_csv(content: str, *, now: datetime | None = None) -> Snapshot:
    """Accept exactly one snapshot. Invalid input raises; never substitute zeros."""
    now = _clock(now)
    try:
        rows = list(csv.reader(io.StringIO(content, newline=""), strict=True))
    except csv.Error as exc:
        raise ValueError("malformed CSV") from exc
    if len(rows) != 2 or tuple(rows[0]) != HEADER or len(rows[1]) != len(HEADER):
        raise ValueError("expected exact ordered header and exactly one complete row")
    timestamp = parse_utc(rows[1][0])
    age = now - timestamp
    if age < timedelta(0) or age > MAX_AGE:
        raise ValueError("macro snapshot is future-dated or older than 15 minutes")
    numbers = []
    for name, raw in zip(HEADER[1:4], rows[1][1:4]):
        if not _NUMBER.fullmatch(raw):
            raise ValueError(f"{name} must contain a finite number without whitespace")
        try:
            number = float(raw)
        except ValueError as exc:
            raise ValueError(f"{name} is not numeric") from exc
        if not math.isfinite(number):
            raise ValueError(f"{name} must be finite")
        numbers.append(number)
    if rows[1][4] not in ("0", "1"):
        raise ValueError("high_impact_news_block must be exactly 0 or 1")
    return Snapshot(timestamp, *numbers, rows[1][4] == "1")


def load_snapshot(path: str | Path, *, now: datetime | None = None) -> Snapshot:
    try:
        content = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError("macro snapshot is unavailable or not UTF-8") from exc
    return validate_csv(content, now=now)


def validate_provenance(manifest: dict, snapshot: Snapshot, *, now: datetime) -> None:
    """Require human-recorded sources and availability times before publication."""
    now = _clock(now)
    if not isinstance(manifest, dict) or manifest.get("mode") != "manual":
        raise ValueError("provenance mode must be manual")
    expected_units = {
        "dxy_change_pct": "percent", "us10y_change_bps": "basis_points",
        "real_yield_change_bps": "basis_points", "high_impact_news_block": "boolean",
    }
    feeds = manifest.get("feeds")
    if not isinstance(feeds, dict) or set(feeds) != set(expected_units):
        raise ValueError("provenance must describe all four fields")
    for field, unit in expected_units.items():
        feed = feeds[field]
        if not isinstance(feed, dict):
            raise ValueError(f"invalid provenance for {field}")
        for key in ("source", "instrument", "observation_window", "license_note"):
            if not isinstance(feed.get(key), str) or not feed[key].strip():
                raise ValueError(f"{field} needs {key}")
        if feed.get("unit") != unit:
            raise ValueError(f"incorrect unit for {field}")
        if field != "high_impact_news_block" and feed["observation_window"] != "1-day":
            raise ValueError(f"{field} requires the documented 1-day observation window")
        observed, published, received = (
            parse_utc(feed.get(key))
            for key in ("observed_at_utc", "published_at_utc", "received_at_utc")
        )
        if not observed <= published <= received <= snapshot.timestamp_utc <= now:
            raise ValueError(f"{field} availability times are inconsistent or in the future")
        if field == "high_impact_news_block":
            expires = parse_utc(feed.get("valid_until_utc"))
            if not received <= now <= expires:
                raise ValueError("event calendar validity has expired")
        elif now - observed > MAX_AGE:
            raise ValueError(f"{field} observation is older than 15 minutes")


def publish_snapshot(source: str | Path, destination: str | Path,
                     provenance: str | Path, *, now: datetime | None = None) -> Snapshot:
    """Validate before touching destination, then atomically replace that CSV only."""
    now = _clock(now)
    source = Path(source)
    try:
        content = source.read_text(encoding="utf-8")
        manifest = json.loads(Path(provenance).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("source or provenance is unavailable/malformed") from exc
    snapshot = validate_csv(content, now=now)
    validate_provenance(manifest, snapshot, now=now)
    destination = Path(destination)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--provenance", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = publish_snapshot(args.source, args.destination, args.provenance)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"BLOCKED: {exc}\n")
    print(json.dumps(result.as_dict(), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
