"""Download only the 15 inspected public monthly XAUUSD tick ZIP identities.

Raw output stays private. No account, credentials, paid service or route change.
403/429 stops; only one timeout/5xx retry. Data hash changes require review.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import time
import urllib.request
import urllib.parse
import urllib.error
import zipfile

class Form(HTMLParser):
    def __init__(self):super().__init__();self.active=False;self.values={};self.seen=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='form' and a.get('id')=='file_down':
            if self.seen or a.get('action')!='/get.php' or a.get('method','').upper()!='POST':raise ValueError('Download form changed')
            self.active=self.seen=True
        elif tag=='input' and self.active:
            key=a.get('name')
            if a.get('type')!='hidden' or key in self.values:raise ValueError('Unexpected form field')
            self.values[key]=a.get('value')
    def handle_endtag(self,tag):
        if tag=='form':self.active=False

class OfficialOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        u=urllib.parse.urlsplit(newurl)
        if u.scheme!='https' or u.hostname!='www.histdata.com' or u.username or u.password or u.port not in (None,443):raise ValueError('Unreviewed redirect')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    identities=json.loads(Path(__file__).with_name('histdata_source_hashes.json').read_text())['raw_zips'];manifest={'status':'INCOMPLETE','source':'HISTDATA.COM','files':[]}
    op=urllib.request.build_opener(OfficialOnly())
    def save():
        temp=a.output/'acquisition.json.tmp';temp.write_text(json.dumps(manifest,indent=2));temp.replace(a.output/'acquisition.json')
    for name,expected in sorted(identities.items()):
        month=name.rsplit('_',1)[1][:6];target=a.output/name;page=f'https://www.histdata.com/download-free-forex-historical-data/?/ascii/tick-data-quotes/xauusd/{month[:4]}/{int(month[4:])}'
        if target.exists():
            if digest(target)!=expected:raise ValueError('Cached source identity conflict')
            origin='VERIFIED_CACHE'
        else:
            for attempt in range(2):
                try:
                    with op.open(page,timeout=45) as r:
                        if r.status!=200:raise ValueError('Unexpected page response')
                        html=r.read(2097153)
                        if len(html)>2097152:raise ValueError('Oversized form page')
                    f=Form();f.feed(html.decode('utf8'))
                    if (not f.seen or set(f.values)!={'tk','date','datemonth','platform','timeframe','fxpair'}
                            or any(f.values[k]!=v for k,v in {'date':month[:4],'datemonth':month,'platform':'ASCII','timeframe':'T','fxpair':'XAUUSD'}.items())
                            or not f.values['tk']):raise ValueError('Public form identity changed')
                    req=urllib.request.Request('https://www.histdata.com/get.php',data=urllib.parse.urlencode(f.values).encode(),headers={'Referer':page})
                    with op.open(req,timeout=45) as r:
                        if r.status!=200:raise ValueError('Unexpected archive response')
                        data=r.read(134217729)
                    if len(data)>134217728 or data[:4]!=b'PK\x03\x04' or hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Downloaded archive identity changed')
                    temp=target.with_suffix('.part');temp.write_bytes(data);temp.replace(target);origin='PUBLIC_SAME_ORIGIN_FORM_POST';break
                except urllib.error.HTTPError as exc:
                    if exc.code in (403,429):manifest.update(status='ACCESS_OR_RATE_LIMIT_STOP',http_status=exc.code);save();raise
                    if exc.code not in (500,502,503,504) or attempt:save();raise
                except (TimeoutError,ConnectionError):
                    if attempt:save();raise
                time.sleep(2)
        with zipfile.ZipFile(target) as z:
            if z.testzip() is not None:raise ValueError('ZIP CRC mismatch')
        manifest['files'].append({'month':month,'file':name,'source_page':page,'bytes':target.stat().st_size,'sha256':expected,'origin':origin,'crc_verified':True});save();print(json.dumps({'month':month,'status':'PINNED_HASH_AND_CRC_VERIFIED'}),flush=True)
    manifest['status']='ALL_15_PINNED_ARCHIVES_ACQUIRED';save()

if __name__=='__main__':main()
