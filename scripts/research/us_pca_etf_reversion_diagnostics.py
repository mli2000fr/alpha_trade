"""Post-replay coverage explanation only; no parameter change or new strategy."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

from scripts.research import us_pca_etf_residual_reversion as study
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def run(root):
    if (root/'coverage-explanation.json').exists():
        raise ValueError('Immutable diagnosis')
    p = study.prepare(root); ready = study.READ(root/'data-ready.json')
    verify_hashes(root, ready['files'])
    days, stocks, refs, mapping = study.load_market(p)
    factor_ready = dict(np.load(root/'basis.npz'))['ready']
    top = pd.read_parquet(study.sector.PARENT/'oracle-top10.parquet')
    topkeys = set(zip(top.symbol, pd.to_datetime(top.date)))
    candidates = pd.read_parquet(root/'candidates.parquet')
    candidate_groups = dict(tuple(candidates[candidates.arm.eq('PCA3_ETF')].groupby(['scope', 'year'])))
    totals = {}; ratios = {}
    for name in ready['files']:
        if not name.endswith('-features.parquet'): continue
        chunk = pd.read_parquet(root/name)
        for symbol, f in chunk[chunk.arm.eq('PCA3_ETF')].groupby('symbol', sort=False):
            f = f.set_index('date').reindex(days)
            g = study.base.valid_grid(stocks[symbol], days, p['rules']['price_reserves'].get(symbol), p['rules']['identity_events'].get(symbol, []))
            common = (study.sector.supported_history(g) & study.sector.supported_history(refs['SPY'])
                & study.sector.supported_history(refs[str(mapping.loc[symbol, 'hedge_etf'])])
                & factor_ready & g.liquidity_pass).to_numpy(bool)
            ar_ok = (np.isfinite(f[['beta', 'ar_b', 'equilibrium_sigma', 's_score', 'tau_sessions']]).all(axis=1)
                & f.ar_b.gt(0) & f.ar_b.lt(np.exp(-1/30)) & f.equilibrium_sigma.gt(1e-8)).to_numpy(bool)
            hedge_ok = (f.beta.gt(0) & f.beta.le(3)).to_numpy(bool)
            accepted = ar_ok & hedge_ok
            for scope in p['scopes']:
                membership = np.ones(len(days), bool) if scope == 'FULL_TRADABLE' else np.array([(symbol, d) in topkeys for d in days])
                for year in p['rules']['years']:
                    selected = (days.year == year) & (days <= p['rules']['signal_end']) & membership
                    common_selected = selected & common
                    counts = dict(ranked_symbol_dates=int(selected.sum()), common_input=int(common_selected.sum()),
                        invalid_ou_or_numeric=int((common_selected & ~ar_ok).sum()),
                        valid_ou_but_hedge_cap_fail=int((common_selected & ar_ok & ~hedge_ok).sum()),
                        accepted_model=int((common_selected & accepted).sum()),
                        entry_signals=int((common_selected & accepted & f.s_score.abs().gt(1.25).to_numpy()).sum()))
                    counts['accepted_without_entry'] = counts['accepted_model']-counts['entry_signals']
                    key = (scope, int(year))
                    target = totals.setdefault(key, {k: 0 for k in counts})
                    for k, v in counts.items(): target[k] += v
                    ratios.setdefault(key, []).extend(f.beta.to_numpy(float)[common_selected & np.isfinite(f.beta.to_numpy(float))].tolist())
    rows = []
    for (scope, year), counts in sorted(totals.items()):
        f = candidate_groups.get((scope, year), pd.DataFrame())
        assert counts['entry_signals'] == len(f)
        assert counts['common_input'] == counts['invalid_ou_or_numeric']+counts['valid_ou_but_hedge_cap_fail']+counts['accepted_model']
        rows.append(dict(scope=scope, year=year, **counts,
            independent_candidates=int(f.independent.sum()) if len(f) else 0,
            independent_qualified=int((f.independent & f.quality.eq('OK')).sum()) if len(f) else 0,
            hedge_l1_median=float(np.median(ratios[(scope, year)])) if ratios[(scope, year)] else None))
    pd.DataFrame(rows).to_csv(root/'coverage-explanation.csv', index=False)
    result = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        purpose='Post-replay explanation of coverage, NOT a new signal, chosen threshold or alternative PCA.',
        source_sha256=digest(Path(__file__)), report_sha256=digest(root/'report.json'),
        data_ready_sha256=digest(root/'data-ready.json'), rows=rows,
        files={'coverage-explanation.csv': digest(root/'coverage-explanation.csv')})
    atomic_json(root/'coverage-explanation.json', result)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
