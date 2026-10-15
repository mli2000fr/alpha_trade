"""Offline frozen-entry news-exit counterfactual. No SQL/API, fit or live changes.

Current sentiment versions are NOT immutable historical PIT. Publication-timed
results are exploratory; a separate updated-at guard is only a diagnostic.
"""
import argparse
from dataclasses import asdict
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.simulator import BacktestEngine
from common.market_calendar import get_market_calendar
from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

SOURCE = Path('artifacts/research/us_oracle_path_economic/20261013-v1')
NEWS = Path('artifacts/research/us_news_same_day/audit-202510-20261011-v1')
LOG = logging.getLogger(__name__)
MODES = ('PUBLICATION_RETROSPECTIVE', 'UPDATED_AT_GUARDED_DIAGNOSTIC')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


class NewsSignals:
    """One close decision per session; late/weekend news belong to next close."""
    def __init__(self, news, sessions, mode):
        if mode not in MODES:
            raise ValueError('Unknown availability mode')
        sessions = [s for s in sessions if s.is_open]
        self.opens = {pd.Timestamp(s.session_date):pd.Timestamp(s.open_at_utc) for s in sessions}
        days = pd.DatetimeIndex([s.session_date for s in sessions])
        closes = pd.DatetimeIndex([s.close_at_utc for s in sessions])
        frame = news.copy()
        frame['published'] = pd.to_datetime(frame.published_at_utc, utc=True)
        frame['available'] = pd.to_datetime(frame.available_at, utc=True)
        ambiguous = frame.published.dt.hour.eq(0) & frame.published.dt.minute.eq(0) & frame.published.dt.second.eq(0)
        self.ambiguous_excluded = int(ambiguous.sum())
        frame = frame[frame.published.notna() & ~ambiguous].copy()
        timestamp = frame.published
        if mode == MODES[1]:
            frame = frame[frame.available.notna()].copy()
            timestamp = frame[['published','available']].max(axis=1)
        # Exactly at close is not known BEFORE close: consume on a later day.
        positions = closes.searchsorted(pd.DatetimeIndex(timestamp), side='right')
        mask = positions < len(days)
        frame = frame.loc[mask].copy()
        positions = positions[mask]
        frame['decision_date'] = days.take(positions).to_numpy()
        self.groups = {key:part for key,part in frame.groupby(['decision_date','symbol'])}

    def get(self, day, symbol, entry_date):
        part = self.groups.get((pd.Timestamp(day), symbol))
        if part is None:
            return dict(label='NONE', articles=0, last_published=None, last_available=None)
        part = part[part.published.ge(self.opens[pd.Timestamp(entry_date)])]
        if part.empty:
            return dict(label='NONE', articles=0, last_published=None, last_available=None)
        positive = pd.to_numeric(part.positive_score, errors='coerce')
        negative = pd.to_numeric(part.negative_score, errors='coerce')
        valid = positive.between(0,1).all() and negative.between(0,1).all()
        pos = valid and positive.gt(.9).all()
        neg = valid and negative.gt(.9).all()
        if pos and neg:
            raise ValueError('Contradictory strong positive/negative scores')
        return dict(label='POSITIVE' if pos else 'NEGATIVE' if neg else 'OTHER', articles=len(part),
            last_published=str(part.published.max()), last_available=str(part.available.max()))


def resolve_exit(trade, decision_day, next_day, next_open):
    """Never override stops already consumed, scheduled expiry or opening gaps."""
    if not pd.Timestamp(trade.entry_date) <= decision_day < pd.Timestamp(trade.exit_date):
        raise ValueError('News decision must be on a surviving position')
    if not np.isfinite(next_open) or next_open <= 0 or next_day <= decision_day:
        raise ValueError('Invalid next-open execution')
    exit_day = pd.Timestamp(trade.exit_date)
    if next_day > exit_day:
        raise ValueError('Cannot resurrect a closed trade')
    gap = next_open <= trade.replay_initial_stop_price or next_open >= trade.replay_take_profit_price
    due = next_day == exit_day and (trade.exit_reason == 'expiry_open' or trade.exit_reason.startswith('regime_'))
    if gap or due:
        if next_day != exit_day:
            raise ValueError('Archived gap protection not consumed at the open')
        return dict(date=exit_day, price=float(trade.exit_price), reason=str(trade.exit_reason), priority='NATIVE_OPEN_FIRST')
    return dict(date=next_day, price=float(next_open), reason='news_negative_next_open', priority='NEWS_AT_OPEN_BEFORE_INTRADAY')


def exit_proceeds(engine, trade, price, adv_usd):
    """Same native flat commissions/slippage/spread as archived LONG ledger."""
    cfg = engine.config
    if cfg.use_tiered_commission or cfg.cost_round_trip_bps or cfg.cost_multiplier != 1:
        raise ValueError('Unqualified alternative cost contract')
    if not np.isfinite(adv_usd) or adv_usd <= 0:
        raise ValueError('Missing causal ADV for exit costs')
    notional = float(trade.quantity)*price
    extra = cfg.microstructure.slippage.compute_bps(notional, adv_usd)/10000.
    fee = engine._effective_fees_pct + extra + engine._spread_fallback_bps/20000.
    return float(notional*(1-fee))


def frozen_curve(trades, daily, price_groups, overrides):
    """Exact archived entries; freed capital unused, no new sizing/risk decisions."""
    if not trades.side.eq('buy').all() or trades.groupby(['symbol','entry_date']).size().max() != 1:
        raise ValueError('Paired replay currently requires complete one-leg LONG positions')
    cash, rows, minimum_cash = 4000., [], 4000.
    holdings = {}
    opening = {day:part for day,part in trades.groupby('entry_date')}
    exits = {}
    for index, row in trades.iterrows():
        override = overrides.get(index, {})
        day = pd.Timestamp(override.get('date', row.exit_date))
        exits.setdefault(day, []).append((index, float(override.get('proceeds', row.proceeds))))
    # Baseline does open exits before entries; intraday exits after entries.
    for day in pd.to_datetime(daily.date):
        today = exits.get(day, [])
        open_exits, intra_exits = [], []
        for index, proceeds in today:
            row = trades.loc[index]
            early = index in overrides and overrides[index]['reason'] == 'news_negative_next_open'
            reason = overrides.get(index, {}).get('reason', row.exit_reason)
            at_open = early or reason in ('expiry_open','initial_stop_gap_open','take_profit_gap_limit') or reason.startswith('regime_')
            (open_exits if at_open and day != pd.Timestamp(row.entry_date) else intra_exits).append((index,proceeds))
        for index, proceeds in open_exits:
            cash += proceeds
            holdings.pop(index)
        if day in opening:
            for index, row in opening[day].iterrows():
                cash -= float(row.entry_cost)
                holdings[index] = (row.symbol, float(row.quantity))
            minimum_cash = min(minimum_cash, cash)
        for index, proceeds in intra_exits:
            cash += proceeds
            holdings.pop(index)
        mark = sum(q*float(price_groups[s].at[day,'close']) for s,q in holdings.values())
        rows.append(dict(date=day, equity=cash+mark, cash=cash, gross_notional=mark, positions=len(holdings)))
    if holdings:
        raise ValueError('Paired replay still holds positions')
    if minimum_cash < -1e-6:
        raise ValueError('Frozen quantities would require new financing; no invented zero interest')
    frame = pd.DataFrame(rows)
    curve = pd.concat([pd.Series([4000.]), frame.equity], ignore_index=True)
    return frame, dict(capital_final_usd=float(frame.equity.iloc[-1]),
        return_pct=float((frame.equity.iloc[-1]/4000-1)*100),
        max_drawdown_pct=float((curve/curve.cummax()-1).min()*100), min_cash_usd=minimum_cash)


def build_states(trades, signals, prices, adv, calendar, engine):
    rows, overrides, orders = [], {}, []
    for index, trade in trades.iterrows():
        bars = prices[trade.symbol]
        entry_idx = calendar.get_loc(pd.Timestamp(trade.entry_date))
        end_idx = calendar.get_loc(pd.Timestamp(trade.exit_date))
        if not np.isclose(exit_proceeds(engine,trade,float(trade.exit_price),float(adv[trade.symbol].at[trade.exit_date])),trade.proceeds,atol=1e-6):
            raise ValueError('Native exit cost parity failure')
        first_strong_seen, exit_decided = False, False
        for position in range(entry_idx, end_idx):
            day, next_day = calendar[position], calendar[position+1]
            info = signals.get(day, trade.symbol, trade.entry_date)
            # Full current session known; native intraday protection already consumed.
            observed = bars.loc[trade.entry_date:day]
            if (observed.low.le(trade.replay_initial_stop_price) | observed.high.ge(trade.replay_take_profit_price)).any():
                raise ValueError('Unconsumed barrier before close decision')
            close = float(bars.at[day,'close'])
            next_open = float(bars.at[next_day,'open'])
            resolved = resolve_exit(trade,day,next_day,next_open)
            proceeds = (float(trade.proceeds) if resolved['priority']=='NATIVE_OPEN_FIRST' else
                exit_proceeds(engine,trade,next_open,float(adv[trade.symbol].at[next_day])))
            advantage = float(trade.proceeds)-proceeds
            first = info['label'] in ('POSITIVE','NEGATIVE') and not first_strong_seen
            first_strong_seen |= first
            previous = float(bars.at[calendar[position-1],'close'])
            rows.append(dict(trade_id=index,symbol=trade.symbol,entry_date=trade.entry_date,
                decision_date=day,next_day=next_day,age=position-entry_idx,
                pnl_at_close_pct=(close/trade.entry_price-1)*100,
                day_return_pct=(close/previous-1)*100, first_strong=first,
                hold_advantage_usd=advantage, hold_advantage_pct=100*advantage/(float(trade.quantity)*next_open),
                hold_positive=advantage>0, future_price_return_pct=(float(trade.exit_price)/next_open-1)*100,
                baseline_exit_reason=trade.exit_reason, execution_priority=resolved['priority'],**info))
            if info['label']=='NEGATIVE' and not exit_decided:
                exit_decided = True
                orders.append(dict(trade_id=index, symbol=trade.symbol,decision_date=str(day.date()),
                    date=str(resolved['date'].date()), priority=resolved['priority'],reason=resolved['reason']))
                if resolved['priority'] != 'NATIVE_OPEN_FIRST':
                    overrides[index] = dict(resolved, proceeds=proceeds, pnl=proceeds-float(trade.entry_cost))
    return pd.DataFrame(rows), overrides, orders


def describe_states(frame):
    result={}
    if frame.empty:
        return result
    for label, part in frame.groupby('label'):
        result[label]=dict(states=len(part), trades=int(part.trade_id.nunique()),
            dates=int(part.decision_date.nunique()), mean_hold_advantage_pct=float(part.hold_advantage_pct.mean()),
            median_hold_advantage_pct=float(part.hold_advantage_pct.median()),
            holding_better_pct=float(part.hold_positive.mean()*100))
    return result


def matched_states(frame):
    """Condition on price state already known, not the later loss/win label."""
    if frame.empty:
        return {}
    frame=frame.copy()
    frame['month']=pd.to_datetime(frame.decision_date).dt.strftime('%Y-%m')
    frame['pnl_bucket']=pd.cut(frame.pnl_at_close_pct,[-np.inf,-5,0,5,10,np.inf],right=False)
    frame['age_bucket']=pd.cut(frame.age,[-1,4,9,19])
    keys=['month','pnl_bucket','age_bucket']
    controls=frame[frame.label.isin(['NONE','OTHER'])].groupby(keys,observed=True).agg(
        control_n=('hold_advantage_pct','size'),control_mean=('hold_advantage_pct','mean'))
    primary=frame[frame.first_strong].join(controls,on=keys)
    primary=primary[primary.control_n.ge(5)]
    result={}
    for label,part in primary.groupby('label'):
        delta=part.hold_advantage_pct-part.control_mean
        result[label]=dict(first_news_states=len(part),trades=int(part.trade_id.nunique()),
            mean_hold_advantage_delta_pct=float(delta.mean()),
            explanation='first strong event per original trade, same month/age/PnL bucket; descriptive, correlated controls')
    return result


def metrics(trades, overrides):
    pnl=trades.pnl.copy()
    for index,row in overrides.items():
        pnl.at[index]=row['pnl']
    return dict(trades=len(pnl), winners=int(pnl.gt(0).sum()),losers=int(pnl.lt(0).sum()),
        win_pct=float(pnl.gt(0).mean()*100), gains_usd=float(pnl[pnl.gt(0)].sum()),
        losses_usd=float(pnl[pnl.lt(0)].sum()),net_pnl_usd=float(pnl.sum()), changed_exits=len(overrides))


def run(output):
    output=Path(output)
    with exclusive_run(output):
        if (output/'protocol.json').exists():
            raise ValueError('Use new run ID; protocol immutable')
        manifest=read(SOURCE/'manifest.json')
        verify_hashes(Path('.'),manifest['source_hashes'])
        verify_hashes(Path('.'),manifest['code_hashes'])
        verify_hashes(SOURCE,manifest['files'])
        prices_path=Path(manifest['tapes'])/'prices.parquet'
        news_report=read(NEWS/'report.json')
        files=sorted(NEWS.glob('news-*.parquet'))
        for p in files:
            if digest(p)!=news_report['source_files'][p.name]:
                raise ValueError('Changed news archive')
        inputs={str(p):digest(p) for p in [*files,prices_path,SOURCE/'manifest.json',Path(__file__)]}
        protocol=dict(source=str(SOURCE), backend='lightgbm_path_amplitude', years=[2025,2026],tops=[10,20,50],
            primary_top=10,tp=.2,sl=.1,trailing=False,horizon='20 held sessions, native expiry session21 open',
            news_rule='All scored new articles since previous close, published since actual entry, must be >0.9 negative; positive means KEEP',
            afterhours='first subsequent close; exact close waits until next decision',
            publication_midnight='excluded from timed analysis, no hour invented',
            execution='next open only, expiry/regime/open protections precede news; intraday stops already consumed',
            primary='same actual archived entries/quantities, paired exits, freed cash NOT reinvested',
            modes=list(MODES), windows=manifest['windows'], threshold_tuning=False,
            availability='updated_at guard is not immutable historical first availability',
            matching='month x current PnL fixed bucket x position age; first strong event per original trade',
            no_sql=True,no_api=True,no_fit=True,no_broker=True,no_production_change=True,
            inputs=inputs,reserves=['not a rerun of dynamic entry/risk after changes in equity',
                'baseline-current sectors and adjusted prices, macro vintages not historical PIT',
                'only collected/scored articles; first-event labels use actual baseline exit, not unconditional H20',
                'overlapping symbol paths and reused years; no new independent holdout'])
        atomic_json(output/'protocol.json',protocol)
        raw=pd.concat([pd.read_parquet(p) for p in files],ignore_index=True)
        raw=raw.sort_values('available_at').drop_duplicates(['symbol','dedupe_hash','published_at_utc'])
        calendar=nyse_sessions('2023-01-01','2026-10-09')
        sessions=get_market_calendar('US_EQ',allow_us_weekday_fallback=False).sessions(calendar.min().date(),calendar.max().date())
        signals={mode:NewsSignals(raw,sessions,mode) for mode in MODES}
        prices=pd.read_parquet(prices_path)
        prices.date=pd.to_datetime(prices.date)
        groups={symbol:part.set_index('date').reindex(calendar) for symbol,part in prices.groupby('symbol')}
        adv={symbol:(part.close*part.volume).rolling(20,min_periods=20).mean().shift(1) for symbol,part in groups.items()}
        cfg=frozen_backtest_config('2025-01-01','2026-10-09')
        if json.loads(json.dumps(asdict(cfg.risk_config),default=str)) != manifest['risk']:
            raise ValueError('Native risk configuration changed')
        engine=BacktestEngine(cfg)
        reports=[]
        for year in (2025,2026):
            for count in (10,20,50):
                case=SOURCE/f'{year}-TOP{count}'
                saved=read(case/'case-report.json')
                verify_hashes(case,saved['files'])
                for name in ('trades.parquet','daily.parquet','case-report.json'):
                    inputs[str(case/name)]=digest(case/name)
                trades=pd.read_parquet(case/'trades.parquet')
                daily=pd.read_parquet(case/'daily.parquet')
                if saved['margin_interest'] or saved['corporate_action_events']:
                    raise ValueError('Paired-case CA/financing needs explicit adaptation')
                base_curve, base_metric=frozen_curve(trades,daily,groups,{})
                if not np.allclose(base_curve.equity,daily.equity,atol=1e-6,rtol=1e-10):
                    raise ValueError('Paired no-change baseline curve does not reproduce native ledger')
                for mode in MODES:
                    dest=output/f'{year}-TOP{count}-{mode}'
                    dest.mkdir(exist_ok=True)
                    states,overrides,orders=build_states(trades,signals[mode],groups,adv,calendar,engine)
                    curve,financial=frozen_curve(trades,daily,groups,overrides)
                    states.to_parquet(dest/'states.parquet',index=False)
                    curve.to_parquet(dest/'daily.parquet',index=False)
                    atomic_json(dest/'orders.json',orders)
                    report=dict(year=year,top=count,mode=mode,status='COMPLETED_EXPLORATORY',
                        baseline={**base_metric,**metrics(trades,{})}, news_exit={**financial,**metrics(trades,overrides)},
                        all_states=describe_states(states),first_strong=describe_states(states[states.first_strong]),
                        price_state_matched=matched_states(states),
                        native_priority_orders=sum(x['priority']=='NATIVE_OPEN_FIRST' for x in orders),
                        source_positions=len(trades), source_baseline_parity=True,
                        delta_net_pnl_usd=float(financial['capital_final_usd']-base_metric['capital_final_usd']),
                        files={p.name:digest(p) for p in dest.iterdir() if p.suffix=='.parquet'})
                    atomic_json(dest/'report.json',report)
                    reports.append(report)
                    atomic_json(output/'progress.json',dict(status='RUNNING',completed=len(reports),total=12,
                        year=year,top=count,mode=mode))
                    LOG.info('%s TOP%s %s: changed=%s delta=%+.2f',year,count,mode,len(overrides),report['delta_net_pnl_usd'])
        # Freeze late-added source trade files too; verify all archived data after run.
        atomic_json(output/'input-manifest.json',inputs)
        verify_hashes(Path('.'),inputs)
        verify_hashes(Path('.'),manifest['source_hashes'])
        verify_hashes(Path('.'),manifest['code_hashes'])
        report=dict(status='COMPLETED_EXPLORATORY_NOT_PIT_PROMOTION',cases=reports,completed=12,
            no_fit=True,no_sql=True,no_api=True,no_broker=True,source_hashes_verified=True)
        atomic_json(output/'report.json',report)
        atomic_json(output/'progress.json',dict(status='COMPLETED',completed=12,total=12))


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        run(args.output)
    except Exception as exc:
        path=Path(args.output)
        path.mkdir(parents=True,exist_ok=True)
        atomic_json(path/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
