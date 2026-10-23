"""Private frozen HistData quote input under a conditional empirical timebase.

No downloads, interpolation, sorting, general deduplication, broker calibration,
trading or performance calculation. Original archives are never changed.
"""
from __future__ import annotations

import argparse
import calendar
from collections import Counter
from datetime import datetime, timezone
import hashlib
import heapq
import json
from pathlib import Path
import re
import tempfile
import zipfile

from repair_histdata_duplicates import PLANS, _repair_verified_archive, checked_members

START = 1698796800000  # UTC 2023-11-01 inclusive.
END = 1735689600000    # UTC 2025-01-01 exclusive.
HOUR = 3600000
EXPECTED_HOURS = 10248
TIMEBASE = "EMPIRICALLY_CALIBRATED_RESEARCH_TIMEBASE_NOT_FULLY_CERTIFIED"
RAW_SHA256 = {
    "202310": "dc29013c1f8403d0763de0b5a7462e57eb347b5095c12663da2defb389d58d76",
    "202311": "d6cb3e5be053f9d049bf3fd60a2723c8d74a5eb9c8ee2829b82170718cc41383",
    "202312": "aa9937564474a11738c863a9f3498ce94433c0ff2bf93b386d7621cdf9a1b3b7",
    "202401": "5b73733b7e1fcc5f10943602d83e54396338f7e106a2f80f03605eabf37a8990",
    "202402": "fedd441ffc428d7b8556f5328c3017fdc87b7088a0419dcd688c968ad9ceb2eb",
    "202403": "27719c29ee4aed7a36678a9050db035fa0330f66862a01f0cd8ccbbdc6e75457",
    "202404": "e7f0a460fc2b20fdc9c06fc247802a811fec43dad7255c592f17f8365754e207",
    "202405": "ec9128f89afb2091912310ef55a1cd6006475f27817707a0d2c08983fd74b5aa",
    "202406": "a94e12301134b02899f8402d6f990fb65d2e2a837daf243cb2a642625cb8a980",
    "202407": "cec29b35b592b3ca9810b84e0af81ea6e84af78d1d16f22e2ee2eb4bddb7c810",
    "202408": "b8a47d911027bccd9a51ed1cdfc0241978551b9191ae52ca7d31da0df8b34ef6",
    "202409": "65d6a9049577f6ce96b39a26090a5ce15486f4247b54cb1acee9fc92e7330ef9",
    "202410": "32d92448517fa1ef292a8f14ef2be52af090c9cbae72ec10bbad240ba30343c1",
    "202411": "db22c7a181eb6475dfecd36f8c8d247838c7befcb1f296d6755f6a276062fc1e",
    "202412": "f1b5e51db7807cb11369069da5e0be8592bfa44d5277e1b7c25564b2fa069e32",
}
EVIDENCE = {
    "control_comparison_sha256": "d9e7b7a7002fa58a1f1ce91c7d9931aba0df669ccae2f03b8ed9b6e51361cafb",
    "transition_comparison_sha256": "bb7da6ff4b15054f43e656b5183f5e3cfb5594cfc2d80c9bd486c2be929677f2",
    "reference": "EXNESS_OFFICIAL_PUBLIC_XAUUSDm_ARCHIVE_PARTIAL_2024",
    "reference_archive_sha256": "e20f29457ede7b107ade6feca2f64ca33eb7e118171497300a89bccee3c94047",
    "method": "Pearson of consecutive observed-minute midpoint changes; exact UTC intersections; no interpolation",
    "candidate_offsets": [3, 4, 5, 6],
    "minimum_pairs": 300, "minimum_correlation": 0.8, "minimum_margin": 0.2,
    "main_controls_utc_window": "13:00 inclusive to 21:00 exclusive",
    "strong_winter_controls": ["20240116", "20240308", "20240312", "20240325", "20241028"],
    "strong_summer_controls": ["20240402", "20240715", "20241021"],
    "excluded_anomalous_reference_day": "20241104",
    "transition_controls": [
        {"day": "20240328", "offset": 5, "pairs": 956, "correlation": 0.9957777404002296},
        {"day": "20240331", "offset": 4, "pairs": 293, "correlation": 0.9941294293804301,
         "below_predeclared_minimum_pairs": True, "evidence_strength": "WEAK"},
        {"day": "20240401", "offset": 4, "pairs": 1205, "correlation": 0.9952101971198946},
        {"day": "20241025", "offset": 4, "pairs": 1017, "correlation": 0.99350079533504},
        {"day": "20241027", "offset": 5, "pairs": 414, "correlation": 0.9945867089410729},
    ],
    "limitations": ["March31 control has only293 pairs, below300; boundary is a research assumption",
                    "Reference has two November sequence anomalies and ends December15, not full2024",
                    "2023 warmup and every unsampled day lack independent calibration"],
    "full_timebase_certification": False,
}


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def offset_for_date(date):
    return 4 if b"20240331" <= date <= b"20241026" else 5


def point_integer(value):
    if not re.fullmatch(rb"[0-9]+\.[0-9]+", value):
        raise ValueError("quote must be a finite positive decimal")
    whole, fraction = value.split(b".")
    if len(fraction) > 3 and fraction[3:].strip(b"0"):
        raise ValueError("price is not on the frozen .001 tick grid")
    result = int(whole) * 1000 + int((fraction + b"000")[:3])
    if result <= 0:
        raise ValueError("nonpositive price")
    return result


def format_price(points):
    return f"{points // 1000}.{points % 1000:03d}"


def parse_row(line, month, day_cache):
    if len(line) > 1024 or not line.endswith(b"\n"):
        raise ValueError("overlong or unterminated source row")
    columns = line.rstrip(b"\r\n").split(b",")
    if len(columns) != 4:
        raise ValueError("expected headerless DateTime,Bid,Ask,Volume four-column rows")
    stamp, bid, ask, volume = columns
    if (not re.fullmatch(rb"\d{8} \d{9}", stamp)
            or not stamp.startswith(month.encode())):
        raise ValueError("invalid source timestamp or month")
    date = stamp[:8]
    if date not in day_cache:
        parsed = datetime.strptime(date.decode(), "%Y%m%d")
        day_cache[date] = calendar.timegm(parsed.timetuple()) * 1000 + offset_for_date(date) * HOUR
    hour, minute, second, millis = int(stamp[9:11]), int(stamp[11:13]), int(stamp[13:15]), int(stamp[15:18])
    if hour > 23 or minute > 59 or second > 59:
        raise ValueError("invalid clock component")
    if not re.fullmatch(rb"[0-9]+(?:\.[0-9]+)?", volume):
        raise ValueError("invalid placeholder volume")
    bid, ask = point_integer(bid), point_integer(ask)
    if ask < bid:
        raise ValueError("ask below bid")
    return day_cache[date] + ((hour * 60 + minute) * 60 + second) * 1000 + millis, bid, ask, stamp


def stream_month(path, month, output, state):
    source_hash = hashlib.sha256()
    normalized_source_rows = 0
    day_cache = {}
    local_previous = None
    csv_name, txt_name = f"DAT_ASCII_XAUUSD_T_{month}.csv", f"DAT_ASCII_XAUUSD_T_{month}.txt"
    with zipfile.ZipFile(path) as z:
        infos = checked_members(z)
        if {i.filename for i in infos} != {csv_name, txt_name}:
            raise ValueError("unexpected monthly CSV/header or metadata member")
        with z.open(csv_name) as f:
            for row, line in enumerate(f, 1):
                source_hash.update(line)
                try:
                    t, bid, ask, stamp = parse_row(line, month, day_cache)
                    if local_previous is not None and stamp < local_previous:
                        raise ValueError("source timestamp reversal after whitelisted repair")
                    if state["previous_all"] is not None and t < state["previous_all"]:
                        raise ValueError("UTC reversal or cross-file overlap")
                except ValueError as exc:
                    raise ValueError(f"{month} source row {row}: {exc}") from exc
                local_previous, state["previous_all"] = stamp, t
                if not START <= t < END:
                    continue
                normalized_source_rows += 1
                encoded = f"{t},{format_price(bid)},{format_price(ask)}\n".encode("ascii")
                output.write(encoded)
                state["hash"].update(encoded)
                index = (t - START) // HOUR
                hour = state["hours"][index]
                hour["ticks"] += 1
                if hour["first_utc_msc"] is None:
                    hour["first_utc_msc"] = t
                hour["last_utc_msc"] = t
                previous = state["last"]
                if previous is not None:
                    gap = (t - previous, previous, t)
                    if len(state["gaps"]) < 20:
                        heapq.heappush(state["gaps"], gap)
                    elif gap > state["gaps"][0]:
                        heapq.heapreplace(state["gaps"], gap)
                    if t == previous:
                        state["same_timestamp_pairs"] += 1
                if state["first"] is None:
                    state["first"] = t
                state["last"] = t
                state["rows"] += 1
        if local_previous is None:
            raise ValueError("empty monthly CSV")
        metadata = z.read(txt_name)
        return {"month": month, "source_csv_rows_after_whitelisted_repair": row,
                "included_rows": normalized_source_rows, "csv_sha256_after_whitelisted_repair": source_hash.hexdigest(),
                "original_source_metadata_sha256": hashlib.sha256(metadata).hexdigest(),
                "original_source_metadata_preserved": True, "crc_verified": True,
                "members_crc32": {i.filename: f"{i.CRC:08x}" for i in infos}}


def convert(archive_dir, output, quality):
    archive_dir, output, quality = Path(archive_dir), Path(output), Path(quality)
    if output == quality or output.exists() or quality.exists():
        raise ValueError("distinct output and quality paths must not already exist")
    files = {}
    for path in archive_dir.glob("*.zip"):
        match = re.fullmatch(r"HISTDATA_COM_ASCII_XAUUSD_T_(\d{6})\.zip", path.name)
        if not match or match[1] not in RAW_SHA256:
            raise ValueError("unknown monthly ZIP in input directory")
        files[match[1]] = path
    if set(files) != set(RAW_SHA256):
        raise ValueError("all15 predeclared original monthly ZIPs are required")
    # Verify the entire frozen source set before calculating any derived quote.
    for month, path in files.items():
        if file_sha(path) != RAW_SHA256[month]:
            raise ValueError(f"{month} original ZIP SHA mismatch")
    output.parent.mkdir(parents=True, exist_ok=True)
    quality.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="histdata-research-") as temporary:
        temp = Path(temporary)
        normalized = temp / "quotes.csv"
        state = {"hash": hashlib.sha256(), "rows": 0, "first": None, "last": None,
                 "previous_all": None, "gaps": [], "same_timestamp_pairs": 0,
                 "hours": [{"utc_hour": datetime.fromtimestamp((START + n * HOUR) / 1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                            "ticks": 0, "first_utc_msc": None, "last_utc_msc": None}
                           for n in range(EXPECTED_HOURS)]}
        repairs, archives = [], []
        with normalized.open("wb") as out:
            header = b"time_utc_msc,bid,ask\n"
            out.write(header)
            state["hash"].update(header)
            for month in sorted(files):
                path = files[month]
                if month in PLANS:
                    repaired = temp / path.name
                    repairs.append(_repair_verified_archive(path.read_bytes(), PLANS[month], repaired))
                    path = repaired
                record = stream_month(path, month, out, state)
                record["raw_zip_sha256"] = RAW_SHA256[month]
                archives.append(record)
                print(f"Verified {month}: {record['source_csv_rows_after_whitelisted_repair']} source rows", flush=True)
        if not state["rows"]:
            raise ValueError("no observed ticks in frozen window")
        unknown = [h["utc_hour"] for h in state["hours"] if not h["ticks"]]
        daily = Counter()
        for hour in state["hours"]:
            daily[hour["utc_hour"][:10]] += hour["ticks"]
        result = {
            "schema": "agai.histdata-empirical-research-quality/1", "status": "STRUCTURAL_CHECKS_PASSED",
            "reference_scope": "OBSERVED_TICKS_REFERENCE", "coverage_status": "UNVERIFIED_SOURCE_GAPS",
            "source_provider": "HISTDATA.COM", "source_format": "GENERIC_ASCII_TICKS_BID_ASK",
            "source_replaces_dukascopy": True, "data_are_dukascopy_quotes": False,
            "source_timezone": "EMPIRICAL_SOURCE_LOCAL_RESEARCH_RULE_2024_SUMMER_PLUS4_OTHER_PLUS5",
            "timebase_status": TIMEBASE, "timebase_fully_certified": False, "timebase_confidence_certified": False,
            "timebase_rule": {"source_local_dates_plus4_inclusive": ["20240331", "20241026"],
                              "other_2023_2024_source_local_dates_plus5": True,
                              "conversion": "research UTC = source local time + declared offset",
                              "official_fixed_EST_claim_not_used_as_calibration": True},
            "timebase_evidence": EVIDENCE,
            "full_2024_coverage_verified": False, "coverage_confidence_certified": False,
            "provenance_and_license": "NOT_INDEPENDENTLY_AUTHENTICATED_OR_REDISTRIBUTION_LICENSED",
            "broker_quote_or_contract_calibration": "NOT_VALIDATED",
            "frozen_from_utc": "2023-11-01T00:00:00Z", "frozen_to_utc_exclusive": "2025-01-01T00:00:00Z",
            "required_local_months": sorted(RAW_SHA256), "raw_archives": archives,
            "whitelisted_exact_duplicate_repairs": repairs,
            "original_archives_and_original_metadata_unchanged": True,
            "general_deduplication_sort_interpolation_or_synthetic_quotes": False,
            "rows": state["rows"], "normalized_sha256": state["hash"].hexdigest(),
            "first_utc_msc": state["first"], "last_utc_msc": state["last"],
            "same_timestamp_pairs_preserved": state["same_timestamp_pairs"],
            "expected_hours": EXPECTED_HOURS, "expected_hours_are_utc_grid_not_download_successes": True,
            "unclassified_failed_hours": [], "download_failures": "NOT_APPLICABLE_OFFLINE_ORIGINAL_ARCHIVES",
            "unobserved_hour_count": len(unknown), "unobserved_hours": unknown,
            "unobserved_hour_classification": "UNKNOWN_SOURCE_GAP",
            "zero_quote_hours_are_not_assumed_market_closures": True,
            "hourly_coverage": state["hours"], "daily_observed_tick_counts": dict(sorted(daily.items())),
            "largest_quote_gaps_milliseconds_with_edges": sorted(state["gaps"], reverse=True),
            "coverage_review_required": True, "source_gap_review_status": "NOT_VALIDATED_NO_AUTHENTICATED_SESSION_CALENDAR",
            "volume_is_not_verified_executed_trade_volume": True,
            "private_raw_or_normalized_quotes_not_for_public_redistribution": True,
            "authorizes_trading_or_performance": False,
        }
        # Copy a completed private CSV only after all15 months and CRCs succeed.
        # Quality is published last; consumers must require its matching hash.
        import shutil
        shutil.copyfile(normalized, output)
        quality.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quality", type=Path, required=True)
    args = parser.parse_args()
    convert(args.archive_dir, args.output, args.quality)


if __name__ == "__main__":
    main()
