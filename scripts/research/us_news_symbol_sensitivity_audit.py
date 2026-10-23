"""Separate deterministic arithmetic/clock review; not independent human review."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm

from scripts.research import us_news_symbol_sensitivity as research


def audit(output):
    research.check(output)
    report = json.loads((output/'report.json').read_text(encoding='utf-8'))
    for name, expected in report['output_hashes'].items():
        assert research.digest(output/name) == expected, name
    schedule = research.schedule_frame()
    raw = pd.read_parquet(research.SOURCE/'bars.parquet')
    raw['date'] = pd.to_datetime(raw.date)
    by_symbol = {symbol: g.set_index('date') for symbol, g in raw.groupby('symbol')}
    events = pd.read_parquet(output/'news-events.parquet')
    assert (events.entry_time > events.last_publication+pd.Timedelta(minutes=5)).all()
    assert events[['symbol','entry_idx']].duplicated().sum() == 0
    assert events.articles.sum() == report['news_quality']['timed_deduped_rows']
    scalar_checks = 0
    selection_checks = 0
    extreme = []
    for horizon in research.HORIZONS:
        panel = pd.read_parquet(output/f'events-H{horizon}.parquet')
        members = pd.read_csv(output/f'train-memberships-H{horizon}.csv')
        assert (panel.exit_idx == panel.entry_idx+horizon-1).all()
        # Reconstruct spacing on all observations, without calling research.spaced.
        indices = []
        until = {}
        for symbol, rows in panel.groupby('symbol'):
            last = -1
            for row in rows.sort_values('entry_idx').itertuples():
                if row.entry_idx > last:
                    indices.append(row.Index)
                    last = row.exit_idx
        episodes = panel.loc[indices]
        assert len(episodes) == report['horizons'][str(horizon)]['nonoverlap_events']
        train = episodes[(episodes.year == 2025) & episodes.exit_date.lt('2026-01-01') &
                         episodes.tone.isin(research.TONES) & episodes.signed_excess_spy_pct.notna()]
        baselines = {tone: (g.signed_excess_spy_pct.gt(0).mean(),
                           g.signed_after_assumed_16bps_pct.mean()) for tone, g in train.groupby('tone')}
        grouped = {(s,t):g for (s,t),g in train.groupby(['symbol','tone'])}
        assert len(members) == len(grouped)
        recomputed_p = []
        min_n, min_half, min_months = research.GATES[horizon]
        for row in members.itertuples():
            g = grouped[row.symbol,row.tone]
            n = len(g)
            wins = int((g.signed_excess_spy_pct > 0).sum())
            base_hit, base_net = baselines[row.tone]
            z = norm.ppf(.95)
            denominator = 1 + z*z/n
            centre = (wins/n + z*z/(2*n))/denominator
            margin = z*np.sqrt((wins/n)*(1-wins/n)/n + z*z/(4*n*n))/denominator
            lower = centre-margin
            a = g[g.entry_date.dt.month <= 6]
            b = g[g.entry_date.dt.month > 6]
            enough = n >= min_n and min(len(a),len(b)) >= min_half and g.entry_date.dt.month.nunique() >= min_months
            stable = all(len(p)>0 and p.signed_after_assumed_16bps_pct.mean()>0 and
                         p.signed_excess_spy_pct.mean()>0 for p in (a,b))
            chosen = bool(enough and stable and lower>max(.5,base_hit) and
                          g.signed_after_assumed_16bps_pct.mean()>max(0,base_net))
            assert row.n_train == n and row.selected_pre_bh == chosen
            assert abs(row.wilson90_lower_pct-100*lower) < 1e-9
            p = binomtest(wins,n,p=max(.5,base_hit),alternative='greater').pvalue
            recomputed_p.append(p)
            assert abs(p-row.p_value)<1e-12
            assert g.exit_date.max() < pd.Timestamp('2026-01-01')
            selection_checks += 1
        # Independent BH step-up calculation, including underpowered cells.
        order = np.argsort(recomputed_p)
        q = np.ones(len(order))
        running = 1.
        for rank in range(len(order),0,-1):
            i = order[rank-1]
            running = min(running,recomputed_p[i]*len(order)/rank)
            q[i] = running
        np.testing.assert_allclose(q,members.q_bh,atol=1e-12)
        assert np.array_equal(members.selected_bh, members.selected_pre_bh & (q<=.05))
        # Deterministic sample plus every large terminal return; never drop tails.
        sampled = panel.sample(min(250,len(panel)),random_state=820+horizon)
        tails = panel[panel.return_pct.abs()>50]
        if len(tails):
            extreme.append(tails.assign(horizon=horizon)[['symbol','entry_date','exit_date','return_pct','horizon']])
        chosen_rows = pd.concat([sampled,tails]).drop_duplicates(['symbol','entry_idx'])
        for row in chosen_rows.itertuples():
            if not row.qualified_path:
                continue
            dates = schedule.day.iloc[row.entry_idx:row.exit_idx+1]
            prices = by_symbol[row.symbol].reindex(dates)
            assert prices[['open','close']].notna().all().all()
            actual = (float(prices.close.iloc[-1])/float(prices.open.iloc[0])-1)*100
            assert abs(actual-row.return_pct)<1e-9
            spy = by_symbol['SPY'].reindex(dates)
            if pd.notna(row.excess_spy_pct):
                actual_spy = (float(spy.close.iloc[-1])/float(spy.open.iloc[0])-1)*100
                assert abs((actual-actual_spy)-row.excess_spy_pct)<1e-9
            assert abs(row.signed_after_assumed_16bps_pct-(row.sign*actual-.16))<1e-9
            scalar_checks += 1
    reserve = pd.concat(extreme,ignore_index=True) if extreme else pd.DataFrame(
        columns=['symbol','entry_date','exit_date','return_pct','horizon'])
    reserve.to_csv(output/'extreme-returns-reserve.csv',index=False)
    result = dict(status='PASS_CLOCK_SPACING_SELECTION_MULTIPLICITY_ARITHMETIC',
        event_groups=len(events),scalar_price_checks=scalar_checks,selection_cells=selection_checks,
        extreme_rows_reserved=len(reserve),extreme_symbols=sorted(reserve.symbol.unique()),
        independent_human_review=False,full_identity_ost_certification=False,
        no_pit_or_profitability_promotion=True,report_sha256=research.digest(output/'report.json'),
        auditor_sha256=research.digest(Path(__file__)))
    research.save(output/'final-audit.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=research.DEFAULT_OUTPUT)
    audit(parser.parse_args().output_dir)
