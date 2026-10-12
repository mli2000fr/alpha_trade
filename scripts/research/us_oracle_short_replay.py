"""Frozen SHORT-head portfolios, offline; hypothetical borrow, no broker/SQL.

This is an exploratory whole-share margin scenario, NOT historical shortability
certification. Existing LONG portfolios and archived protocols are not rewritten.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, replace
from functools import partial
import json
import logging
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.oracle_exit_policy import load_oracle_backtest_exit_policy
from backtesting.oracle_portfolio_ledger import OraclePortfolioLedger
from backtesting.oracle_portfolio_session import OraclePortfolioSession
from common.config_loader import load_config
from execution_engine.models import IntentRole
from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro, run_portfolio
from scripts.research.us_oracle_barrier_comparison import COUNTS, SECTORS, read
from scripts.research.us_oracle_merger_ledger import EVENTS
from service.market import parse_market_regimes

SHORT_SCORE = 'proba_short_tp_before_sl'
BORROW_ANNUAL = .003  # Native model assumption, NOT a historical quote/locate.
_CACHE = None


def freeze_short_candidates(scores, count):
    if type(count) is not int or count not in COUNTS:
        raise ValueError('TOP10/20/50 required')
    frame = scores[['date', 'symbol', SHORT_SCORE]].copy()
    if frame.duplicated(['date', 'symbol']).any() or not np.isfinite(frame[SHORT_SCORE]).all():
        raise ValueError('Duplicate key or unknown SHORT score')
    if not frame[SHORT_SCORE].between(0,1).all():
        raise ValueError('Invalid SHORT score')
    frame = frame.sort_values(['date', SHORT_SCORE, 'symbol'], ascending=[True,False,True])
    frame['selection_rank'] = frame.groupby('date').cumcount()+1
    population = frame.groupby('date').symbol.transform('size')
    frame['proba_extreme'] = 1-(frame.selection_rank-1)/population
    frame = frame.loc[frame.selection_rank.le(count)].copy()
    frame['selected'] = True
    return frame.rename(columns={SHORT_SCORE:'raw_short_score'})


def short_protections(native, tp, sl):
    if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<1 for v in (tp,sl)):
        raise ValueError('Positive TP/SL fractions below one required')
    signals, frame, orders = native.signals_df.copy(), native.protection_frame.copy(), native.order_lifecycle_frame.copy()
    if not signals.empty:
        if not signals.side.eq('sell').all():
            raise ValueError('SHORT protections cannot be applied to LONG signals')
        fills = signals.set_index('symbol').fill_price.astype(float)
        if not fills.index.is_unique or not np.isfinite(fills).all() or fills.le(0).any():
            raise ValueError('Invalid SHORT fill anchors')
        stops, targets = fills*(1+sl), fills*(1-tp)
        for target in (signals,frame):
            if not target.empty:
                target['replay_initial_stop_price'] = target.symbol.map(stops)
                target['replay_take_profit_price'] = target.symbol.map(targets)
        if not orders.empty:
            stop_mask, tp_mask = orders.intent_role.eq(IntentRole.INITIAL_STOP), orders.intent_role.eq(IntentRole.TAKE_PROFIT)
            orders.loc[stop_mask,'stop_price'] = orders.loc[stop_mask,'symbol'].map(stops)
            orders.loc[tp_mask,'limit_price'] = orders.loc[tp_mask,'symbol'].map(targets)
    return replace(native, signals_df=signals, protection_frame=frame, order_lifecycle_frame=orders,
        diagnostics=dict(native.diagnostics, research_side='SHORT', research_take_profit_pct=tp,
            research_initial_stop_pct=sl, research_trailing_enabled=False, anchor='actual_next_open_fill'))


class ShortSession(OraclePortfolioSession):
    def __init__(self, config, **kwargs):
        # No fractional SHORT sells. Preserve actual side caps and all regime gates.
        super().__init__(config.with_overrides(allow_fractional_shares=False), strategy_side='sell', **kwargs)


class ShortLedger(OraclePortfolioLedger):
    def __init__(self, *args, tp_pct=.20, sl_pct=.10, borrow_annual=BORROW_ANNUAL, events=EVENTS, **kwargs):
        if type(borrow_annual) not in (float,int) or not math.isfinite(borrow_annual) or not 0<=borrow_annual<=1:
            raise ValueError('Invalid assumed borrow annual rate')
        if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<1 for v in (tp_pct,sl_pct)):
            raise ValueError('Invalid SHORT TP/SL')
        self.tp_pct, self.sl_pct, self.ca_events = tp_pct, sl_pct, tuple(events)
        self.whole_share_reductions = []
        self.corporate_action_audits = []
        super().__init__(*args, entry_side='sell', **kwargs)
        self._cost_model = replace(self._cost_model, borrow_fee_annual=borrow_annual)

    def begin_day(self, day):
        for event in self.ca_events:
            if pd.Timestamp(event['day']) == pd.Timestamp(day) and event['source'] in self.state.positions:
                raise ValueError(f"Unqualified SHORT corporate-action liability {event['source']}/{day}")
        super().begin_day(day)

    def corporate_action_open(self, session, pending, steps, day):
        # Retired identities are not newly sold; no LONG exchange assumption is
        # reused to invent the obligations owed to a securities lender.
        retired = {e['source'] for e in self.ca_events if pd.Timestamp(e['day'])<=day}
        self.corporate_action_audits.extend(dict(date=day, symbol=p.symbol,
            action='RETIRED_IDENTITY_ENTRY_BLOCKED') for p in pending if p.symbol in retired)
        return [p for p in pending if p.symbol not in retired], steps

    def corporate_action_report(self):
        return dict(short_whole_share_reductions=self.whole_share_reductions,
                    historical_shortability_verified=False, dividend_cash_obligations_modelled=False)

    def _build_entry_protections(self, phase3, *, execution_config):
        return short_protections(super()._build_entry_protections(phase3, execution_config=execution_config),
                                 self.tp_pct, self.sl_pct)

    def execute_approved(self, entries, *, execution_config):
        if any(e.approved_shares>0 and not np.isclose(e.approved_shares,round(e.approved_shares),atol=1e-8,rtol=0)
               for e in entries):
            raise ValueError('Fractional SHORT entry is not supported')
        return super().execute_approved(entries, execution_config=execution_config)

    def apply_observed_protections(self, *, phase, take_profit_enabled=True, trailing_enabled=False):
        if trailing_enabled or not take_profit_enabled:
            raise ValueError('This SHORT experiment requires TP enabled and trailing OFF')
        return super().apply_observed_protections(phase=phase, take_profit_enabled=True, trailing_enabled=False)

    def close_resolved(self, exits, *, phase):
        resolved = []
        for row in exits:
            row = dict(row)
            if 'quantity' in row and row['exit_reason']=='regime_reduce':
                requested = float(row['quantity'])
                row['quantity'] = math.floor(requested+1e-9)
                if row['quantity'] != requested:
                    self.whole_share_reductions.append(dict(date=self.current_day, symbol=row['symbol'],
                        requested=requested, executed=row['quantity'], convention='whole_share_round_down'))
                if row['quantity']<=0:
                    continue
            resolved.append(row)
        closed = super().close_resolved(resolved, phase=phase)
        for trade in closed:
            # Preserve native reciprocal-return reporting for compatibility;
            # add the economically transparent entry-notional price return.
            trade['entry_notional_return_pct'] = 100*(1-trade['exit_price']/trade['entry_price'])
        return closed


def verify_short_trades(trades, prices, calendar, tp, sl, borrow_annual):
    if trades.empty:
        return dict(closed_positions=0, winning=0, losing=0, flat=0, borrow_usd=0.)
    if not trades.side.eq('sell').all():
        raise ValueError('Unexpected LONG trade')
    if trades[['entry_price','exit_price','quantity','pnl','borrow_cost']].isna().any().any():
        raise ValueError('Missing SHORT accounting field')
    if not np.isfinite(trades[['entry_price','exit_price','quantity','pnl','borrow_cost']]).all().all():
        raise ValueError('Nonfinite SHORT accounting')
    if not np.allclose(trades.replay_initial_stop_price,trades.entry_price*(1+sl),atol=1e-7,rtol=1e-8):
        raise ValueError('SHORT SL not anchored to fill')
    if not np.allclose(trades.replay_take_profit_price,trades.entry_price*(1-tp),atol=1e-7,rtol=1e-8):
        raise ValueError('SHORT TP not anchored to fill')
    if not np.allclose(trades.quantity,trades.quantity.round(),atol=1e-8,rtol=0) or trades.quantity.le(0).any():
        raise ValueError('Fractional/invalid SHORT quantity')
    if not np.allclose(trades.entry_notional_return_pct,100*(1-trades.exit_price/trades.entry_price),atol=1e-7):
        raise ValueError('Incorrect signed SHORT return')
    if not np.allclose(trades.return_pct,100*(trades.entry_price/trades.exit_price-1),atol=5.1e-5,rtol=0):
        raise ValueError('Native reciprocal SHORT return was changed')
    entry_idx = calendar.get_indexer(pd.to_datetime(trades.entry_date))
    exit_idx = calendar.get_indexer(pd.to_datetime(trades.exit_date))
    holding = exit_idx-entry_idx
    if (entry_idx<0).any() or (exit_idx<0).any() or (holding<0).any() or (holding>20).any():
        raise ValueError('Invalid holding chronology')
    expected_borrow = trades.quantity*trades.entry_price*borrow_annual*holding/252
    if not np.allclose(trades.borrow_cost,expected_borrow,atol=1e-7,rtol=1e-8):
        raise ValueError('Incorrect borrow-charge assumption')
    # Canonical entries have no fixed commission in this frozen Alpaca preset:
    # sale credit = 2*gross-entry_cost, cover flow=proceeds (<0).
    if not np.allclose(trades.pnl,2*trades.quantity*trades.entry_price-trades.entry_cost
                       +trades.proceeds-trades.borrow_cost,atol=1e-7,rtol=1e-8):
        raise ValueError('SHORT net cash flows do not reconcile')
    bars = prices.set_index(['symbol','date'])
    for i, row in enumerate(trades.itertuples()):
        bar = bars.loc[(row.symbol,pd.Timestamp(row.exit_date))]
        reason, stop, target = row.exit_reason,row.replay_initial_stop_price,row.replay_take_profit_price
        if reason=='expiry_open':
            if holding[i]!=20 or not np.isclose(row.exit_price,bar.open):
                raise ValueError('Incorrect SHORT expiry open')
        elif reason=='initial_stop_gap_open':
            if bar.open<stop-1e-7 or not np.isclose(row.exit_price,bar.open):
                raise ValueError('Incorrect adverse SHORT gap')
        elif reason=='take_profit_gap_limit':
            if bar.open>target+1e-7 or not np.isclose(row.exit_price,target):
                raise ValueError('Incorrect favourable SHORT gap limit')
        elif reason=='initial_stop':
            if bar.high<stop-1e-7 or not np.isclose(row.exit_price,stop):
                raise ValueError('Incorrect intraday SHORT SL')
        elif reason=='take_profit':
            if bar.low>target+1e-7 or bar.high>=stop or not np.isclose(row.exit_price,target):
                raise ValueError('Incorrect SHORT TP/collision ordering')
        elif reason not in {'regime_reduce','regime_liquidate'}:
            raise ValueError(f'Unexpected SHORT exit {reason}')
        elif not np.isclose(row.exit_price,bar.open):
            raise ValueError('Regime SHORT cover must occur at the next open')
    pnls = trades.groupby(['symbol','entry_date']).pnl.sum()
    return dict(closed_positions=len(pnls), winning=int(pnls.gt(0).sum()), losing=int(pnls.lt(0).sum()),
        flat=int(pnls.eq(0).sum()), win_rate=float(pnls.gt(0).mean()),
        winning_pnl_usd=float(pnls[pnls>0].sum()), losing_pnl_usd=float(pnls[pnls<0].sum()),
        net_trade_pnl_usd=float(pnls.sum()), borrow_usd=float(trades.borrow_cost.sum()))


def worker_init(inputs):
    global _CACHE
    root = Path(inputs)
    original = read(Path(read(root/'input-protocol.json')['source'])/'protocol.json')
    _CACHE = dict(prices=pd.read_parquet(root/'prices.parquet'), scores=pd.read_parquet(root/'scores.parquet'),
        macro=pd.read_parquet(root/'macro.parquet'),
        calendar=nyse_sessions(pd.Timestamp('2024-01-01').date(),pd.Timestamp(original['as_of']).date()),
        sectors=pd.read_parquet(SECTORS).set_index('symbol').sector.to_dict(),
        market=parse_market_regimes(load_config().get('market_regimes')))


def case_key(year,count):
    return f'{year}-TOP{count}-NEW_BARRIER_SHORT-TP20_SL10'


def run_case(year,count,output,tp,sl,borrow_annual,allow_short_normal=False):
    root = Path(output)/case_key(year,count)
    root.mkdir(parents=True,exist_ok=True)
    if (root/'case-report.json').exists() and read(root/'case-report.json')['status']=='COMPLETED_EXPLORATORY':
        saved = read(root/'case-report.json')
        verify_hashes(root,saved['output_hashes'])
        return saved
    cache = _CACHE
    candidates = freeze_short_candidates(cache['scores'].loc[cache['scores'].date.dt.year.eq(year)],count)
    required = set(candidates.symbol)|{'SPY'}
    prices = cache['prices'].loc[cache['prices'].symbol.isin(required)]
    if required-{'SPY'}-set(cache['sectors']):
        raise ValueError('Missing current candidate sectors')
    calendar = cache['calendar']
    cutoff = '2025-12-31' if year==2025 else '2026-09-03'
    last = calendar[calendar<=cutoff][-1]
    end = calendar[calendar.get_loc(last)+21]
    base = dict(year=year,count=count,side='SHORT',arm='NEW_BARRIER_SHORT',tp_pct=tp,sl_pct=sl,
        trailing=False,decision_cutoff=cutoff,terminal_date=str(end.date()),borrow_fee_annual=borrow_annual,
        historical_shortability_verified=False,short_borrow_availability_assumed=True,
        borrow_recall_modelled=False,dividend_cash_obligations_modelled=False,serving_ready=False)
    base['research_allow_short_normal'] = allow_short_normal
    frames = {key: prices.pivot(index='date',columns='symbol',values=col).reindex(calendar)
        for key,col in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
    try:
        with (root/'stderr.log').open('a',encoding='utf-8') as log:
            logging.basicConfig(level=logging.WARNING,stream=log,force=True)
            with redirect_stderr(log),redirect_stdout(log):
                result = run_portfolio(frames=frames,scores=candidates,sectors=cache['sectors'],
                    macro=ArchivedMacro(cache['macro']),market_config=cache['market'],policy='selected',
                    variant='CURRENT_NO_EXPIRY',output=root,start_date=f'{year}-01-01',end_date=str(end.date()),
                    decision_end_date=str(last.date()),quality=prices[['date','symbol','is_filled','instrument_id']],
                    session_factory=ShortSession,
                    ledger_factory=partial(ShortLedger,tp_pct=tp,sl_pct=sl,borrow_annual=borrow_annual),
                    expiry_open_sessions=20,protection_options=dict(take_profit_enabled=True,trailing_enabled=False),
                    research_allow_short_normal=allow_short_normal)
        trades = pd.read_parquet(root/'trades.parquet')
        audit = verify_short_trades(trades,prices,calendar,tp,sl,borrow_annual)
        regimes = read(root/'regimes.json')
        decision_regimes = [r for r in regimes if pd.Timestamp(r['date'])<=last]
        base.update(short_entry_permission=('RESEARCH_NORMAL_AND_NATIVE_CP' if allow_short_normal else
                                            'NATIVE_CP_ONLY_NORMAL_BLOCKED'),
            decision_sessions=len(decision_regimes),
            short_permitted_sessions=sum(r.get('allow_short',False) for r in decision_regimes))
        if abs(result['cash_reconciliation_error'])>1e-6:
            raise ValueError('SHORT portfolio cash reconciliation failed')
        result.update(base,trade_audit=audit,status='COMPLETED_EXPLORATORY',
            initial_capital_usd=4000.,final_capital_usd=4000*(1+result['return_pct']),output=str(root))
        result['trailing_unchanged'] = False  # Explicitly OFF, not native trailing.
        result['sizing_unchanged'] = False  # Whole-share SHORT vs fractional LONG.
        result['approved_entry_quantities_unchanged_at_commit'] = True
        result['output_hashes'] = {p.name:digest(p) for p in root.glob('*')
            if p.is_file() and p.suffix in {'.parquet','.json'} and p.name!='case-report.json'}
        atomic_json(root/'case-report.json',result)
        return result
    except Exception as exc:
        result = dict(base,status='FAILED',error_type=type(exc).__name__,error=str(exc))
        atomic_json(root/'case-report.json',result)
        return result


def write_report(output,reports,total,verified=False):
    complete = sum(r['status']=='COMPLETED_EXPLORATORY' for r in reports)
    failed = sum(r['status']=='FAILED' for r in reports)
    status = ('COMPLETED_EXPLORATORY' if verified and complete==total else
        'PARTIAL_FAILED' if verified and len(reports)==total else 'VERIFYING_INPUTS' if len(reports)==total else 'RUNNING')
    result = dict(status=status,completed=complete,failed=failed,finished=len(reports),total=total,
        portfolios=reports,input_hashes_verified=verified,training=False,sql_writes=False,broker_orders=False,
        production_strategy_changed=False,historical_shortability_verified=False,
        borrow_availability_assumed=True,dividend_cash_obligations_modelled=False)
    atomic_json(output/'report.json',result)
    atomic_json(output/'progress.json',{k:result[k] for k in ('status','completed','failed','finished','total')})
    lines = ['# Oracle SHORT forcé — TP20/SL10, sans trailing','',
        '**Simulation exploratoire : emprunt supposé disponible, pas une preuve historique broker.**','',
        '| Année | TOP | Gagnants | Perdants | Rendement | DD | Capital final | Emprunt payé | Statut |',
        '| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
    for r in sorted(reports,key=lambda r:(r['year'],r['count'])):
        if r['status']=='FAILED':
            lines.append(f"| {r['year']} | {r['count']} | — | — | — | — | — | — | FAILED |")
        else:
            a = r['trade_audit']
            lines.append(f"| {r['year']} | {r['count']} | {a['winning']} | {a['losing']} | "
                f"{r['return_pct']:+.2%} | {r['max_drawdown']:.2%} | {r['final_capital_usd']:.2f} $ | "
                f"{a['borrow_usd']:.2f} $ | EXPLORATOIRE |")
    lines += ['', 'Chaque scénario repart de 4 000 USD. 2026 : décisions jusqu’au 3 septembre, sorties début octobre.',
        'Actions entières seulement, caps SHORT et régime natifs conservés. Prix ajustés fournisseur, secteurs actuels/non PIT.',
        ('SHORT en régime normal explicitement autorisé pour cette recherche seulement ; close/cash-only restent bloqués.'
         if any(r.get('research_allow_short_normal') for r in reports) else
         'Le régime natif autorise de nouvelles ventes SHORT en capital-preservation, pas en régime normal.'),
        'Emprunt à 0,3 %/an supposé, prorata de séances ; pas de locate historique, rappel ou paiement compensateur de dividendes.',
        'Les positions traversant une conversion corporate non qualifiée déclenchent FAILED, pas une correction opportuniste.']
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result


def run(inputs,output,workers=2,smoke=False,allow_short_normal=False):
    if type(workers) is not int or not 1<=workers<=3:
        raise ValueError('One to three research workers required')
    inputs,output = Path(inputs),Path(output)
    policy = load_oracle_backtest_exit_policy()
    if (policy.take_profit_pct,policy.stop_loss_pct)!=(.20,.10):
        raise ValueError('This preregistered experiment requires TP20/SL10')
    prepared, lineage = read(inputs/'prepared.json'),read(inputs/'input-protocol.json')
    verify_hashes(inputs,prepared['files'])
    verify_hashes(Path('.'),lineage['source_hashes'])
    original = read(Path(lineage['source'])/'protocol.json')
    risk = frozen_backtest_config('2025-01-01',original['as_of'])
    market = parse_market_regimes(load_config().get('market_regimes'))
    if (json.loads(json.dumps(asdict(risk.risk_config),default=str))!=original['portfolio']['risk']
            or json.loads(json.dumps(asdict(market),default=str))!=original['portfolio']['market']):
        raise ValueError('Risk/market settings differ from common LONG inputs')
    if not risk.risk_config.short_selling_enabled:
        raise ValueError('SHORT disabled by current risk settings')
    code = [Path(__file__),Path('config.yaml'),Path('backtesting/oracle_exit_policy.py'),
        Path('backtesting/oracle_portfolio_ledger.py'),Path('backtesting/oracle_portfolio_session.py'),
        Path('backtesting/simulator.py'),Path('risk_management/portfolio_builder.py'),
        Path('scripts/research/us_concentrated_live_portfolio.py'),Path('scripts/research/us_concentrated_contract_audit.py'),
        Path('backtesting/execution_replay.py'),Path('backtesting/execution_lifecycle_replay.py'),
        Path('backtesting/protection_watcher_replay.py'),Path('backtesting/exit_lifecycle_replay.py')]
    # Include transitively used risk, regime, direction and cost primitives.
    for directory in ('risk_management','execution_engine','service/market','backtesting','core'):
        code.extend(Path(directory).rglob('*.py'))
    code.extend([SECTORS, Path('scripts/research/us_oracle_merger_ledger.py')])
    hashes = {str(p):digest(p) for p in code}
    cases = [(2026,10)] if smoke else [(y,n) for y in (2025,2026) for n in COUNTS]
    protocol = dict(inputs=str(inputs),input_files=prepared['files'],prepared_sha256=digest(inputs/'prepared.json'),
        input_protocol_sha256=digest(inputs/'input-protocol.json'),source_hashes=hashes,lineage_hashes=lineage['source_hashes'],
        cases=cases,tp_pct=.20,sl_pct=.10,trailing=False,score=SHORT_SCORE,
        ranking='decreasing SHORT score, symbol tie-break; percentile only for native sizing; no future reselection',
        entry='J+1 actual open fill',expiry='21st holding-session open',
        annual_initial_capital_usd=4000.,risk=asdict(risk.risk_config),market=asdict(market),
        short_max_positions=risk.risk_config.max_short_positions,whole_share_entries=True,
        borrow_fee_annual=BORROW_ANNUAL,borrow_availability='ASSUMED_ALL_NOT_HISTORICALLY_VERIFIED',
        borrow_recall_modelled=False,dividend_cash_obligations_modelled=False,
        corporate_action_liability='BLOCK_IF_HELD_AT_UNQUALIFIED_EXCHANGE',
        current_sectors_non_pit=True,price_adjustment='current_provider_adjusted_not_raw_execution_prices',
        side='SHORT',frozen_model=True,training=False,sql_writes=False,broker_orders=False,promotion=False)
    protocol['regime_short_permissions'] = ('RESEARCH_NORMAL_AND_NATIVE_CP' if allow_short_normal else
                                           'NATIVE_CP_ONLY_NORMAL_BLOCKED')
    protocol['research_allow_short_normal'] = allow_short_normal
    canonical = json.loads(json.dumps(protocol,default=str))
    output.mkdir(parents=True,exist_ok=True)
    if (output/'protocol.json').exists() and read(output/'protocol.json')!=canonical:
        raise ValueError('Resume protocol changed: use a new output directory')
    atomic_json(output/'protocol.json',protocol)
    reports,pending = [],[]
    for y,n in cases:
        path = output/case_key(y,n)/'case-report.json'
        if path.exists() and read(path)['status']=='COMPLETED_EXPLORATORY':
            saved = read(path)
            verify_hashes(path.parent,saved['output_hashes'])
            reports.append(saved)
        else:
            pending.append((y,n))
    write_report(output,reports,len(cases))
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[name]='1'
    with ProcessPoolExecutor(max_workers=workers,initializer=worker_init,initargs=(str(inputs),)) as executor:
        futures = {executor.submit(run_case,y,n,str(output),.20,.10,BORROW_ANNUAL,allow_short_normal):(y,n) for y,n in pending}
        for future in as_completed(futures):
            y,n = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = dict(year=y,count=n,status='FAILED',error_type=type(exc).__name__,error=str(exc))
                folder = output/case_key(y,n)
                folder.mkdir(parents=True,exist_ok=True)
                atomic_json(folder/'case-report.json',result)
            reports.append(result)
            write_report(output,reports,len(cases))
            print(f'{len(reports)}/{len(cases)} {case_key(y,n)} {result["status"]}',flush=True)
    verify_hashes(Path('.'),hashes)
    verify_hashes(Path('.'),lineage['source_hashes'])
    verify_hashes(inputs,prepared['files'])
    if digest(inputs/'prepared.json')!=protocol['prepared_sha256'] or digest(inputs/'input-protocol.json')!=protocol['input_protocol_sha256']:
        raise ValueError('Input manifests changed during replay')
    result = write_report(output,reports,len(cases),verified=True)
    if result['failed']:
        raise RuntimeError(f"SHORT replay: {result['failed']} failed case(s), see report.json")
    return result


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--allow-short-normal',action='store_true',
        help='Counterfactual research only: allow forced SHORT also in NORMAL; all other gates retained')
    args = parser.parse_args()
    try:
        run(**vars(args))
    except Exception as exc:
        if args.output.exists():
            atomic_json(args.output/'failure.json',dict(error_type=type(exc).__name__,error=str(exc)))
            prior = read(args.output/'progress.json') if (args.output/'progress.json').exists() else {}
            atomic_json(args.output/'progress.json',dict(prior,status='FAILED',error=str(exc)))
        raise
