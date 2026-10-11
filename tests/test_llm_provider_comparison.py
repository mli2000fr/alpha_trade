from types import SimpleNamespace
import pytest
from service.llm_directional.provider_comparison import SharedWebClient, comparison_rows
from service.llm_directional.config import FilterConfig


def test_common_web_never_generates_new_openai_answer(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test')
    session = SimpleNamespace(post=lambda *a, **k: pytest.fail('unexpected paid call'))
    client = SharedWebClient(FilterConfig(provider='deepseek'),
        {'ABC': {'request': {'model': 'test'}, 'response': {'status': 'completed'}}}, session=session)
    client.current_symbol = 'ABC'
    assert client._post('https://api.openai.com/v1/responses', {'model': 'test'}, 'test', 'OpenAI')['status'] == 'completed'
    with pytest.raises(ValueError):
        client._post('https://api.openai.com/v1/responses', {'model': 'other'}, 'test', 'OpenAI')


def test_missing_answers_are_not_agreement():
    rows = comparison_rows({'candidates': []}, {'candidates': []})
    assert len(rows) == 11 and not any(r['same_decision'] for r in rows)
