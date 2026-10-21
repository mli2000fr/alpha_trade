import copy

import pytest

from scripts.research.us_llm_factual_readiness import (
    checked_stamp, excerpts, quote_span, readable_documents,
    request_key, request_material, run, validate_answer,
)


def document(text='Revenue was $12 million. Outlook remains unchanged.'):
    doc = dict(document_id='0:EX-99.1', text=text, text_sha256='test')
    doc['excerpts'] = excerpts(doc, [])
    return doc


def packet():
    return dict(symbol='TEST', cik='000001', sec_acceptance_proxy='2024-01-02T21:00:00Z',
                documents=[document()])


def answer():
    quote = 'Revenue was $12 million.'
    return dict(facts=[dict(category='ACTUAL', metric='Revenue', value_text='$12 million',
            period_label=None, currency=None, unit='million', accounting_basis=None,
            novelty='NOT_ESTABLISHED', document_id='0:EX-99.1',
            start=0, end=len(quote), quote=quote)], limitations=['Period not supplied'])


def test_exact_grounding_and_abstention():
    assert validate_answer(packet(), answer())
    assert validate_answer(packet(), dict(facts=[], limitations=['Insufficient context']))


@pytest.mark.parametrize('change', ['quote', 'offset', 'bool_offset', 'direction', 'novelty', 'category', 'duplicate'])
def test_bad_answer_rejected(change):
    value = answer()
    if change == 'quote': value['facts'][0]['quote'] = 'Revenue was $30 million.'
    if change == 'offset': value['facts'][0]['start'] = -1
    if change == 'bool_offset': value['facts'][0]['start'] = False
    if change == 'direction': value['direction'] = 'LONG'
    if change == 'novelty': value['facts'][0]['novelty'] = 'NEW'
    if change == 'category': value['facts'][0]['category'] = 'SHORT'
    if change == 'duplicate': value['facts'].append(copy.deepcopy(value['facts'][0]))
    with pytest.raises(ValueError): validate_answer(packet(), value)


def test_quote_outside_supplied_windows_rejected():
    p = packet(); p['documents'][0]['excerpts'] = [dict(start=25, end=35, quote=p['documents'][0]['text'][25:35])]
    with pytest.raises(ValueError, match='supplied'): validate_answer(p, answer())


def test_timezone_required_and_original_instant_preserved():
    with pytest.raises(ValueError): checked_stamp('2024-01-01T21:00:00')
    assert checked_stamp('2024-01-01T21:00:00Z').hour == 21


def test_no_human_label_or_price_in_request():
    p = packet(); p['relative_reaction'] = -0.9; p['reviewed_kind'] = 'RESULTS'
    assert set(request_material(p)) == {'prompt', 'symbol', 'cik', 'sec_acceptance_proxy', 'documents'}


def test_cache_identity_includes_issuer_excerpts_provider_and_options():
    p = packet(); key = request_key(p, 'provider', 'model', {'temperature': 0})
    assert key == request_key(p, 'provider', 'model', {'temperature': 0})
    assert key != request_key(p, 'other', 'model', {'temperature': 0})
    assert key != request_key(p, 'provider', 'other', {'temperature': 0})
    assert key != request_key(p, 'provider', 'model', {'temperature': 1})
    p['symbol'] = 'OTHER'
    assert key != request_key(p, 'provider', 'model', {'temperature': 0})
    p = packet(); p['documents'][0]['excerpts'][0]['quote'] += 'changed'
    assert key != request_key(p, 'provider', 'model', {'temperature': 0})


def test_full_text_is_not_silently_sent_and_late_required_quote_included():
    text = 'a' * 30000 + 'Special fiscal quarter ended on March 29.'
    doc = document(text); span = quote_span([doc], 'Special fiscal quarter ended on March 29.')
    chunks = excerpts(doc, [span])
    assert sum(len(c['quote']) for c in chunks) < len(text)
    assert any(c['start'] <= span['start'] and c['end'] >= span['end'] for c in chunks)


def test_sec_indexes_not_treated_as_earnings_text():
    body = ('<DOCUMENT><TYPE>EX-99\n<TEXT>SEC EDGAR Submission ' + 'a' * 200 + '</TEXT></DOCUMENT>'
            '<DOCUMENT><TYPE>EX-99.1\n<TEXT><p>Real results ' + 'b' * 200 + '</p></TEXT></DOCUMENT>')
    docs = readable_documents(body)
    assert len(docs) == 1
    assert 'Real results' in docs[0]['text']


def test_missing_quote_is_not_invented():
    with pytest.raises(ValueError): quote_span([document()], 'EPS was 4.0')


def test_never_replace_existing_output(tmp_path):
    with pytest.raises(ValueError, match='Fresh'): run(tmp_path)
