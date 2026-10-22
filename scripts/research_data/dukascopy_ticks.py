#!/usr/bin/env python3
"""Archive legacy hourly Dukascopy BI5 quotes, normalize, and audit structure.

Only public HTTPS downloads; no AWS/requester-pays operation or credentials.
Raw data must stay in a private research directory, never a public git commit.
CSV output is time_utc_msc,bid,ask with every source record in stable order.
Structural quality is distinct from licensing, scale/timebase verification,
broker equivalence, MT5 readback and trading/performance authorization.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import heapq
import json
import lzma
import math
from pathlib import Path
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

UTC = timezone.utc
RECORD = struct.Struct('>IIIff')
MAX_COMPRESSED = 32 * 1024 * 1024
MAX_DECOMPRESSED = 128 * 1024 * 1024
PUBLIC_HOSTS = ('www.dukascopy.com', 'datafeed.dukascopy.com')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def stamp(value):
    return value.astimezone(UTC).isoformat().replace('+00:00', 'Z')


def hour_arg(value):
    try:
        value = datetime.strptime(value, '%Y-%m-%dT%H:00:00Z').replace(tzinfo=UTC)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Use an exact UTC hour YYYY-MM-DDTHH:00:00Z') from exc
    return value


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    temporary.replace(path)


def hourly_url(hour, host='www.dukascopy.com'):
    if host not in PUBLIC_HOSTS or hour.utcoffset() != timedelta(0):
        raise ValueError('Expected official public host and UTC hour')
    return f'https://{host}/datafeed/XAUUSD/{hour.year:04}/{hour.month-1:02}/{hour.day:02}/{hour.hour:02}h_ticks.bi5'


class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        self.chain = []

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        old = urllib.parse.urlsplit(request.full_url)
        new = urllib.parse.urlsplit(newurl)
        if old.hostname not in PUBLIC_HOSTS or new.hostname not in PUBLIC_HOSTS or new.scheme not in ('http', 'https'):
            self.chain.append({'status': code, 'from': request.full_url, 'to': newurl, 'accepted': False})
            raise urllib.error.URLError('Nonofficial redirect refused; review source explicitly')
        # Some official legacy www links advertise HTTP. Upgrade transport before
        # requesting the official destination; never send the quote request in HTTP.
        effective = urllib.parse.urlunsplit(('https', new.netloc, new.path, new.query, new.fragment))
        self.chain.append({'status': code, 'from': request.full_url, 'to': newurl,
                           'effective_https_destination': effective, 'accepted': True})
        return super().redirect_request(request, fp, code, msg, headers, effective)


def decode_records(compressed):
    if not compressed:
        return []
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_AUTO, memlimit=256 * 1024 * 1024)
    raw = decoder.decompress(compressed, max_length=MAX_DECOMPRESSED + 1)
    if len(raw) > MAX_DECOMPRESSED or not decoder.eof or decoder.unused_data or len(raw) % RECORD.size:
        raise ValueError('Oversized/truncated/trailing compressed stream or incomplete 20-byte record')
    return list(RECORD.iter_unpack(raw))


def archive_one(hour, root, host, retries, timeout, stop):
    relative = Path('raw') / 'XAUUSD' / f'{hour.year:04}' / f'{hour.month-1:02}' / f'{hour.day:02}' / f'{hour.hour:02}h_ticks.bi5'
    target = root / relative
    metadata = target.with_suffix('.json')
    result = {'hour_utc': stamp(hour), 'url': hourly_url(hour, host), 'relative_path': relative.as_posix(),
              'retrieved_utc': None, 'http_status': None, 'status': 'NOT_ATTEMPTED', 'sha256': None,
              'bytes': None, 'records': None, 'error': None}
    if metadata.exists() and target.exists():
        prior = json.loads(metadata.read_text(encoding='utf-8'))
        if (prior.get('url') != result['url'] or prior.get('hour_utc') != result['hour_utc']
                or prior.get('status') not in ('DOWNLOADED', 'EMPTY_HTTP200')
                or prior.get('sha256') != file_digest(target)):
            result.update(status='CACHE_CONFLICT', error='Existing raw/metadata mismatch; no overwrite')
            return result
        return prior
    if target.exists() and not metadata.exists():
        result.update(status='CACHE_CONFLICT', error='Raw exists without provenance metadata; no overwrite')
        return result
    if stop.is_set():
        result['status'] = 'STOPPED_BY_RATE_OR_ACCESS_LIMIT'
        return result
    target.parent.mkdir(parents=True, exist_ok=True)
    redirects = SameHostRedirect()
    opener = urllib.request.build_opener(redirects)
    request = urllib.request.Request(result['url'], headers={'User-Agent': 'AnticipatoryGoldResearch/1.0'})
    for attempt in range(retries + 1):
        if stop.is_set():
            result['status'] = 'STOPPED_BY_RATE_OR_ACCESS_LIMIT'
            break
        result['attempts'] = attempt + 1
        result['retrieved_utc'] = stamp(datetime.now(UTC))
        try:
            with opener.open(request, timeout=timeout) as response:
                result['http_status'] = response.status
                result['final_url'] = response.geturl()
                result['headers'] = {key: response.headers.get(key) for key in
                                     ('Content-Type', 'Content-Length', 'Last-Modified', 'ETag')}
                content = response.read(MAX_COMPRESSED + 1)
            if len(content) > MAX_COMPRESSED:
                raise ValueError('Compressed hour exceeds size cap')
            # Retain even malformed successful responses for private diagnosis.
            temporary = target.with_suffix('.part')
            temporary.write_bytes(content)
            temporary.replace(target)
            result.update(sha256=digest(content), bytes=len(content), redirects=redirects.chain)
            try:
                ticks = decode_records(content)
            except (ValueError, lzma.LZMAError) as exc:
                result.update(status='RETAINED_RESPONSE_DECODE_FAILED', error=f'{type(exc).__name__}: {exc}')
                break
            # Validation of price scale and timebase belongs to normalize/evidence.
            result.update(status='DOWNLOADED' if content else 'EMPTY_HTTP200',
                          records=len(ticks), error=None)
            break
        except urllib.error.HTTPError as exc:
            result['http_status'] = exc.code
            result['error'] = str(exc)
            if exc.code in (403, 429):
                result['status'] = 'ACCESS_OR_RATE_LIMIT_STOP'
                result['retry_after'] = exc.headers.get('Retry-After') if exc.headers else None
                stop.set()
                break
            if exc.code == 404:
                # This is not proof of a scheduled closure; preserve separately.
                result['status'] = 'NOT_FOUND_UNCLASSIFIED'
                break
            result['status'] = 'HTTP_ERROR'
            if exc.code not in (500, 502, 503, 504):
                break
        except (OSError, ValueError, lzma.LZMAError) as exc:
            result.update(status='DOWNLOAD_OR_DECODE_ERROR', error=f'{type(exc).__name__}: {exc}')
        if attempt < retries:
            # Retry budget is finite; do not retry an access/rate-limit response.
            time.sleep(min(2 ** attempt, 4))
    result['redirects'] = redirects.chain
    atomic_json(metadata, result)
    return result


def acquire(args):
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.end <= args.start:
        raise ValueError('End must be after start, exclusive')
    hours = []
    hour = args.start
    while hour < args.end:
        hours.append(hour)
        hour += timedelta(hours=1)
    plan = {'schema': 'agai.dukascopy-hourly-archive/1', 'symbol': 'XAUUSD',
            'host': args.host, 'start_utc': stamp(args.start), 'end_utc_exclusive': stamp(args.end),
            'download_only_no_strategy_returns': True}
    plan_path = root / 'download-plan.json'
    if plan_path.exists() and json.loads(plan_path.read_text()) != plan:
        raise ValueError('Existing download plan differs; use another private output directory')
    atomic_json(plan_path, plan)
    start_clock = time.monotonic()
    stop = threading.Event()
    results = []
    # Submit all tasks, but queued tasks stop without network calls after 403/429.
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(archive_one, hour, root, args.host, args.retries, args.timeout, stop): hour for hour in hours}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({'hour_utc': stamp(futures[future]), 'status': 'UNHANDLED_ARCHIVE_ERROR',
                                'error': f'{type(exc).__name__}: {exc}'})
            if len(results) % 100 == 0 or len(results) == len(hours):
                print(json.dumps({'completed_hours': len(results), 'expected_hours': len(hours),
                                  'statuses': dict(Counter(row['status'] for row in results)),
                                  'elapsed_seconds': round(time.monotonic() - start_clock, 3)}), flush=True)
    report = dict(plan, created_utc=stamp(datetime.now(UTC)), elapsed_seconds=round(time.monotonic()-start_clock, 3),
                  workers=args.workers, expected_hours=len(hours),
                  statuses=dict(Counter(row['status'] for row in results)),
                  total_compressed_bytes=sum(row.get('bytes') or 0 for row in results),
                  total_records=sum(row.get('records') or 0 for row in results),
                  files=sorted(results, key=lambda row: row['hour_utc']), source_validation='NOT_VALIDATED')
    atomic_json(root / 'download-manifest.json', report)
    blocked = any(row['status'] not in ('DOWNLOADED', 'EMPTY_HTTP200') for row in results)
    print(json.dumps({key: value for key, value in report.items() if key != 'files'}, indent=2))
    return 2 if blocked else 0


def normalized_ticks(rows, hour, divisor):
    previous = -1
    for sequence, (offset, ask, bid, ask_volume, bid_volume) in enumerate(rows):
        if not 0 <= offset < 3600000:
            raise ValueError(f'Offset outside explicit legacy-hour timebase at source sequence {sequence}')
        if offset < previous:
            raise ValueError(f'Out-of-order source sequence {sequence}; never silently sort')
        previous = offset
        if bid <= 0 or ask < bid:
            raise ValueError(f'Nonpositive/crossed source quote at sequence {sequence}')
        if not all(math.isfinite(value) and value >= 0 for value in (ask_volume, bid_volume)):
            raise ValueError(f'Invalid original side-volume at source sequence {sequence}')
        absolute = int(hour.timestamp()) * 1000 + offset
        yield absolute, bid, ask, format(Decimal(bid) / divisor, 'f'), format(Decimal(ask) / divisor, 'f')


def quantile(histogram, numerator, denominator):
    count = sum(histogram.values())
    if not count:
        return None
    target = max(1, (count * numerator + denominator - 1) // denominator)
    cumulative = 0
    for value, frequency in sorted(histogram.items()):
        cumulative += frequency
        if cumulative >= target:
            return value


def normalize(args):
    root = args.archive.resolve()
    manifest_path = root / 'download-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    divisor = Decimal(args.price_divisor)
    if not divisor.is_finite() or divisor <= 0 or divisor != divisor.to_integral_value():
        raise ValueError('Explicit positive integral price divisor required; no commodity default')
    evidence = json.loads(args.evidence.read_text()) if args.evidence else {}
    verified = (evidence.get('instrument') == 'XAUUSD' and evidence.get('price_divisor') == int(divisor)
                and evidence.get('scale_verified') is True and evidence.get('legacy_hourly_utc_timebase_verified') is True
                and bool(evidence.get('scale_reference')) and bool(evidence.get('timebase_reference')))
    if not verified and not args.diagnostic_unvalidated:
        raise ValueError('Scale/hourly-UTC evidence required, or explicitly choose diagnostic-unvalidated')
    output = args.output.resolve()
    quality = args.quality.resolve()
    if output.exists() or quality.exists():
        raise ValueError('Output/quality already exists; preserve evidence and use fresh paths')
    output.parent.mkdir(parents=True, exist_ok=True)
    quality.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.part')
    if temporary.exists():
        raise ValueError('Prior partial normalization exists; preserve it and choose a new output path')
    count = ties = duplicates = zero_spreads = 0
    previous_tick = None
    spreads = Counter()
    days = {}
    largest_gaps = []
    failures = []
    empty_hours = []
    min_bid = max_bid = min_ask = max_ask = None
    first = last = None
    files = manifest['files']
    hours = [row['hour_utc'] for row in files]
    expected = []
    cursor = hour_arg(manifest['start_utc'])
    while cursor < hour_arg(manifest['end_utc_exclusive']):
        expected.append(stamp(cursor)); cursor += timedelta(hours=1)
    if hours != expected or len(files) != manifest['expected_hours']:
        raise ValueError('Manifest does not enumerate exact frozen hourly interval once in order')
    try:
        with temporary.open('w', newline='', encoding='ascii') as stream:
            writer = csv.writer(stream, lineterminator='\n')
            writer.writerow(('time_utc_msc', 'bid', 'ask'))
            for item in files:
                if item['status'] not in ('DOWNLOADED', 'EMPTY_HTTP200'):
                    failures.append({'hour_utc': item['hour_utc'], 'status': item['status']})
                    continue
                hour = hour_arg(item['hour_utc'])
                path = root / item['relative_path']
                if not path.resolve().is_relative_to(root):
                    raise ValueError('Archive path escapes private root')
                raw = path.read_bytes()
                if digest(raw) != item['sha256'] or len(raw) != item['bytes']:
                    raise ValueError(f'Raw archive hash/size mismatch: {item["hour_utc"]}')
                rows = decode_records(raw)
                if len(rows) != item['records']:
                    raise ValueError('Decoded record count differs from acquisition')
                if not rows:
                    empty_hours.append(item['hour_utc'])
                for absolute, bid, ask, bid_text, ask_text in normalized_ticks(rows, hour, divisor):
                    if previous_tick is not None:
                        gap = absolute - previous_tick[0]
                        if gap < 0:
                            raise ValueError('Cross-hour event order decreased')
                        ties += gap == 0
                        duplicates += (absolute, bid, ask) == previous_tick
                        if gap > 0:
                            edge = (gap, previous_tick[0], absolute)
                            if len(largest_gaps) < 20:
                                heapq.heappush(largest_gaps, edge)
                            elif edge > largest_gaps[0]:
                                heapq.heapreplace(largest_gaps, edge)
                    previous_tick = (absolute, bid, ask)
                    spreads[ask-bid] += 1
                    zero_spreads += ask == bid
                    count += 1
                    first = absolute if first is None else first
                    last = absolute
                    min_bid = bid if min_bid is None else min(min_bid, bid)
                    max_bid = bid if max_bid is None else max(max_bid, bid)
                    min_ask = ask if min_ask is None else min(min_ask, ask)
                    max_ask = ask if max_ask is None else max(max_ask, ask)
                    day = datetime.fromtimestamp(absolute / 1000, UTC).date().isoformat()
                    entry = days.setdefault(day, {'ticks': 0, 'first_utc_msc': absolute, 'last_utc_msc': absolute})
                    entry['ticks'] += 1; entry['last_utc_msc'] = absolute
                    writer.writerow((absolute, bid_text, ask_text))
        structural_pass = not failures and count > 0
        report = {'schema': 'agai.quote-structure-quality/1', 'status': 'STRUCTURAL_CHECKS_PASSED' if structural_pass else 'BLOCKED_INCOMPLETE_OR_NO_TICKS',
                  'authorizes_trading_or_performance': False,
                  'source': 'Dukascopy public legacy hourly BI5 XAUUSD', 'download_manifest_sha256': file_digest(manifest_path),
                  'price_divisor': int(divisor), 'scale_and_hourly_utc_evidence_verified': verified,
                  'validation_evidence_sha256': file_digest(args.evidence) if args.evidence else None,
                  'source_authentication_license_and_broker_equivalence': 'NOT_VALIDATED',
                  'normalized_sha256': file_digest(temporary), 'rows': count, 'expected_hours': len(files),
                  'empty_http200_or_empty_stream_hours': empty_hours, 'unclassified_failed_hours': failures,
                  'first_utc_msc': first, 'last_utc_msc': last, 'same_millisecond_pairs_preserved': ties,
                  'consecutive_exact_quote_duplicates_preserved': duplicates, 'zero_spread_rows': zero_spreads,
                  'quote_price_min_max': {key: format(Decimal(value)/divisor, 'f') if value is not None else None
                                          for key,value in [('min_bid',min_bid),('max_bid',max_bid),('min_ask',min_ask),('max_ask',max_ask)]},
                  'spread_quote_units_nearest_rank': {f'p{n}': format(Decimal(quantile(spreads,n,100))/divisor, 'f') if count else None for n in (0,50,90,95,99,100)},
                  'largest_gaps_milliseconds_with_edges': sorted(largest_gaps, reverse=True), 'daily_coverage': days,
                  'limitations': ['No strategy returns computed; no MT5 test executed',
                                 'Empty/missing hours do not prove scheduled market closure; session/calendar review remains required',
                                 'Quote record timestamp is not proof of independent bid/ask source observation age',
                                 'No interpolation, invented spread, quote sorting or timestamp-only deduplication',
                                 'Scale/timebase evidence is an external reviewed assertion, not authenticated by this script',
                                 'Structural checks do not prove source license, broker costs, execution quality or MT5 readback parity']}
        if structural_pass or args.diagnostic_unvalidated:
            temporary.replace(output)
            report['normalized_path'] = str(output)
        else:
            report['partial_diagnostic_path'] = str(temporary)
        atomic_json(quality, report)
        print(json.dumps({key:value for key,value in report.items() if key not in ('daily_coverage','empty_http200_or_empty_stream_hours')}, indent=2))
        return 0 if structural_pass and verified else 2
    except Exception:
        # Keep a partial file clearly named .part for investigation; never publish it as complete.
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    download = commands.add_parser('acquire')
    download.add_argument('--start', type=hour_arg, required=True)
    download.add_argument('--end', type=hour_arg, required=True)
    download.add_argument('--output', type=Path, required=True)
    download.add_argument('--host', choices=PUBLIC_HOSTS, default='www.dukascopy.com')
    download.add_argument('--workers', type=int, choices=range(1,13), default=1)
    download.add_argument('--retries', type=int, choices=range(0,4), default=1)
    download.add_argument('--timeout', type=int, choices=range(5,61), default=20)
    norm = commands.add_parser('normalize')
    norm.add_argument('--archive', type=Path, required=True)
    norm.add_argument('--price-divisor', required=True)
    norm.add_argument('--evidence', type=Path)
    norm.add_argument('--diagnostic-unvalidated', action='store_true')
    norm.add_argument('--output', type=Path, required=True)
    norm.add_argument('--quality', type=Path, required=True)
    args = parser.parse_args()
    return acquire(args) if args.command == 'acquire' else normalize(args)


if __name__ == '__main__':
    raise SystemExit(main())
