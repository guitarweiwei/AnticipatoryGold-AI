"""Synthetic point-in-time tests; these values are never live market data."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from config.macro_feed import HEADER, validate_csv, load_snapshot, publish_snapshot, validate_provenance

NOW = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)
STAMP = '2026-01-02T12:00:00Z'
def sample(stamp=STAMP, values='0.1,2,-1,1'):
    return ','.join(HEADER) + '\n' + stamp + ',' + values + '\n'
def provenance():
    feeds = {}
    for name, unit in zip(HEADER[1:], ('percent', 'basis_points', 'basis_points', 'boolean')):
        feeds[name] = dict(source='SYNTHETIC TEST ONLY', instrument=name, unit=unit,
            observation_window='1-day', license_note='Synthetic fixture', observed_at_utc=STAMP,
            published_at_utc=STAMP, received_at_utc=STAMP)
    feeds['high_impact_news_block']['valid_until_utc'] = '2026-01-02T12:05:00Z'
    return dict(mode='manual', feeds=feeds)

class MacroTests(unittest.TestCase):
    def test_valid_and_utc_offset(self):
        for stamp in (STAMP, '2026-01-02T12:00:00+00:00'):
            result = validate_csv(sample(stamp), now=NOW)
            self.assertEqual(result.as_dict()['timestamp_utc'], STAMP)
            self.assertTrue(result.high_impact_news_block)
        self.assertFalse(validate_csv(sample(values='0,0,0,0'), now=NOW).high_impact_news_block)
    def test_age_boundary_and_future(self):
        validate_csv(sample('2026-01-02T11:45:00Z'), now=NOW)
        for stamp in ('2026-01-02T11:44:59Z', '2026-01-02T12:00:00.000001Z'):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                validate_csv(sample(stamp), now=NOW)
    def test_utc_syntax_and_clock(self):
        for stamp in ('2026-01-02T12:00:00', '2026-01-02T13:00:00+01:00',
                      '2026-02-30T12:00:00Z', '2026-01-02', ' '+STAMP):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                validate_csv(sample(stamp), now=NOW)
        with self.assertRaises(ValueError):
            validate_csv(sample(), now=NOW.replace(tzinfo=None))
    def test_exact_schema_single_row(self):
        for content in ('', sample().replace('timestamp_utc', 'timestamp'),
                        sample().replace('dxy_change_pct,us10y_change_bps', 'us10y_change_bps,dxy_change_pct'),
                        sample()+'\n', sample()+sample().splitlines()[1]+'\n',
                        sample(values='0,0,1'), sample(values='0,0,0,1,1'),
                        '\ufeff'+sample()):
            with self.subTest(content=content), self.assertRaises(ValueError):
                validate_csv(content, now=NOW)
    def test_finite_numeric_values(self):
        for raw in ('', 'NaN', 'nan', 'inf', '-Infinity', '1e999', ' 1', 'foo', '1_000', '１２'):
            for position in range(3):
                values = ['0', '0', '0', '0']; values[position] = raw
                with self.subTest(raw=raw, position=position), self.assertRaises(ValueError):
                    validate_csv(sample(values=','.join(values)), now=NOW)
    def test_strict_boolean(self):
        for raw in ('true', 'false', 'yes', '2', '-1', '0.0', '', ' 1'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validate_csv(sample(values='0,0,0,'+raw), now=NOW)
    def test_historical_future_data_rejected(self):
        with self.assertRaises(ValueError):
            validate_csv(sample(), now=NOW-timedelta(days=30))
    def test_missing_file_fails_closed(self):
        with self.assertRaises(ValueError):
            load_snapshot('/nonexistent/macro.csv', now=NOW)
    def test_provenance(self):
        snapshot = validate_csv(sample(), now=NOW)
        validate_provenance(provenance(), snapshot, now=NOW)
        for field, key, value in (
            ('dxy_change_pct', 'received_at_utc', '2026-01-02T12:00:01Z'),
            ('dxy_change_pct', 'observed_at_utc', '2026-01-02T11:44:59Z'),
            ('us10y_change_bps', 'unit', 'percent'),
            ('real_yield_change_bps', 'source', ''),
            ('us10y_change_bps', 'observation_window', 'year-to-date'),
            ('high_impact_news_block', 'valid_until_utc', '2026-01-02T11:59:59Z')):
            manifest = provenance(); manifest['feeds'][field][key] = value
            with self.subTest(field=field, key=key), self.assertRaises(ValueError):
                validate_provenance(manifest, snapshot, now=NOW)
    def test_atomic_publish_failure_preserves_previous(self):
        with tempfile.TemporaryDirectory() as folder:
            source, dest, manifest = [Path(folder)/name for name in ('source.csv', 'out.csv', 'source.json')]
            source.write_text(sample(), encoding='utf-8')
            manifest.write_text(json.dumps(provenance()), encoding='utf-8')
            dest.write_text('previous', encoding='utf-8')
            publish_snapshot(source, dest, manifest, now=NOW)
            self.assertEqual(dest.read_text(), sample())
            source.write_text(sample(values='nan,0,0,0'), encoding='utf-8')
            with self.assertRaises(ValueError):
                publish_snapshot(source, dest, manifest, now=NOW)
            self.assertEqual(dest.read_text(), sample())
            source.write_text(sample(), encoding='utf-8')
            with patch('config.macro_feed.os.replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    publish_snapshot(source, dest, manifest, now=NOW)
            self.assertEqual(dest.read_text(), sample())
            self.assertEqual(sorted(p.name for p in Path(folder).iterdir()), ['out.csv', 'source.csv', 'source.json'])

if __name__ == '__main__':
    unittest.main()
