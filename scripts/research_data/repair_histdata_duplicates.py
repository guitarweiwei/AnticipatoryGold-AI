"""Remove only two pre-audited byte-identical repeated hours; never calibrate time.

Private derivative archives only. This is neither general deduplication nor evidence
of complete source coverage, broker calibration, or trading performance.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import zipfile


@dataclass(frozen=True)
class Plan:
    month: str
    zip_sha256: str
    second_start: int  # One-based source row.
    rows: int
    block_sha256: str  # Exact source bytes, including line endings.
    hour: bytes


# Frozen from time-reversal-forensics.json; no CLI overrides or inferred repairs.
PLANS = {
    "202310": Plan("202310", "dc29013c1f8403d0763de0b5a7462e57eb347b5095c12663da2defb389d58d76",
                   2582523, 4136, "23f281bb9ccd3816e6496e7f4fcf59917f09ea23cdb8223e1d0e17cf245330cb", b"20231029 19"),
    "202410": Plan("202410", "32d92448517fa1ef292a8f14ef2be52af090c9cbae72ec10bbad240ba30343c1",
                   4494120, 7079, "9ce0f923165d5ae96e8d20881d3a652082eb4575cd70285db4d90fb37a53283f", b"20241027 19"),
}
MAX_ZIP = 128 * 1024 * 1024
MAX_MEMBER = 1024 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked_members(z):
    infos = z.infolist()
    names = [i.filename for i in infos]
    if len(names) != len(set(names)):
        raise ValueError("duplicate ZIP member names")
    for i in infos:
        p = PurePosixPath(i.filename)
        if (p.is_absolute() or ".." in p.parts or "\\" in i.filename
                or ":" in i.filename or i.flag_bits & 1
                or ((i.external_attr >> 16) & 0o170000) == 0o120000
                or i.file_size > MAX_MEMBER):
            raise ValueError("unsafe or oversized ZIP member")
    return infos


def rewrite_csv(source, target, plan):
    """Private streaming primitive; production entry point uses only PLANS."""
    first_start = plan.second_start - plan.rows
    second_end = plan.second_start + plan.rows - 1
    first, second = [], []
    source_hash, output_hash = hashlib.sha256(), hashlib.sha256()
    previous = None
    regressions = []
    dates = set()
    count = 0
    for count, line in enumerate(source, 1):
        source_hash.update(line)
        stamp = line.split(b",", 1)[0]
        if (len(line) > 1024 or not re.fullmatch(rb"\d{8} \d{9}", stamp)
                or not stamp.startswith(plan.month.encode())
                or int(stamp[9:11]) > 23 or int(stamp[11:13]) > 59
                or int(stamp[13:15]) > 59):
            raise ValueError("invalid source timestamp or row")
        date = stamp[:8]
        if date not in dates:
            datetime.strptime(date.decode(), "%Y%m%d")
            dates.add(date)
        if previous is not None and stamp < previous:
            regressions.append(count)
            if count != plan.second_start:
                raise ValueError("unapproved timestamp reversal")
        previous = stamp
        in_blocks = first_start <= count <= second_end
        if stamp.startswith(plan.hour) != in_blocks:
            raise ValueError("hour block is incomplete, noncontiguous, or misplaced")
        if first_start <= count < plan.second_start:
            first.append(line)
        if plan.second_start <= count <= second_end:
            second.append(line)
        else:
            target.write(line)
            output_hash.update(line)
    first_bytes, second_bytes = b"".join(first), b"".join(second)
    if (regressions != [plan.second_start] or count <= second_end
            or len(first) != plan.rows or len(second) != plan.rows
            or first_bytes != second_bytes or sha(first_bytes) != plan.block_sha256):
        raise ValueError("predeclared exact duplicate block verification failed")
    return {
        "source_rows": count, "output_rows": count - plan.rows,
        "source_csv_sha256": source_hash.hexdigest(),
        "output_csv_sha256": output_hash.hexdigest(),
        "verified_block_sha256": plan.block_sha256,
        "retained_first_block_source_rows": [first_start, plan.second_start - 1],
        "deleted_second_block_source_rows": [plan.second_start, second_end],
        "row_mapping": [
            {"source": [1, plan.second_start - 1], "output": [1, plan.second_start - 1]},
            {"source": [plan.second_start, second_end], "output": None},
            {"source": [second_end + 1, count], "output": [plan.second_start, count - plan.rows]},
        ],
    }


def _repair_verified_archive(raw, plan, output):
    if len(raw) > MAX_ZIP or sha(raw) != plan.zip_sha256:
        raise ValueError("raw monthly ZIP hash or size mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as source:
        infos = checked_members(source)
        csv_name = f"DAT_ASCII_XAUUSD_T_{plan.month}.csv"
        txt_name = f"DAT_ASCII_XAUUSD_T_{plan.month}.txt"
        if {i.filename for i in infos} != {csv_name, txt_name}:
            raise ValueError("unexpected monthly ZIP member set")
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as repaired:
            with source.open(csv_name) as inp, repaired.open(csv_name, "w") as out:
                report = rewrite_csv(inp, out, plan)  # Reading to EOF verifies original CSV CRC.
            metadata = source.read(txt_name)  # Original text and CRC, no relabelled source claims.
            repaired.writestr(txt_name, metadata)
        report.update({"month": plan.month, "raw_zip_sha256": sha(raw),
                       "original_source_metadata_preserved": True,
                       "original_source_metadata_sha256": sha(metadata),
                       "source_members_crc32": {i.filename: f"{i.CRC:08x}" for i in infos},
                       "source_crc_verified": True})
    with zipfile.ZipFile(output) as check:
        if check.testzip() is not None:
            raise ValueError("output CRC verification failed")
        report["output_members_crc32"] = {i.filename: f"{i.CRC:08x}" for i in check.infolist()}
    report["output_zip_sha256"] = sha(Path(output).read_bytes())
    report["output_crc_verified"] = True
    return report


def repair_bundle(bundle, output_dir):
    """New directory published only if both fixed repairs pass; originals untouched."""
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError("output directory must not exist")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".histdata-repair-", dir=output_dir.parent))
    try:
        reports = []
        with zipfile.ZipFile(bundle) as outer:
            checked_members(outer)
            for month, plan in PLANS.items():
                name = f"raw/HISTDATA_COM_ASCII_XAUUSD_T_{month}.zip"
                info = outer.getinfo(name)
                if info.file_size > MAX_ZIP:
                    raise ValueError("oversized monthly archive")
                reports.append(_repair_verified_archive(
                    outer.read(name), plan, stage / f"HISTDATA_COM_ASCII_XAUUSD_T_{month}.zip"))
        manifest = {
            "schema": "agai.histdata-exact-duplicate-repair/1",
            "status": "EXACT_PREDECLARED_SEQUENCE_REDUNDANCY_REMOVED",
            "only_deleted_second_identical_adjacent_hour_blocks": True,
            "timestamp_or_timezone_adjusted": False,
            "sort_or_general_deduplication_performed": False,
            "source_metadata_text_is_original_unmodified_not_derivative_certification": True,
            "source_coverage_or_clock_calibration": "NOT_VALIDATED",
            "broker_equivalence": "NOT_VALIDATED",
            "performance_result": "NOT_RUN",
            "private_derivatives_not_for_public_redistribution": True,
            "months": reports,
        }
        (stage / "repair-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        stage.rename(output_dir)
        return manifest
    except BaseException:
        shutil.rmtree(stage)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    repair_bundle(args.bundle, args.output_dir)


if __name__ == "__main__":
    main()
