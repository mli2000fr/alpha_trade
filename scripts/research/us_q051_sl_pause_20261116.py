"""Isolated causal research: two consecutive SL in 30 sessions, pause 100.

Frozen global Oracle scores; account-specific eligibility is applied BEFORE
Oracle ranking. No production edits, provider calls, orders or shared SQL writes.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

ROOT = Path('artifacts/research/us_q051_sl_pause/20261116-30sessions-pause100-v1')
REFERENCE = Path('artifacts/research/us_q051_feature_groups/20261116-lot1')
WINDOW = 30
PAUSE = 100


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def case_progress(folder, name, done, total, day, pause_triggers):
    """The isolated child writes only its case; its parent publishes campaign progress."""
    atomic_json(Path(folder)/'progress.json', dict(status='REPLAYING',case=name,
        completed=done,total=total,last_date=str(day),pause_triggers=pause_triggers))


class StopLedger:
    """Receives actual completed campaign exits, never baseline future outcomes."""
    def __init__(self, sessions, window=WINDOW, pause=PAUSE):
        self.sessions = list(sessions)
        self.indices = {d: i for i, d in enumerate(self.sessions)}
        self.window, self.pause = window, pause
        self.previous, self.until, self.pending, self.seen = {}, {}, [], set()
        self.receipts = []

    def observe(self, symbol, reason, available_at, campaign):
        stamp = pd.Timestamp(available_at)
        if stamp.tzinfo is None:
            raise ValueError('Exit availability must be timezone aware')
        if campaign in self.seen:
            raise ValueError('Duplicate completed campaign exit')
        self.seen.add(campaign)
        self.pending.append((stamp, symbol, reason, campaign))

    def flush(self, cutoff):
        cutoff = pd.Timestamp(cutoff)
        if cutoff.tzinfo is None:
            raise ValueError('Decision cutoff must be timezone aware')
        ready = sorted((p for p in self.pending if p[0] <= cutoff), key=lambda p: (p[0], p[3]))
        self.pending = [p for p in self.pending if p[0] > cutoff]
        for stamp, symbol, reason, campaign in ready:
            day = stamp.tz_convert('America/New_York').date()
            i = self.indices[day]
            if reason not in ('STOP', 'STOP_GAP'):
                self.previous.pop(symbol, None)
                continue
            previous = self.previous.get(symbol)
            if previous is not None and i - previous < self.window:
                resume = i + self.pause + 1
                if resume >= len(self.sessions):
                    raise ValueError('Session calendar too short for pause expiry')
                self.until[symbol] = resume
                self.previous.pop(symbol, None)
                self.receipts.append(dict(symbol=symbol, second_sl_at=stamp.isoformat(),
                    campaign_id=campaign, first_sl_session=str(self.sessions[previous]),
                    trigger_session=str(day), window_sessions=self.window, pause_sessions=self.pause,
                    resume_session=str(self.sessions[resume]), known_at=stamp.isoformat()))
            else:
                self.previous[symbol] = i

    def blocked(self, cutoff):
        self.flush(cutoff)
        day = pd.Timestamp(cutoff).tz_convert('America/New_York').date()
        index = self.indices[day]
        return {symbol for symbol, resume in self.until.items() if index < resume}


def choose(rows, blocked, universe_size=1790, fraction=.10, long_top_n=10):
    """Remove paused members first; recompute TOP fraction on model members."""
    from backtesting.per_symbol_selection import select_per_symbol, PerSymbolSelection
    eligible_size = universe_size - len(blocked)
    if eligible_size <= 0:
        return rows.iloc[:0].copy(), 0
    top = math.ceil(eligible_size * fraction)
    eligible = rows.loc[~rows.symbol.isin(blocked)].copy()
    if eligible.empty:
        return eligible, top
    ranked = select_per_symbol(eligible, PerSymbolSelection(oracle_top_n=top,
        long_top_n=min(long_top_n, top), allow_short=False,
        min_long_probability=.50, min_long_auc=.50))
    return ranked.loc[ranked.selected].sort_values('rank'), top


class Selection:
    def __init__(self, ledger, universe, enabled=True):
        self.ledger, self.universe, self.enabled = ledger, set(universe), enabled
        self.receipts, self.selected, self.book = [], [], None

    def __call__(self, signal_day, rows, cutoff):
        blocked = self.ledger.blocked(cutoff) & self.universe if self.enabled else set()
        selected, top = choose(rows.rename(columns={'trade_date': 'date'}), blocked, len(self.universe))
        ranks = selected.set_index('symbol')['rank'].to_dict()
        # Native hook receives a daily copy. Preserve its chosen LONG priority.
        rows.loc[:, 'rank'] = rows.symbol.map(ranks).fillna(999999).astype(int)
        self.selected.extend(selected.assign(decision_at=str(cutoff)).to_dict('records'))
        self.receipts.append(dict(signal_day=str(signal_day), cutoff=str(cutoff),
            paused=sorted(blocked), eligible_model_members=len(self.universe)-len(blocked),
            oracle_top_n=top, selected=selected.symbol.tolist()))
        return dict(incomplete=False, selected=selected.symbol.tolist())


def prepare():
    from scripts.research import us_q051_feature_groups_20261116 as base
    from scripts.research.us_q051_global_rank_h10_20261115 import FEATURE_2026
    if (ROOT/'protocol.json').exists():
        return read(ROOT/'protocol.json')
    ROOT.mkdir(parents=True, exist_ok=True)
    plan = deepcopy(read(REFERENCE/'protocol.json'))
    original = read(base.ORIGINAL/'protocol.json')
    plan.update(tasks=[], experiment='SL30_PAUSE100_BEFORE_ORACLE', window_sessions=WINDOW,
        pause_sessions=PAUSE, baseline='T0_SIMPLE', reference_root=str(REFERENCE),
        universe=original['universe'],
        pause_convention='Trigger-session remainder plus 100 following NYSE sessions; reopen on following session 101',
        consecutive='STOP or STOP_GAP only; any other completed campaign exit resets the streak',
        selection='Remove paused symbols -> TOP10% of eligible model universe -> TOP10 LONG -> score>.50 and calibration AUC>=.50 -> unchanged risk -> daily J+1 open',
        observation='Only actual replay exits; STOP known at bar close, STOP_GAP at observed open; no same-open refill',
        inference='Frozen full-universe Oracle scoring context unchanged; eligibility applied before sorting, not post-selection',
        production_changes=False, created_at_utc=datetime.now(timezone.utc).isoformat())
    for year in range(2021, 2027):
        item = original['models'][str(year)]
        future = Path(original['models'][str(year+1)]['source_root']) if year < 2026 else FEATURE_2026
        paths = {}
        for p in sorted((future/'chunks').glob('*/bars.parquet')):
            paths.update({s: str(p) for s in pd.read_parquet(p, columns=['symbol']).symbol.unique()})
            plan['sources'][str(p)] = digest(p)
        folder = ROOT/'years'/str(year)
        folder.mkdir(parents=True, exist_ok=True)
        oracle = pd.read_parquet(REFERENCE/'years'/str(year)/'oracle.parquet')
        # Predict all frozen Oracle rows, including candidates promoted by a pause.
        oracle.to_parquet(folder/'pool.parquet', index=False)
        plan['sources'][str(folder/'pool.parquet')] = digest(folder/'pool.parquet')
        for p in sorted((Path(item['root'])/'chunks').glob('*/bars.parquet')):
            symbols = sorted(set(pd.read_parquet(p, columns=['symbol']).symbol) & set(oracle.symbol))
            if not symbols:
                continue
            plan['tasks'].append(dict(key=f'{year}-{p.parent.name}', year=year, source=str(p),
                symbols=symbols, future=sorted({paths[s] for s in symbols if s in paths})))
            plan['sources'][str(p)] = digest(p)
    plan['sources'][str(Path(__file__))] = digest(Path(__file__))
    for p in [Path('execution_engine/winner_live_risk.py'), Path('tests/test_q051_sl_pause.py')]:
        plan['sources'][str(p)] = digest(p)
    atomic_json(ROOT/'protocol.json', plan)
    atomic_json(ROOT/'progress.json', dict(status='READY', training_jobs=len(plan['tasks']),
        rule='2 consecutive SL within 30 sessions; pause100 before Oracle'))
    return plan


def worker(key):
    """Extend the existing score cache; reuse every already qualified fit."""
    import joblib
    from scripts.research import us_q051_feature_groups_20261116 as base
    from modelFactory.oracle_path.directional_metrics import predict
    old = REFERENCE/'jobs'/key
    records, skipped = {}, set()
    if (old/'models.json').exists():
        archive = read(old/'models.json')
        for r in archive['models']:
            records.setdefault((r['symbol'], r['model_year']), {})[r['variant']] = r
        skipped = {(r['symbol'], r['year']) for r in archive['skipped']}
        prior = pd.read_parquet(old/'T0-probabilities.parquet')
    else:
        prior = pd.DataFrame(columns=['date', 'symbol', 'long_probability'])
    original_fit = base.fit_variants
    audits = []

    def reuse(panel, year, seed):
        symbol = str(panel.symbol.iloc[0]) if len(panel) else None
        key_ = (symbol, int(year))
        if key_ in records:
            rr = records[key_]
            if set(rr) != set(base.GROUPS):
                raise ValueError('Incomplete reference fitted-model group')
            weights = {}
            for variant, r in rr.items():
                if digest(Path(r['file'])) != r['sha256']:
                    raise ValueError('Changed archived model')
                weights[variant] = joblib.load(r['file'])
            oldp = prior[prior.symbol.eq(symbol) & prior.date.dt.year.eq(year)]
            a = oldp.merge(panel, on=['date', 'symbol'], validate='one_to_one')
            if len(a) != len(oldp) or not np.allclose(predict(weights['T0'], a), a.long_probability, atol=1e-12, rtol=0):
                raise ValueError('Reference input/prediction equivalence failed')
            meta = {k: v for k, v in rr['T0'].items() if k in ('fit_rows', 'calibration_rows', 'fit_start',
                'fit_end', 'fit_available_max', 'calibration_start', 'calibration_end', 'available')}
            meta['metrics'] = {v: r['calibration'] for v, r in rr.items()}
            audits.append(dict(symbol=symbol, year=int(year), reused=True, checked=len(a)))
            return weights, meta
        if key_ in skipped:
            return {}, dict(reason='PRESERVED_REFERENCE_ABSTENTION')
        weights, meta = original_fit(panel, year, seed)
        audits.append(dict(symbol=symbol, year=int(year), reused=False, qualified=bool(weights)))
        return weights, meta

    with patch.object(base, 'ROOT', ROOT), patch.object(base, 'fit_variants', reuse):
        base.worker(key)
    atomic_json(ROOT/'jobs'/key/'reuse-validation.json', dict(status='PASS', records=audits))


def assemble():
    plan = read(ROOT/'protocol.json')
    expected = pd.read_parquet(REFERENCE/'variants/T0/signals.parquet')
    for year in range(2021, 2027):
        parts = []
        for task in (t for t in plan['tasks'] if t['year'] == year):
            folder = ROOT/'jobs'/task['key']
            for name, h in read(folder/'done.json')['outputs'].items():
                if digest(folder/name) != h:
                    raise ValueError('Changed extended score-cache output')
            parts.append(pd.read_parquet(folder/'T0-probabilities.parquet'))
        probabilities = pd.concat(parts, ignore_index=True)
        oracle = pd.read_parquet(ROOT/'years'/str(year)/'pool.parquet')
        a = oracle.merge(probabilities, on=['date', 'symbol'], how='left', validate='one_to_one')
        a['short_probability'] = np.nan
        selected = []
        for day, rows in a.groupby('date', sort=True):
            b, _ = choose(rows, set(), len(plan['universe']))
            selected.append(b)
        control = pd.concat(selected, ignore_index=True)
        control['rank'] = control['rank'].astype(int)
        e = expected[expected.entry_year.eq(year)].rename(columns={'trade_date': 'date'})
        k = ['date', 'rank', 'symbol']
        left = control.sort_values(k)[k+['long_probability']].reset_index(drop=True)
        right = e.sort_values(k)[k+['long_probability']].reset_index(drop=True)
        if not left[k].equals(right[k]) or not np.allclose(left.long_probability, right.long_probability, atol=1e-12, rtol=0):
            raise ValueError(f'No-pause selection does not reproduce reference {year}')
        a.to_parquet(ROOT/'years'/str(year)/'rankings.parquet', index=False)
        atomic_json(ROOT/'years'/str(year)/'equivalence.json', dict(status='PASS', selected=len(left)))
    atomic_json(ROOT/'score-cache-validation.json', dict(status='PASS', no_pause_selection='EXACT_2021_2026'))


def prepare_daily():
    from database.connection import get_sqlalchemy_engine
    from backtesting.winner_data import daily_bars
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from scripts.research.us_q051_feature_groups_20261116 import shared
    from sqlalchemy import text, bindparam
    inputs = ROOT/'inputs'
    inputs.mkdir(exist_ok=True)
    if (inputs/'manifest.json').exists():
        return
    pivots = {c: pd.read_parquet(REFERENCE/'inputs'/(c+'.parquet')) for c in ['open','high','low','close','volume']}
    sectors = pd.read_parquet(REFERENCE/'inputs/sectors.parquet')
    actions = pd.read_parquet(REFERENCE/'inputs/actions.parquet')
    extra = sorted(set(read(ROOT/'protocol.json')['universe']) - set(pivots['close']))
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    with ReadOnlyReplay(ROOT).install(), replay_market_registry(shared.restore_registry(shared.ROOT)), engine.connect() as conn, conn.begin():
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        if extra:
            daily = pd.concat([daily_bars(conn,extra[i:i+100],pivots['close'].index.min().date(),pd.Timestamp('2026-10-01').date())
                for i in range(0,len(extra),100)],ignore_index=True)
            daily.to_parquet(inputs/'additional-daily.parquet', index=False)
            for c in pivots:
                pivots[c] = pd.concat([pivots[c],daily.pivot(index='date',columns='symbol',values=c)],axis=1).sort_index()
            def query(sql):
                return pd.read_sql(text(sql).bindparams(bindparam('symbols',expanding=True)),conn,params=dict(symbols=extra))
            sectors = pd.concat([sectors,query('SELECT symbol,sector FROM stock_metadata WHERE symbol IN :symbols')],ignore_index=True)
            actions = pd.concat([actions,query("SELECT symbol,ca_type,ex_date,payable_date,amount_per_share,currency FROM corporate_actions_events WHERE symbol IN :symbols AND ex_date BETWEEN '2021-01-01' AND '2026-10-01'")],ignore_index=True)
        for c, f in pivots.items():
            f.to_parquet(inputs/(c+'.parquet'))
        sectors.to_parquet(inputs/'sectors.parquet',index=False)
        actions.to_parquet(inputs/'actions.parquet',index=False)
        atomic_json(inputs/'manifest.json',dict(files={str(p):digest(p) for p in inputs.glob('*.parquet')},SQL_writes=0,provider_calls=0))


def run_case(enabled=True):
    from datetime import timedelta
    import requests
    from sqlalchemy import text
    from database.connection import get_sqlalchemy_engine
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from modelFactory.oracle.build_labels import nyse_sessions
    from scripts.research.us_q051_feature_groups_20261116 import shared, no_http
    from scripts.research.us_q051_feature_groups_cd_20261116 import ReferencePrices, missing_pairs
    from scripts.research.us_winner_vol20_extensions_20261109 import ROOT as EXT
    from backtesting.winner_campaign_replay import SqlIntradaySource, metrics
    from backtesting.simulator import BacktestEngine, BacktestResult
    from backtesting.winner_intraday import ReplayBroker
    from execution_engine import winner_live_risk
    name = 'PAUSE100_SL30' if enabled else 'CONTROL'
    folder = ROOT/'cases'/name
    folder.mkdir(parents=True, exist_ok=False)
    out = folder/'result'; out.mkdir()
    plan = read(ROOT/'protocol.json')
    for file, h in plan['sources'].items():
        if digest(Path(file)) != h:
            raise ValueError('Changed sealed source: '+file)
    cfg = shared.configuration(plan['reference'], shared.CASES['Q051_050'])
    pivots = {c:pd.read_parquet(ROOT/'inputs'/(c+'.parquet')) for c in ['open','high','low','close','volume']}
    sectors = pd.read_parquet(ROOT/'inputs/sectors.parquet')
    actions = pd.read_parquet(ROOT/'inputs/actions.parquet')
    sessions = [d.date() for d in nyse_sessions(pd.Timestamp('2020-01-01').date(),pd.Timestamp('2028-01-01').date())]
    ledger = StopLedger(sessions)
    selection = Selection(ledger,plan['universe'],enabled)
    parts = [pd.read_parquet(ROOT/'years'/str(y)/'rankings.parquet') for y in range(2021,2027)]
    signals = pd.concat(parts,ignore_index=True).rename(columns={'date':'trade_date'})
    signals['selected']=True;signals['side']='long';signals['rank']=1
    native_init, native_close = ReplayBroker.__init__, ReplayBroker.close
    native_concentration = winner_live_risk.concentration_allowed

    def init(book,*args,**kwargs):
        native_init(book,*args,**kwargs);selection.book=book

    def close(book,*args,**kwargs):
        before=len(book.trades)
        native_close(book,*args,**kwargs)
        new=book.trades[before:]
        for t in new:
            if any(l['remaining'] for l in book.lots.values() if l['campaign_id']==t['campaign_id']):
                raise ValueError('Partial campaign exit not qualified for consecutive-SL research')
            observed=pd.Timestamp(book.now)+(pd.Timedelta(minutes=5) if t['exit_reason']=='STOP' else pd.Timedelta(0))
            ledger.observe(t['symbol'],t['exit_reason'],observed,t['campaign_id'])

    execution_veto=[]
    def concentration(fills,current,candidate,day,kind):
        native=native_concentration(fills,current,candidate,day,kind)
        paused=enabled and candidate in ledger.blocked(selection.book.now)
        if paused:execution_veto.append(dict(time=str(selection.book.now),symbol=candidate,reason='SL30_PAUSE100_KNOWN_AT_EXECUTION'))
        return native and not paused

    ref=deepcopy(plan['reference']);ref['risk']=asdict(cfg.risk_config)
    ref['settings_profile']='Q051_'+name
    atomic_json(folder/'protocol.json',{**plan,'case':name,'reference':ref})
    atomic_json(out/'configuration.json',dict(profile=name,portfolio=asdict(cfg)))
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    old=ReferencePrices(EXT)
    tape=folder/'intraday';tape.mkdir()
    try:
        with ReadOnlyReplay(folder).install(),replay_market_registry(shared.restore_registry(shared.ROOT)),\
                patch.object(requests.Session,'request',no_http),engine.connect() as conn,conn.begin():
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            source=SqlIntradaySource(conn,discard_unqualified=True,allow_daily_fallback=True)
            def intraday(day,symbols):
                groups=old.day(day)
                missing=missing_pairs(day,symbols,groups)
                frames=[groups[s] for s in symbols if s in groups]
                if missing:
                    extra=source(day,missing)
                    path=tape/(str(day)+'.parquet')
                    if path.exists():raise ValueError('Repeated day intraday supplement')
                    extra.to_parquet(path,index=False)
                    atomic_json(tape/(str(day)+'.json'),dict(requested=missing,rows=len(extra),SQL_writes=0,provider_calls=0))
                    if not extra.empty:frames.append(extra)
                return pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
            def tick(done,total,day):
                case_progress(folder,name,done,total,day,len(ledger.receipts))
            with patch.object(ReplayBroker,'__init__',init),patch.object(ReplayBroker,'close',close),\
                    patch.object(winner_live_risk,'concentration_allowed',concentration):
                result=BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],high=pivots['high'],low=pivots['low'],
                    volume=pivots['volume'],signals_df=signals,sector_map=sectors.set_index('symbol').sector.to_dict(),
                    intraday_source=intraday,winner_research_assumptions=True,winner_progress=tick,
                    winner_corporate_actions=actions.to_dict('records'),winner_selection_source=selection)
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
            result.intraday_equity_curve.to_parquet(out/'equity-5m.parquet',index=False)
            result.closed_trades_df.to_csv(out/'trades.csv',index=False)
            result.trade_events_df.to_csv(out/'events.csv',index=False)
            result.drawdown_breaker_df.to_csv(out/'risk-5m.csv',index=False)
            ledger.flush(pd.Timestamp('2026-10-02',tz='UTC'))
            pd.DataFrame(ledger.receipts).to_csv(out/'pause-triggers.csv',index=False)
            pd.DataFrame(selection.receipts).to_json(out/'selection-decisions.json',orient='records',indent=2)
            pd.DataFrame(selection.selected).to_parquet(out/'selected-signals.parquet',index=False)
            pd.DataFrame(execution_veto).to_csv(out/'execution-vetoes.csv',index=False)
            report=metrics(result,4000.)
            annual=[];opening=4000.
            for y in range(2021,2027):
                curve=result.equity_curve[result.equity_curve.index.year==y]
                t=result.closed_trades_df;m=result.intraday_equity_curve
                part=BacktestResult(equity_curve=curve,closed_trades_df=t[pd.to_datetime(t.exit_date,utc=True).dt.year.eq(y)],
                    intraday_equity_curve=m[pd.to_datetime(m.timestamp,utc=True).dt.year.eq(y)],
                    tracker_snapshot={'winner_replay':dict(status=report['status'],full_live_parity=False)})
                annual.append(dict(year=y,**metrics(part,opening)));opening=float(curve.iloc[-1])
            pd.DataFrame(annual).to_csv(out/'annual-summary.csv',index=False)
            report.update(case=name,pause_triggers=len(ledger.receipts),provider_calls=0,orders=0,SQL_writes=0,
                production_changes=False,strict_pit=False,model_timing_oos=True,annual_reset=False)
            atomic_json(out/'report.json',report)
        from scripts.research.us_q051_feature_groups_replay_20261116 import validate_case
        validate_case(folder)
        if not enabled:
            a=pd.read_csv(out/'equity-daily.csv')
            b=pd.read_csv(REFERENCE/'variants/T0/cases/T0_SIMPLE/result/equity-daily.csv')
            if not a.iloc[:,0].equals(b.iloc[:,0]) or not np.allclose(a.equity,b.equity,atol=1e-8,rtol=0):
                raise ValueError('No-pause full-capital-curve equivalence failed')
        atomic_json(folder/'validation.json',dict(status='PASS',arithmetic=True,control_equivalence=not enabled))
        atomic_json(folder/'progress.json',dict(status='COMPLETED_EXPLORATORY',case=name))
        atomic_json(ROOT/'progress.json',dict(status='CASE_COMPLETED_EXPLORATORY',case=name,report=report))
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',case=name,error_type=type(exc).__name__,error=str(exc)))
        raise


def finish():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=[];curves=[]
    cases={'T0_SIMPLE':REFERENCE/'variants/T0/cases/T0_SIMPLE','SL30_PAUSE100':ROOT/'cases/PAUSE100_SL30'}
    for name, folder in cases.items():
        report=read(folder/'result/report.json')
        rows.append(dict(case=name,**{k:report.get(k) for k in ['final_equity','return_pct','max_drawdown_pct',
            'closed_lot_trades','win_pct','average_gross_capital','average_winning_pnl','average_losing_pnl']}))
        curves.append(pd.read_csv(folder/'result/equity-daily.csv',index_col=0,parse_dates=True).equity.rename(name))
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False)
    c=pd.concat(curves,axis=1);c.to_csv(ROOT/'capital-curves.csv')
    ax=c.plot(figsize=(13,7),title='Q051 témoin / 2 SL dans 30 séances → pause 100 avant Oracle')
    ax.set_ylabel('Capital ($)');ax.grid(alpha=.2);ax.figure.tight_layout()
    ax.figure.savefig(ROOT/'capital-comparison.png',dpi=140);plt.close(ax.figure)
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',cases=rows,production_changes=False))


def run():
    from scripts.research import us_q051_feature_groups_20261116 as base
    prepare()
    try:
        # Launch the original worker through our module's dispatcher, not its CLI.
        with patch.object(base,'ROOT',ROOT),patch.object(base,'__spec__',__spec__):
            pending=[t['key'] for t in read(ROOT/'protocol.json')['tasks'] if not (ROOT/'jobs'/t['key']/'done.json').exists()]
            base.launch_tasks(pending,4,'worker')
        atomic_json(ROOT/'progress.json',dict(status='CHECKING_NO_PAUSE_SELECTION_EQUIVALENCE'))
        assemble();prepare_daily()
        # Separate processes: the coordinator alone owns campaign progress;
        # each isolated child owns its case-local progress and result files.
        for name in ['CONTROL','PAUSE100_SL30']:
            if not (ROOT/'cases'/name/'validation.json').exists():
                with patch.object(base,'ROOT',ROOT),patch.object(base,'__spec__',__spec__):
                    base.launch_tasks([name],1,'case')
        finish()
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',choices=['all','prepare','worker','assemble','case','finish'],required=True)
    parser.add_argument('--key')
    args=parser.parse_args()
    if args.phase=='all':run()
    elif args.phase=='prepare':prepare()
    elif args.phase=='worker':worker(args.key)
    elif args.phase=='assemble':assemble()
    elif args.phase=='case':run_case(args.key!='CONTROL')
    else:finish()
