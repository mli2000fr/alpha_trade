"""Frozen overnight/intraday decomposition on existing H20 Oracle ranks.

Offline only: no training, provider, LLM, SQL or order. Returns are per occasion,
not capital returns. Historical vendor adjustments are not broker fills/PIT receipts.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

PRICE = Path('artifacts/research/us_h10_price_readiness/20261019-v1/qualification-final-v4/research-prices.parquet')
SCORES = Path('artifacts/research/us_h10_h20_frozen_comparison/20261019-v1')
UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')
READ = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
POLICIES = ['INTRADAY20', 'OVERNIGHT20', 'AGREEMENT20', 'CLOSE20', 'ALWAYS_LONG']
HORIZONS = [5, 10, 20]
EPS = 1e-12


def window_all(values, start, stop):
    """Inclusive positional windows; out-of-bounds always false, never wrap."""
    a = np.asarray(values, bool); left = np.asarray(start, int); right = np.asarray(stop, int)
    good = (left >= 0) & (right < len(a)) & (right >= left)
    out = np.zeros(len(left), bool); prefix = np.r_[0, np.cumsum(~a)]
    out[good] = prefix[right[good]+1] == prefix[left[good]]
    return out


def stable(values, left, right):
    s = pd.Series(values); known = s.notna() & ~s.astype(str).str.upper().isin(['', 'UNKNOWN', 'NAN', 'NONE'])
    code = pd.factorize(s)[0]; transitions = np.r_[True, code[1:] == code[:-1]]
    return window_all(known.to_numpy(), left, right) & window_all(transitions, np.asarray(left)+1, right)


def sign(values):
    a = np.asarray(values, float)
    return np.where(np.isfinite(a) & (a > EPS), 1, np.where(np.isfinite(a) & (a < -EPS), -1, 0))


def decompose(opens, closes, qualified, window=20):
    o = np.asarray(opens, float); c = np.asarray(closes, float); q = np.asarray(qualified, bool)
    if o.shape != c.shape or c.shape != q.shape or o.ndim != 1:
        raise ValueError('Aligned one-dimensional arrays required')
    n = len(c); pos = np.arange(n)
    with np.errstate(divide='ignore', invalid='ignore'):
        intra = np.log(c/o); night = np.r_[np.nan, np.log(o[1:]/c[:-1])]
    valid = window_all(q, pos-window, pos)
    i = pd.Series(intra).rolling(window, min_periods=window).sum().to_numpy()
    v = pd.Series(night).rolling(window, min_periods=window).sum().to_numpy()
    valid &= np.isfinite(i) & np.isfinite(v)
    i[~valid] = np.nan; v[~valid] = np.nan
    return pd.DataFrame(dict(intraday20=i, overnight20=v, close20=i+v, history_good=valid))


def directions(intra, night):
    i, n = sign(intra), sign(night)
    return dict(INTRADAY20=i, OVERNIGHT20=n, AGREEMENT20=np.where((i == n) & (i != 0), i, 0),
                CLOSE20=sign(np.asarray(intra)+np.asarray(night)), ALWAYS_LONG=np.ones(len(i), int))


def grid(rows, days, reserve=None, identities=()):
    if rows.duplicated('date').any(): raise ValueError('Duplicate symbol/date bars')
    g = rows.set_index('date').reindex(days).copy()
    raw = g[['open', 'high', 'low', 'close', 'adj_close', 'volume', 'is_filled']].apply(pd.to_numeric, errors='coerce')
    with np.errstate(divide='ignore', invalid='ignore'): factor = raw.adj_close/raw.close
    good = (np.isfinite(raw).all(axis=1) & raw[['open','high','low','close','adj_close','volume']].gt(0).all(axis=1)
        & raw.is_filled.eq(0) & raw.high.ge(raw[['open','low','close']].max(axis=1))
        & raw.low.le(raw[['open','high','close']].min(axis=1)) & factor.gt(0) & np.isfinite(factor))
    for field in ['instrument_id','data_source','data_adjustment']:
        good &= g[field].notna() & ~g[field].astype(str).str.upper().isin(['','UNKNOWN','NAN','NONE'])
    good &= g.data_source.astype(str).str.lower().isin(['eodhd_eod','alpaca_sip','alpaca_sip_research_successor'])
    for field in ['open','high','low','close']: g[field] = raw[field]*factor
    # Inherited source break guard. It marks unknown rather than replacing a title.
    ratio = g.close/g.close.shift(1)
    good &= ~(ratio.ge(20) | ratio.le(.05))
    if reserve: good &= days < pd.Timestamp(reserve['start'])
    g['point_good'] = good
    pos = np.arange(len(g)); history = window_all(good, pos-20, pos)
    for field in ['instrument_id','data_source','data_adjustment']:
        history &= stable(g[field].to_numpy(), pos-20, pos)
    for ev in identities:
        left, right = pd.Timestamp(ev['last_predecessor_date']), pd.Timestamp(ev['first_successor_date'])
        history &= ~((days >= right) & (pd.Series(days).shift(20).le(left).to_numpy()))
    f = decompose(g.open, g.close, good)
    history &= f.history_good.to_numpy(); f.loc[~history, ['intraday20','overnight20','close20']] = np.nan
    f['history_good'] = history
    return g, f


def outcomes(g, horizon, identities=()):
    n = len(g); pos = np.arange(n); end = pos+horizon; left = pos+1
    good = window_all(g.point_good.to_numpy(), pos, end)
    for field in ['instrument_id','data_source','data_adjustment']:
        good &= stable(g[field].to_numpy(), pos, end)
    for ev in identities:
        good &= ~((g.index <= pd.Timestamp(ev['last_predecessor_date']))
                  & (pd.Series(g.index).shift(-horizon).ge(pd.Timestamp(ev['first_successor_date'])).to_numpy()))
    entry = g.open.shift(-1).to_numpy(float); exit = g.close.shift(-horizon).to_numpy(float)
    with np.errstate(divide='ignore', invalid='ignore'): ret = exit/entry-1
    valid = good & np.isfinite(ret) & (entry > 0) & (exit > 0)
    ret[~valid] = np.nan
    return ret, valid


def independent(frame, max_horizon=20):
    """Choose earliest membership before history/future checks, same episodes for policies/H."""
    flags = pd.Series(False, index=frame.index)
    for _, group in frame.sort_values(['pos','rank','symbol']).groupby('symbol', sort=False):
        next_pos = -1
        for r in group.itertuples():
            if r.pos >= next_pos:
                flags.at[r.Index] = True; next_pos = r.pos+max_horizon
    return flags


def net_return(ret, sides, calendar_days, cost=.001):
    r = np.asarray(ret, float); s = np.asarray(sides, int); days = np.asarray(calendar_days, int)
    if not np.isin(s, [-1,1]).all() or cost < 0: raise ValueError('Executable LONG/SHORT sides required')
    if not np.isfinite(r).all() or (r <= -1).any(): raise ValueError('Qualified positive entry/exit required')
    fees = cost*(2+r)
    borrow = np.where(s < 0, .003*np.maximum(days, 0)/365, 0.)
    return s*r-fees-borrow


def blocked_interval(rows, days, value, alpha=.05, draws=1999):
    """Fixed20-session moving-block bootstrap over full decision calendar, event-weighted."""
    if rows.empty or rows.date.nunique() < 20: return None
    daily = rows.groupby('date')[value].agg(['sum','count']).reindex(days, fill_value=0)
    sums = daily['sum'].to_numpy(float); counts = daily['count'].to_numpy(float)
    n = len(days); block = min(20,n); rng = np.random.default_rng(20261020)
    batches = []; blocks = int(np.ceil(n/block))
    for _ in range(draws):
        starts = rng.integers(0,n-block+1,size=blocks)
        indices = (starts[:,None]+np.arange(block)).ravel()[:n]
        total = counts[indices].sum()
        if total: batches.append(sums[indices].sum()/total)
    return [float(x) for x in np.quantile(batches, [alpha/2,1-alpha/2])] if batches else None


def prepare(root):
    if (root/'protocol.json').exists():
        p = READ(root/'protocol.json'); verify_hashes(Path('.'), p['sources']); return p
    if root.exists(): raise ValueError('Fresh output required')
    old = READ(SCORES/'protocol.json')
    if READ(SCORES/'final-audit.json')['status'] != 'PASS_EXPLORATORY_ONLY': raise ValueError('Unqualified Oracle input')
    expected = next(v for k,v in old['sources'].items() if Path(k).name == PRICE.name)
    if digest(PRICE) != expected: raise ValueError('Changed normalized price tape')
    files = [Path(__file__), Path('tests/test_us_overnight_intraday_pilot.py'),
        Path('scripts/research/us_overnight_intraday_audit.py'), PRICE, PRICE.parent/'quality-reserves.json',
        PRICE.parent/'report.json', UNIVERSE, SCORES/'protocol.json', SCORES/'final-audit.json',
        Path('scripts/research/us_concentrated_historical_tapes.py')]
    for year in [2024,2025,2026]:
        name = f'{year}-H20-scores.parquet'; done = READ(SCORES/f'{year}-done.json')
        if digest(SCORES/name) != done['files'][name]: raise ValueError('Changed frozen scores')
        files += [SCORES/name, SCORES/f'{year}-done.json']
    p = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), sources={str(f):digest(f) for f in files},
        hypothesis='Different persistent20session overnight and intraday components may reveal direction masked by close-to-close momentum; not replication or established US edge.',
        source='Tsinghua2025 overnight/intraday thesis abstract; Chinese2020 decomposition literature. No assumption CN findings transfer to US.',
        source_url='https://newetds.lib.tsinghua.edu.cn/qh/paper/summary?dbCode=ETDQH&sysId=302463',
        scopes=['TOP10','TOP20PCT'], primary_scope='TOP10', additional_scope='TOP20PCT explicitly authorized by user before result',
        oracle='Frozen annual research CatBoost PATH_H20 ranks2024/25/26, independently tested chronological training/validation folds; NOT current live model or H10 ranks.',
        scores_columns=['date','symbol','rank','score'],
        selection='rank<=10 or rank<=ceil(.2*N contemporaneously scored), score DESC symbol ASC; before history and future qualification, no replacement.',
        decisions_start='2024-01-01', decisions_end='2026-09-01', observation_end='2026-09-30',
        lookback=20, horizons=HORIZONS, primary_horizon=20, policies=POLICIES,
        rules='Sum20log(C_t/O_t), sum20log(O_t/C_(t-1)); sign momentum for INTRADAY20/OVERNIGHT20; AGREEMENT20 only same nonzero sign; CLOSE20 sign sum for benchmark. Numericalzero1e-12, no calibrated threshold.',
        execution='Signal afterJclose; J+1open to J+Hclose (H includes entry session), fixed endpoint, NO TP/SL/trailing, one-unit per occasion. Diagnostic, not live risk implementation.',
        prices='Use same-date adj_close/close factor on ALL OHLC. Need21 valid history bars, stable identity/provider/adjustment; all J..J+H future bars validated separately, no fill, no missing=loss. Vendor adjusted total-return proxy, not broker cashflow proof.',
        quality_reserves=READ(PRICE.parent/'quality-reserves.json')['price_reserves'], identity_events=old['identity_events'],
        feature_reserves='Do not reuse old cached features; recompute solely from normalized prices. Original Oracle scoring exclusions remain inherited.',
        tails='Perdate/horizon bottom/top ceil10% of QUALIFIED full Oracle-scored universe open-entry terminal returns, only if>=95% price-qualified. Explicit conditional tails, NOT existing SQL D1/D10 labels or rank amongTOP10.',
        nonoverlap='Common20session symbol-level admission by earliest original scope membership BEFORE history, sides or future-quality checks. Block until previous fixed20close; next signal may be at that close. Unknown still blocks. Continue across year boundary.',
        controls='AlwaysLONG and close20 momentum. Compare each rule against alwaysLONG on exact same qualified nonabstaining cases. Report LONG and SHORT separately. No inversion promoted after seeing results.',
        fees_per_leg=.001, stress_fees_per_leg=.0025, borrow_annual=.003,
        costs='Hypothetical10bps entry plus10bps on exit notional, annual0.3% initial-short-notional borrow ACT/365. Stress25bps/leg. No verified borrow availability, spread/fills, taxes, margin or cash recycling.',
        inference='Primary NON_OVERLAP H20; fixed20calendar-session moving-block bootstrap1999 draws seed20261020, event-weighted mean. Six primary directionalrule/scope tests; CI99.1667%(Bonferroni6) plus95%, no tunedpvalue.',
        promotion_gate='Net and paired incremental mean vs same-casesLONG positive EACH2024/25/26, pooled primary net and paired Bonferroni CI lower>0, stress net>0 EACHyear, >=30episodes EACHyear; otherwise no promotion. Already explored years, not virgin confirmation even if pass.',
        no_training=True,no_sql=True,no_provider=True,no_llm=True,no_orders=True,no_production_changes=True)
    root.mkdir(parents=True); atomic_json(root/'protocol.json', p); return p


def build(root):
    p = prepare(root)
    if (root/'data-ready.json').exists(): raise ValueError('Immutable built input')
    days = mcal.get_calendar('NYSE').schedule(start_date='2023-01-01', end_date=p['observation_end']).index
    scores = []
    for year in [2024,2025,2026]:
        f = pd.read_parquet(SCORES/f'{year}-H20-scores.parquet', columns=p['scores_columns'])
        f = f[f.date.ge(p['decisions_start']) & f.date.le(p['decisions_end'])].copy()
        expected = f.sort_values(['date','score','symbol'],ascending=[True,False,True]).groupby('date').cumcount()+1
        if not f['rank'].eq(expected.reindex(f.index)).all(): raise ValueError('Noncausal rank/order mismatch')
        scores.append(f)
    scores = pd.concat(scores, ignore_index=True)
    if scores.duplicated(['date','symbol']).any(): raise ValueError('Duplicate ranks')
    scores['scored_count'] = scores.groupby('date').symbol.transform('size')
    scores['top10'] = scores['rank'].le(10); scores['top20'] = scores['rank'].le(np.ceil(.2*scores.scored_count))
    scores['pos'] = days.get_indexer(scores.date)
    if (scores.pos < 0).any(): raise ValueError('Non-NYSE score dates')
    for name in ['intraday20','overnight20','close20']: scores[name] = np.nan
    scores['history_good'] = False
    for h in HORIZONS: scores[f'return_h{h}'] = np.nan
    bars = pd.read_parquet(PRICE, columns=['date','symbol','open','high','low','close','adj_close','volume','is_filled','instrument_id','data_source','data_adjustment'])
    grouped = {s:x for s,x in bars.groupby('symbol',sort=False)}
    for i,(symbol, f) in enumerate(scores.groupby('symbol',sort=True),1):
        if symbol not in grouped: continue
        g, features = grid(grouped[symbol], days, p['quality_reserves'].get(symbol), p['identity_events'].get(symbol,[]))
        positions = f.pos.to_numpy(int)
        for name in ['intraday20','overnight20','close20','history_good']:
            scores.loc[f.index,name] = features[name].to_numpy()[positions]
        for h in HORIZONS:
            ret,_ = outcomes(g,h,p['identity_events'].get(symbol,[])); scores.loc[f.index,f'return_h{h}'] = ret[positions]
        if i%200 == 0:
            atomic_json(root/'progress.json',dict(status='BUILDING',symbols=i,total=scores.symbol.nunique()))
            print('Symbols',i,'/',scores.symbol.nunique(),flush=True)
    tails = []
    for h in HORIZONS:
        col = f'return_h{h}'; scores[f'tail_h{h}'] = 0
        for day, f in scores.groupby('date',sort=True):
            eligible = f[f[col].notna()].sort_values([col,'symbol'])
            ratio = len(eligible)/len(f); admitted = ratio >= .95
            if admitted:
                k = int(np.ceil(.1*len(eligible)))
                scores.loc[eligible.index[:k], f'tail_h{h}'] = -1
                scores.loc[eligible.index[-k:], f'tail_h{h}'] = 1
            tails.append(dict(date=day,horizon=h,scored=len(f),qualified=len(eligible),ratio=ratio,tail_labels_available=admitted))
    selected = scores[scores.top20 | scores.top10].copy()
    for scope, flag in [('TOP10','top10'),('TOP20PCT','top20')]:
        subset = selected[selected[flag]]
        selected['independent_'+scope] = independent(subset).reindex(selected.index,fill_value=False)
    selected.to_parquet(root/'candidates.parquet',index=False)
    pd.DataFrame(tails).to_parquet(root/'tail-coverage.parquet',index=False)
    pd.DataFrame(dict(date=days)).to_parquet(root/'sessions.parquet',index=False)
    verify_hashes(Path('.'), p['sources'])
    atomic_json(root/'data-ready.json',dict(status='BUILT',full_score_rows=len(scores),selected_rows=len(selected),
        files={n:digest(root/n) for n in ['candidates.parquet','tail-coverage.parquet','sessions.parquet']}))


def summarize(root):
    p = prepare(root); verify_hashes(root, READ(root/'data-ready.json')['files'])
    if (root/'report.json').exists(): raise ValueError('Immutable result')
    f = pd.read_parquet(root/'candidates.parquet'); sessions = pd.DatetimeIndex(pd.read_parquet(root/'sessions.parquet').date)
    parts = []; coverage = []
    for scope,flag in [('TOP10','top10'),('TOP20PCT','top20')]:
        members = f[f[flag]].copy()
        for independence in ['ALL','NON_OVERLAP20']:
            admitted = members if independence == 'ALL' else members[members['independent_'+scope]]
            for h in HORIZONS:
                valid = admitted.history_good & admitted[f'return_h{h}'].notna()
                for year in [2024,2025,2026]:
                    a = admitted[admitted.date.dt.year.eq(year)]
                    coverage.append(dict(scope=scope,admission=independence,horizon=h,year=year,
                        members=len(a),invalid_history=int((~a.history_good).sum()),
                        missing_outcome=int(a[f'return_h{h}'].isna().sum()),qualified=int((a.history_good & a[f'return_h{h}'].notna()).sum())))
                a = admitted[valid].copy(); raw = a[f'return_h{h}'].to_numpy(float)
                exit_dates = sessions.take(a.pos.to_numpy(int)+h); entry_dates = sessions.take(a.pos.to_numpy(int)+1)
                held_days = (exit_dates-entry_dates).days.to_numpy(int)
                sides = directions(a.intraday20.to_numpy(),a.overnight20.to_numpy())
                for policy,side in sides.items():
                    active = side != 0; x = a.loc[active, ['date','symbol','rank','pos']].copy()
                    r = raw[active]; s = side[active]; cd = held_days[active]
                    x['scope']=scope; x['admission']=independence; x['horizon']=h; x['policy']=policy
                    x['side']=s; x['return']=r; x['tail']=a.loc[active,f'tail_h{h}'].to_numpy(int)
                    x['gross']=s*r; x['net']=net_return(r,s,cd,p['fees_per_leg'])
                    x['net_stress']=net_return(r,s,cd,p['stress_fees_per_leg'])
                    x['always_long_net']=net_return(r,np.ones(len(s),int),cd,p['fees_per_leg'])
                    x['incremental_vs_long']=x.net-x.always_long_net
                    actual=sign(r)
                    x['correct']=np.where(actual!=0,(s*actual>0).astype(float),np.nan)
                    x['net_win']=x.net>0
                    parts.append(x)
    trades = pd.concat(parts,ignore_index=True); trades['year']=trades.date.dt.year
    summaries = []
    for keys, group in trades.groupby(['scope','admission','horizon','policy','year'],sort=True):
        scope,admission,h,policy,year=keys
        rows = dict(scope=scope,admission=admission,horizon=int(h),policy=policy,year=int(year),
            n=len(group),dates=group.date.nunique(),symbols=group.symbol.nunique(),
            longs=int(group.side.eq(1).sum()),shorts=int(group.side.eq(-1).sum()),
            directional_n=int(group.correct.notna().sum()),
            directional_accuracy=float(group.correct.mean()),net_win_rate=float(group.net_win.mean()),
            mean_net=float(group.net.mean()),median_net=float(group.net.median()),mean_stress=float(group.net_stress.mean()),
            same_cases_long_mean=float(group.always_long_net.mean()),incremental_vs_long=float(group.incremental_vs_long.mean()))
        tail = group[group['tail'].ne(0) & group['return'].abs().gt(EPS)]
        rows.update(tail_n=len(tail),tail_directional_accuracy=float((tail.side==tail['tail']).mean()) if len(tail) else None)
        summaries.append(rows)
    summaries = pd.DataFrame(summaries)
    tests = []
    decision_days=sessions[(sessions>=pd.Timestamp(p['decisions_start'])) & (sessions<=pd.Timestamp(p['decisions_end']))]
    for scope in p['scopes']:
        for policy in POLICIES[:3]:
            rows=trades[(trades.scope==scope)&(trades.admission=='NON_OVERLAP20')&trades.horizon.eq(20)&(trades.policy==policy)]
            ci = blocked_interval(rows,decision_days,'net'); paired=blocked_interval(rows,decision_days,'incremental_vs_long')
            corrected=blocked_interval(rows,decision_days,'net',alpha=.05/6)
            corrected_delta=blocked_interval(rows,decision_days,'incremental_vs_long',alpha=.05/6)
            annual=summaries[(summaries.scope==scope)&(summaries.admission=='NON_OVERLAP20')&summaries.horizon.eq(20)&(summaries.policy==policy)]
            passed=(len(annual)==3 and annual.n.ge(30).all() and annual.mean_net.gt(0).all()
                and annual.incremental_vs_long.gt(0).all() and annual.mean_stress.gt(0).all()
                and corrected is not None and corrected[0]>0 and corrected_delta is not None and corrected_delta[0]>0)
            tests.append(dict(scope=scope,policy=policy,n=len(rows),mean_net=float(rows.net.mean()) if len(rows) else None,
                incremental_vs_long=float(rows.incremental_vs_long.mean()) if len(rows) else None,
                net_ci95=ci,incremental_ci95=paired,net_ci_bonferroni6=corrected,
                incremental_ci_bonferroni6=corrected_delta,passes_frozen_gate=bool(passed)))
    trades.to_parquet(root/'outcomes.parquet',index=False); summaries.to_csv(root/'annual-summary.csv',index=False)
    pd.DataFrame(coverage).to_csv(root/'coverage.csv',index=False)
    result=dict(status='EXPLORATORY_CANDIDATE_REQUIRES_FRESH_CONFIRMATION' if any(r['passes_frozen_gate'] for r in tests) else 'NO_ROBUST_OVERNIGHT_INTRADAY_IMPROVEMENT',
        finished_at_utc=datetime.now(timezone.utc).isoformat(),primary_tests=tests,summary_rows=len(summaries),
        outcome_rows=len(trades),per_occasion_not_portfolio=True,no_fitted_model=True,no_sql_or_order_or_provider=True,
        caveats=['Current survivor universe; reconstructed adjusted vendor prices, not historic local receipts',
            '2024..2026 already heavily explored, not virgin holdout; Bonferroni6 does not correct entire research history',
            'Costs and borrow hypothetical; short availability/capital/execution parity not certified',
            'ALL observations overlap; common NON_OVERLAP20 and block intervals primary, no annual capital return',
            'Conditional D1/D10 defined here over price-qualified full scored universe, not legacy SQL labels'],
        files={n:digest(root/n) for n in ['protocol.json','data-ready.json','candidates.parquet','tail-coverage.parquet','sessions.parquet','outcomes.parquet','annual-summary.csv','coverage.csv']})
    verify_hashes(Path('.'),p['sources']); atomic_json(root/'report.json',result)
    atomic_json(root/'progress.json',dict(status=result['status'],outcome_rows=len(trades)))
    print(result['status'],len(trades),'occasion rows',flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--phase',choices=['prepare','build','summarize'],required=True);args=a.parse_args()
    globals()[args.phase](args.output)
