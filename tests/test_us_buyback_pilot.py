from decimal import Decimal
from bs4 import BeautifulSoup
import pytest
from scripts.research.us_buyback_pilot import (
    annual, unique, sample_symbols, select_filing, extract, primary_from_index,
    ix_number, original_facts, corroborate,
)


def row(**kw):
    return dict(start='2023-01-01', end='2023-12-31', filed='2024-02-15',
                form='10-K', accn='a', val=100, **kw)


def payload(tags):
    return {'facts': {'us-gaap': {t: {'units': {u: r}} for t, (u, r) in tags.items()}}}


@pytest.mark.parametrize('days,ok', [(90, False), (349, False), (350, True), (378, True), (379, False)])
def test_duration(days, ok):
    import pandas as pd
    r = row(); r['end'] = str((pd.Timestamp(r['start'])+pd.Timedelta(days=days-1)).date())
    assert annual(r) == ok


def test_missing_not_zero_and_conflicts():
    assert unique([]) == (None, 'MISSING_NOT_ZERO')
    assert unique([{'val': 0}]) == (0., 'OK')
    assert unique([{'val': 1}, {'val': 2}])[0] is None
    assert unique([{'val': float('nan')}])[0] is None


def test_selection_does_not_use_values_or_future_year():
    a = row(); b = dict(a, filed='2024-03-01', accn='b', val=100000)
    c = dict(a, filed='2025-01-01', accn='c', val=-100000)
    chosen = select_filing(payload({'PaymentsForRepurchaseOfCommonStock': ('USD', [a,b,c])}))
    assert chosen['accession'] == 'a'


def test_no_amended_or_foreign_substitution():
    assert select_filing(payload({'X': ('USD', [dict(row(), form='20-F'), dict(row(), form='10-K/A')])})) is None


def test_no_sum_issuance_or_missing_zero():
    p = payload({'PaymentsForRepurchaseOfCommonStock': ('USD', [row()]),
                 'ProceedsFromIssuanceOfCommonStock': ('USD', [dict(row(), val=20)]),
                 'ProceedsFromStockOptionsExercised': ('USD', [dict(row(), val=10)])})
    e = extract(p, select_filing(p))
    assert e['values']['common_issuance_cash'] == 20
    assert e['values']['option_exercises_cash'] == 10
    assert e['values']['issuance_cash'] is None
    assert 'net_buyback' not in e['values']
    assert e['values']['shares_change'] is None


def test_no_ytd_or_restatement_in_original_accession():
    p = payload({'PaymentsForRepurchaseOfCommonStock': ('USD', [row(), dict(row(), accn='b', filed='2025-01-01', val=900)])})
    assert extract(p, select_filing(p))['values']['repurchases'] == 100


def test_hash_cohort_is_order_independent_and_deduplicates():
    assert sample_symbols(['B','A','B','C'], 2) == sample_symbols(['C','B','A'], 2)


def test_primary_strict_form_and_path():
    html = b'<table><tr><td>1</td><td>Form</td><td><a href="/ixviewer/a">issuer.htm</a></td><td>10-K</td></tr></table>'
    assert primary_from_index(html) == 'issuer.htm'
    with pytest.raises(ValueError): primary_from_index(html.replace(b'issuer.htm', b'../issuer.htm'))


@pytest.mark.parametrize('text,scale,sign,expected', [('1,234', '3', None, '1234000'), ('(12)', '0', None, '-12'), ('12', '0', '-', '-12'), ('—','0',None,'0')])
def test_inline_scaling(text, scale, sign, expected):
    n = BeautifulSoup('<ix:nonfraction>'+text+'</ix:nonfraction>', 'html.parser').find('ix:nonfraction')
    n['scale'] = scale
    if sign: n['sign'] = sign
    assert ix_number(n) == Decimal(expected)


def test_original_no_dimension_and_wrong_entity():
    body = '''<html><xbrli:unit id="u"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
    <xbrli:context id="c"><xbrli:entity><xbrli:identifier>123</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2023-01-01</xbrli:startDate><xbrli:endDate>2023-12-31</xbrli:endDate></xbrli:period></xbrli:context>
    <ix:nonFraction name="us-gaap:PaymentsForRepurchaseOfCommonStock" contextRef="c" unitRef="u" scale="3">100</ix:nonFraction></html>'''
    fs = original_facts(body.encode(), '0000000123')
    assert len(fs) == 1 and Decimal(fs[0]['val']) == 100000
    assert not original_facts(body.encode(), '0000000124')
    dimensional = body.replace('</xbrli:entity>', '<xbrldi:explicitMember>ClassA</xbrldi:explicitMember></xbrli:entity>')
    assert not original_facts(dimensional.encode(), '0000000123')
    e = {'evidence': {'repurchases': [dict(row(), tag='PaymentsForRepurchaseOfCommonStock', unit='USD', val=100000)]}}
    assert corroborate(e, fs)[0]['exact_match']
    fs.append(dict(fs[0], val='999'))
    assert not corroborate(e, fs)[0]['exact_match']
