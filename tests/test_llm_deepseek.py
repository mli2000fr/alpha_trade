"""Provider switching, archived evidence and fail-closed behaviour; no network."""
import copy
import json
from datetime import datetime
from types import SimpleNamespace
import pytest
from service.llm_directional.config import FilterConfig, load_filter_config
from service.llm_directional.openai_client import ResponsesClient, build_request
from service.llm_directional.validation import parse_response


def web_response():
    sources = [{'url': f'https://issuer.example/{i}', 'title': f'Release {i}',
                'published_at': '2026-10-07T18:00:00Z'} for i in range(2)]
    answer = dict(symbol='ABC', issuer='ABC Corp', identity_verified=True,
                  decision='LONG', confidence=.9, bull_case='Growth', bear_case='Risk',
                  catalysts=['Results'], sources=sources)
    return {'status': 'completed', 'output': [
        {'type': 'web_search_call', 'status': 'completed', 'action': {'sources': sources}},
        {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(answer)}]}]}


def session_for(web, finish='stop', mutate=None, code=200):
    answer = json.loads(web['output'][-1]['content'][0]['text'])
    if mutate:
        mutate(answer)
    raw = {'choices': [{'finish_reason': finish, 'message': {'content': json.dumps(answer)}}]}
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=200 if len(calls) == 1 else code,
                               headers={}, json=lambda: web if len(calls) == 1 else raw)
    return SimpleNamespace(post=post), calls


@pytest.fixture
def credentials(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-not-a-real-key')
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-deepseek-not-a-real-key')


def test_provider_config_and_legacy(tmp_path):
    path = tmp_path / 'config.yaml'
    path.write_text('llm_directional_filter:\n  provider: deepseek\n  deepseek_model: my-deepseek\n', encoding='utf-8')
    config = load_filter_config(path)
    assert config.provider_label == 'DeepSeek' and config.analysis_model == 'my-deepseek'
    assert FilterConfig().provider_label == 'GPT'
    legacy = FilterConfig().snapshot()
    for field in ('provider', 'deepseek_model', 'deepseek_api_key_env'):
        legacy.pop(field)
    assert build_request({}, FilterConfig(**legacy)) == build_request({}, FilterConfig())
    with pytest.raises(ValueError):
        FilterConfig(provider='unknown')


def test_deepseek_requires_both_keys(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    with pytest.raises(ValueError, match='DEEPSEEK_API_KEY'):
        ResponsesClient(FilterConfig(provider='deepseek'))


def test_deepseek_transport_archive_and_parse(credentials):
    config = FilterConfig(provider='deepseek', deepseek_model='deepseek-flash')
    web = web_response()
    session, calls = session_for(web)
    request = build_request({'symbol': 'ABC'}, config)
    archived = ResponsesClient(config, session)(request)
    parsed = parse_response(archived, 'ABC', config, datetime(2026, 10, 7, 22))
    assert parsed['eligible'] and parsed['decision'] == 'LONG'
    assert archived['web_response'] == web and archived['analysis_response']['choices']
    assert calls[0][0] == 'https://api.openai.com/v1/responses'
    assert calls[1][0] == 'https://api.deepseek.com/chat/completions'
    assert calls[1][1]['json']['model'] == config.deepseek_model
    assert calls[1][1]['json']['response_format'] == {'type': 'json_object'}
    assert all(call[1]['allow_redirects'] is False for call in calls)
    serialized = json.dumps(archived) + json.dumps(request) + json.dumps(config.snapshot())
    assert 'test-openai-not-a-real-key' not in serialized
    assert 'test-deepseek-not-a-real-key' not in serialized


def test_deepseek_cannot_invent_web_trace(credentials):
    cfg = FilterConfig(provider='deepseek')
    session, _ = session_for(web_response(), mutate=lambda a: a['sources'][0].update(url='https://invented.example'))
    raw = ResponsesClient(cfg, session)(build_request({'symbol': 'ABC'}, cfg))
    # A fabricated URL even inserted into the convenience output must not qualify.
    raw['output'][0]['action']['sources'] = copy.deepcopy(raw['output'][0]['action']['sources'])
    raw['output'][0]['action']['sources'].append({'url': 'https://invented.example'})
    parsed = parse_response(raw, 'ABC', cfg, datetime(2026, 10, 7, 22))
    assert not parsed['eligible'] and parsed['excluded_sources']


@pytest.mark.parametrize('finish,code', [('length', 200), ('stop', 403)])
def test_deepseek_failure_keeps_web_and_blocks(credentials, finish, code):
    cfg = FilterConfig(provider='deepseek')
    session, calls = session_for(web_response(), finish=finish, code=code)
    raw = ResponsesClient(cfg, session)(build_request({'symbol': 'ABC'}, cfg))
    assert raw['web_response']['status'] == 'completed' and len(calls) == 2
    with pytest.raises(ValueError, match='DeepSeek'):
        parse_response(raw, 'ABC', cfg, datetime(2026, 10, 7, 22))


def test_no_web_no_deepseek_call(credentials):
    cfg = FilterConfig(provider='deepseek')
    web = web_response()
    web['output'] = web['output'][1:]
    session, calls = session_for(web)
    raw = ResponsesClient(cfg, session)(build_request({'symbol': 'ABC'}, cfg))
    assert len(calls) == 1 and raw['status'] == 'failed'
    with pytest.raises(ValueError):
        parse_response(raw, 'ABC', cfg, datetime(2026, 10, 7, 22))
