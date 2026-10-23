#!/usr/bin/env python3
"""Frozen private acquisition; one bounded resume for network-only failures."""
import argparse,json,shutil
from pathlib import Path
from types import SimpleNamespace
import dukascopy_ticks as d


def can_resume(report):
 failures=[x for x in report['files'] if x['status'] not in ('DOWNLOADED','EMPTY_HTTP200')]
 if not failures or len(failures)>max(32,report['expected_hours']//20):return False
 for x in failures:
  status=x.get('http_status');error=x.get('error') or ''
  if x['status']=='HTTP_ERROR' and status in (500,502,503,504):continue
  if x['status']=='DOWNLOAD_OR_DECODE_ERROR' and error.startswith(('TimeoutError:','URLError:','SSLError:','ConnectionError:','ConnectionResetError:')):continue
  return False
 return True


def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 args=SimpleNamespace(start=d.hour_arg('2023-11-01T00:00:00Z'),end=d.hour_arg('2025-01-01T00:00:00Z'),output=a.output,host='datafeed.dukascopy.com',workers=8,retries=1,timeout=20)
 code=d.acquire(args)
 if not code:return 0
 manifest=a.output/'download-manifest.json';first=json.loads(manifest.read_text());shutil.copyfile(manifest,a.output/'download-manifest-first-pass.json')
 if not can_resume(first):
  print('Acquisition remains blocked: not a small set of network-only failures.',flush=True);return code
 print('Resuming the same frozen interval once; valid cached raw files retain their original hash/provenance.',flush=True)
 return d.acquire(args)
if __name__=='__main__':raise SystemExit(main())
