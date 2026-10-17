"""Second technical check of archived stop recovery, not independent human review."""
from pathlib import Path
import argparse

import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_path_top5_leverage_grid import read


def review(output):
    root = Path(output); p, report = read(root/'protocol.json'), read(root/'report.json')
    # The protocol document can gain a dated results section AFTER the freeze.
    document = 'doc/ml/oracle_path_stop_recovery_20261014.md'
    verify_hashes(Path('.'), {k: v for k, v in p['sources'].items() if Path(k).as_posix() != document})
    verify_hashes(root, report['files'])
    prices = pd.read_parquet(p['prices'])
    groups = {s: f.set_index('date') for s, f in prices.groupby('symbol')}
    days = nyse_sessions('2023-01-01', '2027-03-31')
    stopped = pd.read_parquet(root/'stopped-lots.parquet')
    atr = pd.read_parquet(root/'closed-lot-atr.parquet')
    native = []
    for year in (2024, 2025, 2026):
        frame = pd.read_parquet(Path(p['source'])/f'{year}-FIXED_REFERENCE/trades.parquet')
        frame['year'] = year; native.append(frame)
    native = pd.concat(native, ignore_index=True)
    keys = ['year', 'symbol', 'entry_date']
    pd.testing.assert_frame_equal(atr[keys+['exit_date', 'pnl_usd']].sort_values(keys).reset_index(drop=True),
        native[keys+['exit_date', 'pnl']].rename(columns={'pnl': 'pnl_usd'}).sort_values(keys).reset_index(drop=True))
    expected = set(map(tuple, native[native.exit_reason.isin(p['stop_reasons'])][keys].to_numpy()))
    for horizon in p['horizons']:
        sub = stopped[stopped.horizon.eq(horizon)]
        assert set(map(tuple, sub[keys].to_numpy())) == expected
        assert not sub.duplicated(keys).any()
    verified = 0
    for t in stopped.itertuples(index=False):
        start = days.get_loc(t.entry_date); dates = days[start:start+t.horizon]
        assert t.observation_end == dates[-1]
        if t.status == 'IMMATURE_WINDOW':
            assert dates[-1] > pd.Timestamp(p['as_of'])
        elif t.status == 'STOP_ON_OR_AFTER_WINDOW_END':
            assert t.exit_date >= dates[-1]
        elif t.status == 'QUALIFIED':
            assert dates[-1] <= pd.Timestamp(p['as_of']) and t.exit_date < dates[-1]
            bars = groups[t.symbol].loc[dates]
            after = bars[bars.index > t.exit_date]
            hit_dates = after.index[after.high.ge(t.entry_price*1.2)]
            assert bool(len(hit_dates)) == t.recovered_high20
            assert bool(after.close.ge(t.entry_price*1.2).any()) == t.recovered_close20
            assert np.isclose(t.min_after_stop_pct, 100*(after.low.min()/t.entry_price-1))
            if len(hit_dates):
                k = bars.index.get_loc(hit_dates[0])
                before = bars.low.iloc[:k]
                lower = min(0., 100*(before.min()/t.entry_price-1)) if len(before) else 0.
                upper = min(lower, 100*(bars.low.iloc[k]/t.entry_price-1))
                assert np.isclose(t.min_before_target_excluding_hit_day_pct, lower)
                assert np.isclose(t.min_before_target_including_hit_day_pct, upper)
                assert pd.Timestamp(t.first_target_date) == hit_dates[0]
            event, event_day = 'NONE', None
            # Alternate chronological implementation, no call to diagnostic resolver.
            for day, b in bars.iterrows():
                if b.open <= t.entry_price*.9:
                    event, event_day = 'SL', day; break
                if b.open >= t.entry_price*1.2:
                    event, event_day = 'TP', day; break
                if b.low <= t.entry_price*.9:
                    event, event_day = 'SL', day; break
                if b.high >= t.entry_price*1.2:
                    event, event_day = 'TP', day; break
            survived = event == 'TP' and event_day > t.exit_date
            assert bool(t.recovered_high20_without_prior_sl10) == survived
            verified += 1
    for summary in report['summaries']:
        sub = stopped[stopped.year.eq(summary['year']) & stopped.horizon.eq(summary['horizon'])]
        assert summary['statuses'] == sub.status.value_counts().to_dict()
        valid = sub[sub.status.eq('QUALIFIED')]
        assert len(valid) == summary['qualified_stops']
        assert int(valid.recovered_high20.sum()) == summary['recovered_high20']
        assert int(valid.recovered_high20_without_prior_sl10.sum()) == summary['recovered_without_prior_sl10']
        assert int(valid.nonoverlapping.sum()) == summary['nonoverlapping']['qualified_stops']
        for symbol, g in valid[valid.nonoverlapping].groupby('symbol'):
            indices = [days.get_loc(d) for d in g.entry_date.sort_values()]
            assert all(b-a >= summary['horizon'] for a, b in zip(indices, indices[1:]))
    result = dict(status='RAW_PATH_RECOVERIES_CHRONOLOGY_AND_DENOMINATORS_VERIFIED',
        checked_qualified_windows=verified, closed_lots=len(atr), actual_stopped_lots=len(expected),
        assertions='entry horizon, post-stop strict dates, OHLC order bounds, SL10 gaps/collisions, attrition, nonoverlap',
        independent_human_review=False, no_new_portfolio_or_training=True,
        reviewed_report_sha256=digest(root/'report.json'), review_code_sha256=digest(__file__),
        protocol_document_at_freeze_sha256=next(v for k, v in p['sources'].items() if Path(k).as_posix() == document),
        current_document_sha256=digest(document))
    atomic_json(root/'second-check.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__); parser.add_argument('--output', required=True)
    print(review(parser.parse_args().output))
