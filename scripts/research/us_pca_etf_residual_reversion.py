"""Offline, frozen PCA(3) of eleven sector ETFs versus SPY / assigned ETF.

Not full-stock PCA or a replication of fund results. No SQL, downloads, model
training, orders or production changes. All basket legs charged explicitly.
"""
import argparse
from datetime import datetime, timezone
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from scripts.research import us_professional_residual_reversion as base
from scripts.research import us_sector_residual_reversion as sector
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

PARENT = Path('artifacts/research/us_sector_residual_reversion/20261019-v1')
ETFS = sorted(sector.ETF.values())
REFS = ['SPY'] + ETFS
ARMS = ['SPY', 'SECTOR_ETF', 'PCA3_ETF']
POLICIES = ['OU_DYNAMIC', 'SAME_SIDE_FIXED10']
READ = base.READ
LOG = logging.getLogger(__name__)


def rolling_basis(close, good, window=252, components=3):
    """Fit correlation PCA at J using J-251..J returns only, no filling.

    Store the current basis projected onto the last 60 returns, not a series
    spliced from historical, rotating eigenvectors. Arbitrary signs cancel.
    """
    c = np.asarray(close, float); good = np.asarray(good, bool)
    if c.ndim != 2 or good.shape != c.shape or window < 60 or not 0 < components < c.shape[1]:
        raise ValueError('Aligned ETF panels, window>=60 and 0<k<n required')
    n, m = c.shape
    ready = np.zeros(n, bool)
    design = np.zeros((n, 60, components))
    operator = np.zeros((n, components, 60))
    loading = np.zeros((n, m, components))
    spectrum = np.full((n, m), np.nan)
    with np.errstate(divide='ignore', invalid='ignore'):
        returns = np.vstack([np.full(m, np.nan), c[1:] / c[:-1] - 1])
    for pos in range(window, n):
        if not good[pos-window:pos+1].all():
            continue
        x = returns[pos-window+1:pos+1]
        if not np.isfinite(x).all():
            continue
        sd = x.std(axis=0, ddof=1)
        if (sd <= 1e-10).any():
            continue
        z = (x - x.mean(axis=0)) / sd
        values, vectors = np.linalg.eigh(z.T @ z / (window-1))
        order = np.argsort(values)[::-1]; values = values[order]; vectors = vectors[:, order]
        if values[components-1] <= 1e-10 or values[components-1]-values[components] <= 1e-8*values[0]:
            continue  # A degenerate boundary does not define a unique retained subspace.
        v = vectors[:, :components]
        signs = np.sign(v[np.abs(v).argmax(axis=0), np.arange(components)])
        v = v * signs
        factors = z[-60:] @ v
        factors -= factors.mean(axis=0)
        singular = np.linalg.svd(factors, compute_uv=False)
        if singular[-1] <= singular[0]*1e-10:
            continue
        design[pos] = factors
        operator[pos] = np.linalg.pinv(factors, rcond=1e-10)
        loading[pos] = v / sd[:, None]
        spectrum[pos] = values
        ready[pos] = True
    return dict(ready=ready, design=design, operator=operator, loading=loading, spectrum=spectrum)


def pca_signals(close, history_good, basis):
    c = np.asarray(close, float); n = len(c)
    if n != len(basis['ready']) or n <= 60:
        raise ValueError('Aligned history required')
    with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
        y = np.full((n, 60), np.nan)
        y[60:] = sliding_window_view(c[1:]/c[:-1]-1, 60)
        yc = y-y.mean(axis=1)[:, None]
        coefficient = np.einsum('tki,ti->tk', basis['operator'], yc)
        hedge = np.einsum('tmk,tk->tm', basis['loading'], coefficient)
        eps = yc-np.einsum('tik,tk->ti', basis['design'], coefficient)
        state = np.cumsum(eps, axis=1)
        prev, nxt = state[:, :-1], state[:, 1:]
        pc = prev-prev.mean(axis=1)[:, None]
        b = (pc*(nxt-nxt.mean(axis=1)[:, None])).sum(axis=1)/(pc*pc).sum(axis=1)
        a = nxt.mean(axis=1)-b*prev.mean(axis=1)
        error = nxt-a[:, None]-b[:, None]*prev
        sigma = np.sqrt((error*error).sum(axis=1)/57/(1-b*b))
        score = (state[:, -1]-a/(1-b))/sigma
        tau = -1/np.log(b)
    supported = np.r_[np.zeros(60, bool), sliding_window_view(np.asarray(history_good, bool), 61).all(axis=1)]
    supported &= basis['ready']
    l1 = np.abs(hedge).sum(axis=1)
    f = pd.DataFrame(dict(beta=l1, ar_b=b, equilibrium_sigma=sigma, s_score=score, tau_sessions=tau))
    f['model_valid'] = (supported & np.isfinite(f).all(axis=1) & np.isfinite(hedge).all(axis=1)
        & (l1 > 0) & (l1 <= 3) & (b > 0) & (b < np.exp(-1/30)) & (sigma > 1e-8))
    f.loc[~supported, ['beta', 'ar_b', 'equilibrium_sigma', 's_score', 'tau_sessions']] = np.nan
    hedge[~supported] = np.nan
    return f, hedge


def path_reasons(g, reserve=None, events=()):
    """Vector form of the sealed parent's window_reason; same precedence."""
    n = len(g); result = np.full(n, 'OK', dtype=object)
    def reject(mask, reason):
        result[(result == 'OK') & np.asarray(mask, bool)] = reason
    def forward_sum(x):
        return pd.Series(np.asarray(x, float)).rolling(12, min_periods=12).sum().shift(-11).to_numpy()
    reject(forward_sum(g.daily_good) != 12, 'INVALID_OR_MISSING_FUTURE_PRICE')
    for field in ['instrument_id', 'data_source', 'data_adjustment']:
        code = pd.Series(pd.factorize(g[field])[0], dtype=float)
        lo = code.rolling(12, min_periods=12).min().shift(-11).to_numpy()
        hi = code.rolling(12, min_periods=12).max().shift(-11).to_numpy()
        bad = (lo < 0) | (lo != hi)
        if field != 'instrument_id':
            bad |= forward_sum(g[field].astype(str).str.upper().isin(['UNKNOWN', '', 'NAN', 'NONE'])) > 0
        reject(bad, 'CHANGED_OR_UNKNOWN_'+field.upper())
    ratio = g.close.to_numpy(float)[1:]/g.close.to_numpy(float)[:-1]
    breaks = np.r_[False, (ratio >= 20) | (ratio <= .05)]
    # A 12-price path has 11 successive ratios; the ratio leading into J is not part of it.
    reject(pd.Series(breaks).rolling(11, min_periods=11).sum().shift(-11).fillna(0).to_numpy() > 0,
           'UNEXPLAINED_20X_BREAK')
    end = pd.Series(g.index, index=g.index).shift(-11)
    if reserve:
        reject(end.ge(pd.Timestamp(reserve['start'])), 'RESERVED_PRICE_BASIS')
    for event in events:
        reject((g.index <= pd.Timestamp(event['last_predecessor_date']))
            & end.ge(pd.Timestamp(event['first_successor_date'])), 'IDENTITY_BREAK')
    result[max(0, n-11):] = 'IMMATURE'
    return result


def weights_for(hedge, side):
    h = np.asarray(hedge, float)
    l1 = np.abs(h).sum()
    if side not in ('LONG', 'SHORT') or not np.isfinite(h).all() or not 0 < l1 <= 3+1e-10:
        raise ValueError('Invalid basket exposure/side')
    sign = 1 if side == 'LONG' else -1
    return sign*np.r_[1., -h]/(1+l1)


def basket_returns(entry, exit_prices, weights, calendar_days):
    en = np.asarray(entry, float); ex = np.asarray(exit_prices, float); w = np.asarray(weights, float)
    if en.shape != ex.shape or w.shape != en.shape or not np.isfinite([en, ex, w]).all() or (en <= 0).any() or (ex <= 0).any():
        raise ValueError('Invalid basket prices/weights')
    if not np.isclose(np.abs(w).sum(), 1, rtol=0, atol=1e-10):
        raise ValueError('Initial gross exposure must equal one')
    ratio = ex/en
    gross = float(w @ (ratio-1))
    turnover = float(np.abs(w) @ (1+ratio))
    borrow = float(-w[w < 0].sum()*.003*max(1, calendar_days)/365)
    return dict(gross=gross, costs=.0008*turnover, borrow=borrow, net=gross-.0008*turnover-borrow,
                net_stress=gross-.002*turnover-borrow)


def basket_exit(opens, closes, scores, valid, pos, side, hedge):
    w = weights_for(hedge, side); sign = 1 if side == 'LONG' else -1
    if pos < 0 or pos+11 >= len(opens) or opens.shape != closes.shape or opens.shape[1] != len(w):
        raise ValueError('Incomplete basket path')
    path = np.r_[opens[pos+1:pos+12].ravel(), closes[pos+1:pos+11].ravel()]
    if not np.isfinite(path).all() or (path <= 0).any():
        raise ValueError('Invalid basket path')
    entry = opens[pos+1]
    for age in range(1, 11):
        k = pos+age
        mark = float(w @ (closes[k]/entry-1))
        if mark <= -.05+1e-12:
            return k+1, 'DAILY_RISK_NEXT_OPEN', age
        if not valid[k] or not np.isfinite(scores[k]):
            return k+1, 'INVALID_MODEL_NEXT_OPEN', age
        if sign*scores[k] >= -.5:
            return k+1, 'REVERSION_NEXT_OPEN', age
    return pos+11, 'TIMEOUT_NEXT_OPEN', 10


def prepare(root):
    if (root/'protocol.json').exists():
        p = READ(root/'protocol.json'); verify_hashes(Path('.'), p['sources']); return p
    if root.exists():
        raise ValueError('Fresh directory required')
    parent = READ(PARENT/'protocol.json'); a = READ(PARENT/'final-audit.json')
    if a['status'] != 'PASS_EXPLORATORY_SECTOR_PROXY_ONLY' or a['report_sha256'] != digest(PARENT/'report.json'):
        raise ValueError('Unaudited sector parent')
    verify_hashes(Path('.'), parent['sources'])
    files = [Path(__file__), Path('scripts/research/us_pca_etf_residual_reversion_audit.py'),
        Path('tests/test_us_pca_etf_residual_reversion.py'), Path(base.__file__), Path(sector.__file__),
        PARENT/'protocol.json', PARENT/'report.json', PARENT/'final-audit.json', PARENT/'data-ready.json',
        PARENT/'prepared.json', PARENT/'snapshot-ready.json', PARENT/'etf-bars.parquet',
        PARENT/'symbol-sector-map.parquet', PARENT/'trades.parquet', base.PRICE,
        sector.PARENT/'sessions.parquet', sector.PARENT/'oracle-top10.parquet']
    root.mkdir(parents=True)
    p = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), sources={str(f): digest(f) for f in files},
        parent=str(PARENT), rules=parent['rules'], symbols=parent['retained_symbols'], refs=REFS, arms=ARMS,
        method='PCA3 of 11 sector ETFs, NOT full-stock PCA. No sector assignment used in PCA fit; current mapping retained for comparable sector baseline universe only.',
        pca_window=252, components=3, regression_window=60,
        fit='At J, standardize ETF close returns J-251..J by mean/std(ddof1); top3 eigenvectors of correlation matrix. Reproject last60 returns in that SAME current basis; OLS with intercept; cumulative residual AR1, noise SSE/57.',
        support='253 past ETF prices, all eleven source-qualified/stable; same eligible dates and symbols in all arms. Own 61 stock/SPY/assignedETF history and liquidity proxy remain. No missing-value filling.',
        exposure='PCA hedge coefficients translated to eleven ETFs; signed coefficients allowed. Require 0<L1(hedge)<=3. Fixed entry units, initial gross stock+all hedges=1; not equal volatility or net-dollar neutrality.',
        boundary='No fit for zero ETF standard deviation, nonunique component3/4 boundary relative gap<=1e-8 or rank-deficient last60 factor design relative tolerance1e-10.',
        signal='Same s<-1.25 long stock, s>1.25 short stock, at J; entry next open J+1. 0<ARb<exp(-1/30), equilibrium sigma>1e-8.',
        exit='Same -5% close-observed gross basket threshold, invalid daily model or normalization +/-0.5, execute ALL fixed legs next open; at most10 sessions then J+11 open. No TP/trailing.',
        costs='8bps per executed dollar EACH leg entry and exit, stress20bps; .3% annual borrow on initial short exposure, calendar/365. No netting between trades, no free synthetic factor.',
        independence='All trigger candidates archived. Earliest per stock/arm/scope blocks through J+11 BEFORE future quality. Replay NON_OVERLAP only (no all-overlapping PnL secondary).',
        future_quality='Identical stock+SPY+ALL11 ETF J..J+11 path required for all arms. Unknown candidate still blocks; no substitution.',
        comparison='Compare own independent signals, not identical trades. Equal-date differences on common entry dates only, no zero-filled absent arms.',
        gates='Inherited absolute n>=100, both CI95 lower>0, stress>0, top20positive share<50% in2025AND2026. Additionally PCA-minus-EACH-SPY/sector common-date CI lower>0 both years. No tuning after outcomes.',
        policies=POLICIES, scopes=parent['rules']['scopes'], sql=False, downloads=0, api_calls=0,
        new_ml_training=False, production_changes=False, orders=False, finite_capital=False,
        references=[dict(url='https://math.nyu.edu/~avellane/AvellanedaLeeStatArb20090616.pdf',
            use='Residual OU framework only; ETF PCA differs from full-stock PCA in paper; no claimed replication'),
            dict(url='https://numpy.org/doc/stable/reference/generated/numpy.linalg.eigh.html', use='Symmetric correlation eigenproblem')],
        limits=['2024-26 already viewed, not fresh OOS; static survivor universe and current non-PIT classifications in sector baseline',
            'ETF PCA still large-cap sector proxies, not full-stock PCA or certified factors for small caps/ADRs',
            'Historical fetch timestamps do not prove historical data availability; adjusted prices/reserves inherited',
            'No independently certified dividends/locates/margin/financing, integer sizing or annual capital PnL; no market-neutrality guarantee'])
    atomic_json(root/'protocol.json', p)
    return p


def load_market(p):
    days = pd.DatetimeIndex(pd.read_parquet(sector.PARENT/'sessions.parquet').date)
    stocks = dict(tuple(pd.read_parquet(base.PRICE).groupby('symbol', sort=False)))
    spy = base.valid_grid(stocks['SPY'], days)
    refs = {'SPY': spy}
    refs.update({str(s): sector.etf_grid(f, days) for s, f in pd.read_parquet(PARENT/'etf-bars.parquet').groupby('symbol')})
    mapping = pd.read_parquet(PARENT/'symbol-sector-map.parquet').set_index('symbol')
    return days, stocks, refs, mapping


def factor_panel(refs):
    close = np.column_stack([refs[s].close for s in ETFS])
    good = np.column_stack([refs[s].history_point_good for s in ETFS])
    # Require stable metadata over the entire 253-price estimation window.
    for j, s in enumerate(ETFS):
        for field in ['instrument_id', 'data_source', 'data_adjustment']:
            codes = pd.Series(pd.factorize(refs[s][field])[0], dtype=float)
            same = codes.rolling(253, min_periods=253).min().eq(codes.rolling(253, min_periods=253).max()) & codes.ge(0)
            # rolling_basis checks all point quality; separate endpoint metadata test.
            if j == 0 and field == 'instrument_id':
                stable = same.to_numpy()
            else:
                stable &= same.to_numpy()
    basis = rolling_basis(close, good)
    basis['ready'] &= stable
    return basis


def build(root):
    p = prepare(root)
    ready = READ(PARENT/'data-ready.json'); verify_hashes(PARENT, ready['files'])
    verify_hashes(PARENT, READ(PARENT/'prepared.json')['files'])
    verify_hashes(PARENT, READ(PARENT/'snapshot-ready.json')['files'])
    if (root/'data-ready.json').exists():
        verify_hashes(root, READ(root/'data-ready.json')['files']); return
    days, stocks, refs, mapping = load_market(p)
    basis = factor_panel(refs)
    np.savez_compressed(root/'basis.npz', **basis)
    supported = days[basis['ready']]
    atomic_json(root/'factor-coverage.json', dict(first_supported=str(supported[0].date()) if len(supported) else None,
        supported_dates=len(supported), etfs=ETFS, eigen_variance_share3=np.nanmedian(
            basis['spectrum'][basis['ready'], :3].sum(axis=1)/basis['spectrum'][basis['ready']].sum(axis=1)).item()))
    refopen = np.column_stack([refs[s].open for s in REFS]); refclose = np.column_stack([refs[s].close for s in REFS])
    reference_reason = np.full(len(days), 'OK', dtype=object)
    for s in REFS:
        r = path_reasons(refs[s]); mask = (reference_reason == 'OK') & (r != 'OK')
        reference_reason[mask] = s+':'+r[mask]
    top = pd.read_parquet(sector.PARENT/'oracle-top10.parquet'); topkeys = set(zip(top.symbol, pd.to_datetime(top.date)))
    root.joinpath('parts').mkdir(exist_ok=False)
    files = {'basis.npz': digest(root/'basis.npz'), 'factor-coverage.json': digest(root/'factor-coverage.json')}
    completed = 0
    period = (days >= '2024-01-01') & (days <= p['rules']['signal_end'])
    for name in ready['files']:
        if not name.endswith('-features.parquet'):
            continue
        archived = pd.read_parquet(PARENT/name)
        feature_parts = []; candidates = []; trades = []
        for symbol, old_features in archived.groupby('symbol', sort=False):
            reserve = p['rules']['price_reserves'].get(symbol); events = p['rules']['identity_events'].get(symbol, [])
            g = base.valid_grid(stocks[symbol], days, reserve, events)
            shared = (sector.supported_history(g) & sector.supported_history(refs['SPY'])
                & sector.supported_history(refs[str(mapping.loc[symbol, 'hedge_etf'])])
                & basis['ready'] & g.liquidity_pass & period).to_numpy(bool)
            quality = path_reasons(g, reserve, events)
            quality = np.where(quality != 'OK', 'STOCK:'+quality, reference_reason)
            opens = np.column_stack([g.open, refopen]); closes = np.column_stack([g.close, refclose])
            pf, hedge = pca_signals(g.close, g.history_point_good, basis)
            pf['model_valid'] &= g.stable_history.to_numpy(bool)
            for arm in ARMS:
                if arm == 'PCA3_ETF':
                    f = pf.copy(); hedges = np.column_stack([np.zeros(len(days)), hedge])
                else:
                    f = old_features[old_features.arm.eq(arm)].set_index('date').reindex(days).copy()
                    hedges = np.zeros((len(days), len(REFS)))
                    idx = 0 if arm == 'SPY' else REFS.index(str(mapping.loc[symbol, 'hedge_etf']))
                    hedges[:, idx] = f.beta.to_numpy(float)
                f['entry_eligible'] = f.model_valid.to_numpy(bool) & shared
                f['date'] = days; f['symbol'] = symbol; f['arm'] = arm
                for j in range(len(REFS)):
                    f[f'h{j}'] = hedges[:, j]
                feature_parts.append(f[['date', 'symbol', 'arm', 'beta', 'ar_b', 'equilibrium_sigma',
                    's_score', 'tau_sessions', 'model_valid', 'entry_eligible']+[f'h{j}' for j in range(len(REFS))]].reset_index(drop=True))
                z = f.s_score.to_numpy(float); valid = f.model_valid.to_numpy(bool)
                blocked = {scope: -1 for scope in p['scopes']}
                for pos in np.flatnonzero(f.entry_eligible.to_numpy(bool) & (np.abs(z) > 1.25)):
                    for scope in p['scopes']:
                        if scope == 'ORACLE_H10_TOP10' and (symbol, days[pos]) not in topkeys:
                            continue
                        independent = pos > blocked[scope]
                        if independent:
                            blocked[scope] = pos+11
                        side = 'LONG' if z[pos] < 0 else 'SHORT'
                        common = dict(symbol=symbol, date=days[pos], year=int(days[pos].year), scope=scope, arm=arm,
                            side=side, beta=float(f.beta.iloc[pos]), s_score=float(z[pos]), independent=independent,
                            entry_date=days[pos+1], last_path_date=days[pos+11], quality=str(quality[pos]))
                        candidates.append(common)
                        if not independent or quality[pos] != 'OK':
                            continue
                        h = hedges[pos]; weights = weights_for(h, side)
                        end, why, age = basket_exit(opens, closes, z, valid, pos, side, h)
                        for policy in POLICIES:
                            j = pos+11 if policy == 'SAME_SIDE_FIXED10' else end
                            ret = basket_returns(opens[pos+1], opens[j], weights, (days[j]-days[pos+1]).days)
                            trades.append(dict(**common, policy=policy, exit_date=days[j],
                                exit_reason='FIXED10_NEXT_OPEN' if policy == 'SAME_SIDE_FIXED10' else why,
                                exit_session=10 if policy == 'SAME_SIDE_FIXED10' else age,
                                hedge_betas=h.tolist(), entry_prices=opens[pos+1].tolist(), exit_prices=opens[j].tolist(), **ret))
            completed += 1
        chunk = Path(name).name.split('-')[0]
        for suffix, frame in [('features', pd.concat(feature_parts, ignore_index=True)),
                              ('candidates', pd.DataFrame(candidates)), ('trades', pd.DataFrame(trades))]:
            out = f'parts/{chunk}-{suffix}.parquet'; frame.to_parquet(root/out, index=False); files[out] = digest(root/out)
        atomic_json(root/'progress.json', dict(status='RUNNING', phase='PCA_AND_REFERENCE_REPLAY', completed=completed, total=len(p['symbols'])))
        LOG.info('PCA and references %d/%d', completed, len(p['symbols']))
    verify_hashes(Path('.'), p['sources'])
    atomic_json(root/'data-ready.json', dict(files=files, completed_symbols=completed))


def compare_dates(trades, days):
    rows = []
    primary = trades[trades.policy.eq('OU_DYNAMIC')]
    for (scope, year), f in primary.groupby(['scope', 'year']):
        a = f.groupby(['date', 'arm']).net.mean().unstack('arm')
        for ref in ['SPY', 'SECTOR_ETF']:
            if not {'PCA3_ETF', ref}.issubset(a.columns):
                continue
            common = a[['PCA3_ETF', ref]].dropna()
            if not len(common):
                continue
            delta = (common.PCA3_ETF-common[ref]).rename('net').reset_index()
            ci = base.block_interval(delta, days)
            rows.append(dict(scope=scope, year=int(year), reference=ref, common_dates=len(common),
                delta=float(delta.net.mean()), ci95=ci, positive_ci=ci[0] is not None and ci[0] > 0))
    return rows


def summarize(root):
    p = prepare(root); ready = READ(root/'data-ready.json'); verify_hashes(root, ready['files'])
    if (root/'report.json').exists():
        raise ValueError('Immutable completed report')
    def load(suffix):
        pieces = [pd.read_parquet(root/n) for n in ready['files'] if n.endswith(suffix)]
        return pd.concat([x for x in pieces if len(x)], ignore_index=True)
    candidates = load('-candidates.parquet'); trades = load('-trades.parquet')
    candidates.to_parquet(root/'candidates.parquet', index=False); trades.to_parquet(root/'trades.parquet', index=False)
    days = pd.DatetimeIndex(pd.read_parquet(sector.PARENT/'sessions.parquet').date)
    summaries = []
    for (arm, scope, year, policy), f in trades.groupby(['arm', 'scope', 'year', 'policy']):
        for side in ['ALL', 'LONG', 'SHORT']:
            subset = f if side == 'ALL' else f[f.side.eq(side)]
            summaries.append(dict(arm=arm, scope=scope, year=int(year), policy=policy, side=side,
                cohort='NON_OVERLAP', **base.metrics(subset, days)))
    comparisons = compare_dates(trades, days)
    pd.DataFrame(summaries).to_csv(root/'summary.csv', index=False)
    pd.DataFrame(comparisons).to_csv(root/'comparisons.csv', index=False)
    primary = [r for r in summaries if r['policy'] == 'OU_DYNAMIC' and r['side'] == 'ALL']
    gates = {}
    for scope in p['scopes']:
        absolute = all(next((r['gate'] for r in primary if r['scope'] == scope and r['arm'] == 'PCA3_ETF'
            and r['year'] == y), False) for y in [2025, 2026])
        improvements = {ref: all(next((r['positive_ci'] for r in comparisons if r['scope'] == scope
            and r['reference'] == ref and r['year'] == y), False) for y in [2025, 2026]) for ref in ['SPY', 'SECTOR_ETF']}
        gates[scope] = dict(absolute_robust=absolute, improvements=improvements, pass_all=absolute and all(improvements.values()))
    report = dict(status='EXPLORATORY_CANDIDATE_ONLY' if any(x['pass_all'] for x in gates.values()) else 'NO_ROBUST_PCA_ETF_IMPROVEMENT',
        candidates=len(candidates), qualified=int(candidates.quality.eq('OK').sum()),
        independent_candidates=int(candidates.independent.sum()), replayed=len(trades)//2,
        primary=primary, summaries=summaries, comparisons=comparisons, gates=gates,
        coverage=candidates.groupby(['arm', 'scope', 'year', 'quality', 'independent']).size().rename('n').reset_index().to_dict('records'),
        factor_coverage=READ(root/'factor-coverage.json'),
        files={n: digest(root/n) for n in ['candidates.parquet', 'trades.parquet', 'summary.csv', 'comparisons.csv']},
        note='PCA of 11 ETF proxies, not full-stock PCA. Already viewed dates; per gross basket opportunity not annual finite-capital PnL; no dividends/actual locates/margin qualification.')
    atomic_json(root/'report.json', report)
    atomic_json(root/'progress.json', dict(status='COMPLETED', verdict=report['status']))
    LOG.info('Finished %s', report['status'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['prepare', 'build', 'summarize'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    {'prepare': prepare, 'build': build, 'summarize': summarize}[args.phase](args.output)


if __name__ == '__main__':
    main()
