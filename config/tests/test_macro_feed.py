"""Synthetic point-in-time fixtures. None are live market observations."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from config.macro_feed import (HEADER, validate_csv, load_snapshot, publish_snapshot,
    validate_provenance, provenance_digest, validate_snapshot_dict)

NOW = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)
STAMP = '2026-01-02T12:00:00Z'

def provenance():
    feeds = {}
    for name, unit in zip(HEADER[2:6], ('percent', 'basis_points', 'basis_points', 'boolean')):
        feeds[name] = dict(source='SYNTHETIC TEST ONLY', instrument=name, unit=unit,
            observation_window='1-day', license_note='Synthetic fixture', observed_at_utc=STAMP,
            published_at_utc=STAMP, received_at_utc=STAMP)
    feeds['high_impact_news_block']['valid_until_utc'] = '2026-01-02T12:05:00Z'
    return dict(mode='manual', feeds=feeds)

def sample(*, manifest=None, **changes):
    m = manifest or provenance()
    fields = ['2', STAMP, '0.1', '2', '-1', '1',
        m['feeds']['dxy_change_pct']['observed_at_utc'],
        m['feeds']['us10y_change_bps']['observed_at_utc'],
        m['feeds']['real_yield_change_bps']['observed_at_utc'],
        m['feeds']['high_impact_news_block']['observed_at_utc'],
        m['feeds']['high_impact_news_block']['valid_until_utc'], provenance_digest(m)]
    for key, value in changes.items(): fields[HEADER.index(key)] = value
    return ','.join(HEADER) + '\n' + ','.join(fields) + '\n'

class MacroTests(unittest.TestCase):
    def test_valid(self):
        result = validate_csv(sample(), now=NOW)
        self.assertEqual(result.as_dict()['timestamp_utc'], STAMP)
        self.assertEqual(result.schema_version, '2')
        self.assertTrue(result.high_impact_news_block)
        self.assertFalse(validate_csv(sample(high_impact_news_block='0'), now=NOW).high_impact_news_block)
        validate_csv(sample().replace('\n','\r\n'), now=NOW)
        validate_csv(sample().rstrip('\n'), now=NOW)

    def test_snapshot_age_boundary_and_future(self):
        m=provenance()
        for feed in m['feeds'].values():
            for key in ('observed_at_utc','published_at_utc','received_at_utc'):
                feed[key]='2026-01-02T11:45:00Z'
        validate_csv(sample(manifest=m,timestamp_utc='2026-01-02T11:45:00Z'),now=NOW)
        for stamp in ('2026-01-02T11:44:59Z','2026-01-02T12:00:01Z'):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                validate_csv(sample(timestamp_utc=stamp),now=NOW)

    def test_utc_syntax_and_clock(self):
        for stamp in ('2026-01-02T12:00:00','2026-01-02T13:00:00+01:00',
                      '2026-01-02T12:00:00+00:00','2026-01-02T12:00:00.000001Z',
                      '2026-02-30T12:00:00Z','2026-01-02',' '+STAMP,
                      '2026-01-02T12:00:60Z','1970-01-01T00:00:00Z'):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                validate_csv(sample(timestamp_utc=stamp),now=NOW)
        with self.assertRaises(ValueError):
            validate_csv(sample(),now=NOW.replace(tzinfo=None))

    def test_exact_schema_single_row(self):
        for content in ('',sample().replace('schema_version','version'),
                        sample()+'\n',sample()+sample().splitlines()[1]+'\n',
                        '\ufeff'+sample(),sample().replace('0.1','"0.1"'),
                        sample().replace('\n','\r'),sample(schema_version='1')):
            with self.subTest(content=content), self.assertRaises(ValueError):
                validate_csv(content,now=NOW)
        old='timestamp_utc,dxy_change_pct,us10y_change_bps,real_yield_change_bps,high_impact_news_block\n'+STAMP+',0,0,0,0\n'
        with self.assertRaises(ValueError): validate_csv(old,now=NOW)

    def test_decimal_numeric_values(self):
        for raw in ('','NaN','nan','inf','-Infinity','1e999','1e2',' 1','foo','1_000','１２'):
            for name in HEADER[2:5]:
                with self.subTest(raw=raw,name=name), self.assertRaises(ValueError):
                    validate_csv(sample(**{name:raw}),now=NOW)
        for raw in ('+1','-0.2','.25','2.'):
            validate_csv(sample(dxy_change_pct=raw),now=NOW)

    def test_strict_boolean(self):
        for raw in ('true','false','yes','2','-1','0.0','',' 1'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validate_csv(sample(high_impact_news_block=raw),now=NOW)

    def test_each_original_numeric_observation_expiry(self):
        for field in HEADER[6:9]:
            validate_csv(sample(**{field:'2026-01-02T11:45:00Z'}),now=NOW)
            for stamp in ('2026-01-02T11:44:59Z','2026-01-02T12:00:01Z'):
                with self.subTest(field=field,stamp=stamp),self.assertRaises(ValueError):
                    validate_csv(sample(**{field:stamp}),now=NOW)

    def test_calendar_expiry_rechecked_at_consumption(self):
        content=sample(high_impact_news_block='0',news_valid_until_utc='2026-01-02T12:00:01Z')
        validate_csv(content,now=NOW)
        validate_csv(content,now=NOW+timedelta(seconds=1))
        with self.assertRaises(ValueError):
            validate_csv(content,now=NOW+timedelta(minutes=4))
        for key,value in [('news_observed_at_utc','2026-01-02T12:00:01Z'),
                          ('news_valid_until_utc','2026-01-02T11:59:59Z')]:
            with self.assertRaises(ValueError): validate_csv(sample(**{key:value}),now=NOW)

    def test_assembled_timestamp_does_not_refresh_source_age(self):
        m=provenance()
        for name,feed in m['feeds'].items():
            if name!='high_impact_news_block':
                for key in ('observed_at_utc','published_at_utc','received_at_utc'):
                    feed[key]='2026-01-02T11:45:00Z'
        content=sample(manifest=m)
        s=validate_csv(content,now=NOW)
        validate_provenance(m,s,now=NOW)
        with self.assertRaises(ValueError):
            validate_csv(content,now=NOW+timedelta(seconds=1))

    def test_missing_file_fails_closed(self):
        with self.assertRaises(ValueError): load_snapshot('/nonexistent/macro.csv',now=NOW)

    def test_provenance(self):
        for field,key,value in (
            ('dxy_change_pct','received_at_utc','2026-01-02T12:00:01Z'),
            ('us10y_change_bps','unit','percent'),('real_yield_change_bps','source',''),
            ('us10y_change_bps','observation_window','year-to-date'),
            ('high_impact_news_block','valid_until_utc','2026-01-02T11:59:59Z')):
            m=provenance();m['feeds'][field][key]=value
            with self.subTest(field=field,key=key),self.assertRaises(ValueError):
                validate_provenance(m,validate_csv(sample(),now=NOW),now=NOW)

    def test_manifest_digest_binding(self):
        m=provenance();s=validate_csv(sample(manifest=m),now=NOW)
        validate_provenance(m,s,now=NOW)
        m['feeds']['dxy_change_pct']['source']='Changed source'
        with self.assertRaises(ValueError): validate_provenance(m,s,now=NOW)
        self.assertEqual(provenance_digest({'a':1,'b':2}),provenance_digest({'b':2,'a':1}))
        for raw in ('0'*63,'A'*64,'g'*64,''):
            with self.assertRaises(ValueError): validate_csv(sample(provenance_sha256=raw),now=NOW)

    def test_json_consumer_shared_validity(self):
        payload=validate_csv(sample(),now=NOW).as_dict()
        self.assertEqual(validate_snapshot_dict(payload,now=NOW).as_dict(),payload)
        for field,value in [('dxy_change_pct',True),('dxy_change_pct',10**999),('high_impact_news_block',0),
                           ('schema_version',2),('dxy_observed_at_utc','2026-01-02T11:44:59Z')]:
            bad=dict(payload);bad[field]=value
            with self.assertRaises(ValueError): validate_snapshot_dict(bad,now=NOW)
        payload['extra']='x'
        with self.assertRaises(ValueError):validate_snapshot_dict(payload,now=NOW)

    def test_atomic_publish_failure_preserves_previous(self):
        with tempfile.TemporaryDirectory() as folder:
            source,dest,manifest=[Path(folder)/n for n in ('source.csv','out.csv','source.json')]
            source.write_text(sample(),encoding='utf-8');manifest.write_text(json.dumps(provenance()),encoding='utf-8')
            dest.write_text('previous',encoding='utf-8')
            publish_snapshot(source,dest,manifest,now=NOW)
            self.assertEqual(load_snapshot(dest,now=NOW).as_dict(),validate_csv(sample(),now=NOW).as_dict())
            for invalid in (sample(dxy_change_pct='nan'),sample(provenance_sha256='0'*64)):
                source.write_text(invalid,encoding='utf-8')
                with self.assertRaises(ValueError):publish_snapshot(source,dest,manifest,now=NOW)
                self.assertEqual(dest.read_text(),sample())
            source.write_text(sample(),encoding='utf-8')
            with patch('config.macro_feed.os.replace',side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):publish_snapshot(source,dest,manifest,now=NOW)
            self.assertEqual(dest.read_text(),sample())
            self.assertEqual(sorted(p.name for p in Path(folder).iterdir()),['out.csv','source.csv','source.json'])

    def test_duplicate_manifest_keys_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source,dest,manifest=[Path(folder)/n for n in ('source.csv','out.csv','source.json')]
            source.write_text(sample(),encoding='utf-8');dest.write_text('previous',encoding='utf-8')
            text=json.dumps(provenance()).replace('"mode": "manual"','"mode": "invalid", "mode": "manual"')
            manifest.write_text(text,encoding='utf-8')
            with self.assertRaises(ValueError):publish_snapshot(source,dest,manifest,now=NOW)
            self.assertEqual(dest.read_text(),'previous')

if __name__=='__main__':unittest.main()
