import pytest

from scripts.research.us_economic_links_feasibility import readonly


@pytest.mark.parametrize('statement',[
    'SELECT id,content_text FROM sec_filing_raw WHERE id=:id',
    'SHOW COLUMNS FROM sec_filing_raw',
    'SET TRANSACTION READ ONLY',
    "SET SESSION time_zone='+00:00'",
    'SET SESSION MAX_EXECUTION_TIME=20000',
])
def test_reader_allows_only_bounded_read_statements(statement):
    readonly(None,None,statement,{},None,False)


@pytest.mark.parametrize('statement',[
    'DELETE FROM sec_filing_raw',
    'UPDATE sec_filing_raw SET symbol=1',
    'CREATE TABLE x(id INT)',
    'SELECT 1; DELETE FROM sec_filing_raw',
    "SELECT 1 INTO OUTFILE '/tmp/sideeffect'",
    "SELECT GET_LOCK('backtesting',1)",
    'SET SESSION TRANSACTION READ WRITE',
])
def test_reader_rejects_mutations_and_lock_operations(statement):
    with pytest.raises(ValueError):
        readonly(None,None,statement,{},None,False)


def test_ambiguous_company_cores_are_not_inferred_from_common_words():
    from scripts.research.us_economic_links_scan import aliases, screen
    mapping = aliases([{'symbol': 'BAND', 'company_name': 'Bandwidth Inc.'},
                       {'symbol': 'PKG', 'company_name': 'Packaging Corporation'},
                       {'symbol': 'RS', 'company_name': 'Reliance Inc.'}])
    assert not screen('Our supplier needs bandwidth, packaging and reliance on shipping.', mapping, 'OTHER')


def test_name_and_nearby_supplier_word_are_only_a_review_candidate():
    from scripts.research.us_economic_links_scan import screen
    result = screen('Our customers include Applied Materials.', {'Applied Materials': 'AMAT'}, 'UCTT')
    assert len(result) == 1
    assert result[0]['screen_kind'] == 'RELATION_WORD_NEAR_NAME'
    assert 'verdict' not in result[0]


def test_lowercase_common_word_does_not_match_one_word_name():
    from scripts.research.us_economic_links_scan import screen
    assert screen('We sell service interface specifications.', {'Service': 'SCI'}, 'MXL') == []


def test_universe_membership_does_not_create_missing_counterparty_reference():
    from scripts.research.us_economic_links_scan import aliases
    assert 'Lam Research' not in aliases([{'symbol': 'UCTT', 'company_name': 'Ultra Clean Holdings Inc.'}])
    assert aliases([{'symbol': 'LRCX', 'company_name': 'LAM RESEARCH CORP'}])['Lam Research'] == 'LRCX'


def test_source_parser_skips_xbrl_attachment_and_retains_primary_identity():
    from scripts.research.us_economic_links_scan import source_parts
    body = ('<DOCUMENT><TYPE>10-Q\n<TEXT><html><body>'
            '<ix:nonNumeric name="dei:TradingSymbol">UCTT</ix:nonNumeric>'
            '<ix:nonNumeric name="dei:EntityCentralIndexKey">0001275014</ix:nonNumeric>'
            + 'Customers and suppliers. ' * 10 + '</body></html></TEXT></DOCUMENT>'
            '<DOCUMENT><TYPE>EX-101.INS\n<TEXT>' + 'SHOULD_NOT_ENTER ' * 20 + '</TEXT></DOCUMENT>')
    parts = source_parts(body, '10-Q')
    assert len(parts) == 1
    assert parts[0]['fields']['TradingSymbol'] == ['UCTT']
    assert 'SHOULD_NOT_ENTER' not in parts[0]['text']


def test_receipt_eligibility_waits_for_runner_and_ignores_unqualified_sec_clock():
    from scripts.research.us_economic_links_review import receipt_ready
    doc = dict(run_status='COMPLETED_WITH_WARNINGS', observed_at='2026-10-31 19:00:00',
               available_at='2026-10-31 19:01:00', collection_finished_at='2026-10-31 19:30:00',
               acceptance_datetime_raw='1990-01-01 00:00:00')
    assert receipt_ready(doc).isoformat() == '2026-10-31T19:30:00+00:00'
    doc['run_status'] = 'RUNNING'
    with pytest.raises(ValueError, match='Unfinished'):
        receipt_ready(doc)


def test_scoped_acquisition_data_is_excluded_from_operating_link_count():
    from scripts.research.us_economic_links_review import VERDICTS
    assert VERDICTS[('SITM', 'AVT')][0] == 'EXCLUDED_ACQUIRED_BUSINESS_SCOPE'
    admitted = {key for key,value in VERDICTS.items() if value[0] == 'DOCUMENTED_OPERATING_LINK'}
    assert len(admitted) == 4
    assert len({owner for owner,_ in admitted}) == 3


def test_proof_retains_exact_offsets_and_rejects_changed_archive(tmp_path):
    from scripts.research.us_economic_links_review import proof
    from scripts.research.us_concentrated_historical_tapes import digest
    path = tmp_path / 'source.txt'
    path.write_text('prefix Named supplier, no revenue weight. Following.', encoding='utf-8')
    doc = dict(document_key='x', visible_file='source.txt', visible_sha256=digest(path), raw_sha256='raw')
    result = proof(tmp_path, doc, 'Named supplier', 'Following.')
    assert path.read_text(encoding='utf-8')[result['start']:result['end']] == result['quote']
    path.write_text('changed', encoding='utf-8')
    with pytest.raises(ValueError, match='evidence changed'):
        proof(tmp_path, doc, 'Named supplier', 'Following.')
