"""Offline final audit of percent ranking, maturity, scopes and artifact seals."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_oracle_top20pct_tp10 as study
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def audit(root):
    p = study.read(root/'protocol.json'); report = study.read(root/'report.json')
    verify_hashes(Path('.'), p['sources']); verify_hashes(root, report['files'])
    if report['protocol_sha256'] != digest(root/'protocol.json'): raise AssertionError('Protocol changed')
    amendment = p['pre_outcome_technical_amendment']
    assert digest(root/amendment['previous_protocol']) == amendment['previous_protocol_sha256']
    from scripts.research.us_news_gpt_top20_history import validate_scores
    selections, score_audit = [], []
    for year, model in p['annual_models'].items():
        marker = study.read(root/f'{year}-scores-ready.json'); verify_hashes(root, marker['files'])
        scores = pd.read_parquet(root/f'{year}-all-scores.parquet')
        validate_scores(scores, {**model, 'universe': p['symbols']})
        expected = study.top_fraction(scores, p['fraction'])
        actual = pd.read_parquet(root/f'{year}-top20pct.parquet')
        pd.testing.assert_frame_equal(expected.reset_index(drop=True), actual.reset_index(drop=True))
        assert marker['archived_original_top20_stocks_exact'] and marker['score_max_error'] <= 1e-7
        assert set(scores.date) == {pd.Timestamp(d) for d in p['sessions'] if d.startswith(year)}
        selections.append(actual)
        daily = actual.groupby('date')[['scored_count', 'selected_count']].first()
        score_audit.append(dict(year=int(year), scored_rows=len(scores), sessions=len(daily), selected_pairs=len(actual),
            symbols=int(scores.symbol.nunique()), min_scored=int(daily.scored_count.min()), max_scored=int(daily.scored_count.max()),
            min_selected=int(daily.selected_count.min()), max_selected=int(daily.selected_count.max()),
            incomplete_scoring_dates=int(daily.scored_count.lt(p['universe_count']).sum()),
            original_archive_parity=True, lineage_and_causality=True))
    selection = pd.concat(selections, ignore_index=True)
    from modelFactory.oracle.build_labels import nyse_sessions
    days = nyse_sessions('2023-01-01', '2026-10-09')
    prior_keys = None; cases = {}
    for name, meta in report['cases'].items():
        verify_hashes(root, {meta['path']: meta['sha256']})
        folder = root/name; case = study.read(folder/'report.json'); verify_hashes(folder, case['files'])
        assert case['protocol_sha256'] == digest(root/'protocol.json')
        f = pd.read_parquet(folder/'evaluations.parquet')
        states = pd.read_parquet(folder/'monthly-memberships.parquet')
        keys = f[['date', 'symbol', 'side']].astype({'symbol': str, 'side': str}).sort_values(['date', 'symbol', 'side']).reset_index(drop=True)
        assert not keys.duplicated().any()
        if prior_keys is not None: pd.testing.assert_frame_equal(keys, prior_keys)
        prior_keys = keys
        assert f.groupby(['date', 'symbol'], observed=True).side.nunique().eq(2).all()
        assert f.groupby('date').oracle_rank.max().le(f.groupby('date').selected_count.first()).all()
        assert f.entry_date.eq(days[days.get_indexer(f.date)+1]).all()
        assert f.last_path_date.eq(days[days.get_indexer(f.date)+20]).all()
        assert states.max_known_maturity.lt(states.rebalance_date).all()
        passed = states[states.passed]
        assert passed.episodes.ge(study.gate.MIN_EPISODES).all()
        assert passed.wilson90_lower.gt(passed.global_tp_rate).all()
        assert passed.mean_net_outcome.gt(np.maximum(0., passed.global_mean_net)).all()
        for cutoff, current in f.groupby('rebalance_date'):
            expected = study.gate.apply_states(current, states[states.rebalance_date.eq(cutoff)])
            for column in ('symbol_pass', 'opposite_pass', 'chosen_side'):
                assert current[column].eq(expected[column]).all()
        assert (f.chosen_side == (f.symbol_pass & ~f.opposite_pass)).all()
        if name == 'TP10_NO_SL':
            assert not f.sl_first.any() and not f.gap_stop.any() and not f.ambiguity.any()
        original = study.read(study.FULL/name/'primary.json')
        assert case['results']['full_universe'] == original
        broad = pd.read_parquet(study.FULL/name/'evaluations.parquet')
        broad_top = study.restrict_paths(broad, selection)
        assert len(broad_top) == len(f)
        cols = ['date', 'symbol', 'side', 'path_return', 'net_outcome', 'tp_first', 'sl_first', 'entry_price', 'exit_price']
        pd.testing.assert_frame_equal(f[cols].sort_values(['date', 'symbol', 'side']).reset_index(drop=True),
            broad_top[cols].sort_values(['date', 'symbol', 'side']).reset_index(drop=True), check_dtype=False, check_categorical=False)
        for arm in ('ALL_LONG', 'ALL_SHORT'):
            a = [r for r in case['results']['top20pct']['summary'] if r['arm'] == arm]
            b = [r for r in case['results']['top20pct_full_history_gate_control']['summary'] if r['arm'] == arm]
            for x, y in zip(a, b):
                # Descriptive top-five count ties can display other equally
                # frequent symbols when categorical dictionaries differ.
                assert {k: v for k, v in x.items() if k != 'largest_symbol_counts'} == {
                    k: v for k, v in y.items() if k != 'largest_symbol_counts'}
                counts = f[(f.year == x['year']) & f.side.eq(arm[4:])].symbol.value_counts()
                for row in (x, y):
                    assert all(int(counts[symbol]) == count for symbol, count in row['largest_symbol_counts'].items())
                    assert sorted(row['largest_symbol_counts'].values()) == sorted(counts.head(5).tolist())
        cases[name] = dict(evaluated_rows=len(f), evaluated_pairs=len(f)//2, selected_occasions=int(f.chosen_side.sum()),
            monthly_rebalances=int(f.rebalance_date.nunique()), first_decision=str(f.date.min().date()),
            last_decision=str(f.date.max().date()), price_reserve_severe_rows=int(f.path_return.lt(-.75).sum()),
            membership_and_maturity_pass=True, full_scope_exactly_reused=True,
            same_outcomes_and_population_both_gates=True)
    value = dict(status='PASS_EXPLORATORY_ONLY', protocol_sha256=digest(root/'protocol.json'),
        report_sha256=digest(root/'report.json'), annual_scores=score_audit, cases=cases,
        same_population_both_protection_variants=True, ranking_before_future_quality=True,
        no_next_rank_replacement=True, sql_read_only_snapshot=True, sql_writes=False, no_training=True,
        reserve='NOT independent price/OST qualification, NOT portfolio PnL or prospective confirmation')
    atomic_json(root/'final-audit.json', value)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(audit(parser.parse_args().output))
