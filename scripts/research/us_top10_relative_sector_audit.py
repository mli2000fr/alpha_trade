"""Frozen exploratory pre-entry rule, archived data only; no SQL or PnL."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from scripts.research.us_top10_2024_context_audit import group_metrics


def trailing_returns(prices, horizon=20):
    """Global session grid: no forward fill across missing quotes."""
    return prices / prices.shift(horizon) - 1


def peer_context(frame, minimum_peers=5):
    """Leave-one-out peers, never include the candidate in its own benchmark."""
    result = frame.copy()
    medians, breadths, counts = {}, {}, {}
    known = result.sector.notna() & result.ret20.notna()
    for _, part in result.loc[known].groupby(['date', 'sector']):
        for idx in part.index:
            peers = part.loc[part.index != idx, 'ret20']
            counts[idx] = len(peers)
            if len(peers) >= minimum_peers:
                medians[idx] = float(peers.median())
                breadths[idx] = float(peers.gt(0).mean())
    result['peer_count'] = pd.Series(counts, dtype=float)
    result['peer_ret20'] = pd.Series(medians, dtype=float)
    result['peer_breadth20'] = pd.Series(breadths, dtype=float)
    result['context_known'] = result.peer_ret20.notna() & result.peer_breadth20.notna()
    result['weakness_flag'] = (result.context_known & result.ret20.lt(result.peer_ret20)
                               & result.peer_breadth20.lt(.5))
    return result


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    root = Path('artifacts/research/us_extreme50_capture/audit-20261006-v1')
    sector_path = Path('artifacts/research/us_concentrated_replay/live-parity-preflight-current-sectors-20261007-v1/current-sector-mapping.parquet')
    champ_path = Path('artifacts/models/oracle/champions/model-factory-20261003082853-e98332/oracle_champions.json')
    paths = [root/str(y)/'panel.parquet' for y in (2022, 2023, 2024)]
    atomic_json(output/'protocol.json', dict(
        rule='ret20 < leave-one-out sector median AND sector positive-ret20 breadth < 0.5',
        lookback_sessions=20, minimum_peers=5, missing_context='UNKNOWN, never a veto',
        decision='After signal close; earliest order next session',
        years=[2023,2024], status='EXPLORATORY_ALREADY_OBSERVED_YEARS',
        sources={str(p):digest(p) for p in paths+[sector_path,champ_path]},
        training=False, sql_reads=False, sql_writes=False, pnl=False,
        threshold_search=False, current_sectors_non_pit=True,
        caveats=['Current static universe', 'Adjusted-price history not vintage certified',
                 'Daily H20 labels overlap', 'No independent confirmation period']))
    atomic_json(output/'progress.json',dict(status='RUNNING'))
    panels = pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)
    panels['date'] = pd.to_datetime(panels.date)
    if panels.duplicated(['date','symbol']).any():
        raise ValueError('Duplicate symbol/session')
    valid_price = (panels.entry_is_filled.eq(0) & panels.entry_volume.gt(0)
                   & panels.entry_adj_close.gt(0))
    prices = panels.assign(price=panels.entry_adj_close.where(valid_price)).pivot(
        index='date',columns='symbol',values='price').sort_index()
    identities = panels.pivot(index='date',columns='symbol',values='entry_instrument_id').reindex_like(prices)
    same_identity = identities.notna() & identities.eq(identities.shift(20))
    returns = trailing_returns(prices).where(same_identity).stack().rename('ret20').reset_index()
    sectors = pd.read_parquet(sector_path)
    returns = returns.merge(sectors, on='symbol', how='left', validate='many_to_one')
    # Compute exact leave-one-out context only for TOP10; peers still whole universe.
    candidates = panels.loc[panels.date.dt.year.isin([2023,2024]) & panels.ORACLE_TOP10].copy()
    contexts = []
    for day, selected in candidates.groupby('date'):
        daily = returns.loc[returns.date.eq(day)].copy().reset_index(drop=True)
        daily['selected'] = daily.symbol.isin(selected.symbol)
        for sector, group in daily.loc[daily.sector.notna()].groupby('sector'):
            for idx in group.index[group.selected]:
                peers = group.loc[group.index != idx, 'ret20'].dropna()
                contexts.append(dict(date=day, symbol=daily.loc[idx,'symbol'],
                    sector=sector, ret20=float(daily.loc[idx,'ret20']),peer_count=len(peers),
                    peer_ret20=float(peers.median()) if len(peers)>=5 else np.nan,
                    peer_breadth20=float(peers.gt(0).mean()) if len(peers)>=5 else np.nan))
    context = pd.DataFrame(contexts)
    data = candidates.merge(context,on=['date','symbol'],how='left',validate='one_to_one')
    data['context_known'] = data.peer_ret20.notna() & data.peer_breadth20.notna()
    data['weakness_flag'] = data.context_known & data.ret20.lt(data.peer_ret20) & data.peer_breadth20.lt(.5)
    data['group'] = np.where(~data.context_known,'UNKNOWN',np.where(data.weakness_flag,'FLAGGED','RETAINED'))
    data['year'] = data.date.dt.year
    data['semester'] = data.year.astype(str)+'H'+np.where(data.date.dt.month.le(6),'1','2')
    data.to_parquet(output/'candidates.parquet',index=False)
    metrics = {key:group_metrics(data,keys) for key,keys in [
        ('year',['year']),('year_group',['year','group']),('semester_group',['semester','group'])]}
    champions = json.loads(champ_path.read_text())
    starts = sorted(m['t_start'] for m in champions)
    lineage = dict(manifest_keys=sorted(set().union(*(m.keys() for m in champions))),
        champion_count=len(champions), first_start=starts[0],last_start=starts[-1],
        model_files_present=all((champ_path.parent/m['model_file']).is_file() for m in champions),
        scores_before_first_champion=int((panels.date < pd.Timestamp(starts[0])).sum()),
        selected_fold_in_future=int((pd.to_datetime(data.fold_start)>data.date).sum()),
        trained_label_availability='NOT_RECORDED_IN_CHAMPION_MANIFEST',
        exact_test_end='NOT_RECORDED_IN_CHAMPION_MANIFEST',
        code_guard='train.oracle_available_date < val_start; val.oracle_available_date < test_start',
        historical_serving_before_first_fold='Uses earliest fold: NOT safe for dates before training cutoff',
        conclusion='PARTIAL_LINEAGE_ONLY_NOT_FULL_PIT_CERTIFICATION')
    atomic_json(output/'lineage.json',lineage)
    atomic_json(output/'report.json',dict(status='COMPLETED_EXPLORATORY_NOT_PROMOTED',metrics=metrics,lineage=lineage))
    atomic_json(output/'progress.json',dict(status='COMPLETED',candidates=len(data)))
    print(json.dumps(metrics['year_group'],indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
