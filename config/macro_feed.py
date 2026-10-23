"""Fail-closed v2 macro snapshots; source evidence remains a human-reviewed archive."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

HEADER = (
    "schema_version", "timestamp_utc", "dxy_change_pct", "us10y_change_bps",
    "real_yield_change_bps", "high_impact_news_block", "dxy_observed_at_utc",
    "us10y_observed_at_utc", "real_yield_observed_at_utc", "news_observed_at_utc",
    "news_valid_until_utc", "provenance_sha256",
)
MAX_AGE = timedelta(minutes=15)
UTC = timezone.utc
_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def parse_utc(value: str) -> datetime:
    """The shared Python/EA lexical subset is exact seconds and uppercase Z."""
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise ValueError("timestamp must be exact-second UTC YYYY-MM-DDTHH:MM:SSZ")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid UTC timestamp") from exc
    if result.year < 1970 or result == datetime(1970, 1, 1, tzinfo=UTC):
        raise ValueError("timestamp must be after the Unix epoch")
    return result


def _clock(now: datetime | None) -> datetime:
    now = now if now is not None else datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("validation clock must be timezone-aware UTC")
    return now


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Snapshot:
    schema_version: str
    timestamp_utc: datetime
    dxy_change_pct: float
    us10y_change_bps: float
    real_yield_change_bps: float
    high_impact_news_block: bool
    dxy_observed_at_utc: datetime
    us10y_observed_at_utc: datetime
    real_yield_observed_at_utc: datetime
    news_observed_at_utc: datetime
    news_valid_until_utc: datetime
    provenance_sha256: str

    def as_dict(self) -> dict:
        return {name: _stamp(value) if isinstance(value, datetime) else value
                for name, value in vars(self).items()}


def validate_csv(content: str, *, now: datetime | None = None) -> Snapshot:
    """Validate on every consumption, including original observations/calendar expiry."""
    now = _clock(now)
    if not isinstance(content, str):
        raise ValueError("CSV must be text")
    # One unquoted header + row, optional final LF/CRLF. Reject blank/extra lines,
    # quoted cells, bare CR, BOM, and whitespace rather than normalizing them.
    text = content.replace("\r\n", "\n")
    if "\r" in text or '"' in text or "\ufeff" in text or "\x00" in text:
        raise ValueError("noncanonical CSV")
    if text.endswith("\n"):
        text = text[:-1]
    rows = text.split("\n")
    if len(rows) != 2 or rows[0].split(",") != list(HEADER):
        raise ValueError("expected exact v2 header and one complete unquoted row")
    fields = rows[1].split(",")
    if len(fields) != len(HEADER) or fields[0] != "2":
        raise ValueError("expected macro CSV schema_version 2")
    snapshot = parse_utc(fields[1])
    if not timedelta(0) <= now - snapshot <= MAX_AGE:
        raise ValueError("macro snapshot is future-dated or older than 15 minutes")
    values = []
    for name, raw in zip(HEADER[2:5], fields[2:5]):
        if not _NUMBER.fullmatch(raw):
            raise ValueError(f"{name} must be an unquoted decimal without exponent/whitespace")
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
        values.append(value)
    if fields[5] not in ("0", "1"):
        raise ValueError("high_impact_news_block must be exactly 0 or 1")
    observed = [parse_utc(raw) for raw in fields[6:10]]
    for stamp in observed[:3]:
        if stamp > snapshot or not timedelta(0) <= now - stamp <= MAX_AGE:
            raise ValueError("numeric source observation is future-dated or older than 15 minutes")
    expires = parse_utc(fields[10])
    if not observed[3] <= snapshot <= now <= expires:
        raise ValueError("calendar observation order/validity is invalid or expired")
    if not _DIGEST.fullmatch(fields[11]):
        raise ValueError("provenance_sha256 must be 64 lowercase hexadecimal characters")
    return Snapshot("2", snapshot, *values, fields[5] == "1", *observed, expires, fields[11])


def validate_snapshot_dict(payload: dict, *, now: datetime | None = None) -> Snapshot:
    """Validate the API's JSON macro object with the same v2 consumer policy."""
    if not isinstance(payload, dict) or set(payload) != set(HEADER):
        raise ValueError("expected exactly the v2 macro fields")
    fields = []
    for name in HEADER:
        value = payload[name]
        if name in HEADER[2:5]:
            if type(value) not in (int, float):
                raise ValueError("macro JSON numbers must be finite numeric scalars")
            try:
                finite = math.isfinite(value)
            except (OverflowError, ValueError):
                finite = False
            if not finite:
                raise ValueError("macro JSON numbers must be finite numeric scalars")
            fields.append(format(Decimal(str(value)), "f"))
        elif name == "high_impact_news_block":
            if type(value) is not bool:
                raise ValueError("macro JSON news flag must be a boolean")
            fields.append("1" if value else "0")
        elif not isinstance(value, str) or any(c in value for c in ",\r\n"):
            raise ValueError("macro JSON metadata must be canonical text")
        else:
            fields.append(value)
    return validate_csv(",".join(HEADER) + "\n" + ",".join(fields) + "\n", now=now)


def load_snapshot(path: str | Path, *, now: datetime | None = None) -> Snapshot:
    try:
        # Preserve line endings: validator, not universal-newline conversion, owns syntax.
        with Path(path).open("r", encoding="utf-8", newline="") as handle:
            content = handle.read()
    except (OSError, UnicodeError) as exc:
        raise ValueError("macro snapshot is unavailable or not UTF-8") from exc
    return validate_csv(content, now=now)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate provenance JSON key")
        result[key] = value
    return result


def provenance_digest(manifest: dict) -> str:
    """SHA256 of sorted-key compact ensure_ascii=True JSON encoded as UTF-8, no newline."""
    try:
        canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("provenance must be finite JSON") from exc
    return hashlib.sha256(canonical).hexdigest()


def validate_provenance(manifest: dict, snapshot: Snapshot, *, now: datetime) -> None:
    """Validate source evidence and bind its exact semantic JSON to the atomic CSV."""
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
    for (field, unit), original_observed in zip(expected_units.items(), (
        snapshot.dxy_observed_at_utc, snapshot.us10y_observed_at_utc,
        snapshot.real_yield_observed_at_utc, snapshot.news_observed_at_utc)):
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
        observed, published, received = (parse_utc(feed.get(key)) for key in
            ("observed_at_utc", "published_at_utc", "received_at_utc"))
        if observed != original_observed:
            raise ValueError(f"{field} observed timestamp disagrees with CSV")
        if not observed <= published <= received <= snapshot.timestamp_utc <= now:
            raise ValueError(f"{field} availability times are inconsistent or in the future")
        if field == "high_impact_news_block":
            expires = parse_utc(feed.get("valid_until_utc"))
            if expires != snapshot.news_valid_until_utc or not received <= now <= expires:
                raise ValueError("event calendar validity disagrees with CSV or has expired")
        elif now - observed > MAX_AGE:
            raise ValueError(f"{field} observation is older than 15 minutes")
    if provenance_digest(manifest) != snapshot.provenance_sha256:
        raise ValueError("CSV provenance digest does not match the archived manifest")


def publish_snapshot(source: str | Path, destination: str | Path,
                     provenance: str | Path, *, now: datetime | None = None) -> Snapshot:
    """Atomically replace one self-contained validity artifact after evidence validation."""
    now = _clock(now)
    try:
        with Path(source).open("r", encoding="utf-8", newline="") as handle:
            content = handle.read()
        manifest = json.loads(Path(provenance).read_text(encoding="utf-8"),
                              object_pairs_hook=_unique_object)
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
