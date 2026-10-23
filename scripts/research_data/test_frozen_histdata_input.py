"""Synthetic protocol tests; optional local original-source sample check."""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import frozen_histdata_input as subject


def msc(iso):
    return int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp() * 1000)


def write_zip(directory, month, data):
    path = Path(directory) / f"HISTDATA_COM_ASCII_XAUUSD_T_{month}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"DAT_ASCII_XAUUSD_T_{month}.csv", data)
        z.writestr(f"DAT_ASCII_XAUUSD_T_{month}.txt", b"ORIGINAL metadata\r\n")
    return path


class ParsingTests(unittest.TestCase):
    def test_empirical_transition_dates_are_explicit_not_us_dst(self):
        examples = [
            (b"20231031 190000000", "202310", "2023-11-01T00:00:00"),
            (b"20240312 120000001", "202403", "2024-03-12T17:00:00.001"),
            (b"20240330 120000001", "202403", "2024-03-30T17:00:00.001"),
            (b"20240331 120000001", "202403", "2024-03-31T16:00:00.001"),
            (b"20241026 120000001", "202410", "2024-10-26T16:00:00.001"),
            (b"20241027 120000001", "202410", "2024-10-27T17:00:00.001"),
        ]
        for stamp, month, utc in examples:
            with self.subTest(stamp=stamp):
                parsed = subject.parse_row(stamp + b",2000.001000,2000.003000,0\n", month, {})
                self.assertEqual(parsed[:3], (msc(utc), 2000001, 2000003))

    def test_invalid_dates_fields_prices_or_missing_ask_rejected(self):
        samples = [
            b"DateTime,Bid,Ask,Volume\n", b"20240230 120000000,1.000,1.001,0\n",
            b"20240201 240000000,1.000,1.001,0\n", b"20240201 120060000,1.000,1.001,0\n",
            b"20240201 120000000,1.0001,1.001,0\n", b"20240201 120000000,NaN,1.001,0\n",
            b"20240201 120000000,0.000,1.001,0\n", b"20240201 120000000,1.001,1.000,0\n",
            b"20240201 120000000,1.000,,0\n", b"20240201 120000000,1.000,1.001\n",
            b"20240101 120000000,1.000,1.001,0\n", b"20240201 120000000,1.000,1.001,0",
        ]
        for line in samples:
            with self.subTest(line=line), self.assertRaises(ValueError):
                subject.parse_row(line, "202402", {})

    def test_tick_grid_format_uses_integer_arithmetic(self):
        for raw in [b"2000.123", b"2000.123000000"]:
            self.assertEqual(subject.format_price(subject.point_integer(raw)), "2000.123")
        self.assertEqual(subject.point_integer(b"2000.1"), 2000100)
        self.assertFalse(subject.EVIDENCE["full_timebase_certification"])
        weak = next(c for c in subject.EVIDENCE["transition_controls"] if c["day"] == "20240331")
        self.assertEqual(weak["pairs"], 293)
        self.assertTrue(weak["below_predeclared_minimum_pairs"])


class FrozenConversionTests(unittest.TestCase):
    def fixture(self, directory, bad_month=None, bad_data=None):
        hashes = {}
        for month in subject.RAW_SHA256:
            stamp = "20231031 190000000" if month == "202310" else month + "01 000000000"
            line = (stamp + ",2000.001000,2000.003000,0\n").encode()
            if month == "202311":
                line += line  # Ordinary equal-time quote rows MUST survive.
            if month == bad_month:
                line = bad_data
            path = write_zip(directory, month, line)
            hashes[month] = subject.file_sha(path)
        return hashes

    def test_full_synthetic_source_set_preserves_same_ms_and_unknown_gaps(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d) / "archives"
            data.mkdir()
            hashes = self.fixture(data)
            output, quality = Path(d) / "ticks.csv", Path(d) / "quality.json"
            originals = {p.name: subject.file_sha(p) for p in data.iterdir()}
            # Only synthetic test fixtures bypass the hard-coded production hashes/repair plans.
            with patch.object(subject, "RAW_SHA256", hashes), patch.object(subject, "PLANS", {}):
                result = subject.convert(data, output, quality)
            with output.open() as f:
                reader = csv.DictReader(f)
                self.assertEqual(reader.fieldnames, ["time_utc_msc", "bid", "ask"])
                quotes = list(reader)
            self.assertEqual(len(quotes), 16)
            self.assertEqual(quotes[1], quotes[2])
            self.assertEqual(result["same_timestamp_pairs_preserved"], 1)
            self.assertEqual(int(quotes[0]["time_utc_msc"]), subject.START)
            self.assertEqual(result["normalized_sha256"], subject.file_sha(output))
            self.assertEqual(result["expected_hours"], 10248)
            self.assertEqual(sum(h["ticks"] for h in result["hourly_coverage"]), 16)
            self.assertEqual(result["unobserved_hour_count"], 10233)
            self.assertEqual(result["unclassified_failed_hours"], [])
            self.assertEqual(result["unobserved_hour_classification"], "UNKNOWN_SOURCE_GAP")
            for key in ["full_2024_coverage_verified", "timebase_fully_certified", "coverage_confidence_certified"]:
                self.assertIs(result[key], False)
            self.assertEqual(result["timebase_status"], subject.TIMEBASE)
            self.assertEqual(json.loads(quality.read_text())["coverage_status"], "UNVERIFIED_SOURCE_GAPS")
            self.assertEqual(originals, {p.name: subject.file_sha(p) for p in data.iterdir()})

    def test_all_sources_hash_checked_before_any_output(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d) / "archives"
            data.mkdir()
            hashes = self.fixture(data)
            hashes["202412"] = "0" * 64
            out, quality = Path(d) / "quotes.csv", Path(d) / "quality.json"
            with patch.object(subject, "RAW_SHA256", hashes), self.assertRaisesRegex(ValueError, "SHA mismatch"):
                subject.convert(data, out, quality)
            self.assertFalse(out.exists())
            self.assertFalse(quality.exists())

    def test_extra_missing_month_or_existing_output_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d) / "archives"
            data.mkdir()
            hashes = self.fixture(data)
            out, quality = Path(d) / "quotes.csv", Path(d) / "quality.json"
            extra = data / "unknown.zip"
            extra.write_bytes(b"unknown")
            with self.assertRaisesRegex(ValueError, "unknown"):
                subject.convert(data, out, quality)
            extra.unlink()
            (data / "HISTDATA_COM_ASCII_XAUUSD_T_202412.zip").unlink()
            with self.assertRaisesRegex(ValueError, "all15"):
                subject.convert(data, out, quality)
            out.write_bytes(b"KEEP")
            with self.assertRaisesRegex(ValueError, "already exist"):
                subject.convert(data, out, quality)
            self.assertEqual(out.read_bytes(), b"KEEP")

    def test_unapproved_reversal_never_sorts_or_publishes(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d) / "archives"
            data.mkdir()
            hashes = self.fixture(data, "202412", b"20241201 120000001,1.000,1.001,0\n20241201 120000000,1.000,1.001,0\n")
            out, quality = Path(d) / "quotes.csv", Path(d) / "quality.json"
            with patch.object(subject, "RAW_SHA256", hashes), patch.object(subject, "PLANS", {}), self.assertRaisesRegex(ValueError, "reversal"):
                subject.convert(data, out, quality)
            self.assertFalse(out.exists())
            self.assertFalse(quality.exists())

    def test_frozen_end_excluded_without_bypassing_row_validation(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d) / "archives"
            data.mkdir()
            hashes = self.fixture(data, "202412", b"20241231 185959999,1.000,1.001,0\n20241231 190000000,1.000,1.001,0\n")
            with patch.object(subject, "RAW_SHA256", hashes), patch.object(subject, "PLANS", {}):
                result = subject.convert(data, Path(d) / "ticks", Path(d) / "quality")
            self.assertEqual(result["last_utc_msc"], subject.END - 1)
            self.assertEqual(result["raw_archives"][-1]["source_csv_rows_after_whitelisted_repair"], 2)
            self.assertEqual(result["raw_archives"][-1]["included_rows"], 1)

    def test_bad_crc_even_if_raw_hash_matches_never_publishes(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d) / "archives"
            data.mkdir()
            hashes = self.fixture(data)
            path = data / "HISTDATA_COM_ASCII_XAUUSD_T_202412.zip"
            raw = bytearray(path.read_bytes())
            central = raw.index(b"PK\x01\x02")
            raw[central + 16] ^= 1
            path.write_bytes(raw)
            hashes["202412"] = subject.file_sha(path)
            out, quality = Path(d) / "quotes.csv", Path(d) / "quality.json"
            with patch.object(subject, "RAW_SHA256", hashes), patch.object(subject, "PLANS", {}), self.assertRaises(zipfile.BadZipFile):
                subject.convert(data, out, quality)
            self.assertFalse(out.exists())
            self.assertFalse(quality.exists())


if __name__ == "__main__":
    unittest.main()
