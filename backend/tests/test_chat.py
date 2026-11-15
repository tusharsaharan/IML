"""Exercise the actual orchestration endpoint with isolated storage and no paid calls."""
import hashlib
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.core import pipeline, providers
from gateway.core.config import Settings
from gateway.core.provenance import verified_source_bytes
from gateway.core.store import Store
from gateway.features.cache import api as cache_api
from gateway.features.insights import api as insights_api
from gateway.features.routing import service as routing_api


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, database_path=tmp_path / "pipeline.sqlite3")
    for module in (pipeline, cache_api, insights_api, routing_api):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    with TestClient(app) as test_client:
        yield test_client, settings


def ask(client, **options):
    http, _ = client
    return http.post('/api/v1/chat', json={"text": "Yaar basically mera hostel ka wifi bahut slow chal raha hai", **options})


def test_real_cold_pipeline_and_repeat_short_circuit(client, monkeypatch):
    first = ask(client, compression={"method": "crf"}).json()
    assert first['answer_source'] == 'authored-demo'
    assert first['compression']['method'] == 'crf'
    assert first['routing']['scorer']['proxy'] is False
    assert first['cache']['stored'] is True
    assert first['provider_called'] is False
    assert first['usage']['provider']['total_tokens'] is None
    assert [s['stage'] for s in first['trace']] == ['cache', 'compression', 'routing', 'generation', 'insights']
    monkeypatch.setattr(pipeline, 'compression_service', lambda: pytest.fail('Cache hit compressed again'))
    monkeypatch.setattr(pipeline, 'routing_service', lambda: pytest.fail('Cache hit routed again'))
    second = ask(client, compression={"method": "crf"}).json()
    assert second['cache']['hit'] is True
    assert second['answer'] == first['answer']
    assert second['compression'] is second['routing'] is None
    assert second['usage']['reference_sent_tokens'] == 0
    assert second['model'] is None
    assert all(s['status'] == 'skipped' for s in second['trace'][1:4])
    assert len(Store(client[1].database_path).list_requests()) == 2


@pytest.mark.parametrize('language,text', [
    ('en', 'How can I renew a library book?'),
    ('hinglish', 'library ki book renew kaise karu'),
    ('hi', 'असाइनमेंट जमा करने की अंतिम तिथि कहाँ देख सकते हैं?'),
])
def test_multilingual_demo_has_labelled_answers(client, language, text):
    response = ask(client, text=text)
    assert response.status_code == 200
    assert response.json()['language'] == language
    assert response.json()['answer_source'] == 'authored-demo'


def test_optional_stages_and_generic_fallback_not_cached(client):
    body = ask(client, text='Explain quantum entanglement', compression={"enabled": False}, routing={"enabled": False}, cache={"enabled": False}).json()
    assert body['compression'] is body['routing'] is None
    assert body['answer_source'] == 'demo-fallback'
    assert body['cache']['stored'] is False
    assert body['usage']['input_tokens_saved'] == 0
    assert body['cost']['basis'] == 'no_provider_call'


@pytest.mark.parametrize('change', [
    {"routing": {"policy": "quality"}}, {"compression": {"enabled": False}},
    {"output": {"max_tokens": 15}}, {"output": {"format_constraint": "JSON only"}},
    {"language": "hi"},
])
def test_cache_does_not_cross_answer_configuration(client, change):
    first = ask(client).json()
    second = ask(client, **change).json()
    assert first['cache']['scope'] != second['cache']['scope']
    assert second['cache']['hit'] is False


def test_scope_isolation_and_management(client):
    http, _ = client
    first = ask(client).json()
    other = http.post('/api/v1/chat', headers={'X-Cache-Scope': 'another-browser'}, json={'text': first['compression']['original']}).json()
    assert other['cache']['hit'] is False
    assert other['cache']['scope'] != first['cache']['scope']
    headers = {'X-Cache-Scope': first['cache']['scope']}
    entries = http.get('/api/v1/cache/entries', headers=headers).json()['items']
    assert len(entries) == 1
    assert http.delete('/api/v1/cache/entries', headers=headers).status_code == 200
    assert ask(client).json()['cache']['hit'] is False


def test_lost_book_false_match_not_automatically_reused(client):
    ask(client, text='How can I renew a library book?')
    body = ask(client, text='How do I renew a library book I have already lost?').json()
    assert body['cache']['candidate_hit'] is True
    assert body['cache']['match_type'] == 'semantic'
    assert body['cache']['hit'] is False
    assert body['answer_source'] == 'authored-demo'


def test_approximate_reuse_requires_opt_in(client):
    ask(client, text='How can I renew a library book?')
    body = ask(client, text='library ki book renew kaise karu', cache={'accept_semantic': True}).json()
    assert body['cache']['hit'] is True
    assert body['cache']['match_type'] == 'semantic'
    assert body['answer_source'] == 'cache'


def test_changed_math_operators_not_an_exact_reuse(client):
    ask(client, text='Explain assignment x > 5')
    body = ask(client, text='Explain assignment x < 5').json()
    assert body['cache']['hit'] is False
    assert body['cache']['stored'] is False
    assert 'not saved' in body['cache']['store_reason']


def test_private_content_not_learned(client):
    body = ask(client, text='My wifi account email is user@example.com').json()
    assert body['cache']['stored'] is False


@pytest.mark.parametrize('cap', [1, 2, 9, 40, 120])
@pytest.mark.parametrize('fmt', [None, '3 bullets', 'JSON only'])
def test_demo_caps_and_valid_json(client, cap, fmt):
    body = ask(client, output={'max_tokens': cap, 'format_constraint': fmt}).json()
    assert 0 < body['usage']['reference_output_tokens'] <= cap
    if fmt == 'JSON only':
        json.loads(body['answer'])
    repeat = ask(client, output={'max_tokens': cap, 'format_constraint': fmt}).json()
    assert repeat['output']['demo_truncated'] == body['output']['demo_truncated']


def test_compression_export_handoff_not_compressed_twice(client):
    body = ask(client, text='wifi is slow', compression={'enabled': False, 'method': 'crf', 'budget': 0.6}, compare=False).json()
    assert body['compression'] is None
    assert body['usage']['reference_prompt_tokens'] == body['usage']['reference_original_tokens']


def test_phrase_guard_survives_pipeline(client):
    text = 'yaar matlab mera email user@example.com par bhejo na'
    body = ask(client, text=text, compression={'method': 'crf', 'protected_phrases': ['yaar']}).json()
    assert body['compression']['protection_fallback'] is True
    assert body['compression']['compressed'] == text


@pytest.mark.parametrize('options', [
    {'text': ''}, {'text': '   '}, {'text': 'x' * 4001}, {'output': {'max_tokens': 0}},
    {'output': {'max_tokens': 4097}}, {'routing': {'policy': 'magic'}}, {'compare': True},
    {'compression': {'protected_phrases': ['absent']}}, {'unexpected': True},
])
def test_invalid_request_does_not_record(client, options):
    assert ask(client, **options).status_code == 422
    assert Store(client[1].database_path).list_requests() == []


def test_unconfigured_live_never_falls_back_to_demo(client):
    response = ask(client, mode='live')
    assert response.status_code == 503
    assert Store(client[1].database_path).list_requests() == []


def live_transport(client, monkeypatch, handler):
    settings = client[1]
    settings.mode = 'live'
    settings.api_base_url = 'https://provider.invalid/v1'
    settings.api_key = 'test-key-not-real'
    settings.cheap_model, settings.strong_model = 'small-test', 'large-test'
    original = httpx.AsyncClient
    monkeypatch.setattr(providers.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))


def test_live_forwards_selected_model_compression_and_output_controls(client, monkeypatch):
    sent = []
    def handler(request):
        payload = json.loads(request.content)
        sent.append(payload)
        assert request.headers['authorization'] == 'Bearer test-key-not-real'
        return httpx.Response(200, json={'choices': [{'message': {'content': 'Test provider answer'}}], 'usage': {'prompt_tokens': 31, 'completion_tokens': 4, 'total_tokens': 35}})
    live_transport(client, monkeypatch, handler)
    client[1].cheap_input_price = client[1].strong_input_price = 1
    client[1].cheap_output_price = client[1].strong_output_price = 2
    body = ask(client, mode='live', output={'max_tokens': 40, 'format_constraint': '3 bullets'}).json()
    assert sent[0]['model'] == body['routing']['selected_model_label'] == body['model']
    assert sent[0]['messages'][-1]['content'] == body['compression']['compressed']
    assert sent[0]['messages'][0]['role'] == 'system'
    assert sent[0]['max_tokens'] == 40
    assert body['answer_source'] == 'live-provider'
    assert body['usage']['provider']['total_tokens'] == 35
    assert body['cost']['usd'] == pytest.approx(39 / 1_000_000)
    assert body['cost']['basis'] == 'configured_prices_provider_usage'
    again = ask(client, mode='live', output={'max_tokens': 40, 'format_constraint': '3 bullets'}).json()
    assert again['answer_source'] == 'cache'
    assert len(sent) == 1
    assert again['usage']['provider']['total_tokens'] is None


def test_live_missing_usage_and_prices_remain_unknown(client, monkeypatch):
    live_transport(client, monkeypatch, lambda _: httpx.Response(200, json={'choices': [{'message': {'content': 'Test'}}]}))
    body = ask(client, mode='live').json()
    assert body['cost']['usd'] is None
    assert all(value is None for value in body['usage']['provider'].values())


@pytest.mark.parametrize('status,body', [(401, {}), (500, {}), (200, {'choices': []}), (200, {'choices': [{'message': {'content': ''}}]}), (200, {'choices': [{'message': {'content': 'answer'}}], 'usage': {'prompt_tokens': -1}})])
def test_provider_failure_does_not_write_success_or_cache(client, monkeypatch, status, body):
    live_transport(client, monkeypatch, lambda _: httpx.Response(status, json=body))
    response = ask(client, mode='live')
    assert response.status_code == 502
    assert 'test-key' not in response.text
    assert Store(client[1].database_path).list_requests() == []
    assert Store(client[1].database_path).list_cache() == []


def test_provider_timeout_is_visible(client, monkeypatch):
    def timeout(_):
        raise httpx.ReadTimeout('fake')
    live_transport(client, monkeypatch, timeout)
    assert ask(client, mode='live').status_code == 504


def test_history_preserves_cache_zero_and_source(client):
    ask(client)
    ask(client)
    item = client[0].get('/api/v1/insights/history?limit=1').json()['items'][0]
    assert item['input_tokens'] == 0
    assert item['cache_hit'] is True
    assert item['answer_source'] == 'cache'
    assert item['cost_usd'] == 0


def test_documented_env_names_and_blank_optional_values(tmp_path, monkeypatch):
    monkeypatch.delenv('IML_MODE', raising=False)
    path = tmp_path / '.env'
    path.write_text('IML_MODE=live\nIML_API_BASE_URL=https://example.invalid/v1\nIML_API_KEY=test\nIML_CHEAP_MODEL=small\nIML_STRONG_MODEL=large\nIML_CHEAP_INPUT_PRICE=\n', encoding='utf-8')
    settings = Settings(_env_file=path)
    assert settings.mode == 'live'
    assert providers.Provider(settings).is_live()
    assert settings.cheap_input_price is None


def test_source_verification_accepts_only_manifest_matching_newlines(tmp_path):
    path = tmp_path / 'example.py'
    path.write_bytes(b'original\n')
    expected = hashlib.sha256(b'original\r\n').hexdigest()
    assert verified_source_bytes(path, expected) == b'original\r\n'
    path.write_bytes(b'changed\n')
    with pytest.raises(ValueError):
        verified_source_bytes(path, expected)
    binary = tmp_path / 'model.pkl'
    binary.write_bytes(b'original\n')
    with pytest.raises(ValueError):
        verified_source_bytes(binary, expected)


@pytest.mark.parametrize('cap', [1, 2, 9])
@pytest.mark.parametrize('fmt', [None, '3 bullets', 'JSON only', 'no preamble'])
def test_insights_small_caps_do_not_exceed_ceiling(client, cap, fmt):
    body = client[0].post('/api/v1/insights/cost-estimate', json={'text': 'wifi help', 'estimated_output_tokens': 1, 'max_tokens_cap': cap, 'format_constraint': fmt}).json()
    assert 1 <= body['estimated_output_tokens'] <= cap
    assert body['output_tokens_saved'] >= 0
