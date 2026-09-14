from service.forward_pit.guidance_backfill import submission_filings, history_pages, merge_history


def test_filing_window_and_priority_without_future_targets():
    payload={'filings':{'recent':{'accessionNumber':['A','B','C','D'],
        'filingDate':['2025-02-01','2025-03-01','2026-01-01','2025-04-01'],
        'form':['8-K','8-K','8-K','10-Q'],'items':['7.01','2.02','2.02','2.02']}}}
    result=submission_filings(payload,'2025-01-01','2025-06-30',1)
    assert [r['accession'] for r in result]==['B']
    assert result[0]['acceptance_datetime'] is None


def test_empty_or_ineligible_submissions_do_not_invent_filings():
    assert submission_filings({},'2025-01-01','2025-06-30',4)==[]


def test_matching_history_pages_are_safe_and_overlap_window():
    payload = {'filings': {'files': [
        {'name': 'CIK123-submissions-001.json', 'filingFrom': '2010-01-01', 'filingTo': '2020-01-01'},
        {'name': '../evil.json', 'filingFrom': '2010-01-01', 'filingTo': '2020-01-01'},
        {'name': 'CIK123-submissions-002.json', 'filingFrom': '2000-01-01', 'filingTo': '2005-01-01'}]}}
    assert len(history_pages(payload, '2016-01-01', '2020-12-31')) == 1


def test_history_merge_keeps_missing_columns_aligned():
    payload = {'filings': {'recent': {'accessionNumber': ['new'], 'items': ['2.02']}}}
    result = merge_history(payload, {'accessionNumber': ['old'], 'filingDate': ['2016-01-01']})
    assert result['filings']['recent']['items'] == ['2.02', None]
    assert result['filings']['recent']['filingDate'] == [None, '2016-01-01']
