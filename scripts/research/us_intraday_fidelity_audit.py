"""Offline independent signal/time-count audit; never certifies actual fills."""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_intraday_fidelity_readiness import READ, PARENT


def audit(root):
    if (root/'final-audit.json').exists():
        raise ValueError('Immutable completed audit')
    verify_hashes(Path('.'), READ(root/'protocol.json')['sources'])
    verify_hashes(root, READ(root/'prepared.json')['files'])
    verify_hashes(root, READ(root/'snapshot.json')['files'])
    report = READ(root/'report.json')
    verify_hashes(root, report['files'])
    xml = ET.parse(root/'test-results.xml').getroot()
    suites = list(xml.iter('testsuite'))
    tests = sum(int(s.get('tests', 0)) for s in suites)
    if tests < 83 or any(int(s.get('errors', 0))+int(s.get('failures', 0)) for s in suites):
        raise AssertionError('Missing/pending/failing tests')
    cov = pd.read_parquet(PARENT/'coverage.parquet')
    cases = pd.read_parquet(root/'candidates.parquet')
    if len(cases) != 2*int(cov.status.eq('OK').sum()) or cases.duplicated(['pair_id', 'side']).any():
        raise AssertionError('Changed/duplicated cohort')
    snap = READ(PARENT/'snapshot-ready.json')
    verify_hashes(PARENT, snap['files'])
    raw = pd.concat([g for n in snap['files'] if len(g := pd.read_parquet(PARENT/n))], ignore_index=True)
    groups = {(s, d): f.sort_values('bar_timestamp') for (s, d), f in raw.groupby(['symbol', 'trade_date'])}
    calendar = pd.read_parquet(PARENT/'sessions.parquet')
    days = pd.DatetimeIndex(calendar.date)
    for r in cases.itertuples():
        start = days.get_loc(r.oracle_date)
        frames = [groups[r.symbol, d] for d in days[start:start+21]]
        found = None
        for previous, frame in zip(frames[:-1], frames[1:]):
            c = frame.close.to_numpy(float)
            prior = np.r_[previous.close.iloc[-1], c[:-3]]
            if r.side == 'buy':
                bound = previous.high.max()
                valid = (prior <= bound) & (c[:-2] > bound) & (c[1:-1] > bound)
            else:
                bound = previous.low.min()
                valid = (prior >= bound) & (c[:-2] < bound) & (c[1:-1] < bound)
            for k in np.flatnonzero(valid)+2:
                if frame.bar_timestamp.iloc[k] == frames[-1].bar_timestamp.iloc[-1]:
                    continue
                found = (frame.bar_timestamp.iloc[k], frame.bar_timestamp.iloc[k-1], float(c[k-1]))
                break
            if found:
                break
        if (found is None) != (r.status == 'NO_SIGNAL'):
            raise AssertionError('Changed signal/no-signal')
        if found and (found[0] != r.decision_time or found[1] != r.signal_bar_start or found[2] != r.signal_close):
            raise AssertionError(f'Signal timing/price mismatch {r.pair_id}/{r.side}')
    q = pd.read_parquet(root/'quotes.parquet')
    b = pd.read_parquet(root/'borrow.parquet')
    readiness = pd.read_parquet(root/'readiness.parquet').set_index(['pair_id', 'side'])
    counter = dict(quote_market_event_cases=0, quote_as_known_cases=0, borrow_status_candidates=0)
    for r in cases[cases.status.eq('SIGNAL')].itertuples():
        quotes = q[q.symbol.eq(r.symbol)]
        market = 0
        receipt = 0
        # Scalar comparison rather than the report's vector masks.
        for x in quotes.itertuples():
            t = pd.to_datetime(x.source_timestamp, utc=True, errors='coerce')
            a = pd.to_datetime(x.collected_at, utc=True, errors='coerce')
            values = [x.bid_price, x.ask_price, x.bid_size, x.ask_size]
            if (pd.isna(t) or not 0 <= (r.decision_time-t).total_seconds() <= 300
                or x.feed != 'sip' or x.provider != 'alpaca'
                or not all(pd.notna(v) and np.isfinite(float(v)) and float(v) > 0 for v in values)
                or x.ask_price < x.bid_price or not isinstance(x.raw_payload_sha256, str)
                or len(x.raw_payload_sha256) != 64 or pd.isna(x.raw_payload_path)):
                continue
            market += 1
            receipt += int(pd.notna(a) and t <= a <= r.decision_time)
        borrow = b[b.symbol.eq(r.symbol)]
        n_borrow = 0
        for x in borrow.itertuples():
            a = pd.to_datetime(x.available_at, utc=True, errors='coerce')
            if pd.notna(a) and 0 <= (r.decision_time-a).total_seconds() <= 86400 and x.provider == 'alpaca' and pd.notna(x.payload_hash):
                n_borrow += 1
        actual = readiness.loc[(r.pair_id, r.side), :]
        if (market != actual.market_event_quote_candidates or receipt != actual.quote_candidates
                or n_borrow != actual.borrow_candidates):
            raise AssertionError('Quote/borrow causal inventory mismatch')
        counter['quote_market_event_cases'] += int(market > 0)
        counter['quote_as_known_cases'] += int(receipt > 0)
        counter['borrow_status_candidates'] += int(n_borrow > 0)
    atomic_json(root/'final-audit.json', dict(status='PASS_COMPONENT_TESTS_AND_READ_ONLY_INVENTORY',
        tests=tests, signals_checked=int(cases.status.eq('SIGNAL').sum()), **counter,
        report_sha256=digest(root/'report.json'), test_results_sha256=digest(root/'test-results.xml'),
        full_live_parity=False, optimization_started=False,
        verdict='NATIVE_COMPONENTS_IMPROVED_HISTORICAL_FULL_PARITY_NOT_QUALIFIED',
        note='Same assistant separate scalar checks, not independent human review. Market-event backfills can support simulation under explicit latency assumptions, never invented old reception timestamps.'))
    print(READ(root/'final-audit.json'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    audit(p.parse_args().output)
