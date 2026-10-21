"""Offline exploratory LONG/SHORT protection grid, native execution primitives.

No provider, database, training, broker or production configuration mutation.
Annual accounts restart at4000 USD. Unknown loan/quotes/actions remain assumptions.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from itertools import product
import json
import logging
from pathlib import Path
import time

import numpy as np
import pandas as pd

from backtesting.research_intraday_native import IntradayNativeLedger
from common.trading_costs import TradingCostModel
from core.direction import compute_take_profit_price
from execution_engine.config import ExecutionConfig, LeverageConfig
from risk_management.config import RiskConfig
from risk_management.models import PriceInfo
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

PARENT = Path('artifacts/research/us_oracle_pyramiding/20261020-v1')
FIDELITY = Path('artifacts/research/us_intraday_fidelity/20261021-v2')
PRICE = Path('artifacts/research/us_h10_price_readiness/20261019-v1/qualification-final-v4/research-prices.parquet')
SL = (.03, .05, .07)
TRAIL = (None, .10, .15, .20)
HORIZON = (5, 10, 15, 20)
TP = (None, .10, .20)
READ = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
LOG = logging.getLogger(__name__)
CACHE = None


def risk_config():
    # Half of a maximum50%-equity full target => at most25%equity per fill.
    # This is the leveraged counterpart of the preceding25%full/12.5%half study.
    return RiskConfig(account_equity=4000., risk_per_trade_pct=.04, max_positions=8,
        max_short_positions=8, max_position_weight=.5, max_sector_weight=2.,
        max_gross_exposure=2., min_position_notional=0., short_selling_enabled=True,
        allow_fractional_shares=False, max_tickers_per_sector=None)


def execution_config():
    return ExecutionConfig(account_type='margin', swing_only=False, dry_run=True,
        simulated_account_equity=4000., simulated_margin_buying_power_multiplier=2.,
        leverage=LeverageConfig(enabled=True, mode='regt_swing', max_leverage=2.,
            dry_run_simulated_leverage=2., min_equity_usd=2000., audit_log=False))


def cases():
    return [dict(year=y, side=s, sl=sl, trailing=tr, horizon=h, tp=tp)
        for y, s, sl, tr, h, tp in product((2025, 2026), ('buy', 'sell'), SL, TRAIL, HORIZON, TP)]


def case_key(c):
    pct = lambda x: 'OFF' if x is None else f'{100*x:g}'
    return f"{c['year']}-{'LONG' if c['side']=='buy' else 'SHORT'}-SL{pct(c['sl'])}-TR{pct(c['trailing'])}-H{c['horizon']}-TP{pct(c['tp'])}"


class GridLedger(IntradayNativeLedger):
    """Only research policy extensions:2x, ACT/360 financing, marks and metadata.

    Native sizing/checks/fills/trackers/borrow/cash are NOT reimplemented.
    Fast mark/gross algebra is tested against native frame-based valuation.
    """
    def __init__(self, calendar, **kwargs):
        super().__init__(calendar, risk=risk_config(), strict=False, **kwargs)
        self.engine.config.exec_config = execution_config()
        self.engine.config.margin_interest_rate_annual = .065
        self.live_meta = {}
        self.entry_context = None
        self.bar_number = -1
        self.maintenance_pending = False
        self.margin_log = []

    def _frame(self):
        # Native day_idx addresses a DAILY index, even for an intraday fill.
        # Earlier rows stay unknown: no fabricated historical marks are used.
        frame=pd.DataFrame(np.nan,index=self.days[:self.days.get_loc(self.day)+1],columns=list(self.prices))
        frame.loc[self.day]=self.prices
        return frame

    def equity(self):
        return self.state.settled_cash+self.state.unsettled_cash+sum(
            p.quantity*self.prices[s]*(-1 if p.side=='sell' else 1)
            for s,p in self.state.positions.items())+sum(c['amount'] for c in self.claims.values())

    def gross(self):
        return sum(p.quantity*self.prices[s] for s,p in self.state.positions.items())

    def close(self, symbol, price, reason, *, phase='OPEN'):
        meta = self.live_meta[symbol]
        t = super().close(symbol, price, reason, phase=phase)
        t.update(meta, exit_timestamp=self.now if phase=='OPEN' else self.now+pd.Timedelta(minutes=5),
            exit_bar=self.bar_number, exit_phase=phase,
            holding_sessions=self.days.get_loc(self.day)-self.days.get_loc(pd.Timestamp(t['entry_date']))+1)
        t['holding_calendar_days'] = (t['exit_timestamp']-t['entry_timestamp']).total_seconds()/86400
        t['qty'] = t['quantity']
        t['net_return_pct'] = 100*t['pnl']/(t['quantity']*t['entry_price'])
        del self.live_meta[symbol]
        return t

    def enter(self, symbol, side, price_info, **kwargs):
        opened = super().enter(symbol, side, price_info, **kwargs)
        if opened:
            self.live_meta[symbol] = dict(self.entry_context, entry_timestamp=self.now, entry_bar=self.bar_number)
        return opened

    def resolve_open(self, *, expiry_symbols=None):
        # Standing TP receives its limit, not a favourable expiry-open windfall.
        self._healthy()
        if self.phase != 'OPEN':
            raise ValueError('Invalid opening phase')
        expiry_symbols = self.expiry_symbols if expiry_symbols is None else expiry_symbols
        for s,p in list(self.state.positions.items()):
            op,stop = self.prices[s],self.known_stop(s)
            target = compute_take_profit_price(p.side,p.entry_price,self.tp) if self.tp else None
            if (op>=stop if p.side=='sell' else op<=stop):
                self.close(s,op,'GAP_STOP')
            elif target is not None and (op<=target if p.side=='sell' else op>=target):
                self.close(s,target,'TP_GAP_LIMIT')
            elif s in expiry_symbols:
                self.close(s,op,'EXPIRY')

    def finish_day(self):
        # Same6.5%ACT/360 debit convention as the earlier2x annual backtest.
        self._healthy()
        if self.phase!='INTRABAR' or self.last_bar_end!=self.calendar.at[self.day,'market_close']:
            raise ValueError('Incomplete session')
        i=self.days.get_loc(self.day)
        boundary=self.days[i+1] if i+1<len(self.days) else self.day+pd.Timedelta(days=1)
        charge=max(-self.state.settled_cash,0.)*.065*(boundary-self.day).days/360
        self.state.settled_cash-=charge
        self.interest+=charge
        equity=self.equity()
        # Conservative assumed maintenance tiers, NOT historical broker terms.
        required=0.
        for s,p in self.state.positions.items():
            price=self.prices[s]
            unit=(max(2.5,price) if price<5 else max(5.,.3*price)) if p.side=='sell' else price*(1. if price<2.5 else .5 if price<=6 else .3)
            required+=p.quantity*unit
        self.maintenance_pending=equity<required
        self.margin_log.append(dict(date=self.day,interest=charge,equity=equity,
            required=required,breach=self.maintenance_pending))
        self.state.equity_points.append(equity)
        self.state.peak_equity=max(self.state.peak_equity,equity)
        self.last_finished,self.phase=self.day,'FINISHED'
        return equity


def prepare(root):
    if (root/'prepared.json').exists():
        verify_hashes(Path('.'),READ(root/'protocol.json')['sources'])
        verify_hashes(root,READ(root/'prepared.json')['files'])
        return
    if root.exists() and any(p.name!='run.lock' for p in root.iterdir()):
        raise ValueError('Fresh preparation directory required')
    for parent in (PARENT,FIDELITY):
        verify_hashes(Path('.'),READ(parent/'protocol.json')['sources'])
        verify_hashes(parent,READ(parent/'prepared.json')['files'])
    if READ(PARENT/'final-audit.json')['status']!='PASS_SHARED_CASH_RESEARCH_AUDIT':
        raise ValueError('Parent audit absent')
    names=[Path(__file__),Path('scripts/research/us_intraday_protection_grid_audit.py'),
        Path('tests/test_us_intraday_protection_grid.py'),Path('backtesting/research_intraday_native.py'),
        Path('backtesting/simulator.py'),Path('common/trading_costs.py'),Path('core/direction.py'),
        Path('risk_management/config.py'),Path('risk_management/constraints.py'),
        Path('risk_management/position_sizer.py'),Path('execution_engine/config.py'),PRICE]
    for parent,files in [(PARENT,['protocol.json','prepared.json','final-audit.json','bars.parquet','calendar.parquet']),
                         (FIDELITY,['protocol.json','prepared.json','final-audit.json','candidates.parquet'])]:
        names += [parent/f for f in files]
    root.mkdir(parents=True,exist_ok=True)
    atomic_json(root/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources={str(p):digest(p) for p in names},cases=cases(),parameter_policies=288,
        annual_replays=576,capital_per_year_usd=4000.,annual_reset=True,max_entry_leverage=2.,
        risk=asdict(risk_config()),execution=asdict(execution_config()),costs=asdict(TradingCostModel()),
        margin_rate_annual=.065,margin_basis='ACT/360 EOD debit incl weekends; calendar clipped at annual end',
        entry='Frozen first fresh two-close breakout/breakdown, next contiguous5m open; TOP10 research CatBoost PATH_H20 OOS. HALF of leveraged full target, integer shares. No adds/retries/rerank/replacement. Waiting counts towards J+H, fixed parent20-session admission block.',
        expiry='OPEN of final5m bar of OracleJ+H; never enter at/after expiry. Existing TP limit precedes expiry; stop first on collision. Prior completed-bar extrema only.',
        marking='Five-minute closes and after daily financing; gap/intrabar fills are reflected in next close. NOT tickwise worst equity. Annual open positions remain MTM, not forced terminal trades.',
        allocation='Time-weighted regular-session5m CLOSE gross notional=long market value+absolute short liability. Report mean USD, mean percent equity, mean own equity committed=min(gross,equity), excess gross=max(gross-equity,0), max and time above1x. Short sale proceeds are not free buying power.',
        sizing='Full target<=50%equity and4%equity planned SL risk, HALF =><=25%equity at fill; max8positions,2x gross admission cap. Remaining budget can reduce target;2x is not forced. Native repeat/loss blacklist guards retained.',
        maintenance='Assumed EOD tiers: LONG100%below2.5/50%through6/30%above6; SHORT max2.5USD/share below5 else max5USD/share or30%notional. Breach liquidates next open before new entries. No intraday margin call/locate/recall proof.',
        limitations=['Same213 future-price-qualified campaigns:119in2025,94in2026,72symbols; full original TOP10 unavailable. Survivor and full-path-coverage selection bias.',
            'Only current sealed research scores; not production LightGBM.2025/26 already inspected: optimizing these periods is retrospective, no fresh holdout.',
            'Borrow assumed available,constant0.3%annual/252entry-notional; no actual historical loan fees/locates/recalls or broker fills.',
            'No certifiedNBBO/PIT sector/regime/correlation/breaker or complete corporate-action cashflows. Sector caps disabled via assumed shared sector cap200%, not qualified neutral context.',
            'Prior-session ATR/ADV from restated daily archive, availability not historically certified. SL fixed so ATR level is a coverage guard only.',
            'Native execution components reused, NOT complete historical live/PAPER parity.2x/financing conventions aligned, other strategy choices differ from older TOP5 backtest.'],
        writes_sql=False,provider_calls=False,training=False,broker_calls=False))
    for source,name in [(PARENT/'bars.parquet','bars.parquet'),(PARENT/'calendar.parquet','calendar.parquet'),
                        (FIDELITY/'candidates.parquet','candidates.parquet')]:
        pd.read_parquet(source).to_parquet(root/name,index=False)
    candidates=pd.read_parquet(root/'candidates.parquet')
    daily=pd.read_parquet(PRICE)
    daily=daily[daily.symbol.isin(candidates.symbol.unique())].copy()
    daily['date']=pd.to_datetime(daily.date)
    if daily.duplicated(['date','symbol']).any():raise ValueError('Duplicate daily source')
    schedule=pd.read_parquet('artifacts/research/us_oracle_campaign/20261020-v1/sessions.parquet')
    # Include archive warmup prior2024, but never borrow the same-session daily bar.
    from modelFactory.oracle.build_labels import nyse_sessions
    days=nyse_sessions(daily.date.min(),daily.date.max())
    rows=[]
    for s,g in daily.groupby('symbol'):
        g=g.set_index('date').reindex(days)
        valid=(g.volume.gt(0)&g.close.gt(0)&g.low.gt(0)&g.high.ge(g[['open','close']].max(axis=1))
               &g.low.le(g[['open','close']].min(axis=1))&g.is_filled.fillna(1).eq(0))
        g.loc[~valid,['open','high','low','close','volume']]=np.nan
        prev=g.close.shift()
        tr=pd.concat([g.high-g.low,(g.high-prev).abs(),(g.low-prev).abs()],axis=1).max(axis=1,skipna=False)
        atr=tr.rolling(20,min_periods=20).mean().shift()
        adv=(g.close*g.volume).rolling(20,min_periods=20).mean().shift()
        for i in range(1,len(days)):
            if days[i].year in (2025,2026):
                rows.append(dict(symbol=s,date=days[i],atr=atr.iloc[i],adv=adv.iloc[i],atr_date=days[i-1]))
    pd.DataFrame(rows).to_parquet(root/'prior-context.parquet',index=False)
    atomic_json(root/'prepared.json',dict(files={n:digest(root/n) for n in
        ['bars.parquet','calendar.parquet','candidates.parquet','prior-context.parquet']}))


def load_tapes(root):
    root=Path(root)
    bars=pd.read_parquet(root/'bars.parquet')
    cand=pd.read_parquet(root/'candidates.parquet')
    symbol=cand.drop_duplicates('pair_id').set_index('pair_id').symbol
    bars['symbol']=bars.pair_id.map(symbol)
    if bars.symbol.isna().any():raise ValueError('Missing parent identity')
    distinct=bars.drop_duplicates(['symbol','bar_timestamp','open','high','low','close'])
    if distinct.duplicated(['symbol','bar_timestamp']).any():raise ValueError('Conflicting overlapping paths')
    calendar=pd.read_parquet(root/'calendar.parquet')
    pertime=defaultdict(dict)
    for r in distinct.itertuples():
        pertime[r.bar_timestamp][r.symbol]=(r.open,r.high,r.low,r.close)
    paths={int(k):g.sort_values('bar_timestamp').reset_index(drop=True) for k,g in bars.groupby('pair_id')}
    expiry={}
    for pid,g in paths.items():
        for h in HORIZON:
            expiry[pid,h]=g[g.session_offset.eq(h)].bar_timestamp.iloc[-1]
    context={(r.symbol,r.date):r for r in pd.read_parquet(root/'prior-context.parquet').itertuples()}
    result={}
    for year in (2025,2026):
        cal=calendar[calendar.date.dt.year.eq(year)].copy()
        timeline=[(t,r.date,t==r.market_close-pd.Timedelta(minutes=5)) for r in cal.itertuples()
            for t in pd.date_range(r.market_open,r.market_close-pd.Timedelta(minutes=5),freq='5min')]
        result[year]=dict(calendar=cal,timeline=timeline,bars=[pertime[t] for t,d,last in timeline],
            candidates=cand[cand.year.eq(year)].sort_values(['oracle_date','rank','symbol','pair_id']),
            context=context,expiry=expiry,paths=paths)
    return result


def metrics(marks,trades,open_rows,initial=4000.):
    e=marks.equity.to_numpy(float)
    peak=np.maximum.accumulate(np.r_[initial,e])[1:]
    dd=100*np.max(1-e/peak)
    w=trades[trades.pnl.gt(1e-8)] if len(trades) else trades
    l=trades[trades.pnl.lt(-1e-8)] if len(trades) else trades
    mean=lambda frame,col:float(frame[col].mean()) if len(frame) else None
    return dict(initial_capital_usd=initial,final_capital_usd=float(e[-1]),net_pnl_usd=float(e[-1]-initial),
        return_pct=100*(e[-1]/initial-1),max_drawdown_pct=float(dd),trades=len(trades),
        winners=len(w),losers=len(l),flat=len(trades)-len(w)-len(l),win_rate_pct=100*len(w)/len(trades) if len(trades) else None,
        avg_win_usd=mean(w,'pnl'),avg_loss_usd=mean(l,'pnl'),
        avg_win_pct=mean(w,'net_return_pct'),avg_loss_pct=mean(l,'net_return_pct'),
        mean_entry_notional_usd=float((trades.qty*trades.entry_price).mean()) if len(trades) and 'qty' in trades else None,
        avg_winner_holding_sessions=mean(w,'holding_sessions'),avg_loser_holding_sessions=mean(l,'holding_sessions'),
        avg_winner_holding_calendar_days=mean(w,'holding_calendar_days'),avg_loser_holding_calendar_days=mean(l,'holding_calendar_days'),
        mean_capital_used_usd=float(marks.gross.mean()),mean_capital_used_pct_equity=float((100*marks.gross/marks.equity).mean()),
        mean_own_equity_used_usd=float(np.minimum(marks.gross,marks.equity.clip(lower=0)).mean()),
        mean_excess_gross_over_equity_usd=float((marks.gross-marks.equity).clip(lower=0).mean()),
        max_capital_used_usd=float(marks.gross.max()),max_observed_leverage=float((marks.gross/marks.equity).max()),
        fraction_time_above_1x_pct=float(100*(marks.gross>marks.equity+1e-8).mean()),
        mean_cash_debit_usd=float((-marks.cash).clip(lower=0).mean()) if 'cash' in marks else None,
        open_positions=len(open_rows),unrealized_pnl_usd=sum(r['unrealized_pnl_usd'] for r in open_rows))


def run_case(root,c):
    start=time.monotonic()
    root=Path(root);key=case_key(c);out=root/'cases'/key
    if (out/'done.json').exists():
        saved=READ(out/'done.json');verify_hashes(out,saved['files']);return saved
    out.mkdir(parents=True,exist_ok=True)
    try:
        tape=CACHE[c['year']]
        ledger=GridLedger(tape['calendar'],sl=c['sl'],trailing=c['trailing'],tp=c['tp'])
        entries=defaultdict(list)
        for r in tape['candidates'][tape['candidates'].side.eq(c['side'])].itertuples():
            expiry=tape['expiry'][r.pair_id,c['horizon']]
            if r.decision_time<expiry:
                entries[r.decision_time].append((r,expiry))
        marks=[];blocked_day=None
        for i,((ts,day,last),ohlc) in enumerate(zip(tape['timeline'],tape['bars'])):
            ledger.bar_number=i
            due={s for s,m in ledger.live_meta.items() if ts>=m['expiry']}
            ledger.begin_bar(ts,{s:a[0] for s,a in ohlc.items()},expiry_symbols=due)
            liquidate=ledger.maintenance_pending and ts==ledger.calendar.at[day,'market_open']
            if liquidate:
                for s in list(ledger.state.positions):ledger.close(s,ledger.prices[s],'MAINTENANCE_NEXT_OPEN')
                ledger.maintenance_pending=False
                blocked_day=day
            ledger.resolve_open()
            for r,expiry in entries.get(ts,[]):
                if blocked_day==day:
                    ledger.audit.append(dict(time=ts,symbol=r.symbol,status='BLOCKED',reasons=['MAINTENANCE_SESSION']))
                    continue
                context=tape['context'].get((r.symbol,day))
                if context is None or not np.isfinite(context.atr) or not np.isfinite(context.adv):
                    ledger.audit.append(dict(time=ts,symbol=r.symbol,status='BLOCKED',reasons=['MISSING_PRIOR_ATR_ADV']))
                    continue
                p=PriceInfo(r.symbol,float(r.signal_close),float(context.atr),price_asof_date=day.date(),
                    atr_asof_date=context.atr_date.date(),adv_usd=float(context.adv))
                ledger.entry_context=dict(pair_id=int(r.pair_id),oracle_date=r.oracle_date,rank=int(r.rank),expiry=expiry)
                ledger.enter(r.symbol,c['side'],p,sector='RESEARCH_NO_SECTOR_CAP',signal_time=ts,
                    quantity_fraction=.5,selection_rank=int(r.rank))
            equity=ledger.observe_bar(ohlc)
            if last:equity=ledger.finish_day()
            marks.append(dict(time=ts+pd.Timedelta(minutes=5),equity=equity,gross=ledger.gross(),
                cash=ledger.state.settled_cash,unsettled=ledger.state.unsettled_cash,interest=ledger.interest))
        trades=pd.DataFrame(ledger.state.closed_trades)
        if not len(trades):trades=pd.DataFrame(columns=['symbol','pnl','net_return_pct','holding_sessions','holding_calendar_days'])
        open_rows=[]
        open_borrow=0.
        for s,p in ledger.state.positions.items():
            sign=-1 if p.side=='sell' else 1
            entry_fee=p.quantity*p.entry_price*ledger.engine._cost_model.per_leg_cost_pct
            pending_borrow=(p.quantity*p.entry_price*.003*(ledger.days.get_loc(ledger.day)-ledger.days.get_loc(p.entry_date))/252
                if p.side=='sell' else 0.)
            open_borrow+=pending_borrow
            open_rows.append(dict(symbol=s,side=p.side,qty=p.quantity,entry_price=p.entry_price,
                mark=ledger.prices[s],borrow_accrued_usd=pending_borrow,
                unrealized_pnl_usd=sign*p.quantity*(ledger.prices[s]-p.entry_price)-entry_fee-pending_borrow,
                **ledger.live_meta[s]))
        # Annual wealth includes unpaid loan cost of unclosed SHORTs too.
        marks[-1]['cash']-=open_borrow
        marks[-1]['equity']-=open_borrow
        m=pd.DataFrame(marks)
        expected=4000+trades.pnl.sum()+sum(r['unrealized_pnl_usd'] for r in open_rows)-ledger.interest
        if not np.isclose(expected,m.equity.iloc[-1],atol=1e-6,rtol=1e-10):raise ValueError('Final cash/MTM mismatch')
        trades.to_parquet(out/'trades.parquet',index=False)
        m.to_parquet(out/'marks.parquet',index=False)
        atomic_json(out/'open-positions.json',open_rows)
        atomic_json(out/'decisions.json',ledger.audit)
        atomic_json(out/'maintenance.json',ledger.margin_log)
        from scripts.research.us_intraday_protection_grid_audit import audit_case
        audit=audit_case(out,c,tape)
        result=dict(case=key,**c,status='COMPLETED_EXPLORATORY',**metrics(m,trades,open_rows),
            financing_usd=ledger.interest,borrow_usd=(float(trades.borrow_cost.sum()) if len(trades) else 0.)+open_borrow,
            margin_breaches=sum(x['breach'] for x in ledger.margin_log),audit=audit,elapsed_seconds=time.monotonic()-start,
            files={p.name:digest(p) for p in out.iterdir() if p.suffix in ('.json','.parquet') and p.name not in ('done.json','failed.json')})
        atomic_json(out/'done.json',result)
        return result
    except Exception as exc:
        import traceback
        result=dict(case=key,**c,status='FAILED',error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
        atomic_json(out/'failed.json',result)
        return result


def worker_init(root):
    global CACHE
    logging.basicConfig(level=logging.ERROR,force=True)
    CACHE=load_tapes(root)


def run(root,workers=2,limit=None):
    from scripts.research.oracle_path_confirmation import exclusive_run
    with exclusive_run(root):
        prepare(root)
        planned=cases()[:limit] if limit else cases()
        reports=[];start=time.monotonic()
        atomic_json(root/'progress.json',dict(status='RUNNING',completed=0,failed=0,total=len(planned)))
        with ProcessPoolExecutor(max_workers=workers,initializer=worker_init,initargs=(str(root),)) as pool:
            futures={pool.submit(run_case,str(root),c):c for c in planned}
            for future in as_completed(futures):
                result=future.result();reports.append(result)
                ok=[r for r in reports if r['status']=='COMPLETED_EXPLORATORY']
                elapsed=time.monotonic()-start
                atomic_json(root/'progress.json',dict(status='RUNNING',completed=len(ok),failed=len(reports)-len(ok),
                    attempted=len(reports),total=len(planned),last=result['case'],last_status=result['status'],
                    elapsed_seconds=elapsed,remaining_seconds_estimate=elapsed/len(reports)*(len(planned)-len(reports)),
                    updated_at_utc=datetime.now(timezone.utc).isoformat()))
                pd.DataFrame([{k:v for k,v in r.items() if k not in ('files','audit','traceback')} for r in reports]).to_csv(root/'annual-summary.partial.csv',index=False)
                LOG.info('%d/%d %s %s',len(reports),len(planned),result['case'],result['status'])
        verify_hashes(Path('.'),READ(root/'protocol.json')['sources'])
        verify_hashes(root,READ(root/'prepared.json')['files'])
        ok=[r for r in reports if r['status']=='COMPLETED_EXPLORATORY']
        pd.DataFrame([{k:v for k,v in r.items() if k not in ('files','audit')} for r in ok]).to_csv(root/'annual-summary.csv',index=False)
        status='COMPLETED_EXPLORATORY' if len(ok)==len(cases()) else 'PARTIAL_FAILED' if len(ok)<len(reports) else 'BENCHMARK_COMPLETED'
        report=dict(status=status,completed=len(ok),failed=len(reports)-len(ok),total=len(cases()),cases=reports,
            elapsed_seconds=time.monotonic()-start,full_live_parity=False)
        atomic_json(root/'report.json',report)
        atomic_json(root/'progress.json',{k:v for k,v in report.items() if k!='cases'})
        return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('artifacts/research/us_intraday_protection_grid/20261021-v1'))
    p.add_argument('--phase',choices=['prepare','run'],default='run')
    p.add_argument('--workers',type=int,default=2)
    p.add_argument('--limit',type=int)
    a=p.parse_args()
    if a.workers<1 or a.workers>4:raise ValueError('Use1..4local workers')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if a.phase=='prepare':prepare(a.output)
    else:run(a.output,a.workers,a.limit)


if __name__=='__main__':main()
