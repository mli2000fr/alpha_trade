"""Second offline implementation: SVD PCA, scalar OLS/OU, basket lifecycle/costs."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

from scripts.research import us_pca_etf_residual_reversion as study
from scripts.research import us_professional_residual_reversion as base
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def independent_scalar(close, etfs, pos):
    raw = etfs[pos-251:pos+1]/etfs[pos-252:pos]-1
    sd = raw.std(axis=0, ddof=1); z = (raw-raw.mean(axis=0))/sd
    _, _, vh = np.linalg.svd(z, full_matrices=False)
    vectors = vh[:3].T; factors = z[-60:] @ vectors
    y = close[pos-59:pos+1]/close[pos-60:pos]-1
    fit = np.linalg.lstsq(np.column_stack([np.ones(60), factors]), y, rcond=None)[0]
    hedge = (vectors/sd[:, None]) @ fit[1:]
    residual = y-fit[0]-factors @ fit[1:]; x = np.cumsum(residual)
    a, b = np.linalg.lstsq(np.column_stack([np.ones(59), x[:-1]]), x[1:], rcond=None)[0]
    error = x[1:]-a-b*x[:-1]
    score = (x[-1]-a/(1-b))/np.sqrt((error@error)/57/(1-b*b))
    return hedge, b, score


def independent_exit(op, cl, z, valid, pos, side, hedge):
    sign = 1 if side == 'LONG' else -1
    w = sign*np.r_[1., -np.asarray(hedge)]/(1+np.abs(hedge).sum())
    for age in range(1, 11):
        j = pos+age
        marked = sum(w[k]*(cl[j, k]/op[pos+1, k]-1) for k in range(len(w)))
        if marked <= -.05+1e-12: return j+1, 'DAILY_RISK_NEXT_OPEN', age
        if not valid[j] or not np.isfinite(z[j]): return j+1, 'INVALID_MODEL_NEXT_OPEN', age
        if sign*z[j] >= -.5: return j+1, 'REVERSION_NEXT_OPEN', age
    return pos+11, 'TIMEOUT_NEXT_OPEN', 10


def audit(root):
    p = study.prepare(root); report = study.READ(root/'report.json'); ready = study.READ(root/'data-ready.json')
    verify_hashes(root, ready['files']); verify_hashes(root, report['files'])
    c = pd.read_parquet(root/'candidates.parquet'); t = pd.read_parquet(root/'trades.parquet')
    keys = ['symbol', 'date', 'arm', 'scope']
    assert not c.duplicated(keys).any() and not t.duplicated(keys+['policy']).any()
    assert t.independent.all() and t.quality.eq('OK').all()
    assert len(t) == 2*int((c.independent & c.quality.eq('OK')).sum())
    for _, f in c.groupby(['symbol', 'arm', 'scope']):
        blocked = pd.Timestamp.min
        for a in f.sort_values('date').itertuples():
            expected = a.date > blocked
            assert expected == a.independent
            if expected: blocked = a.last_path_date
    top = pd.read_parquet(study.sector.PARENT/'oracle-top10.parquet')
    topkeys = set(zip(top.symbol, pd.to_datetime(top.date)))
    assert all((a.symbol, a.date) in topkeys for a in c[c.scope.eq('ORACLE_H10_TOP10')].itertuples())
    days, stocks, refs, mapping = study.load_market(p)
    opref = np.column_stack([refs[s].open for s in study.REFS]); clref = np.column_stack([refs[s].close for s in study.REFS])
    etfs = np.column_stack([refs[s].close for s in study.ETFS])
    basis = dict(np.load(root/'basis.npz'))
    rechecked = study.factor_panel(refs)
    for key in basis:
        np.testing.assert_allclose(basis[key], rechecked[key], rtol=0, atol=1e-12, equal_nan=True)
    reference_reasons = [study.path_reasons(refs[s]) for s in study.REFS]
    for s in study.REFS:
        for i in range(0, len(days), 17):
            assert study.path_reasons(refs[s])[i] == base.window_reason(refs[s], i)
    tradegroups = dict(tuple(t.groupby(['symbol', 'arm'], sort=False)))
    candgroups = dict(tuple(c.groupby(['symbol', 'arm'], sort=False)))
    checks = 0; scalar = 0; prefixes = 0; quality_checks = 0
    for name in ready['files']:
        if not name.endswith('-features.parquet'): continue
        features = pd.read_parquet(root/name)
        for symbol, allf in features.groupby('symbol', sort=False):
            reserve = p['rules']['price_reserves'].get(symbol); events = p['rules']['identity_events'].get(symbol, [])
            g = base.valid_grid(stocks[symbol], days, reserve, events)
            op = np.column_stack([g.open, opref]); cl = np.column_stack([g.close, clref])
            q = study.path_reasons(g, reserve, events)
            # Parent's separate scalar checker: every independently selected entry,
            # including unknowns, plus a deterministic grid unrelated to returns.
            selected = c[c.symbol.eq(symbol) & c.independent]
            positions = sorted(set(days.get_indexer(selected.date)) | set(range(0, len(days), 17)))
            for i in positions:
                assert q[i] == base.window_reason(g, i, reserve, events)
                quality_checks += 1
            for arm, f in allf.groupby('arm', sort=False):
                f = f.set_index('date').reindex(days)
                z = f.s_score.to_numpy(float); valid = f.model_valid.to_numpy(bool)
                if arm == 'PCA3_ETF':
                    positions = np.flatnonzero(valid)
                    for pos in positions[::max(1, len(positions)//2)][:2]:
                        h, b, s = independent_scalar(g.close.to_numpy(float), etfs, int(pos))
                        np.testing.assert_allclose(f.iloc[pos][[f'h{k}' for k in range(1, 12)]].to_numpy(float), h, rtol=0, atol=1e-8)
                        assert np.isclose(s, z[pos], rtol=0, atol=1e-7)
                        assert np.isclose(b, f.ar_b.iloc[pos], rtol=0, atol=1e-8)
                        scalar += 1
                    if sum(map(ord, symbol)) % 37 == 0:
                        cut = days.searchsorted(pd.Timestamp('2025-01-02'))+1
                        shorter = study.rolling_basis(etfs[:cut], np.column_stack([refs[s].history_point_good.iloc[:cut] for s in study.ETFS]))
                        # All ETF metadata are stable in this sealed archive; assert before comparing.
                        assert all(refs[s][k].iloc[:cut].nunique() == 1 for s in study.ETFS for k in ['instrument_id', 'data_source', 'data_adjustment'])
                        pf, ph = study.pca_signals(g.close.iloc[:cut], g.history_point_good.iloc[:cut], shorter)
                        np.testing.assert_allclose(pf.s_score, z[:cut], rtol=0, atol=1e-8, equal_nan=True)
                        prefixes += 1
                for a in candgroups.get((symbol, arm), pd.DataFrame()).itertuples():
                    i = days.get_loc(a.date)
                    assert basis['ready'][i] and f.entry_eligible.iloc[i] and abs(z[i]) > 1.25
                    assert np.isclose(a.s_score, z[i], rtol=0, atol=1e-10)
                    expected = 'STOCK:'+q[i] if q[i] != 'OK' else 'OK'
                    if expected == 'OK':
                        for s, r in zip(study.REFS, reference_reasons):
                            if r[i] != 'OK': expected = s+':'+r[i]; break
                    assert a.quality == expected
                for a in tradegroups.get((symbol, arm), pd.DataFrame()).itertuples():
                    i = days.get_loc(a.entry_date); j = days.get_loc(a.exit_date); pos = days.get_loc(a.date)
                    h = np.asarray(a.hedge_betas, float)
                    np.testing.assert_allclose(h, f.iloc[pos][[f'h{k}' for k in range(12)]].to_numpy(float), rtol=0, atol=1e-12)
                    np.testing.assert_allclose(a.entry_prices, op[i], rtol=0, atol=1e-12)
                    np.testing.assert_allclose(a.exit_prices, op[j], rtol=0, atol=1e-12)
                    sign = 1 if a.side == 'LONG' else -1
                    w = sign*np.r_[1., -h]/(1+np.abs(h).sum())
                    ratios = op[j]/op[i]
                    gross = sum(float(w[k]*(ratios[k]-1)) for k in range(len(w)))
                    turnover = sum(float(abs(w[k])*(1+ratios[k])) for k in range(len(w)))
                    borrow = sum(abs(float(v)) for v in w if v < 0)*.003*max(1, (a.exit_date-a.entry_date).days)/365
                    assert np.isclose(a.gross, gross, rtol=0, atol=1e-12)
                    assert np.isclose(a.net, gross-.0008*turnover-borrow, rtol=0, atol=1e-12)
                    assert np.isclose(a.net_stress, gross-.002*turnover-borrow, rtol=0, atol=1e-12)
                    assert a.date < a.entry_date <= a.exit_date <= a.last_path_date
                    if a.policy == 'OU_DYNAMIC':
                        end, why, age = independent_exit(op, cl, z, valid, pos, a.side, h)
                        assert a.exit_date == days[end] and a.exit_reason == why and a.exit_session == age
                    else:
                        assert a.exit_date == days[pos+11] and a.exit_session == 10
                    checks += 1
            atomic_json(root/'audit-progress.json', dict(status='RUNNING', phase='SCALAR_AND_BASKETS',
                checked_trade_rows=checks, scalar_pca_checks=scalar, prefix_checks=prefixes, checked_stock_path_dates=quality_checks))
    assert checks == len(t)
    parent = pd.read_parquet(study.PARENT/'trades.parquet')
    actual = t[t.arm.ne('PCA3_ETF')]
    joined = actual.merge(parent, on=keys+['policy'], suffixes=('_new', '_parent'), validate='one_to_one')
    assert len(joined) == len(actual)
    maxerror = float((joined.net_new-joined.net_parent).abs().max())
    assert maxerror < 1e-12 and joined.exit_date_new.eq(joined.exit_date_parent).all()
    assert study.compare_dates(t, days) == report['comparisons']
    result = dict(status='PASS_EXPLORATORY_ETF_PCA_ONLY', report_sha256=digest(root/'report.json'),
        checked_trade_rows=checks, checked_candidates=len(c), scalar_pca_checks=scalar, prefix_checks=prefixes,
        checked_stock_path_dates=quality_checks, baseline_parent_trade_rows=len(joined), baseline_max_net_error=maxerror,
        gates=report['gates'], note='Same assistant second implementation, not independent human review. ETF PCA not full-stock PCA; no finite-capital/dividend/locate certification.')
    atomic_json(root/'final-audit.json', result)
    atomic_json(root/'audit-progress.json', dict(status='COMPLETED', **{k: v for k, v in result.items() if k != 'status'}))
    print(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    audit(parser.parse_args().output)
