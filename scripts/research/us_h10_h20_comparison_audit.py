"""Offline final audit and paired model/benchmark comparison, no fitting."""
from hashlib import sha256
from pathlib import Path
import argparse

import numpy as np
import pandas as pd

from scripts.research import us_h10_h20_frozen_comparison as study
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def audit(root):
    p = study.read(root/'protocol.json'); ready = study.read(root/'data-ready.json'); report = study.read(root/'report.json')
    verify_hashes(Path('.'), p['sources']); verify_hashes(root, ready['files']); verify_hashes(root, report['files'])
    assert report['protocol_sha256'] == digest(root/'protocol.json')
    from catboost import CatBoostClassifier
    labels = pd.read_parquet(root/'labels.parquet')
    membership = pd.read_parquet(root/'observable-membership.parquet')
    assert not membership.duplicated(['date', 'symbol']).any()
    assert not labels.duplicated(['date', 'symbol']).any()
    assert set(p['feature_columns']).isdisjoint({'selector_short_score', 'target_h10', 'target_h20', 'future_return', 'path_amplitude'})
    trade = pd.concat([pd.read_parquet(part/'execution.parquet') for part in sorted((root/'parts').iterdir())], ignore_index=True)
    assert not trade.duplicated(['date', 'symbol', 'side', 'holding']).any()
    trade = study.execution.gate.attach_costs(trade)
    cases = []; paired = []; benchmarks = []; diagnostics = []
    days = study.nyse_sessions('2024-01-01', '2026-10-09')
    for year, fold in p['folds'].items():
        done = study.read(root/f'{year}-done.json'); verify_hashes(root, done['files'])
        available = labels.merge(membership, on=['date', 'symbol'], validate='one_to_one')
        common = available.target_h10.notna() & available.target_h20.notna()
        tr = available[common & available.date.isin(pd.to_datetime(fold['train']))]
        va = available[common & available.date.isin(pd.to_datetime(fold['val']))]
        assert len(tr) == done['common_train_rows'] and len(va) == done['common_validation_rows']
        assert tr.available_h20.lt(pd.Timestamp(fold['val'][0])).all()
        assert va.available_h20.lt(pd.Timestamp(fold['test'][0])).all()
        score_keys = None; panels = {}; selected_keys = {}
        for h in p['model_horizons']:
            summary = done['summaries'][str(h)]
            assert summary['n_train'] == len(tr) and summary['n_val'] == len(va)
            assert summary['seed'] == p['seed'] and summary['reloaded_exact']
            model = CatBoostClassifier().load_model(str(root/summary['model_file']))
            assert model.feature_names_ == p['feature_columns']
            contract = study.read((root/summary['model_file']).parent/'contract.json')
            assert contract['target_horizon'] == h and contract['serving_ready'] is False
            assert contract['protocol_sha256'] == digest(root/'protocol.json')
            scores = pd.read_parquet(root/f'{year}-H{h}-scores.parquet')
            keys = scores[['date', 'symbol']].sort_values(['date', 'symbol']).reset_index(drop=True)
            expected_keys = membership[membership.date.isin(pd.to_datetime(fold['test']))][['date', 'symbol']]
            expected_keys = expected_keys.sort_values(['date', 'symbol']).reset_index(drop=True)
            pd.testing.assert_frame_equal(keys, expected_keys)
            if score_keys is not None: pd.testing.assert_frame_equal(keys, score_keys)
            score_keys = keys
            assert not scores.duplicated(['date', 'symbol']).any()
            assert np.isfinite(scores.score).all() and scores.score.between(0, 1).all()
            ordered = scores.sort_values(['date', 'score', 'symbol'], ascending=[True, False, True])
            assert ordered['rank'].eq(ordered.groupby('date').cumcount()+1).all()
            assert scores.selected.eq(scores['rank'].le(np.ceil(.2*scores.scored_count))).all()
            for event in p['feature_reserves']:
                assert not (scores.symbol.eq(event['symbol']) & scores.date.ge(pd.Timestamp(event['start']))).any()
            sel = scores[scores.selected]
            selected_keys[h] = sel[['date', 'symbol']]
            panel = sel[['date', 'symbol']].merge(trade[trade.year.eq(int(year))], on=['date', 'symbol'], validate='one_to_many')
            panels[h] = panel
            cases.append(dict(year=int(year), horizon=h, train_rows=len(tr), val_rows=len(va), scores=len(scores), selected=len(sel),
                training_labels_mature_before_test_year=True, same_feature_keys=True, future_feature_reservations_respected=True))
            label_coverage = {}
            for target_h in p['model_horizons']:
                daily_count = sel.groupby('date')[f'target_h{target_h}'].count()
                label_coverage[str(target_h)] = dict(evaluated=int(daily_count.sum()), selected=len(sel),
                    zero_label_dates=[str(d.date()) for d in daily_count.index[daily_count.eq(0)]])
            diagnostics.append(dict(year=int(year), model_horizon=h, label_coverage=label_coverage))
            for (holding, side), g in panel.groupby(['holding', 'side']):
                expected = next(r for r in report['execution'] if (r['year'], r['model_horizon'], r['holding'], r['side']) == (int(year), h, int(holding), side))
                assert expected['evaluated'] == len(g)
                assert abs(expected['mean_net']-g.net_outcome.mean()) < 1e-12
                assert abs(expected['win_rate']-g.net_outcome.gt(0).mean()) < 1e-12
                assert g.exit_session.between(1, int(holding)).all()
        # Universe baseline uses only rows actually observable for both models.
        baseline = score_keys.merge(trade[trade.year.eq(int(year))], on=['date', 'symbol'], validate='one_to_many')
        for (holding, side), g in baseline.groupby(['holding', 'side']):
            daily_base = g.groupby('date').net_outcome.mean()
            benchmarks.append(dict(year=int(year), holding=int(holding), side=side, n=len(g), mean_net=float(g.net_outcome.mean()),
                win_rate=float(g.net_outcome.gt(0).mean())))
            daily = {}
            for h in p['model_horizons']:
                selected = panels[h]; selected = selected[selected.holding.eq(holding) & selected.side.eq(side)]
                daily[h] = selected.groupby('date').net_outcome.mean()
                advantage = daily[h]-daily_base.reindex(daily[h].index)
                paired.append(dict(year=int(year), holding=int(holding), side=side, comparison=f'MODEL_H{h}_MINUS_ALL_UNIVERSE_SAME_SIDE',
                    interval=study.execution.gate.block_interval(advantage, days)))
            diff = daily[10]-daily[20]
            paired.append(dict(year=int(year), holding=int(holding), side=side, comparison='MODEL_H10_MINUS_MODEL_H20',
                interval=study.execution.gate.block_interval(diff, days)))
        overlap = len(selected_keys[10].merge(selected_keys[20], on=['date', 'symbol'], validate='one_to_one'))
        for row in diagnostics:
            if row['year'] == int(year): row['selection_overlap_h10_h20'] = overlap / len(selected_keys[10])
    atomic_json(root/'paired-model-comparison.json', dict(paired=paired, benchmarks=benchmarks,
        diagnostics=diagnostics,
        reserve='Descriptive block intervals, already examined historical periods; no multiple-test promotion'))
    result = dict(status='PASS_EXPLORATORY_ONLY', cases=cases, protocol_sha256=digest(root/'protocol.json'),
        report_sha256=digest(root/'report.json'), paired_sha256=digest(root/'paired-model-comparison.json'),
        audit_code_sha256=digest(Path(__file__)), sql=False, new_fit=False, production_changes=False,
        claim='Fold/label maturity, score membership, hashes and outcome calculations checked; models fitted today, historical feature versions and all prices not independently certified')
    atomic_json(root/'final-audit.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    print(audit(parser.parse_args().output))
