"""Second scalar formulation of path targets and ranking; same assistant, not human review."""
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_oracle_path_trend_ranking_20261022 import read, digest, save, verify

ROOT = Path('artifacts/research/us_oracle_path_trend_ranking/20261022-v2')


def scalar_metrics(window):
    entry = float(window[0][0])
    out = {}
    for name, sign in [('long', 1), ('short', -1)]:
        r = [sign*(float(bar[3])/entry-1)*100 for bar in window]
        values = [0.]+r
        peak = max(values)
        k = values.index(peak)
        favourable = [(float(bar[1])/entry-1)*100 if sign == 1 else (1-float(bar[2])/entry)*100 for bar in window]
        adverse = [(1-float(bar[2])/entry)*100 if sign == 1 else (float(bar[1])/entry-1)*100 for bar in window]
        ih = ([0.]+favourable).index(max([0.]+favourable))-1
        metrics = dict(area_pct=math.fsum(r)/20,
            persistence_pct=100*sum(x>0 for x in r)/20,
            adverse_before_peak_close_pct=max([0.]+[-x for x in values[:k+1]]),
            peak_close_pct=peak, peak_session=k, terminal_pct=r[-1],
            mfe_intraday_pct=max([0.]+favourable), mae_intraday_pct=max([0.]+adverse),
            adverse_before_high_day_lower_pct=max([0.]+adverse[:ih]) if ih>=0 else 0.,
            adverse_before_high_day_upper_pct=max([0.]+adverse[:ih+1]) if ih>=0 else 0.)
        out.update({name+'_'+key:value for key, value in metrics.items()})
    return out


def corr(a, b):
    x, y = rankdata(a), rankdata(b)
    x, y = x-x.mean(), y-y.mean()
    denominator = math.sqrt(float(x@x)*float(y@y))
    return float(x@y)/denominator if denominator else None


def require_close(actual, expected, label):
    if actual is None and expected is None:
        return
    if actual is None or expected is None or not math.isclose(float(actual), float(expected), abs_tol=1e-9, rel_tol=1e-10):
        raise AssertionError(f'{label}: {actual} != {expected}')


def run(root=ROOT):
    p, report = read(root/'protocol.json'), read(root/'report.json')
    verify(p['sources'])
    verify({str(root/name):sha for name, sha in report['files'].items()})
    data = pd.read_parquet(root/'dataset.parquet')
    original = pd.read_parquet(root/'observable-top10.parquet')
    if len(data)!=len(original) or data.duplicated(['date', 'symbol']).any():
        raise AssertionError('Candidate population changed')
    if not data[['date', 'symbol', 'oracle_rank']].equals(original[['date', 'symbol', 'oracle_rank']]):
        raise AssertionError('Candidate order changed')
    dates = nyse_sessions('2016-01-01', p['as_of'])
    anchor = dates.get_indexer([pd.Timestamp('2018-07-05')])[0]
    expected_n = [(dates.get_indexer([d])[0]-anchor)%21==0 for d in data.date]
    if not np.array_equal(data.nonoverlap, expected_n):
        raise AssertionError('Nonoverlap phase not frozen before outcomes')
    for day, g in data.groupby('date'):
        if sorted(g.oracle_rank.tolist()) != list(range(1,11)):
            raise AssertionError('Not original TOP10')
        if not g.complete_date.eq(g.individual_known.all()).all():
            raise AssertionError('Partial date in common cohort')
    checked = 0
    for source in ('historical', 'recent'):
        subset = data[data.source.eq(source)]
        symbols = sorted(subset.symbol.unique())
        if source == 'historical':
            parts = [pd.read_parquet(x['path'], columns=['date', 'symbol', 'open', 'high', 'low', 'close'],
                                    filters=[('symbol','in',symbols)]) for x in p['historical_price_chunks']]
            prices = pd.concat(parts, ignore_index=True)
        else:
            prices = pd.read_parquet(p['recent_prices'], columns=['date','symbol','open','high','low','close'])
        for symbol, g in subset.loc[subset.path_reason.eq('')].groupby('symbol'):
            raw = prices.loc[prices.symbol.eq(symbol)].set_index('date')
            if not raw.index.is_unique:
                raise AssertionError('Ambiguous price')
            for row in g.itertuples(index=False):
                j = dates.get_indexer([row.date])[0]
                if dates[j+21] != row.label_available or dates[j+21]>pd.Timestamp(p['as_of']):
                    raise AssertionError('Label availability mismatch')
                bars = raw.reindex(dates[j+1:j+21])[['open','high','low','close']].to_numpy(float).tolist()
                expected = scalar_metrics(bars)
                for key, value in expected.items():
                    require_close(getattr(row,key), value, f'{row.symbol}/{row.date}/{key}')
                checked += 1
    valid = data[data.complete_date & data.period.isin(
        ['DISCOVERY','VALIDATION','CONTROL_2023','CHECK_2024','CHECK_2025','CHECK_2026'])]
    ic_count, policies = 0, 0
    for rec in report['features']:
        feature, direction = rec['feature'], rec['orientation_frozen_discovery']
        discovered = []
        for period, stats in rec['periods'].items():
            g = valid[valid.period.eq(period)]
            daily = []
            for day, group in g.groupby('date'):
                v = corr(group[feature].to_numpy(float), group.long_area_pct.to_numpy(float))
                if v is not None:
                    daily.append(v)
                    ic_count += 1
            require_close(stats['ic'], direction*math.fsum(daily)/len(daily) if daily else None, feature+'/'+period+'/IC')
            if period == 'DISCOVERY':
                discovered = daily
            for count, expected in stats['policies'].items():
                n = int(count)
                chosen = g.assign(priority=g[feature]*direction).sort_values(
                    ['date','priority','symbol'],ascending=[True,False,True]).groupby('date').head(n)
                control = g[g.oracle_rank<=n]
                if len(chosen)!=expected['rows'] or chosen.date.nunique()!=expected['dates']:
                    raise AssertionError('Selection count mismatch')
                for metric, m in expected['metrics'].items():
                    c = 'long_'+metric
                    a = chosen.groupby('date')[c].mean()
                    b = control.groupby('date')[c].mean()
                    delta = a-b
                    for key, value in [('selected',a.mean()),('oracle',b.mean()),('delta_oracle',delta.mean())]:
                        require_close(m[key], float(value) if len(a) else None, feature+'/'+period+'/'+count+'/'+metric+'/'+key)
                if not expected['no_portfolio_returns']:
                    raise AssertionError('Path target mislabelled as PnL')
                policies += 1
        orientation = 1 if discovered and math.fsum(discovered)/len(discovered)>=0 else -1
        if direction != orientation:
            raise AssertionError('Orientation differs from discovery-only choice')
        d, v = rec['periods']['DISCOVERY'], rec['periods']['VALIDATION']
        rules = p['rules']
        eligible = feature in p['primary_family'] and rec['p_maxT'] is not None and rec['p_maxT']<=rules['maxT_alpha']
        eligible = eligible and d['ic'] is not None and d['ic']>=rules['discovery_ic'] and d['dates_ic']>=rules['discovery_dates']
        eligible = eligible and v['ic'] is not None and v['ic']>=rules['validation_ic'] and v['dates_ic']>=rules['validation_dates']
        eligible = eligible and all(x['dates']>=rules['validation_dates']
            and x['metrics']['area_pct']['delta_oracle']>0
            and x['metrics']['persistence_pct']['delta_oracle']>=0
            and x['metrics']['adverse_before_peak_close_pct']['delta_oracle']<=0 for x in v['policies'].values())
        if bool(eligible) != rec['selected_before_confirmation']:
            raise AssertionError('Candidate selection did not follow frozen rule')
    selected = [r['feature'] for r in report['features'] if r['selected_before_confirmation']]
    if selected != report['selected_before_confirmation']:
        raise AssertionError('Shortlist mismatch')
    if report['model_fits'] or report['portfolio_runs'] or report['API_calls'] or report['sql_writes']:
        raise AssertionError('Unexpected mutation/training')
    result = dict(status='PASS_SCALAR_PATHS_IC_RANKS_AND_PRECONFIRMATION_GATES',
        candidates=len(data), scalar_paths=checked, scalar_metrics_per_path=20,
        daily_IC_checks=ic_count, policy_checks=policies,
        selected_before_confirmation=selected, independent_human_review=False,
        report_sha256=digest(root/'report.json'), auditor_sha256=digest(__file__))
    save(root/'final-audit.json',result)
    return result


if __name__=='__main__':
    print(run())
