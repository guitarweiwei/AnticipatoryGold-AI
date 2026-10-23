"""Synthetic byte fixtures only: these tests do not certify market timestamps."""
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from dataclasses import replace

from repair_histdata_duplicates import (
    PLANS, Plan, _repair_verified_archive, repair_bundle, rewrite_csv, sha,
)


BEFORE = b"20231029 185959999,1.000,1.002,0\n"
BLOCK = [b"20231029 190000076,1.000,1.002,0\n",
         b"20231029 195959701,1.001,1.003,0\n"]
AFTER = b"20231029 200000000,1.002,1.004,0\n"
PLAN = Plan("202310", "unused", 4, 2, sha(b"".join(BLOCK)), b"20231029 19")


def archive(csv):
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("DAT_ASCII_XAUUSD_T_202310.csv", csv)
        z.writestr("DAT_ASCII_XAUUSD_T_202310.txt", b"ORIGINAL provider metadata\r\n")
    return target.getvalue()


class ExactHourRepairTests(unittest.TestCase):
    def rewrite(self, rows, plan=PLAN):
        output = io.BytesIO()
        report = rewrite_csv(io.BytesIO(b"".join(rows)), output, plan)
        return output.getvalue(), report

    def test_only_second_block_removed_all_other_bytes_preserved(self):
        before = BEFORE.replace(b"\n", b"\r\n")
        output, report = self.rewrite([before, *BLOCK, *BLOCK, AFTER])
        self.assertEqual(output, before + b"".join(BLOCK) + AFTER)
        self.assertEqual(report["deleted_second_block_source_rows"], [4, 5])
        self.assertEqual(report["retained_first_block_source_rows"], [2, 3])
        self.assertEqual(report["row_mapping"], [
            {"source": [1, 3], "output": [1, 3]},
            {"source": [4, 5], "output": None},
            {"source": [6, 6], "output": [4, 4]}])
        self.assertEqual(report["output_csv_sha256"], sha(output))

    def test_similar_hour_with_one_quote_changed_rejected(self):
        changed = BLOCK[1].replace(b"1.001", b"1.009")
        with self.assertRaises(ValueError):
            self.rewrite([BEFORE, *BLOCK, BLOCK[0], changed, AFTER])

    def test_identical_values_with_different_line_endings_rejected(self):
        with self.assertRaises(ValueError):
            self.rewrite([BEFORE, *BLOCK, *(b.replace(b"\n", b"\r\n") for b in BLOCK), AFTER])

    def test_nonadjacent_duplicate_not_repaired(self):
        with self.assertRaises(ValueError):
            self.rewrite([BEFORE, *BLOCK, AFTER, *BLOCK, AFTER])

    def test_partial_or_extra_duplicate_block_rejected(self):
        for rows in ([BEFORE, *BLOCK, BLOCK[0], AFTER],
                     [BEFORE, *BLOCK, *BLOCK, *BLOCK, AFTER]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.rewrite(rows)

    def test_second_unapproved_reversal_rejected(self):
        with self.assertRaisesRegex(ValueError, "unapproved"):
            self.rewrite([BEFORE, *BLOCK, *BLOCK, AFTER,
                          b"20231029 200000001,1,2,0\n", AFTER])

    def test_identical_blocks_still_require_frozen_hash_and_position(self):
        for plan in (replace(PLAN, block_sha256="0" * 64),
                     replace(PLAN, second_start=5)):
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                self.rewrite([BEFORE, *BLOCK, *BLOCK, AFTER], plan)

    def test_archive_hash_crc_metadata_and_output_hash(self):
        csv = BEFORE + b"".join(BLOCK * 2) + AFTER
        raw = archive(csv)
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "repaired.zip"
            report = _repair_verified_archive(raw, replace(PLAN, zip_sha256=sha(raw)), output)
            self.assertTrue(report["source_crc_verified"])
            self.assertTrue(report["output_crc_verified"])
            self.assertEqual(report["output_zip_sha256"], sha(output.read_bytes()))
            with zipfile.ZipFile(output) as z:
                self.assertEqual(z.read("DAT_ASCII_XAUUSD_T_202310.csv"),
                                 BEFORE + b"".join(BLOCK) + AFTER)
                self.assertEqual(z.read("DAT_ASCII_XAUUSD_T_202310.txt"),
                                 b"ORIGINAL provider metadata\r\n")
            with self.assertRaisesRegex(ValueError, "hash"):
                _repair_verified_archive(raw, PLAN, Path(d) / "unapproved.zip")

    def test_corrupt_source_crc_fails(self):
        raw = bytearray(archive(BEFORE + b"".join(BLOCK * 2) + AFTER))
        # Flip central directory CRC; raw hash alone must not bypass CRC checking.
        central = raw.index(b"PK\x01\x02")
        raw[central + 16] ^= 1
        with tempfile.TemporaryDirectory() as d, self.assertRaises(zipfile.BadZipFile):
            _repair_verified_archive(bytes(raw), replace(PLAN, zip_sha256=sha(raw)),
                                     Path(d) / "corrupt.zip")

    def test_unknown_month_has_no_production_plan_and_no_published_output(self):
        self.assertEqual(set(PLANS), {"202310", "202410"})
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "outer.zip"
            with zipfile.ZipFile(source, "w") as z:
                z.writestr("raw/HISTDATA_COM_ASCII_XAUUSD_T_202311.zip", b"unknown")
            original = source.read_bytes()
            output = Path(d) / "result"
            with self.assertRaises((KeyError, ValueError)):
                repair_bundle(source, output)
            self.assertFalse(output.exists())
            self.assertEqual(list(Path(d).iterdir()), [source])
            self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
