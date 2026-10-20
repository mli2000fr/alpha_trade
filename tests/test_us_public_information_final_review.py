import pandas as pd
import pytest

from scripts.research import us_public_information_final_review as s


def test_no_period_by_default_or_from_calendar_alone():
    assert s.period_review({'anchor': '2026-09-30'}, None, None) is None


def test_review_quote_must_exist_in_source():
    row = dict(anchor='2026-09-30', period_quotes=[dict(accession='a', end='2026-09-30', quote='revenue range')])
    note = dict(quote_index=0, accession='a', end='2026-09-30', required=['revenue range'], note='x')
    with pytest.raises(ValueError, match='absent'):
        s.period_review(row, note, lambda a: ('<DOCUMENT><TYPE>EX-99.1\n<TEXT>debt</TEXT></DOCUMENT>', [], True))


def test_fiscal_end_not_replaced_with_normalized_anchor():
    quote = 'For the third quarter ending September 26, 2026 expects sales'
    row = dict(anchor='2026-09-30', period_quotes=[dict(accession='a', end='2026-09-26', quote=quote)])
    note = dict(quote_index=0, accession='a', end='2026-09-26', required=['expects sales'], note='x')
    result = s.period_review(row, note, lambda a: ('<DOCUMENT><TYPE>EX-99.1\n<TEXT>'+quote+'</TEXT></DOCUMENT>', [], True))
    assert result['actual_end'] == '2026-09-26'
    assert result['provider_anchor'] == '2026-09-30'


def test_reversed_year_columns_and_signed_quarter_not_ytd():
    body = '''<DOCUMENT><TYPE>EX-99.1
    <p>In thousands of U.S. dollars</p><table>
    <tr><td>Three Months Ended 2022 2023 2022 2023</td></tr>
    <tr><td>Net revenues</td><td>100</td><td>120</td><td>400</td><td>450</td></tr>
    <tr><td>Loss from operations</td><td>(10)</td><td>(8)</td><td>(40)</td><td>(45)</td></tr>
    </table></DOCUMENT>'''
    note = dict(exhibit='EX-99.1', table=0, header='Three Months Ended 2022 2023 2022 2023',
        scale_literal='In thousands of U.S. dollars', scale=1000, current_column=1, prior_column=0,
        revenue_label='Net revenues', operating_label='Loss from operations')
    values, _ = s.reviewed_table(body, note)
    assert values == [120000, 100000, -8000, -10000]
    with pytest.raises(ValueError, match='scale'):
        s.reviewed_table(body, dict(note, scale_literal='in millions'))


def test_acceptance_first_full_session_entry_next_session_and_no_naive_time():
    schedule = pd.DataFrame({'market_open': pd.to_datetime(['2024-01-26T14:30Z', '2024-01-29T14:30Z', '2024-01-30T14:30Z'])},
        index=pd.to_datetime(['2024-01-26', '2024-01-29', '2024-01-30']))
    assert s.causal_dates('2024-01-26T21:00:19Z', schedule) == ('2024-01-29', '2024-01-30')
    with pytest.raises(ValueError, match='timezone'):
        s.causal_dates('2024-01-26T21:00:19', schedule)
