from service.forward_pit.guidance_structured import extract
from service.forward_pit.guidance_tables import TableLayout


def rows(html):
    return extract(html, {'content_sha256': 'fixture'})


def test_target_header_and_basis_cells():
    html = '<p>The following table summarizes fiscal year 2024 targets:</p><table><tr><td>Earnings per share</td><td>GAAP: $10 to $11</td><td>Non-GAAP: $15 to $16</td></tr></table>'
    found = rows(html)
    assert [r['range_role']['role'] for r in found] == ['NEW_FORECAST'] * 2
    assert found[0]['table_context']['row_label'] == 'Earnings per share'
    assert found[1]['table_context']['cell_text'] == 'Non-GAAP: $15 to $16'
    assert found[0]['suggestions']['basis'] == 'GAAP'
    assert found[1]['suggestions']['basis'] == 'adjusted'
    assert found[0]['table_suggestions']['unit'] == 'USD per share'
    assert found[0]['suggestions']['fiscal_year_candidates'] == ['2024']


def test_segment_label_does_not_become_group_revenue():
    html = '<p>The following table summarizes second quarter fiscal year 2024 targets:</p><table><tr><td>Digital Media segment revenue</td><td>$3 billion to $4 billion</td></tr></table>'
    row = rows(html)[0]
    assert row['table_suggestions']['scope'] == 'Digital Media segment revenue'
    assert row['table_suggestions']['quarter_candidates'] == ['second']


def test_header_does_not_leak_to_next_table():
    html = '<p>The following table summarizes 2024 targets:</p><table><tr><td>Revenue</td><td>$1 to $2</td></tr></table><table><tr><td>Unknown</td><td>$3 to $4</td></tr></table>'
    assert [r['range_role']['role'] for r in rows(html)] == ['NEW_FORECAST', 'AMBIGUOUS']


def test_prior_and_current_columns():
    html = '<table><tr><th>Metric</th><th>Prior guidance</th><th>Current guidance</th></tr><tr><td>EPS</td><td>$2 to $3</td><td>$3 to $4</td></tr></table>'
    assert [r['range_role']['role'] for r in rows(html)] == ['PRIOR_FORECAST', 'NEW_FORECAST']


def test_respectively_is_not_range():
    html = '<p>The following table summarizes 2024 targets:</p><table><tr><td>Allowance</td><td>$17 and $23, respectively</td></tr></table>'
    assert rows(html)[0]['range_role']['role'] == 'AMBIGUOUS'


def test_layout_offsets_equal_normalized_visible_text():
    import re
    parser = TableLayout()
    parser.feed('<p>A &amp; B</p><table><tr><td>EPS</td><td> $1 to $2 </td></tr></table>')
    assert parser.visible == re.sub(r'\s+', ' ', ''.join(parser.parts))
