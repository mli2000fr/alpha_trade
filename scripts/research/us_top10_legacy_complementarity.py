"""Audit archived weak signals on original path-Oracle TOP10. No fitting/SQL/PnL.

Legacy incomplete/future-filtered forecasts are diagnostic only, never inputs
to a decision recipe. Missing scores are not zero, neutral, or a replacement.
"""
from __future__ import annotations

import argparse
import itertools
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle_path.train import digest
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, verify_hashes
from scripts.research.us_directional_hierarchy_diagnostic import holm_adjust
from scripts.research.us_top10_directional_diagnostic import block_test, top10_only
from scripts.research.us_top10_catboost_multiclass import daily_auc

LOG = logging.getLogger(__name__)
CONFIG = Path('config/research/us_top10_legacy_complementarity_20261018.json')
BASELINE = 'OLD_D10_PATH'
OPTION_ARCHIVES = {
    'PROSPECTIVE_OPTIONS_OI': Path('artifacts/research/us_prospective_directional_audit/20261010-v1/prospective_features.parquet'),
    'HISTORICAL_OPTION_BARS': Path('artifacts/research/alpaca_options_history/directional-feb-mar-2024-20261011-v1/features.parquet'),
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def keys(frame, date='date'):
    frame = frame.rename(columns={date: 'date'}).copy()
    frame['date'] = pd.to_datetime(frame.date).dt.normalize()
    if frame[['date', 'symbol']].isna().any().any() or frame.duplicated(['date', 'symbol']).any():
        raise ValueError('Missing/duplicate signal identity')
    return frame


def rank_full_ten(frame, columns):
    """Missing inputs stay missing for that date; never rank only survivors."""
    values = frame[columns].replace([np.inf, -np.inf], np.nan)
    complete = values.notna().groupby(frame.date).transform('sum').eq(10)
    return values.groupby(frame.date).rank(pct=True).where(complete)


def shortlist(frame, score, count=3, allowed=None):
    work = frame[['date', 'oracle_rank']].copy()
    work['score'] = np.asarray(score)
    eligible = work.score.notna() if allowed is None else work.score.notna() & allowed
    ordered = work.loc[eligible].sort_values(['date', 'score', 'oracle_rank'], ascending=[True, False, True])
    picked = ordered.groupby('date').cumcount().lt(count)
    result = pd.Series(False, index=frame.index)
    result.loc[ordered.index[picked]] = True
    return result


def recipe(frame, definition):
    components = definition['components']
    if any(column.startswith('E23_') for column in components):
        raise ValueError('Future-filtered legacy forecasts are never decision inputs')
    full = frame[components].notna().groupby(frame.date).transform('sum').eq(10).all(axis=1)
    if definition['kind'] == 'mean':
        score = frame[components].mean(axis=1, skipna=False).where(full)
        return score, shortlist(frame, score), full
    if definition['kind'] != 'intersection':
        raise ValueError('Only frozen means or fixed agreement supported')
    allowed = full.copy()
    for column in components:
        allowed &= shortlist(frame, frame[column], count=definition['top_each'])
    score = frame[BASELINE].where(full)
    return score, shortlist(frame, score, allowed=allowed), full


def outcomes(frame, chosen, ready):
    """Unknown/empty outcomes are explicit; matched-size references below."""
    selected = chosen.groupby(frame.date).sum()
    known = (chosen & frame.oracle_decile.notna()).groupby(frame.date).sum()
    d10 = (chosen & frame.oracle_decile.eq(10)).groupby(frame.date).sum()
    d1 = (chosen & frame.oracle_decile.eq(1)).groupby(frame.date).sum()
    complete_labels = frame.oracle_decile.notna().groupby(frame.date).sum().eq(10)
    return pd.DataFrame(dict(selected_count=selected, known_count=known,
                             d10=d10/known.replace(0, np.nan), d1=d1/known.replace(0, np.nan),
                             d10_count=d10, d1_count=d1,
                             ready=ready.groupby(frame.date).all(), complete_labels=complete_labels))


def matched_reference(frame, counts, score):
    work = frame[['date', 'oracle_rank']].copy()
    work['score'] = np.asarray(score)
    ordered = work.sort_values(['date', 'score', 'oracle_rank'], ascending=[True, False, True])
    order = ordered.groupby('date').cumcount()+1
    chosen = pd.Series(False, index=frame.index)
    chosen.loc[ordered.index] = order.le(ordered.date.map(counts)).to_numpy()
    return outcomes(frame, chosen, pd.Series(True, index=frame.index))


def qualify(output, cfg, config):
    root = Path(cfg['source'])
    report, protocol = read(root/'report.json'), read(root/'protocol.json')
    if not report['source_hashes_verified_after_calculation'] or report['status'] != 'COMPLETED_EXPLORATORY':
        raise ValueError('Verified completed primary source required')
    verify_hashes(root, report['files'])
    verify_hashes(Path('.'), protocol['source_hashes'])
    if digest(root/'protocol.json') != report['protocol_sha256']:
        raise ValueError('Source protocol mismatch')
    price_root = Path(cfg['price_source'])
    price_report = read(price_root/'report.json')
    verify_hashes(price_root, {'candidate-population.parquet': price_report['files']['candidate-population.parquet']})
    alpha_root, e23_root = Path(cfg['alpha_source']), Path(cfg['e23_source'])
    paths = [config, Path(__file__), root/'report.json', root/'protocol.json', root/'population.parquet',
             price_root/'report.json', price_root/'candidate-population.parquet',
             alpha_root/'alpha_panel.parquet', alpha_root/'report.json', e23_root/'report.json',
             Path(cfg['legacy_consensus_config']), Path('modelFactory/oracle_d10_trajectory_e23.py'),
             Path('modelFactory/directional_alpha_book.py'), Path('scripts/research/us_feature_combination_d10.py'),
             Path('scripts/research/us_top10_catboost_multiclass.py'), Path('scripts/research/us_top10_directional_diagnostic.py')]
    for year in cfg['years']:
        paths.extend([root/str(year)/'predictions.parquet', Path(cfg['linear_source'])/f'predictions-{year}-D10_VS_REST.parquet'])
    for variant, model in itertools.product(cfg['e23_variants'], cfg['e23_models']):
        paths.append(e23_root/f'{variant.lower()}_{model}_oos.parquet')
    paths.extend(path for path in OPTION_ARCHIVES.values() if path.exists())
    frozen = dict(config=cfg, source_hashes={str(p): digest(p) for p in paths},
                  source_scope='Original ten path-Oracle candidates, no reselection from future',
                  decision_signals='Archived before future qualification or fixed J-only formulas',
                  legacy_e23='Descriptive-only: original producer filters on future label before scoring',
                  no_training=True, no_sql=True, no_provider_calls=True, no_broker_calls=True, no_pnl=True,
                  promotion=False, fresh_holdout=False)
    if (output/'protocol.json').exists() and read(output/'protocol.json') != frozen:
        raise ValueError('Changed inputs/protocol; use a new output folder')
    atomic_json(output/'protocol.json', frozen)
    population = top10_only(pd.read_parquet(root/'population.parquet'))
    population = population.loc[population.date.dt.year.isin(cfg['years'])].copy().reset_index(drop=True)
    return frozen, population


def build_panel(population, cfg):
    sources = []
    for year in cfg['years']:
        part = pd.read_parquet(Path(cfg['source'])/str(year)/'predictions.parquet')
        part = part[['date', 'symbol', 'OLD_LOGISTIC_D10', 'CATBOOST_3CLASS', 'CATBOOST_3CLASS_p_d1', 'LOGISTIC_3CLASS']].rename(
            columns={'OLD_LOGISTIC_D10': BASELINE, 'CATBOOST_3CLASS': 'CAT_CONTRAST', 'LOGISTIC_3CLASS': 'LINEAR_CONTRAST'})
        part['CAT_AVOID_D1'] = -part.pop('CATBOOST_3CLASS_p_d1')
        old = pd.read_parquet(Path(cfg['linear_source'])/f'predictions-{year}-D10_VS_REST.parquet', columns=['date', 'symbol', 'GLOBAL_J'])
        sources.append(keys(part).merge(keys(old).rename(columns={'GLOBAL_J': 'OLD_D10_J'}), on=['date', 'symbol'], validate='one_to_one'))
    frame = population.merge(pd.concat(sources, ignore_index=True), on=['date', 'symbol'], how='left', validate='one_to_one')
    price = pd.read_parquet(Path(cfg['price_source'])/'candidate-population.parquet',
                            columns=['date', 'symbol', 'score_lightgbm', 'oracle_rank', 'momentum_120', 'rolling_volatility_60', 'atr20_pct'])
    price = keys(price).rename(columns={'oracle_rank': 'price_oracle_rank', 'score_lightgbm': 'price_oracle_score'})
    frame = frame.merge(price, on=['date', 'symbol'], how='left', validate='one_to_one')
    if not frame.price_oracle_rank.eq(frame.oracle_rank).all() or not np.allclose(frame.price_oracle_score, frame.score_lightgbm, atol=1e-7, rtol=0):
        raise ValueError('Price-rule source refers to different TOP10 candidates')
    rank = rank_full_ten(frame, ['momentum_120', 'rolling_volatility_60', 'atr20_pct'])
    frame['M120'] = rank.momentum_120
    frame['V60_ATR'] = (rank.rolling_volatility_60+rank.atr20_pct)/2
    frame['MV'] = (frame.M120+frame.V60_ATR)/2
    alpha = pd.read_parquet(Path(cfg['alpha_source'])/'alpha_panel.parquet',
                             columns=['date', 'symbol', 'score_residual_momentum_120_10', 'score_short_reversal_5'])
    alpha = keys(alpha).rename(columns={'score_residual_momentum_120_10': 'E17_RESIDUAL120', 'score_short_reversal_5': 'E17_REVERSAL5'})
    frame = frame.merge(alpha, on=['date', 'symbol'], how='left', validate='one_to_one')
    columns = list(cfg['signal_groups'])
    # Apply exactly the same scale within the original ten. No neutral .5 fill.
    frame[columns] = rank_full_ten(frame, columns)
    return frame


def inventory_and_legacy(frame, cfg):
    inventory = [dict(family='RECENT_TOP10_MODELS', status='AVAILABLE_EXPLORATORY', reason='Causal scores saved for every original ten; same underlying price family.'),
                 dict(family='MOMENTUM_VOLATILITY_ATR', status='REAPPLIED_FIXED_RULES', reason='Same M/V/MV formulas applied inside current TOP10; not original ATR intersection population.'),
                 dict(family='E17_LONG_HORIZON_ALPHAS', status='AVAILABLE_EXPLORATORY_PARTIAL', reason='Known-J fixed price scores, originally H60/H120; H20 reinterpretation is new, historical vintage not certified.'),
                 dict(family='E23_STATE_PRICE_SENTIMENT', status='DESCRIPTIVE_ONLY', reason='12 cached forecasts; original future-label-filtered population and incomplete producer lineage; never a recipe input.')]
    old_cfg = read(cfg['legacy_consensus_config'])
    old_paths = set()
    def visit(value):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str): old_paths.add(value['path'])
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
    visit(old_cfg)
    for path in sorted(old_paths):
        inventory.append(dict(family='LEGACY_CONSENSUS_MODEL', path=path, exists=Path(path).exists(),
                              status='MISSING_NO_RETRAINING' if not Path(path).exists() else 'REQUIRES_FIT_AND_TARGET_LINEAGE',
                              reason='No restoration, re-inference or fabrication of absent OOF scores.'))
    excluded = [
        ('YAHOO_ANALYST_REVISIONS', 'EXCLUDED_RIGHTS_AND_PURGED_DATA', 'Disabled source; no restoration or numerical reuse of deleted consensus.'),
        ('FRED_FINRA_LEGACY', 'EXCLUDED_RIGHTS_PRUDENCE', 'No reuse of blocked source inputs in prediction recipes.'),
        ('EARNINGS_SURPRISE_DDR5', 'EXCLUDED_UNPROVEN_PIT', 'Current estimates joined by earnings date do not certify historical known consensus.'),
        ('E20_OPENING_PRICE_VOLUME', 'EXCLUDED_LATER_DECISION', 'J+1 opening information unavailable at J; distinct decision-time study.'),
        ('PROSPECTIVE_OPTIONS_OI', 'OUTSIDE_DECISION_WINDOW', 'Only recent prospective snapshots; not fabricated back to this 2026-09-02-ending cohort.'),
        ('HISTORICAL_OPTION_BARS', 'SECONDARY_PIT_AND_SHORT_COVERAGE', 'February-March 2024 limited archive, indicative bars, no historical OI reconstruction.'),
        ('E17_FUNDAMENTAL_H120_H180', 'EXCLUDED_TARGET_AND_PIT_LINEAGE', 'Long-horizon fundamental alpha not a qualified H20 direction score.'),
        ('EROYA_FORM4_8K_OPTIONS', 'EXCLUDED_UNREQUALIFIED_PRODUCER_LINEAGE', 'Different gate/target and only partial fit/source evidence; no unqualified replacement score.'),
        ('NEWS_STRONG_SENTIMENT', 'EXCLUDED_HISTORICAL_AVAILABILITY', 'Archived score availability before decision not certified; not a neutral value when unknown.'),
        ('GPT_NEWS_HISTORY', 'EXCLUDED_RETROSPECTIVE_PIT', 'Cached 2024-26 opinions explicitly not historical PIT; no new API call.'),
        ('MACRO_DAILY_REGIME', 'SEPARATE_DATE_CONTEXT_NOT_RANKING', 'Same score for every candidate on a day; no hindsight veto or macro fitting.'),
        ('META_ORACLE_LSTM_AMPLITUDE', 'EXCLUDED_NOT_DIRECTIONAL', 'Amplitude disagreement is not a directional vote.'),
        ('EXIT_AND_PROTECTION_SELECTORS', 'EXCLUDED_DIFFERENT_DECISION', 'Position management outcomes not an entry-direction score.'),
        ('TRAJECTORY_MATH_AUDITS', 'NO_ADDITIONAL_QUALIFIED_SCORE', 'Reports alone or alternate targets do not create a model prediction at J.')]
    inventory.extend(dict(family=f, status=s, reason=r) for f,s,r in excluded)
    for family, path in OPTION_ARCHIVES.items():
        item = next(row for row in inventory if row['family'] == family)
        item['path'], item['exists'] = str(path), path.exists()
        if path.exists():
            dates = pd.to_datetime(pd.read_parquet(path, columns=['day']).day).dt.normalize()
            item.update(archive_start=str(dates.min().date()), archive_end=str(dates.max().date()),
                        overlapping_dates=int(frame.date.drop_duplicates().isin(dates).sum()),
                        coverage_only_not_predictive_test=True)
    rows, legacy = [], []
    report = read(Path(cfg['e23_source'])/'report.json')
    for variant, model in itertools.product(cfg['e23_variants'], cfg['e23_models']):
        name = f'{variant}_{model}'.upper()
        path = Path(cfg['e23_source'])/f'{variant.lower()}_{model}_oos.parquet'
        cached = keys(pd.read_parquet(path, columns=['date', 'symbol', 'e23_raw_probability', 'fold_index']))
        folds = {row['fold_index']: (pd.Timestamp(row['test_start']), pd.Timestamp(row['test_end']))
                 for row in report['results'][variant][model]['folds']}
        for index, (start, end) in folds.items():
            sub = cached.loc[cached.fold_index.eq(index)]
            if not sub.date.between(start, end).all():
                raise ValueError('Legacy cached fold boundaries inconsistent')
        matched = frame[['date', 'symbol', 'oracle_rank', 'oracle_decile', 'terminal_return']].merge(
            cached.rename(columns={'e23_raw_probability': name}), on=['date', 'symbol'], how='left', validate='one_to_one')
        rows.append(dict(signal=name, raw_matched_rows=int(matched[name].notna().sum()), total_rows=len(frame),
                         complete_ten_score_dates=int(matched[name].notna().groupby(matched.date).sum().eq(10).sum()),
                         decision_eligible=False, reason='Future-label-filtered source; descriptive intersection only'))
        legacy.append(matched[['date', 'symbol', name]])
    return inventory, rows, legacy


def evaluate(frame, signal, count=3):
    ready = frame[signal].notna().groupby(frame.date).transform('sum').eq(10)
    chosen = shortlist(frame, frame[signal].where(ready), count)
    result = outcomes(frame, chosen, ready)
    reference = matched_reference(frame, result.selected_count, frame[BASELINE])
    oracle = matched_reference(frame, result.selected_count, -frame.oracle_rank)
    result['d10_base'], result['d1_base'] = reference.d10, reference.d1
    result['d10_oracle'], result['d1_oracle'] = oracle.d10, oracle.d1
    up = frame.oracle_decile.eq(10).astype(float).where(frame.oracle_decile.notna())
    result['auc_d10_rest'] = daily_auc(up, frame[signal], frame.date)
    result['signal'] = signal
    return result.rename_axis('date').reset_index()


def pair_diagnostics(frame, first, second):
    ready = frame[[first, second]].notna().groupby(frame.date).transform('sum').eq(10).all(axis=1)
    known = frame.oracle_decile.notna().groupby(frame.date).transform('sum').eq(10)
    part = frame.loc[ready & known].copy()
    if part.empty:
        return pd.DataFrame()
    dates = part.date
    ranked = part[[first, second, 'terminal_return']].groupby(dates).rank(pct=True)
    a,b,y = (ranked[column]-ranked[column].groupby(dates).transform('mean') for column in [first, second, 'terminal_return'])
    def corr(x,z):
        numerator = (x*z).groupby(dates).sum()
        denominator = np.sqrt((x*x).groupby(dates).sum()*(z*z).groupby(dates).sum())
        return numerator/denominator.where(denominator.gt(1e-12))
    denominator = (a*a).groupby(dates).sum()
    slope = ((a*b).groupby(dates).sum()/denominator.replace(0, np.nan))
    residual = b-a*dates.map(slope)
    residual_ic = corr(residual,y)
    pick_a, pick_b = shortlist(part,part[first]), shortlist(part,part[second])
    removed, added = pick_a & ~pick_b, pick_b & ~pick_a
    result = pd.DataFrame(dict(score_spearman=corr(a,b), residual_ic=residual_ic,
                              overlap=(pick_a&pick_b).groupby(dates).sum()/3,
                              removed_d1=(removed&part.oracle_decile.eq(1)).groupby(dates).sum(),
                              lost_d10=(removed&part.oracle_decile.eq(10)).groupby(dates).sum(),
                              added_d10=(added&part.oracle_decile.eq(10)).groupby(dates).sum(),
                              introduced_d1=(added&part.oracle_decile.eq(1)).groupby(dates).sum()))
    result['first'],result['second'] = first,second
    return result.rename_axis('date').reset_index()


def recipe_metrics(frame, definition):
    score, chosen, ready = recipe(frame, definition)
    result = outcomes(frame, chosen, ready)
    reference = matched_reference(frame, result.selected_count, frame[BASELINE])
    oracle = matched_reference(frame, result.selected_count, -frame.oracle_rank)
    result['d10_base'], result['d1_base'] = reference.d10, reference.d1
    result['d10_oracle'], result['d1_oracle'] = oracle.d10, oracle.d1
    up = frame.oracle_decile.eq(10).astype(float).where(frame.oracle_decile.notna())
    result['auc_d10_rest'] = daily_auc(up, score, frame.date)
    result['signal'] = definition['name']
    return result.rename_axis('date').reset_index()


def report_statistics(daily, cfg):
    records=[]
    avg=lambda s: float(s.mean()) if s.notna().any() else None
    for (signal,year), raw in daily.assign(year=daily.date.dt.year).groupby(['signal','year']):
        good=raw.loc[raw.ready & raw.complete_labels & raw.selected_count.gt(0)]
        records.append(dict(signal=signal,year=int(year),dates_total=len(raw),ready_dates=int(raw.ready.sum()),
                            evaluated_dates=len(good),coverage=float(raw.ready.mean()),selected_per_ready_date=avg(raw.loc[raw.ready].selected_count),
                            abstentions=int((raw.ready&raw.selected_count.eq(0)).sum()),d10=avg(good.d10),d1=avg(good.d1),
                            d10_base=avg(good.d10_base),d1_base=avg(good.d1_base),d10_oracle=avg(good.d10_oracle),d1_oracle=avg(good.d1_oracle),
                            d10_lift=avg(good.d10-good.d10_base),d1_reduction=avg(good.d1_base-good.d1),
                            auc_d10_rest=avg(good.auc_d10_rest)))
    return records


def period_gate(row,cfg):
    return bool(row['coverage']>=cfg['min_year_coverage'] and row['evaluated_dates']>=cfg['min_dates']
                and row['d10_lift'] is not None and row['d10_lift']>=cfg['min_d10_lift']
                and row['d1_reduction'] is not None and row['d1_reduction']>=cfg['min_d1_reduction'])


def adjust_family(tests):
    # Keep the entire declared family, including non-testable comparisons.
    # A missing comparison cannot shrink the multiplicity penalty for others.
    adjusted = holm_adjust({key: row['p_raw'] if row['p_raw'] is not None else 1.
                            for key, row in tests.items()})
    return {key: adjusted[key] if row['p_raw'] is not None else None for key, row in tests.items()}


def gates(daily, stats, cfg):
    names=[r['name'] for r in cfg['recipes']]
    calendar=nyse_sessions('2022-01-01','2026-09-02')
    tests={}
    for name in names:
        raw=daily.loc[daily.signal.eq(name)&daily.ready&daily.complete_labels&daily.selected_count.gt(0)
                      &daily.date.dt.year.isin(cfg['confirmation_years'])].set_index('date')
        for measure,values in [('d10_lift',raw.d10-raw.d10_base),('d1_reduction',raw.d1_base-raw.d1)]:
            tests[f'{name}:{measure}']=block_test(values,calendar,cfg)
    adjusted=adjust_family(tests)
    results=[]
    for name in names:
        rows=[r for r in stats if r['signal']==name]
        val=next(r for r in rows if r['year']==cfg['validation_year'])
        confirm=[r for r in rows if r['year'] in cfg['confirmation_years']]
        significance=all(adjusted[f'{name}:{m}'] is not None and adjusted[f'{name}:{m}']<=cfg['alpha_holm']
                         and tests[f'{name}:{m}']['mean_delta']>0 for m in ('d10_lift','d1_reduction'))
        coverage=all(r['coverage']>=cfg['min_year_coverage'] for r in rows)
        positives=sum(period_gate(r,cfg) for r in confirm)
        results.append(dict(recipe=name,validation_pass=period_gate(val,cfg),positive_confirmation_periods=positives,
                            full_period_coverage=coverage,block_comparisons_pass=significance,
                            conclusion='INCONCLUSIVE_FULL_PERIOD' if not coverage else 'GATE_PASS_TO_CONFIRM' if period_gate(val,cfg) and positives>=cfg['min_positive_confirmation_periods'] and significance else 'NO_STABLE_GAIN',
                            gate_pass=bool(period_gate(val,cfg) and positives>=cfg['min_positive_confirmation_periods'] and significance and coverage)))
    for k in tests:tests[k]['p_holm']=adjusted[k]
    return results,tests


def run(output,config=CONFIG):
    output,config=Path(output),Path(config)
    cfg=read(config)
    with exclusive_run(output):
        if (output/'report.json').exists():raise ValueError('Completed dossier immutable; new output required')
        try:
            atomic_json(output/'progress.json',dict(status='RUNNING',phase='source_qualification'))
            protocol,population=qualify(output,cfg,config)
            panel=build_panel(population,cfg)
            inventory,legacy_coverage,legacy=inventory_and_legacy(panel,cfg)
            atomic_json(output/'inventory.json',dict(families=inventory,legacy_scores=legacy_coverage))
            current=list(cfg['signal_groups'])
            panel=panel.merge(legacy[0],on=['date','symbol'],how='left',validate='one_to_one') if legacy else panel
            for part in legacy[1:]:panel=panel.merge(part,on=['date','symbol'],how='left',validate='one_to_one')
            old_columns=[column for part in legacy for column in part if column not in ('date','symbol')]
            panel[old_columns]=rank_full_ten(panel,old_columns)
            panel.to_parquet(output/'signals-top10.parquet',index=False)
            daily=[]
            for column in [*current,*old_columns]:
                daily.append(evaluate(panel,column))
            for definition in cfg['recipes']:daily.append(recipe_metrics(panel,definition))
            daily=pd.concat(daily,ignore_index=True)
            daily.to_parquet(output/'daily-statistics.parquet',index=False)
            stats=report_statistics(daily,cfg)
            pd.DataFrame(stats).to_csv(output/'yearly-statistics.csv',index=False)
            pairs=[]
            for first,second in itertools.combinations(current,2):
                pairs.append(pair_diagnostics(panel,first,second))
            for column in old_columns:pairs.append(pair_diagnostics(panel,BASELINE,column))
            paired=pd.concat([p for p in pairs if not p.empty],ignore_index=True)
            paired.to_parquet(output/'pair-daily-statistics.parquet',index=False)
            pair_summary=paired.groupby(['first','second']).agg(dates=('date','size'),score_spearman=('score_spearman','mean'),
                residual_ic=('residual_ic','mean'),overlap=('overlap','mean'),removed_d1=('removed_d1','sum'),lost_d10=('lost_d10','sum'),
                added_d10=('added_d10','sum'),introduced_d1=('introduced_d1','sum')).reset_index()
            pair_summary.to_csv(output/'pair-summary.csv',index=False)
            results,tests=gates(daily,stats,cfg)
            verify_hashes(Path('.'),protocol['source_hashes'])
            result=dict(status='COMPLETED_EXPLORATORY',verdict='COMPLEMENTARITY_TO_CONFIRM_NOT_ALPHA' if any(r['gate_pass'] for r in results) else 'NO_STABLE_TOP10_COMPLEMENTARITY',
                        primary_recipe=cfg['primary_recipe'],recipe_gates=results,block_tests=tests,statistics=stats,
                        inventory=inventory,legacy_score_coverage=legacy_coverage,source_hashes_verified_after_calculation=True,
                        protocol_sha256=digest(output/'protocol.json'),no_training=True,no_sql=True,no_provider_calls=True,no_broker_calls=True,no_pnl=True,
                        production_promotion=False,independent_holdout=False,
                        limitations=['Not all old OOF scores survive: no claim to combine all historical experiments.',
                          'E23 forecasts are future-label-filtered and not eligible for decision recipes; descriptive intersections only.',
                          'Known-J fixed M/V formulas re-applied to current TOP10, not exact replay of the old ATR intersection.',
                          'E17 price-only factors originally H60/H120; H20 reinterpretation, old adjusted prices and instrument metadata reserved.',
                          '2023 partial, 2026 through September 2 with twenty unknown-label dates; repeated/overlapping H20 outcomes.',
                          'Already examined years after several research choices, not an independent untouched holdout.',
                          'Rank correlations/residual IC and replacement counts are diagnostics, not probabilities or portfolio profits.'])
            result['files']={p.name:digest(p) for p in output.iterdir() if p.suffix in ('.csv','.parquet')}
            atomic_json(output/'report.json',result)
            atomic_json(output/'progress.json',dict(status='COMPLETED',verdict=result['verdict']))
            LOG.info('Finished: %s',result['verdict'])
            return result
        except Exception as exc:
            atomic_json(output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--config',type=Path,default=CONFIG)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    run(**vars(parser.parse_args()))
