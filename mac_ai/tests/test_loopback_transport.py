"""Real localhost HTTPX transport checks, not MQL5 or paid-provider evidence.

Only the timeout configuration is shortened to 0.05 s in the socket-timeout
case. AsyncClient, its HTTP transport and provider parsing execute unchanged.
These checks do not establish the production 12-second deadline's timing.
"""
import asyncio
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from threading import Event, Thread
import time

import httpx
import pytest

from config.macro_feed import HEADER
from mac_ai import app as api


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    # The local server uses an explicit fake credential, never ambient credentials.
    for name in ('ALL_PROXY', 'all_proxy', 'HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('NO_PROXY', '127.0.0.1')
    monkeypatch.setenv('no_proxy', '127.0.0.1')
    now = api.utc_now().replace(microsecond=0)
    stamp = now.isoformat().replace('+00:00', 'Z')
    macro = dict(schema_version='2', timestamp_utc=stamp,
        dxy_change_pct=0.1, us10y_change_bps=2.0, real_yield_change_bps=1.0,
        high_impact_news_block=False, dxy_observed_at_utc=stamp,
        us10y_observed_at_utc=stamp, real_yield_observed_at_utc=stamp,
        news_observed_at_utc=stamp,
        news_valid_until_utc=(now + timedelta(minutes=5)).isoformat().replace('+00:00', 'Z'),
        provenance_sha256='a' * 64)
    path = tmp_path / 'synthetic-macro.csv'
    path.write_text(','.join(HEADER) + '\n' + ','.join(
        '0' if value is False else str(value) for value in (macro[key] for key in HEADER)) + '\n')
    monkeypatch.setattr(api, 'MACRO_FILE', path)
    monkeypatch.setattr(api, 'API_KEY', 'loopback-fake-provider-key')
    return api.DecisionRequest(schema_version='1.1', request_id='loopback-candidate',
        symbol='XAUUSD', timeframe='M5', bar_time_utc=stamp,
        regime='STRONG_DOWNTREND', setup='TREND_CONTINUATION', direction='SELL',
        confidence=0.6, close=4000.0, atr=5.0, ema_fast=3995.0,
        ema_slow=4010.0, adx=24.0, macro=macro, reason='synthetic loopback fixture')


@pytest.fixture
def loopback(monkeypatch):
    state = {'body': b'', 'delay': False, 'requests': []}
    seen, release = Event(), Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state['requests'].append({
                'path': self.path, 'authorization': self.headers.get('Authorization'),
                'body': json.loads(self.rfile.read(int(self.headers['Content-Length']))),
            })
            seen.set()
            if state['delay']:
                release.wait(timeout=2.0)
            body = state['body']
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # The real client is expected to disconnect on timeout.

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    monkeypatch.setattr(api, 'BASE_URL', f'http://127.0.0.1:{server.server_port}/v1')
    try:
        yield state, seen
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)
        assert not thread.is_alive()


def envelope(content):
    return json.dumps({'choices': [{'message': {'content': content}}]}).encode()


def model_content(**updates):
    return json.dumps(dict(signal='SELL', confidence=0.62, reason='fixture',
                           macro_summary='synthetic', **updates))


@pytest.mark.parametrize('body,expected', [
    (envelope(model_content()), 'SELL'),
    (b'{not-json', 'HOLD'),
    (envelope('{not-json'), 'HOLD'),
    (envelope(model_content(lot_size=1.0)), 'HOLD'),
    (envelope(json.dumps(dict(signal='BUY', confidence=0.62,
                             reason='opposite', macro_summary='synthetic'))), 'HOLD'),
])
def test_real_loopback_response_parsing(candidate, loopback, body, expected):
    state, seen = loopback
    state['body'] = body
    result = asyncio.run(api.evaluate(candidate))
    assert seen.is_set(), 'The request must actually reach the local HTTP server'
    assert len(state['requests']) == 1
    request = state['requests'][0]
    assert request['path'] == '/v1/chat/completions'
    assert request['authorization'] == 'Bearer loopback-fake-provider-key'
    submitted = json.loads(request['body']['messages'][1]['content'])
    assert submitted['candidate']['request_id'] == candidate.request_id
    assert result.signal == expected
    assert result.request_id == candidate.request_id


def test_real_loopback_short_socket_read_timeout(candidate, loopback, monkeypatch, caplog):
    state, seen = loopback
    state['body'] = envelope(model_content())
    state['delay'] = True
    real_timeout = httpx.Timeout
    configured = []

    def short_timeout(*args, **kwargs):
        configured.append((args, kwargs))
        return real_timeout(0.05)

    # Configuration-only change. Real AsyncClient.post and core transport remain intact.
    monkeypatch.setattr(httpx, 'Timeout', short_timeout)
    started = time.monotonic()
    with caplog.at_level(logging.DEBUG, logger='httpcore.http11'):
        result = asyncio.run(api.evaluate(candidate))
    elapsed = time.monotonic() - started
    assert seen.is_set(), 'A preflight veto or connection failure is not a read timeout'
    assert len(state['requests']) == 1
    assert configured == [((12.0,), {})]
    assert 'receive_response_headers.failed' in caplog.text
    assert 'ReadTimeout' in caplog.text
    assert 0.04 <= elapsed < 2.0
    assert result.signal == 'HOLD'
    assert result.reason == 'AI unavailable or response invalid'
