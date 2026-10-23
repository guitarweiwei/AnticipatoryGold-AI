"""Synthetic decoding/failure checks; no network or strategy-performance tests."""
from datetime import datetime, timezone
from decimal import Decimal
from argparse import Namespace
import io
import json
import lzma
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from dukascopy_ticks import (decode_records, normalized_ticks, hourly_url, digest,
                            archive_one, SameHostRedirect, quantile, normalize)

HOUR = datetime(2024, 1, 15, 10, tzinfo=timezone.utc)


class DataChecks(unittest.TestCase):
    def record(self, offset=113, ask=2055235, bid=2054925):
        return struct.pack('>IIIff', offset, ask, bid, .00012, .00012)

    def test_explicit_hourly_base_and_price_divisor(self):
        records = decode_records(lzma.compress(self.record(), format=lzma.FORMAT_ALONE))
        values = list(normalized_ticks(records, HOUR, Decimal(1000)))
        self.assertEqual(values[0][0], int(HOUR.timestamp())*1000+113)
        self.assertEqual(values[0][3:], ('2054.925', '2055.235'))

    def test_hourly_path_zero_based_month(self):
        self.assertEqual(hourly_url(HOUR), 'https://www.dukascopy.com/datafeed/XAUUSD/2024/00/15/10h_ticks.bi5')

    def test_equal_timestamp_order_and_duplicates_preserved(self):
        raw = self.record() + self.record(ask=2055236) + self.record(ask=2055236)
        output = list(normalized_ticks(decode_records(lzma.compress(raw)), HOUR, Decimal(1000)))
        self.assertEqual(len(output), 3)
        self.assertEqual([row[4] for row in output], ['2055.235', '2055.236', '2055.236'])

    def test_truncated_trailing_and_incomplete_records_rejected(self):
        compressed = lzma.compress(self.record())
        for bad in (compressed[:-1], compressed+b'garbage', lzma.compress(self.record()[:-1])):
            with self.assertRaises((ValueError, lzma.LZMAError)):
                decode_records(bad)

    def test_order_offset_crossed_and_zero_quote_rejected(self):
        cases = [self.record(offset=3600000), self.record(offset=500)+self.record(offset=113),
                 self.record(bid=2055236), self.record(bid=0)]
        for raw in cases:
            with self.assertRaises(ValueError):
                list(normalized_ticks(decode_records(lzma.compress(raw)), HOUR, Decimal(1000)))

    def test_empty_is_not_a_synthetic_quote(self):
        self.assertEqual(decode_records(b''), [])
        self.assertEqual(decode_records(lzma.compress(b'')), [])

    def test_negative_or_nonfinite_original_volume_rejected(self):
        for value in (-1, float('nan'), float('inf')):
            raw = struct.pack('>IIIff', 113, 2055235, 2054925, value, .00012)
            with self.assertRaises(ValueError):
                list(normalized_ticks(decode_records(lzma.compress(raw)), HOUR, Decimal(1000)))

    def test_429_sets_stop_and_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            error = HTTPError(hourly_url(HOUR), 429, 'Too Many Requests', {}, io.BytesIO())
            with patch('dukascopy_ticks.urllib.request.build_opener') as factory:
                factory.return_value.open.side_effect = error
                stop = threading.Event()
                report = archive_one(HOUR, Path(directory), 'www.dukascopy.com', 3, 10, stop)
                self.assertTrue(stop.is_set())
                self.assertEqual(report['status'], 'ACCESS_OR_RATE_LIMIT_STOP')
                self.assertEqual(factory.return_value.open.call_count, 1)

    def test_raw_without_metadata_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'raw/XAUUSD/2024/00/15/10h_ticks.bi5'
            path.parent.mkdir(parents=True); path.write_bytes(b'original')
            report=archive_one(HOUR,Path(directory),'www.dukascopy.com',0,10,threading.Event())
            self.assertEqual(report['status'],'CACHE_CONFLICT')
            self.assertEqual(path.read_bytes(),b'original')

    def test_nearest_rank_spread_quantiles(self):
        self.assertEqual(quantile({10: 50, 20: 49, 100: 1}, 99, 100),20)
        self.assertEqual(quantile({10: 50, 20: 49, 100: 1}, 100, 100),100)

    def test_official_legacy_http_redirect_is_upgraded_before_request(self):
        from urllib.request import Request
        handler = SameHostRedirect()
        destination = 'http://datafeed.dukascopy.com/datafeed/XAUUSD/file.bi5'
        result = handler.redirect_request(Request(hourly_url(HOUR)), None, 301, '', {}, destination)
        self.assertTrue(result.full_url.startswith('https://datafeed.dukascopy.com/'))
        self.assertEqual(handler.chain[0]['to'], destination)
        from urllib.error import URLError
        with self.assertRaises(URLError):
            handler.redirect_request(Request(hourly_url(HOUR)),None,301,'',{},'https://evil.invalid/file.bi5')

    def test_normalized_dataset_stays_unvalidated_without_source_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            compressed = lzma.compress(self.record()+self.record())
            (root/'raw.bi5').write_bytes(compressed)
            manifest = {'start_utc':'2024-01-15T10:00:00Z','end_utc_exclusive':'2024-01-15T11:00:00Z',
                        'expected_hours':1,'files':[{'hour_utc':'2024-01-15T10:00:00Z',
                        'status':'DOWNLOADED','relative_path':'raw.bi5','sha256':digest(compressed),
                        'bytes':len(compressed),'records':2}]}
            (root/'download-manifest.json').write_text(json.dumps(manifest))
            args=Namespace(archive=root,price_divisor='1000',evidence=None,diagnostic_unvalidated=True,
                           output=root/'normalized.csv',quality=root/'quality.json')
            with patch('builtins.print'):
                self.assertEqual(normalize(args),2)
            quality=json.loads(args.quality.read_text())
            self.assertEqual(quality['rows'],2)
            self.assertEqual(quality['consecutive_exact_quote_duplicates_preserved'],1)
            self.assertFalse(quality['authorizes_trading_or_performance'])
            self.assertFalse(quality['scale_and_hourly_utc_evidence_verified'])
            self.assertEqual(args.output.read_text().splitlines()[0],'time_utc_msc,bid,ask')
            with self.assertRaises(ValueError): normalize(args)


if __name__ == '__main__':
    unittest.main()
