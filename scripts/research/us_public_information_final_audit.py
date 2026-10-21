"""Offline independent calculation path, not an independent human review."""
import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_public_information_review import READ, PARENT, load_bodies, reporting_units
from scripts.research.us_public_information_final_review import NOTES, REVIEW, period_review, source_text


def audit(root):
    if (root / 'audit.json').exists():
        raise ValueError('Audit output immutable')
    report = READ(root / 'report.json'); protocol = READ(root / 'protocol.json')
    verify_hashes(root, report['files'])
    verify_hashes(Path('.'), protocol['sources'])
    verify_hashes(Path('.'), protocol['archived_receipts'])
    evidence = READ(REVIEW / 'evidence.json'); get = load_bodies(); notes = READ(NOTES)
    by_symbol = {r['symbol']: r for r in evidence['consensus']}
    candidates = pd.read_parquet(PARENT / 'consensus-candidates.parquet')
    rows = pd.read_parquet(root / 'consensus-context-review.parquet')
    assert len(rows) == 62 and not rows.symbol.duplicated().any()
    assert set(rows.symbol) == set(candidates.symbol)
    assert not rows.live_qualified.any() and not rows.qualification_backdated.any()
    plan = READ(PARENT / 'document-plan.json')
    requests = {r['accession']: r for r in plan['requests']}
    cutoff = pd.Timestamp('2026-10-16T13:30:00Z')
    for row in rows.to_dict('records'):
        source = by_symbol[row['symbol']]
        assert row['oracle_rank'] == source['rank']
        codes = set()
        for reference in source['references']:
            accession = reference['accession']
            stamp = pd.Timestamp(requests[accession]['metadata']['acceptanceDateTime'])
            assert stamp.tzinfo is not None and stamp < cutoff
            body, _, _ = get(accession)
            codes.update(p['currency'] for p in reporting_units(body)['proofs'])
        if row['currency_evidence_kind'] == 'INLINE_REVENUE_REPORTING_UNIT':
            assert codes == {row['reporting_currency']}
        elif row['symbol'] in notes['currency_text']:
            note = notes['currency_text'][row['symbol']]
            assert note['literal'] in source_text(get, note['accession'])[2]
            assert row['reporting_currency'] == note['currency']
        else:
            assert pd.isna(row['reporting_currency'])
        period = period_review(source, notes['periods'].get(row['symbol']), get)
        assert row['context_complete'] == (row['reporting_currency'] == 'USD' and period is not None)
    top = pd.read_parquet(PARENT / 'q1-top10.parquet')
    assert len(top) == 610 and not top.duplicated(['date', 'symbol']).any()
    assert set(top['rank']) == set(range(1, 11)) and top.groupby('date').size().eq(10).all()
    members = set(zip(pd.to_datetime(top.date).dt.strftime('%Y-%m-%d'), top.symbol))
    events = pd.read_parquet(root / 'q1-reviewed-events.parquet')
    expected = {r['accession'] for r in evidence['releases'] if (r['reaction_date'], r['symbol']) in members}
    assert len(events) == 24 and set(events.accession) == expected
    prices = pd.read_parquet(root / 'reaction-price-inputs.parquet')
    assert not prices.duplicated(['symbol', 'date']).any()
    lookup = {(r['symbol'], pd.Timestamp(r['date'])): r for r in prices.to_dict('records')}
    schedule = mcal.get_calendar('NYSE').schedule(start_date='2023-12-01', end_date='2024-04-08')
    source_events = {r['accession']: r for r in evidence['releases']}
    used_keys = set()
    for row in events.to_dict('records'):
        assert (row['reaction'], row['symbol']) in members and not row['fully_qualified']
        stamp = pd.Timestamp(source_events[row['accession']]['metadata']['acceptanceDateTime'])
        j = schedule.index.get_loc(pd.Timestamp(row['reaction']))
        assert schedule.market_open.iloc[j - 1] <= stamp < schedule.market_open.iloc[j]
        assert str(schedule.index[j + 1])[:10] == row['potential_entry']
        if len(row['reasons']):
            assert pd.isna(row['relative_reaction']) and row['provisional_agreement'] == 'ABSTAIN'
            continue
        # Reproduce the price comparison algebra directly, only from archived J/J-1.
        keys = [(s, d) for s in (row['symbol'], 'SPY') for d in (schedule.index[j - 1], schedule.index[j])]
        used_keys.update(keys)
        stock0, stock1, bench0, bench1 = [lookup[key] for key in keys]
        delta = stock1['close'] / stock0['close'] - bench1['close'] / bench0['close']
        assert abs(delta - row['relative_reaction']) < 1e-12
        a, b, c, d = row['source_values']
        growth = a / b - 1; margin = c / a - d / b
        assert abs(growth - row['revenue_growth']) < 1e-12
        assert abs(margin - row['operating_margin_change']) < 1e-12
        side = 'LONG' if growth > 0 and margin > 0 else 'SHORT' if growth < 0 and margin < 0 else 'ABSTAIN'
        assert row['accounting_pattern'] == side
    assert set(lookup) == used_keys, 'Only decision-day and preceding-session price keys may be retained'
    tal = events[events.symbol.eq('TAL')].iloc[0]
    assert 'KNOWN_RELEASE_PRECEDES_SEC_ACCEPTANCE_REACTION_NOT_NOVEL' in tal.reasons
    result = dict(status='PASS', created_at_utc=datetime.now(timezone.utc).isoformat(),
        consensus_rows=62, event_rows=24, verified_receipts=len(protocol['archived_receipts']),
        original_inputs_unchanged=True, source_currency_reparsed=True, period_quotes_revalidated=True,
        exact_day_top10_reproduced=True, only_reaction_and_prior_prices=True,
        separate_calculation_path=True, independent_human_review=False,
        economic_outcomes_read=False, sql=False, api_calls=0, training=False, orders=False,
        files={str(Path(__file__)): digest(Path(__file__)), 'report.json': digest(root / 'report.json')})
    atomic_json(root / 'audit.json', result)
    print(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    audit(parser.parse_args().output)
