"""Offline safety regression tests; all provider responses are mocked."""
import json
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from mac_ai import app as api


@pytest.fixture
def context(tmp_path, monkeypatch):
    for name in ("ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(name, raising=False)
    now = api.utc_now().replace(microsecond=0)
    stamp = now.isoformat().replace('+00:00', 'Z')
    macro = dict(schema_version="2", timestamp_utc=stamp, dxy_change_pct=0.1, us10y_change_bps=2.0,
                 real_yield_change_bps=1.0, high_impact_news_block=False,
                 dxy_observed_at_utc=stamp, us10y_observed_at_utc=stamp,
                 real_yield_observed_at_utc=stamp, news_observed_at_utc=stamp,
                 news_valid_until_utc=(now + timedelta(minutes=10)).isoformat().replace('+00:00', 'Z'),
                 provenance_sha256='a' * 64)
    req = dict(schema_version='1.1', request_id='candidate-1', symbol='XAUUSD', timeframe='M5',
        bar_time_utc=stamp, regime='STRONG_DOWNTREND', setup='TREND_CONTINUATION',
        direction='SELL', confidence=0.6, close=4000.0, atr=5.0, ema_fast=3995.0,
        ema_slow=4010.0, adx=24.0, macro=macro, reason='fixture')
    path = tmp_path / 'macro.csv'
    def feed(**updates):
        snapshot = {**macro, **updates}
        path.write_text(','.join(snapshot) + '\n' + ','.join(
            str(int(value)) if isinstance(value, bool) else str(value)
            for value in snapshot.values()) + '\n')
    feed()
    monkeypatch.setattr(api, 'TOKEN', 'a' * 40)
    monkeypatch.setattr(api, 'API_KEY', 'fake-test-key')
    monkeypatch.setattr(api, 'MACRO_FILE', path)
    monkeypatch.setattr(api, 'LOG_FILE', tmp_path / 'audit.jsonl')
    api.RECENT_CALLS.clear()
    api.DECISIONS.clear()
    api.IN_FLIGHT.clear()
    return TestClient(api.app), req, feed, now


def post(context, **kwargs):
    client, req, _, _ = context
    return client.post('/decision', json=req, headers={'Authorization': 'Bearer ' + 'a' * 40}, **kwargs)


def model_result(monkeypatch, **updates):
    output = dict(signal='SELL', confidence=0.62, reason='confirmed', macro_summary='fresh')
    output.update(updates)
    async def provider(self, *args, **kwargs):
        return httpx.Response(200, request=httpx.Request('POST', 'https://mock.invalid'),
            json={'choices': [{'message': {'content': json.dumps(output)}}]})
    monkeypatch.setattr(httpx.AsyncClient, 'post', provider)


def forbid_provider(monkeypatch):
    async def provider(*args, **kwargs):
        # pytest's failure is not swallowed by the service's fail-closed Exception handler.
        pytest.fail('Provider should not be called')
    monkeypatch.setattr(httpx.AsyncClient, 'post', provider)


def test_frozen_response_contract(context, monkeypatch):
    model_result(monkeypatch)
    response = post(context)
    assert response.status_code == 200
    body = response.json()
    assert body['signal'] == 'SELL'
    assert body['request_id'] == context[1]['request_id']
    assert body['schema_version'] == '1.1'
    assert api.fresh(body['timestamp_utc'], api.utc_now())
    contract = json.loads((api.Path(__file__).resolve().parents[2] / 'docs/API_CONTRACT.json').read_text())
    assert set(body) == set(contract['response'])
    assert set(context[1]) == set(contract['request'])


@pytest.mark.parametrize('token', ['', 'CHANGE_ME_SHARED_TOKEN', 'replace_with_a_long_random_secret', 'tiny'])
def test_unconfigured_token(context, monkeypatch, token):
    monkeypatch.setattr(api, 'TOKEN', token)
    assert post(context).status_code == 503


def test_wrong_auth(context):
    assert context[0].post('/decision', json=context[1]).status_code == 401


@pytest.mark.parametrize('target,age', [('bar_time_utc', 901), ('bar_time_utc', -1), ('macro', 901), ('macro', -1)])
def test_request_stale_future(context, monkeypatch, target, age):
    forbid_provider(monkeypatch)
    stamp = (context[3] - timedelta(seconds=age)).isoformat().replace('+00:00', 'Z')
    if target == 'macro':
        context[1]['macro']['timestamp_utc'] = stamp
    else:
        context[1][target] = stamp
    assert post(context).json()['signal'] == 'HOLD'


@pytest.mark.parametrize('update', [dict(timestamp_utc='2020-01-01T00:00:00Z'),
    dict(timestamp_utc='2099-01-01T00:00:00Z'), dict(timestamp_utc='bad'),
    dict(dxy_change_pct='nan'), dict(us10y_change_bps='inf'),
    dict(high_impact_news_block='unknown'), dict(high_impact_news_block=True)])
def test_bad_csv(context, monkeypatch, update):
    forbid_provider(monkeypatch)
    context[2](**update)
    assert post(context).json()['signal'] == 'HOLD'


def test_missing_csv(context, monkeypatch):
    api.MACRO_FILE.unlink()
    forbid_provider(monkeypatch)
    assert post(context).json()['signal'] == 'HOLD'


def test_wrong_csv_header(context, monkeypatch):
    api.MACRO_FILE.write_text('timestamp,dxy_change_pct\n2026-01-01T00:00:00Z,0\n')
    forbid_provider(monkeypatch)
    assert post(context).json()['signal'] == 'HOLD'


def test_request_news_block(context, monkeypatch):
    context[1]['macro']['high_impact_news_block'] = True
    forbid_provider(monkeypatch)
    assert post(context).json()['signal'] == 'HOLD'


@pytest.mark.parametrize('field,value', [('close', '4000'), ('confidence', True),
    ('atr', 0.0), ('close', -1.0), ('unknown', 1), ('request_id', ''),
    ('bar_time_utc', '2026-01-01T00:00:00'), ('bar_time_utc', '2026-01-01T00:00:00+01:00')])
def test_invalid_request(context, field, value):
    context[1][field] = value
    assert post(context).status_code == 422


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity'])
def test_nonfinite_request(context, value):
    body = json.dumps(context[1]).replace('4000.0', value)
    response = context[0].post('/decision', content=body,
        headers={'Authorization': 'Bearer ' + 'a' * 40, 'Content-Type': 'application/json'})
    assert response.status_code == 422


@pytest.mark.parametrize('output', [dict(signal='BUY'), dict(signal='EXECUTE'),
    dict(confidence='0.9'), dict(confidence=True), dict(confidence=float('nan')),
    dict(confidence=float('inf')), dict(confidence=-0.1), dict(confidence=1.1),
    dict(confidence=0.5799), dict(reason=42), dict(extra='lot_size'), dict(reason='x'*181)])
def test_invalid_or_veto_model(context, monkeypatch, output):
    model_result(monkeypatch, **output)
    assert post(context).json()['signal'] == 'HOLD'


def test_confidence_threshold_preserved(context, monkeypatch):
    model_result(monkeypatch, confidence=0.58)
    assert post(context).json()['signal'] == 'SELL'


@pytest.mark.parametrize('error', [httpx.ReadTimeout('secret-test'), ValueError('secret-test')])
def test_provider_failure_redacted(context, monkeypatch, error, caplog):
    async def provider(*args, **kwargs):
        raise error
    monkeypatch.setattr(httpx.AsyncClient, 'post', provider)
    response = post(context)
    assert response.json()['signal'] == 'HOLD'
    assert 'secret-test' not in response.text + caplog.text + api.LOG_FILE.read_text()


def test_malformed_provider_json(context, monkeypatch):
    async def provider(*args, **kwargs):
        return httpx.Response(200, request=httpx.Request('POST', 'https://mock.invalid'),
            json={'choices': [{'message': {'content': '{invalid'}}]})
    monkeypatch.setattr(httpx.AsyncClient, 'post', provider)
    assert post(context).json()['signal'] == 'HOLD'


def test_duplicate_and_changed_request_id(context, monkeypatch):
    model_result(monkeypatch)
    assert post(context).json()['signal'] == 'SELL'
    assert post(context).json()['signal'] == 'HOLD'
    context[1]['close'] = 4001.0
    assert post(context).json()['signal'] == 'HOLD'


def test_log_failure_blocks_entry(context, monkeypatch):
    model_result(monkeypatch)
    monkeypatch.setattr(api, 'LOG_FILE', api.LOG_FILE.parent)
    assert post(context).json()['signal'] == 'HOLD'


def test_audit_excludes_free_text(context, monkeypatch):
    context[1]['reason'] = 'sensitive user input'
    model_result(monkeypatch, reason='sensitive model output')
    post(context)
    audit = api.LOG_FILE.read_text()
    assert 'sensitive' not in audit
    assert 'fake-test-key' not in audit


def test_missing_api_key(context, monkeypatch):
    monkeypatch.setattr(api, 'API_KEY', '')
    forbid_provider(monkeypatch)
    assert post(context).json()['signal'] == 'HOLD'


def test_rate_limit(context, monkeypatch):
    monkeypatch.setattr(api, 'API_KEY', '')
    for i in range(60):
        context[1]['request_id'] = f'candidate-{i}'
        assert post(context).status_code == 200
    assert post(context).status_code == 429


@pytest.mark.parametrize('content', [
    '{"signal":"BUY","signal":"SELL","confidence":0.8,"reason":"x","macro_summary":"x"}',
    '{"signal":"SELL","confidence":0.8,"reason":"x"}',
    '[]', 'null', '{"signal":"SELL","confidence":NaN,"reason":"x","macro_summary":"x"}'])
def test_strict_provider_json(context, monkeypatch, content):
    async def provider(*args, **kwargs):
        return httpx.Response(200, request=httpx.Request('POST', 'https://mock.invalid'),
            json={'choices': [{'message': {'content': content}}]})
    monkeypatch.setattr(httpx.AsyncClient, 'post', provider)
    assert post(context).json()['signal'] == 'HOLD'


def test_http_error(context, monkeypatch):
    async def provider(*args, **kwargs):
        return httpx.Response(401, request=httpx.Request('POST', 'https://mock.invalid'))
    monkeypatch.setattr(httpx.AsyncClient, 'post', provider)
    assert post(context).json()['signal'] == 'HOLD'


def test_expired_during_model_call(context, monkeypatch):
    model_result(monkeypatch)
    times = iter([context[3], context[3] + timedelta(seconds=901)])
    monkeypatch.setattr(api, 'utc_now', lambda: next(times, context[3] + timedelta(seconds=901)))
    assert post(context).json()['signal'] == 'HOLD'


def test_csv_out_of_order(context, monkeypatch):
    text = api.MACRO_FILE.read_text()
    api.MACRO_FILE.write_text(text + text.splitlines()[1] + '\n')
    forbid_provider(monkeypatch)
    assert post(context).json()['signal'] == 'HOLD'


def test_historical_then_fresh_csv_rejected(context, monkeypatch):
    lines = api.MACRO_FILE.read_text().splitlines()
    old = lines[1].replace(context[1]['macro']['timestamp_utc'], '2020-01-01T00:00:00Z')
    api.MACRO_FILE.write_text(lines[0] + '\n' + old + '\n' + lines[1] + '\n')
    forbid_provider(monkeypatch)
    assert post(context).json()['signal'] == 'HOLD'


def test_nested_unknown_field(context):
    context[1]['macro']['source'] = 'unexpected'
    assert post(context).status_code == 422


@pytest.mark.parametrize('change', [
    'news_block', 'missing', 'malformed', 'dxy', 'us10y', 'real_yield', 'timestamp',
    'unchanged',
])
def test_macro_revalidated_after_provider(context, monkeypatch, change):
    """Never approve using a snapshot invalidated while the model was awaited."""
    async def provider(self, *args, **kwargs):
        if change == 'news_block':
            context[2](high_impact_news_block=True)
        elif change == 'missing':
            api.MACRO_FILE.unlink()
        elif change == 'malformed':
            api.MACRO_FILE.write_text('invalid feed\n')
        elif change == 'dxy':
            context[2](dxy_change_pct=0.2)
        elif change == 'us10y':
            context[2](us10y_change_bps=3.0)
        elif change == 'real_yield':
            context[2](real_yield_change_bps=2.0)
        elif change == 'timestamp':
            context[2](timestamp_utc=(context[3] - timedelta(seconds=1)).isoformat())
        else:
            # Republishing identical observations must not veto an unchanged review.
            context[2]()
        output = dict(signal='SELL', confidence=0.62, reason='confirmed', macro_summary='fresh')
        return httpx.Response(200, request=httpx.Request('POST', 'https://mock.invalid'),
            json={'choices': [{'message': {'content': json.dumps(output)}}]})

    monkeypatch.setattr(httpx.AsyncClient, 'post', provider)
    response = post(context)
    assert response.status_code == 200
    assert response.json()['signal'] == ('SELL' if change == 'unchanged' else 'HOLD')


@pytest.mark.parametrize('field', [
    'schema_version', 'dxy_observed_at_utc', 'us10y_observed_at_utc',
    'real_yield_observed_at_utc', 'news_observed_at_utc', 'news_valid_until_utc',
    'provenance_sha256',
])
def test_missing_macro_source_metadata_rejected(context, monkeypatch, field):
    forbid_provider(monkeypatch)
    del context[1]['macro'][field]
    assert post(context).status_code == 422


@pytest.mark.parametrize('version', [None, '1.0', 'unknown'])
def test_old_or_unknown_api_protocol_rejected(context, monkeypatch, version):
    forbid_provider(monkeypatch)
    if version is None:
        del context[1]['schema_version']
    else:
        context[1]['schema_version'] = version
    assert post(context).status_code == 422


@pytest.mark.parametrize('side', ['request', 'canonical'])
@pytest.mark.parametrize('field,age', [
    ('dxy_observed_at_utc', 901), ('us10y_observed_at_utc', 901),
    ('real_yield_observed_at_utc', 901), ('news_valid_until_utc', 1),
])
def test_macro_source_or_calendar_expiry(context, monkeypatch, side, field, age):
    forbid_provider(monkeypatch)
    expired = (context[3] - timedelta(seconds=age)).isoformat().replace('+00:00', 'Z')
    if side == 'request':
        context[1]['macro'][field] = expired
    else:
        context[2](**{field: expired})
    assert post(context).json()['signal'] == 'HOLD'


@pytest.mark.parametrize('field', ['dxy_observed_at_utc', 'news_valid_until_utc'])
def test_source_validity_expires_during_provider(context, monkeypatch, field):
    # The assembled snapshot stays fresh: only the source or calendar validity expires.
    stamp = (context[3] - timedelta(seconds=899) if field == 'dxy_observed_at_utc'
             else context[3] + timedelta(seconds=1)).isoformat().replace('+00:00', 'Z')
    context[1]['macro'][field] = stamp
    context[2](**{field: stamp})
    monkeypatch.setattr(api, 'utc_now', lambda: context[3])
    calls = []

    async def provider(self, *args, **kwargs):
        calls.append(True)
        monkeypatch.setattr(api, 'utc_now', lambda: context[3] + timedelta(seconds=2))
        output = dict(signal='SELL', confidence=0.62, reason='confirmed', macro_summary='fresh')
        return httpx.Response(200, request=httpx.Request('POST', 'https://mock.invalid'),
            json={'choices': [{'message': {'content': json.dumps(output)}}]})

    monkeypatch.setattr(httpx.AsyncClient, 'post', provider)
    assert post(context).json()['signal'] == 'HOLD'
    assert calls == [True]


@pytest.mark.parametrize('field,value', [
    ('dxy_change_pct', 0.2), ('us10y_change_bps', 3.0), ('real_yield_change_bps', 2.0),
    ('provenance_sha256', 'b' * 64),
    ('dxy_observed_at_utc', 'older_source'), ('timestamp_utc', 'newer_snapshot'),
])
def test_request_canonical_disagreement_vetoes_before_provider(context, monkeypatch, field, value):
    forbid_provider(monkeypatch)
    if value == 'older_source':
        value = (context[3] - timedelta(seconds=1)).isoformat().replace('+00:00', 'Z')
    elif value == 'newer_snapshot':
        value = (context[3] - timedelta(seconds=1)).isoformat().replace('+00:00', 'Z')
    context[1]['macro'][field] = value
    assert post(context).json()['signal'] == 'HOLD'


def test_old_csv_protocol_rejected(context, monkeypatch):
    forbid_provider(monkeypatch)
    old_fields = ['timestamp_utc', 'dxy_change_pct', 'us10y_change_bps',
                  'real_yield_change_bps', 'high_impact_news_block']
    macro = context[1]['macro']
    api.MACRO_FILE.write_text(','.join(old_fields) + '\n' + ','.join(
        '0' if isinstance(macro[field], bool) else str(macro[field]) for field in old_fields) + '\n')
    assert post(context).json()['signal'] == 'HOLD'
