from scripts.research.us_earnings_reaction_source_audit import sections,excerpts


def test_separate_original_and_exhibit_not_one_mixed_document():
    body='<DOCUMENT>\n<TYPE>8-K\n<TEXT>Item 2.02 Results</TEXT></DOCUMENT><DOCUMENT>\n<TYPE>EX-99.1\n<TEXT>Issuer news</TEXT></DOCUMENT>'
    out=sections(body)
    assert [r['document_type'] for r in out]==['8-K','EX-99.1']
    assert 'Issuer news' not in out[0]['text']


def test_script_and_hidden_facts_not_news_prose():
    body='<DOCUMENT>\n<TYPE>10-Q\n<TEXT><script>secret</script><ix:hidden>999999</ix:hidden><p>Report</p></TEXT></DOCUMENT>'
    out=sections(body)[0]['text']
    assert 'secret' not in out and '999999' not in out and 'Report' in out


def test_no_automatic_full_document_guess_from_missing_sgml_boundary():
    assert sections('<html>Item 2.02 results</html>')==[]


def test_snippet_offsets_exact_not_approval():
    text='Issuer issued a press release yesterday.'
    out=excerpts(text)
    assert out and all(x['quote']==text[x['start']:x['end']] for x in out)
    assert all('qualified' not in x for x in out)
