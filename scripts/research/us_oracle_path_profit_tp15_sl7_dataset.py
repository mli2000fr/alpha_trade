"""Native isolated TP15/SL7 outcomes and J-only TOP20 inputs; offline only.

This is not a portfolio backtest. Candidate membership precedes all future
qualification. Each unit trade has a fresh native state; financing is the
standardized half-notional hypothesis frozen in the preparation protocol.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.microstructure import resolve_intrabar_exit
from backtesting.oracle_portfolio_ledger import OraclePortfolioLedger
from backtesting.simulator import BacktestEngine, BacktestDiagnostics, _RunState
from common.quantity_utils import normalize_share_quantity
from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.security_continuity import (
    DEFAULT_REGISTRY_PATH, load_security_discontinuities,
    path_crosses_known_discontinuity, split_frame_on_discontinuities)
from risk_management.models import PortfolioEntry
from scripts.research import us_oracle_path_profit_filter_tp15_sl7_protocol as plan
from scripts.research import us_oracle_path_protection_dataset as features
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
from scripts.research.us_oracle_barrier_exit_grid import parametric_protections


LOG = logging.getLogger(__name__)
PREP = Path('artifacts/research/us_oracle_path_profit_filter/20261015-tp15-sl7-protocol-v1')
read, digest, atomic_json = plan.original.read, plan.original.digest, plan.original.atomic_json
TP, SL, H = .15, .07, 20


def unit_config(start, end):
    cfg = frozen_backtest_config(start, end)
    # No regime or portfolio selection is learned in a standardized unit target.
    # Native execution costs, gap, quantity/protection and accounting stay intact.
    cfg.margin_interest_rate_annual = 0.  # separate fixed reference charge below
    if cfg.use_tiered_commission or cfg.cost_round_trip_bps or cfg.cost_multiplier != 1:
        raise ValueError('Unexpected native cost contract')
    return cfg


def resolve_path(window, *, tp=TP, sl=SL):
    """Twenty held bars + expiry open; shared native intrabar primitive."""
    window = np.asarray(window, dtype=float)
    if window.shape != (21, 4) or not np.isfinite(window).all() or (window <= 0).any():
        raise ValueError('Incomplete/invalid OHLC window')
    o, h, l, c = window.T
    if (h < np.maximum(o, c)).any() or (l > np.minimum(o, c)).any() or (h < l).any():
        raise ValueError('Inconsistent OHLC')
    fill = float(o[0]); stop, target = fill*(1-sl), fill*(1+tp)
    for k in range(H):
        if k and o[k] <= stop:
            return k, float(o[k]), 'initial_stop_gap_open', False
        if k and o[k] >= target:
            return k, float(target), 'take_profit_gap_limit', False
        result = resolve_intrabar_exit(day_high=h[k], day_low=l[k], take_profit_price=target,
            trailing_stop_price=-np.inf, initial_stop_price=stop, priority='conservative', side='buy')
        if result.triggered:
            return k, float(result.exit_price), result.exit_reason, bool(l[k] <= stop and h[k] >= target)
    return H, float(o[H]), 'expiry_open', False


def market_frames(raw, days):
    grid = raw.set_index('date').reindex(days)
    frames = {key: grid[[col]].rename(columns={col:'UNIT'}) for key, col in (
        ('opens','open'), ('close','close'), ('high','high'), ('low','low'), ('volume','volume'))}
    frames['adv'] = (frames['close']*frames['volume']).rolling(20, min_periods=20).mean().shift(1)
    return grid, frames


def native_unit(frames, j, result, cfg):
    """Book both cash-flows with the actual native engine, not a flat fee proxy.

    Skipping intermediate valuation is intentional ONLY for an isolated trade:
    its exit was already resolved by the common path primitive. No regime,
    available capital path or portfolio performance is inferred from this unit.
    """
    days = frames['close'].index
    k, price, reason, ambiguous = result
    entry_day, exit_day = days[j+1], days[j+1+k]
    previous = float(frames['close'].iloc[j, 0]); fill = float(frames['opens'].iloc[j+1, 0])
    qty = normalize_share_quantity(1600./previous)
    engine = BacktestEngine(cfg)
    state = _RunState(settled_cash=4000., peak_equity=4000.)
    diagnostics = BacktestDiagnostics()
    row = dict(symbol='UNIT', side='buy', score=.9, signal_date=days[j], trade_date=days[j],
        execution_date=entry_day, filled_qty=qty, fill_price=fill, target_weight=.4,
        replay_take_profit_price=fill*(1+TP), replay_initial_stop_price=fill*(1-SL),
        replay_trailing_stop_pct=.2, watcher_transition_state='pending',
        watcher_transition_effective_date=pd.NaT, best_horizon=H)
    opening_marks = frames['close'].loc[:entry_day].copy()
    opening_marks.loc[entry_day] = frames['opens'].loc[entry_day]
    engine._try_open_entries(state=state, candidate_rows=[pd.Series(row)],
        open_df=frames['opens'].loc[:entry_day], high_df=frames['opens'].loc[:entry_day],
        low_df=frames['opens'].loc[:entry_day], close=opening_marks, trade_day=entry_day,
        day_idx=j+1, trading_days=days, adv_usd_df=frames['adv'].loc[:entry_day],
        sector_map={'UNIT':'Reference'}, current_equity=4000., drawdown_allocation_scale=1., diagnostics=diagnostics)
    if set(state.positions) != {'UNIT'}:
        raise ValueError(f'Native unit entry rejected unexpectedly: {state.trade_events}')
    p = state.positions['UNIT']
    if not np.isclose(p.quantity, qty, rtol=0, atol=1e-8):
        raise ValueError('Native reference order resized')
    p.explicit_exit_date, p.explicit_exit_price, p.explicit_exit_reason = exit_day, price, reason
    p.explicit_exit_intent_role, p.explicit_oco_sibling_canceled = reason, True
    engine._try_close_positions(state=state, close=frames['close'].loc[:exit_day],
        high=frames['high'].loc[:exit_day], low=frames['low'].loc[:exit_day],
        trade_day=exit_day, day_idx=j+1+k, trading_days=days,
        adv_usd_df=frames['adv'].loc[:exit_day], rng=None, diagnostics=diagnostics, current_equity=4000.)
    if state.positions or len(state.closed_trades) != 1:
        raise ValueError('Native reference trade not fully closed')
    trade = state.closed_trades[0]
    if not np.isclose(4000+trade['pnl'], state.settled_cash+state.unsettled_cash, atol=1e-7):
        raise ValueError('Native unit cash reconciliation failed')
    notional = trade['quantity']*trade['entry_price']
    financing = .5*notional*.065*(exit_day-entry_day).days/360.
    net = (trade['pnl']-financing)/notional
    return dict(entry_date=entry_day, exit_date=exit_day, entry_price=trade['entry_price'],
        exit_price=price, exit_reason=reason, intrabar_ambiguous=ambiguous, quantity=trade['quantity'],
        entry_notional=notional, entry_outlay=trade['entry_cost'], exit_proceeds=trade['proceeds'],
        native_pnl=trade['pnl'], reference_financing=financing, net_return=net, label=float(net>0),
        holding_sessions=k+1 if k<H else H)


class ReferenceLedger(OraclePortfolioLedger):
    def _build_entry_protections(self, phase3, *, execution_config):
        base = super()._build_entry_protections(phase3, execution_config=execution_config)
        return parametric_protections(base, tp_pct=TP, sl_pct=SL)


def full_native_reference(frames, j, cfg):
    """Independent full daily phase3/4/5/7 ledger for parity probes only."""
    ledger = ReferenceLedger(cfg, **{k:v for k,v in frames.items() if k!='adv'}, sector_map={'UNIT':'Reference'})
    days = ledger.days; fill = float(frames['close'].iloc[j,0]); qty = normalize_share_quantity(1600/fill)
    approved = PortfolioEntry(symbol='UNIT', sector='Reference', entry_price=fill,
        score_used=.9, score_source='frozen_oracle_rank', atr_20=fill*.03,
        proposed_shares=qty, approved_shares=qty, target_notional=qty*fill,
        target_weight=.4, decision='APPROVED', decision_reason='isolated reference',
        score_snapshot_date=days[j].date(), price_asof_date=days[j].date(), trade_date=days[j].date())
    for i in range(j+1,j+22):
        day = days[i]; ledger.begin_day(day)
        if i==j+1:
            _, opened = ledger.execute_approved([approved], execution_config=cfg.exec_config)
            if opened != ['UNIT']:
                raise ValueError('Full native probe refused reference entry')
        if i==j+21 and ledger.state.positions:
            ledger.close_resolved([dict(symbol='UNIT', exit_date=day,
                exit_price=float(frames['opens'].at[day,'UNIT']), exit_reason='expiry_open')], phase='open')
        ledger.apply_observed_protections(phase='open', take_profit_enabled=True, trailing_enabled=False)
        ledger.apply_observed_protections(phase='intraday', take_profit_enabled=True, trailing_enabled=False)
        ledger.mark_close(); ledger.finish_day()
        if not ledger.state.positions:
            break
    if ledger.state.positions or len(ledger.state.closed_trades)!=1:
        raise ValueError('Full native parity trade not closed')
    return ledger.state.closed_trades[0]


def assert_native_parity(frames, j, cfg):
    result = resolve_path(np.column_stack([frames[c].iloc[j+1:j+22,0] for c in ('opens','high','low','close')]))
    unit = native_unit(frames,j,result,cfg); full = full_native_reference(frames,j,cfg)
    for key in ('entry_date','exit_date','exit_reason'):
        if unit[key]!=full[key]:
            raise ValueError(f'Native unit/full chronology mismatch: {key}: {unit[key]} / {full[key]}')
    for key, other in (('quantity','quantity'),('entry_price','entry_price'),('exit_price','exit_price'),
                       ('entry_outlay','entry_cost'),('exit_proceeds','proceeds'),('native_pnl','pnl')):
        if not np.isclose(unit[key],full[other],rtol=1e-9,atol=1e-6):
            raise ValueError(f'Native unit/full cash mismatch {key}: {unit[key]} / {full[other]}')
    return dict(entry_date=str(unit['entry_date'].date()), exit_date=str(unit['exit_date'].date()),
        exit_reason=unit['exit_reason'], pnl=unit['native_pnl'], native_parity=True)


def qualify_path(grid, j, days, symbol, registry):
    if j+22>=len(days): return 'IMMATURE_J22'
    path=grid.iloc[j:j+22]
    numeric=path[['open','high','low','close','volume']].apply(pd.to_numeric,errors='coerce')
    if len(path)!=22 or not np.isfinite(numeric).all().all() or not numeric.gt(0).all().all():
        return 'MISSING_NONPOSITIVE_PATH'
    if not path.is_filled.eq(0).all(): return 'FILLED_PATH'
    if (numeric.high<numeric[['open','close']].max(axis=1)).any() or (numeric.low>numeric[['open','close']].min(axis=1)).any():
        return 'INCONSISTENT_OHLC_PATH'
    for col in ('instrument_id','data_source','data_adjustment'):
        values=path[col].astype('string')
        if values.isna().any() or values.str.upper().isin(['','UNKNOWN']).any() or values.nunique()!=1:
            return 'UNKNOWN_CHANGED_'+col.upper()
    if not pd.to_numeric(path.instrument_id,errors='coerce').gt(0).all(): return 'INVALID_IDENTITY'
    ratio=numeric.close/numeric.close.shift()
    if ratio.ge(20).any() or ratio.le(.05).any(): return 'UNEXPLAINED_20X_BREAK'
    if path_crosses_known_discontinuity(symbol,days[j],days[j+21],registry): return 'KNOWN_IDENTITY_BREAK'
    if abs(float(path.open.iloc[1])/float(path.close.iloc[0])-1)>.03: return 'NO_FILL_ENTRY_GAP'
    return ''


def freeze(output):
    marker=output/'protocol.json'
    if marker.exists():
        p=read(marker)
        for name, expected in p['sources'].items(): plan.original.require_hash(name,expected)
        return p
    plan.prepare(PREP)
    prepared=read(PREP/'protocol.json'); parent=read(PREP/'manifest.json')
    sources=dict(parent['sources'])
    for path in [PREP/'report.json',PREP/'protocol.json',PREP/'manifest.json',
                 Path(__file__),Path('tests/test_us_oracle_path_profit_tp15_sl7_dataset.py'),DEFAULT_REGISTRY_PATH,
                 Path('backtesting/microstructure.py'),Path('backtesting/execution_replay.py'),
                 Path('backtesting/execution_lifecycle_replay.py'),Path('backtesting/protection_watcher_replay.py'),
                 Path('backtesting/exit_lifecycle_replay.py'),Path('common/quantity_utils.py'),
                 plan.original.DATASET/'benchmark-history.parquet']:
        sources[str(path)]=digest(path)
    history=read(plan.original.HISTORY/'protocol.json')
    encoded={s:[asdict(e) for e in events] for s,events in load_security_discontinuities().items()}
    if json.loads(json.dumps(encoded,default=str))!=history['security_discontinuities']:
        raise ValueError('Current security discontinuities differ from frozen Oracle')
    cfg=unit_config('2018-07-05','2023-12-29')
    p=dict(specification=prepared,sources=sources,preparation=str(PREP),
        original_population=str(plan.PARENT/'historical-top20.parquet'),
        input_price_chunks=read(plan.PARENT/'manifest.json')['price_chunks'],
        price_basis='archived split-only OHLC; no extra dividend adjustment of target paths',
        feature_price_basis='existing adj_close/close generator; current vendor vintage reserved',
        native_cost_model=cfg.trading_cost_model.to_dict() if cfg.trading_cost_model else BacktestEngine(cfg)._cost_model.to_dict(),
        native_microstructure=asdict(cfg.microstructure),
        native_cost_multiplier=cfg.cost_multiplier,native_tiered_commission=cfg.use_tiered_commission,
        target_financing='half entry notional * .065 * calendar nights /360; separate from native transaction cash flows',
        stage='DATASET_ONLY_NO_FIT',sql_reads=False,sql_writes=False,API_calls=0,broker_calls=0)
    atomic_json(marker,p);return p


def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    p=freeze(output)
    if (output/'report.json').exists():
        report=read(output/'report.json')
        for name,expected in report['files'].items():plan.original.require_hash(output/name,expected)
        return report
    pool=pd.read_parquet(p['original_population'])
    benchmark=pd.read_parquet(plan.original.DATASET/'benchmark-history.parquet').set_index('date').benchmark_close
    days=nyse_sessions('2016-01-01','2023-12-29')
    registry=load_security_discontinuities();cfg=unit_config(days[0],days[-1])
    symbols=sorted(pool.symbol.unique()); parts=[]
    for i,item in enumerate(p['input_price_chunks']):
        frames=pd.read_parquet(item['path'],filters=[('symbol','in',symbols)])
        parts.append(frames)
        atomic_json(output/'progress.json',dict(status='READING_PRICES',completed=i+1,total=72))
    prices=pd.concat(parts,ignore_index=True)
    if prices.duplicated(['date','symbol']).any() or not prices.data_adjustment.eq('split').all():
        raise ValueError('Ambiguous/unsplit historical price inputs')
    files=[];canaries=[];parities=[];complete=0
    for i,(symbol,group) in enumerate(pool.groupby('symbol',sort=True)):
        chunk=output/f'symbol-{symbol}';chunk.mkdir(exist_ok=True);done=chunk/'done.json'
        if done.exists():
            saved=read(done)
            for name,expected in saved['files'].items():plan.original.require_hash(chunk/name,expected)
            complete+=saved['rows'];canaries.append(saved['canary']);parities+=saved['parities'];files.append(chunk/'dataset.parquet')
            continue
        raw=prices[prices.symbol.eq(symbol)].sort_values('date').reset_index(drop=True)
        grid,frames=market_frames(raw,days)
        calculated=[];qualities=[];segments=list(split_frame_on_discontinuities(raw,symbol,registry))
        for segment in segments:
            calculated.append(features.decision_features(segment,benchmark))
            reindexed=segment.set_index('date').reindex(days[(days>=segment.date.min())&(days<=segment.date.max())])
            qualities.append(features.j_history_quality(reindexed,benchmark,days))
        f=pd.concat(calculated);q=pd.concat(qualities)
        if not f.index.is_unique or not q.index.is_unique:raise ValueError('Duplicate J history segment')
        joined=group.merge(f[features.STOCK+features.MARKET],left_on='date',right_index=True,how='left',validate='one_to_one')
        good=joined.date.map(q).fillna(False)&np.isfinite(joined[features.STOCK+features.MARKET]).all(axis=1)
        joined['J_qualified']=good
        prefix_dates=sorted(set(group.date.iloc[[0,len(group)//2,-1]]))
        for day in prefix_dates:
            segment=next(s for s in segments if s.date.min()<=day<=s.date.max())
            prefix=features.decision_features(segment[segment.date.le(day)],benchmark.loc[:day])
            pd.testing.assert_series_equal(f.loc[day],prefix.loc[day],check_exact=True)
        probe=[];records=[]
        for row in joined.itertuples(index=False):
            record=dict(date=row.date,symbol=symbol,score=row.score,oracle_rank=row.oracle_rank,fold_start=row.fold_start,
                **{name:getattr(row,name) for name in features.STOCK+features.MARKET},
                J_qualified=row.J_qualified,reason='',label=np.nan,net_return=np.nan,
                label_available=pd.NaT,split='UNKNOWN_LABEL')
            j=days.get_indexer([row.date])[0]
            if j<0:raise ValueError('Candidate outside trading calendar')
            record['label_available']=days[j+22] if j+22<len(days) else pd.NaT
            reason='J_HISTORY_OR_FEATURES_UNQUALIFIED' if not row.J_qualified else qualify_path(grid,j,days,symbol,registry)
            if not reason:
                path=grid[['open','high','low','close']].iloc[j+1:j+22].to_numpy(float)
                result=resolve_path(path)
                record.update(native_unit(frames,j,result,cfg))
                record['split']=plan.original.split_for_label(row.date,record['label_available'],p['specification'])
                if row.date in prefix_dates and len(parities)+len(probe)<24:
                    probe.append(dict(symbol=symbol,**assert_native_parity(frames,j,cfg)))
            record['reason']=reason;records.append(record)
        frame=pd.DataFrame(records)
        if len(frame)!=len(group) or frame.duplicated(['date','symbol']).any():raise ValueError('Lost candidate keys')
        frame.to_parquet(chunk/'dataset.parquet',index=False)
        canary=dict(symbol=symbol,prefix_exact=True,prefix_dates=[str(d.date()) for d in prefix_dates],rows=len(frame))
        atomic_json(done,dict(rows=len(frame),canary=canary,parities=probe,
            files={'dataset.parquet':digest(chunk/'dataset.parquet')}))
        files.append(chunk/'dataset.parquet');canaries.append(canary);parities+=probe;complete+=len(frame)
        atomic_json(output/'progress.json',dict(status='BUILDING_NATIVE_LABELS',symbol=symbol,
            completed_symbols=i+1,total_symbols=len(symbols),completed_candidates=complete,total_candidates=len(pool)))
        LOG.info('%s/%s symbols; %s/%s candidates; %s',i+1,len(symbols),complete,len(pool),symbol)
    dataset=pd.concat([pd.read_parquet(path) for path in files],ignore_index=True)
    if len(dataset)!=len(pool) or dataset.duplicated(['date','symbol']).any():raise ValueError('Dataset population lost')
    dataset.to_parquet(output/'dataset.parquet',index=False)
    atomic_json(output/'prefix-checks.json',canaries);atomic_json(output/'native-parity.json',parities)
    gates=p['specification']['gates_before_external_replay'];splits=[]
    for name,rule in p['specification']['splits'].items():
        if name not in ('fit','validation','control'):continue
        original=dataset[dataset.date.between(rule['decision_start'],rule['decision_end'])]
        qualified=original[original.reason.eq('') & original.split.eq(name.upper())]
        finite={c:float(np.isfinite(original[c]).mean()) for c in p['specification']['features']}
        counts=qualified.label.value_counts().to_dict()
        min_rows=gates['minimum_fit_rows'] if name=='fit' else gates['minimum_validation_rows']
        min_dates=gates['minimum_fit_dates'] if name=='fit' else gates['minimum_validation_dates']
        checks=dict(rows=len(qualified)>=min_rows,dates=qualified.date.nunique()>=min_dates,
            both_classes=all(counts.get(float(k),0)>=gates['minimum_examples_each_class_per_split'] for k in (0,1)),
            label_coverage=float(original.label.notna().mean())>=gates['minimum_original_candidate_label_coverage'],
            finite_coverage=min(finite.values())>=gates['minimum_features_coverage_before_J_rejections'])
        # A shorter preregistered 2023 control is not required to equal a full validation year.
        splits.append(dict(name=name.upper(),original_rows=len(original),rows=len(qualified),dates=int(qualified.date.nunique()),
            labels_available_max=str(qualified.label_available.max()),class_counts={str(k):int(v) for k,v in counts.items()},
            known_label_coverage=float(original.label.notna().mean()),feature_coverage=finite,checks=checks,
            dataset_ready=all(checks.values())))
    if len(parities)!=24:raise ValueError('Insufficient real native parity probes')
    ready=all(s['dataset_ready'] for s in splits)
    for name,expected in p['sources'].items():plan.original.require_hash(name,expected)
    report=dict(status='COMPLETED_DATASET_QUALIFICATION',verdict='READY_FOR_SINGLE_FIT' if ready else 'NO_GO_DATASET_GATES',
        candidates=len(dataset),J_qualified=int(dataset.J_qualified.sum()),known_labels=int(dataset.label.notna().sum()),
        exclusions=dataset[dataset.reason.ne('')].reason.value_counts().to_dict(),
        purges=dataset[dataset.split.str.startswith('PURGED')].split.value_counts().to_dict(),
        splits=splits,native_full_parity_probes=len(parities),prefix_symbols=len(canaries),
        model_fits=0,portfolio_runs=0,sql_writes=False,API_calls=0,broker_calls=0,
        files={str(path.relative_to(output)):digest(path) for path in output.rglob('*')
               if path.suffix in ('.parquet','.json') and path.name not in ('report.json','progress.json')})
    atomic_json(output/'report.json',report);atomic_json(output/'progress.json',dict(status=report['status'],verdict=report['verdict']))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    import requests
    def forbidden(*args,**kwargs):raise RuntimeError('Network forbidden in native TP15SL7 research')
    requests.Session.request=forbidden
    with plan.original.exclusive_run(args.output):
        try:print(json.dumps(run(args.output),default=str))
        except Exception as exc:
            atomic_json(args.output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise
