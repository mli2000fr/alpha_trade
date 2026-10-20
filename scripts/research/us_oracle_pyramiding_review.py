"""Descriptive attribution only; no retuning, new portfolio replay or data calls."""
import argparse
from pathlib import Path

import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_pyramiding import ARMS, READ


def review(root):
    if (root/'review.json').exists():
        raise ValueError('Immutable review')
    report = READ(root/'report.json')
    verify_hashes(root, report['files'])
    results = []
    for bps in [8, 25]:
        for arm in ARMS:
            out = root/f'{arm}-{bps}bps'
            lots = pd.read_parquet(out/'lots.parquet')
            orders = pd.read_parquet(out/'orders.parquet')
            marks = pd.read_parquet(out/'marks.parquet')
            campaigns = lots.groupby(['pair_id']).agg(symbol=('pair_id', 'first'),
                net=('net', 'sum'), exit_time=('exit_time', 'max'))
            bysymbol = lots.merge(pd.read_parquet(root/'candidates.parquet')[['pair_id', 'symbol']], on='pair_id').groupby('symbol').net.sum().sort_values(ascending=False)
            initial = lots[lots.leg.eq('INITIAL')].set_index('pair_id')
            control = pd.read_parquet(root/f'HALF_CONTROL-{bps}bps'/'lots.parquet')
            control = control[control.leg.eq('INITIAL')].set_index('pair_id')
            shared = initial.index.intersection(control.index)
            rows = []
            for year, g in campaigns.groupby(campaigns.exit_time.dt.year):
                top = g.nlargest(3, 'net')
                rows.append(dict(year=int(year), completed=len(g), winners=int(g.net.gt(0).sum()),
                    top3=[dict(pair_id=int(pid), net=float(row.net)) for pid, row in top.iterrows()],
                    total_realized=float(g.net.sum()), top3_total=float(top.net.sum()),
                    note='Descriptive realized campaign attribution, NOT annual equity contribution or remove-top3 strategy.'))
            results.append(dict(arm=arm, cost_bps=bps,
                initial_campaigns=len(initial), adds=int(lots.leg.eq('ADD').sum()),
                initial_lot_net=float(lots.loc[lots.leg.eq('INITIAL'), 'net'].sum()),
                add_lot_net=float(lots.loc[lots.leg.eq('ADD'), 'net'].sum()),
                rejection_reasons={str(k): int(v) for k, v in orders.loc[orders.status.ne('FILLED'), 'status'].value_counts().items()},
                common_initial_with_half=len(shared),
                common_initial_qty_changed_vs_half=int(initial.loc[shared, 'quantity'].ne(control.loc[shared, 'quantity']).sum()),
                final_equity=float(marks.equity.iloc[-1]),
                best5_symbol_net={str(k): float(v) for k, v in bysymbol.head(5).items()},
                worst5_symbol_net={str(k): float(v) for k, v in bysymbol.tail(5).items()},
                yearly_campaign_attribution=rows))
    atomic_json(root/'review.json', dict(status='DESCRIPTIVE_NO_TUNING', source_sha256=digest(Path(__file__)),
        report_sha256=digest(root/'report.json'), results=results,
        caveat='Different capital paths imply different subsequent initial quantities/admissions. Add-lot PnL is NOT its causal incremental portfolio contribution.'))
    print(READ(root/'review.json'))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    review(p.parse_args().output)
