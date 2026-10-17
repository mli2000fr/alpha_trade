"""One frozen, offline exposure experiment. No fit, SQL, broker or live changes.

Past returns of yesterday's Oracle TOP50 are observations, not H20 labels.
Only new-entry risk is scaled; existing macro/B4 guards and protections remain.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from functools import partial
import logging
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from backtesting.oracle_portfolio_session import OraclePortfolioSession
from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import freeze_candidates, read
from scripts.research.us_oracle_tp20_sl10_campaign import code_hashes, run_case, annual_metrics
from scripts.research.us_oracle_barrier_grid_summary import verify_trade_contract

SOURCE = Path('artifacts/research/us_three_oracle_comparison/20261012-top50-v1')
POLICY = dict(top_n=50, lookback_sessions=5, minimum_coverage=.9,
    weakness='basket compounded 5-session return < 0 AND excess vs SPY < 0',
    weak_confirmations=[2,4], improving_confirmations=[2,4], levels=[1.,.5,.25],
    unknown_scale=.25, observed_at='J close; basket membership J-1',
    execution='new entries at J+1 only', replace_rejected_candidates=False,
    force_exit=False, override_macro_or_b4=False, training=False)
LOG = logging.getLogger(__name__)


@dataclass
class ExposureState:
    level: float = 1.
    weak_streak: int = 0
    improving_streak: int = 0

    def update(self, weak: bool | None):
        if weak is None:
            self.level, self.weak_streak, self.improving_streak = .25, 0, 0
        elif weak:
            self.weak_streak += 1
            self.improving_streak = 0
            if self.weak_streak >= 4:
                self.level = .25
            elif self.weak_streak >= 2:
                self.level = min(self.level,.5)
        else:
            self.improving_streak += 1
            self.weak_streak = 0
            if self.improving_streak >= 4:
                self.level = 1.
            elif self.improving_streak >= 2:
                self.level = max(self.level,.5)
        return self.level


def build_policy_tape(scores, prices, calendar):
    """Ignore every column except causal native scores, OHLCV and quality flags.

    Equal-weight basket is rebalanced daily using the preceding session's
    membership. Missing/filled/nonpositive-volume bars count against coverage.
    Five contiguous sessions required, never skip missing sessions or ffill.
    """
    ranked = freeze_candidates(scores,50,'NEW_BARRIER_LONG')
    members = {day:list(g.symbol) for day,g in ranked.groupby('date')}
    if prices.duplicated(['date','symbol']).any():
        raise ValueError('Duplicate price observations')
    matrices = {name:prices.pivot(index='date',columns='symbol',values=name).reindex(calendar)
        for name in ('close','volume','is_filled')}
    close = matrices['close']
    if 'SPY' not in close:
        raise ValueError('Missing benchmark')
    state, records = ExposureState(), []
    first, last = pd.Timestamp(scores.date.min()), pd.Timestamp(scores.date.max())
    for j,day in enumerate(calendar):
        if day < first or day > last:
            continue
        previous = calendar[j-1] if j else None
        symbols = members.get(previous,[])
        valid = []
        for symbol in symbols:
            if symbol not in close or previous is None:
                continue
            values = [close.at[previous,symbol],close.at[day,symbol],
                matrices['volume'].at[previous,symbol],matrices['volume'].at[day,symbol]]
            flags = [matrices['is_filled'].at[d,symbol] for d in (previous,day)]
            if all(pd.notna(x) and np.isfinite(x) and x>0 for x in values) \
                    and all(pd.notna(x) and x==0 for x in flags):
                valid.append(symbol)
        coverage = len(valid)/len(symbols) if symbols else 0.
        basket = None
        benchmark = None
        if symbols and len(symbols)==50 and coverage >= POLICY['minimum_coverage']:
            basket = float((close.loc[day,valid]/close.loc[previous,valid]-1).mean())
            spy = [close.at[d,'SPY'] for d in (previous,day)]
            if all(pd.notna(x) and np.isfinite(x) and x>0 for x in spy):
                benchmark = float(spy[1]/spy[0]-1)
        record = dict(date=day, membership_date=previous, requested=len(symbols),
            received=len(valid), missing_symbols=sorted(set(symbols)-set(valid)),
            coverage=coverage,basket_return=basket,spy_return=benchmark)
        window = [*records[-4:],record]
        qualified = len(window)==5 and all(r['basket_return'] is not None
            and r['spy_return'] is not None for r in window)
        ret5 = float(np.prod([1+r['basket_return'] for r in window])-1) if qualified else None
        spy5 = float(np.prod([1+r['spy_return'] for r in window])-1) if qualified else None
        weak = bool(ret5<0 and ret5-spy5<0) if qualified else None
        record.update(basket_return_5=ret5,spy_return_5=spy5,
            excess_return_5=ret5-spy5 if qualified else None,weak=weak,
            status='QUALIFIED' if qualified else 'UNKNOWN_OR_WARMUP',
            exposure_scale=state.update(weak),weak_streak=state.weak_streak,
            improving_streak=state.improving_streak)
        records.append(record)
    return pd.DataFrame(records)


class ExposureSession(OraclePortfolioSession):
    """Research-only multiplicative cap; native risk/B4 can still reduce to zero."""
    def __init__(self,*args,policy_tape,audit_path,**kwargs):
        super().__init__(*args,**kwargs)
        self.tape = policy_tape.set_index('date')
        self.audit_path = Path(audit_path)
        self.audit_rows = []

    def decide(self,day,**kwargs):
        key = pd.Timestamp(day)
        # Tail has no further entries; nevertheless record an explicit reason.
        available = key in self.tape.index
        row = self.tape.loc[key] if available else None
        scale = float(row.exposure_scale) if available else .25
        original = self.config
        if scale not in (1.,.5,.25):
            raise ValueError('Unfrozen exposure level')
        self.config = original.with_overrides(risk_multiplier=original.risk_multiplier*scale)
        try:
            entries = super().decide(day,**kwargs)
        finally:
            self.config = original
        accepted = [e for e in entries if e.approved_shares>0]
        self.audit_rows.append(dict(date=day,exposure_scale=scale,
            signal_status=row.status if available else 'NO_NEW_SIGNALS_EXPIRY_TAIL',
            raw_candidates=len(kwargs['scores']),accepted=len(accepted),
            rejected_reasons=dict(Counter(str(e.decision_reason) for e in entries if e.approved_shares<=0)),
            native_risk_multiplier=original.risk_multiplier,
            resolved_risk_multiplier=self.resolved_config.risk_multiplier,
            total_approved_notional=float(sum(e.target_notional for e in accepted)),
            allow_long=kwargs['regime'].allowed_long_entries))
        if len(self.audit_rows)%10==0:
            self.flush()
        return entries

    def flush(self):
        atomic_json(self.audit_path,self.audit_rows)


def prepare(output,source):
    output,source = Path(output),Path(source)
    manifest = read(source/'manifest.json')
    completed = read(source/'completion-audit.json')
    if completed['status']!='NINE_CASES_COMMON_INPUTS_AND_TRADE_CONTRACTS_VERIFIED':
        raise ValueError('Verified completed comparison required')
    verify_hashes(Path('.'),manifest['source_hashes'])
    verify_hashes(Path('.'),manifest['code_hashes'])
    verify_hashes(Path('.'),completed['source_hashes'])
    arm = source/'TRAIN_TP20_SL10'
    ready = read(arm/'ready.json')['files']
    verify_hashes(arm,ready)
    frozen = dict(status='FROZEN_EXPLORATORY',policy=POLICY,source=str(source),
        batch_id=manifest['models']['TRAIN_TP20_SL10']['batch_id'],years=[2024,2025,2026],
        top_n=50,tp_pct=.2,sl_pct=.1,trailing=False,expiry_sessions=20,
        decision_end='2026-09-03',capital_per_year=4000,sql_writes=False,broker_calls=False,
        models_fitted=False,live_changes=False,external_years_already_inspected=True,
        thresholds_selected_before_new_replay=True,virgin_holdout=False,
        warmup='first five basket observations and missing windows use 25% risk cap',
        state_across_years='policy tape continuous; annual portfolio/B4/capital restart',
        source_hashes={str(source/n):digest(source/n) for n in
            ('manifest.json','report.json','completion-audit.json')},
        code_hashes={**code_hashes(),str(Path(__file__)):digest(__file__)},
        limitations=manifest['limitations']+[
            'basket close-to-close indicator, not execution PnL',
            'unknown basket members may be delistings or identity changes; coverage archived',
            'small account and existing min notional can turn a risk cap into no entries',
            'past 2025 loss knowledge: exploratory only, no parameter search or live promotion'])
    if output.exists():
        if read(output/'exposure-protocol.json')!=frozen:
            raise ValueError('Changed protocol: use a new directory')
        verify_hashes(output,read(output/'ready.json')['files'])
        verify_hashes(output,read(output/'policy-tape.json')['files'])
        return frozen
    output.mkdir(parents=True)
    # Freeze before calculating the indicator or any new PnL.
    atomic_json(output/'exposure-protocol.json',frozen)
    for name in ready:
        shutil.copy2(arm/name,output/name)
    shutil.copy2(arm/'ready.json',output/'ready.json')
    scores,prices = [pd.read_parquet(output/n) for n in ('scores.parquet','prices.parquet')]
    calendar = nyse_sessions(pd.Timestamp('2023-01-01').date(),pd.Timestamp('2026-10-09').date())
    tape = build_policy_tape(scores,prices,calendar)
    tape.to_parquet(output/'exposure-policy.parquet',index=False)
    atomic_json(output/'policy-tape.json',dict(files={'exposure-policy.parquet':digest(output/'exposure-policy.parquet')},
        rows=len(tape),unknown=int(tape.status.ne('QUALIFIED').sum()),
        levels=tape.exposure_scale.value_counts().to_dict()))
    return frozen


def compare(output,source):
    output,source = Path(output),Path(source)
    protocol=prepare(output,source)
    tape=pd.read_parquet(output/'exposure-policy.parquet')
    references={r['year']:r for r in read(source/'report.json')['portfolios'] if r['arm']=='TRAIN_TP20_SL10'}
    reports=[]
    calendar=nyse_sessions(pd.Timestamp('2023-01-01').date(),pd.Timestamp('2026-10-09').date())
    for year in protocol['years']:
        atomic_json(output/'progress.json',dict(status='RUNNING',year=year,completed=len(reports),total=3))
        sessions=[]
        def factory(*args,**kwargs):
            session=ExposureSession(*args,policy_tape=tape,
                audit_path=output/'EXPOSURE_GUARD'/f'{year}-TOP50'/'exposure-decisions.json',**kwargs)
            sessions.append(session)
            return session
        result=run_case(output,year,50,experiment='EXPOSURE_GUARD',session_factory=factory)
        for session in sessions:
            session.flush()
        if result['status']!='COMPLETED_EXPLORATORY':
            atomic_json(output/'progress.json',dict(status='FAILED',year=year,result=result))
            raise ValueError(f'Exposure replay failed: {result}')
        case=output/'EXPOSURE_GUARD'/f'{year}-TOP50'
        trades,daily=[pd.read_parquet(case/n) for n in ('trades.parquet','daily.parquet')]
        if not trades.side.eq('buy').all() or not trades['rank'].between(1,50).all() \
                or daily.positions.iloc[-1] or abs(result['cash_reconciliation_error'])>1e-6:
            raise ValueError('Incomplete or incorrect trade/cash contract')
        verify_trade_contract(trades,.2,.1,calendar)
        if annual_metrics(result,trades,daily,year)!=result['annual_metrics']:
            raise ValueError('Annual metrics mismatch')
        reference=references[year]
        verify_hashes(Path(reference['output']),reference['files'])
        audit=read(case/'exposure-decisions.json')
        if not audit or any(r['accepted'] and not r['allow_long'] for r in audit):
            raise ValueError('Guard bypassed macro permission')
        if any(not pd.Timestamp(t.signal_date).date()<pd.Timestamp(t.entry_date).date()
               for t in trades.itertuples()):
            raise ValueError('Same-day entry/leakage')
        guard,base=result['annual_metrics'],reference['annual_metrics']
        reports.append(dict(year=year,baseline=base,exposure_guard=guard,
            delta_return_pct=guard['return_pct']-base['return_pct'],
            delta_max_drawdown_pct=guard['max_drawdown_pct']-base['max_drawdown_pct'],
            baseline_mean_gross_exposure=reference['mean_gross_exposure_over_equity'],
            guard_mean_gross_exposure=result['mean_gross_exposure_over_equity'],
            signal_levels=tape.loc[tape.date.dt.year.eq(year)].exposure_scale.value_counts().to_dict(),
            unknown_sessions=int(tape.loc[tape.date.dt.year.eq(year)].status.ne('QUALIFIED').sum()),
            rejected_reasons=dict(sum((Counter(r['rejected_reasons']) for r in audit),Counter())),
            output=str(case),protection_audit=result['protection_audit'],
            result_sha256=digest(case/'case-report.json'),decision_audit_sha256=digest(case/'exposure-decisions.json')))
        atomic_json(output/f'results-{year}.json',reports[-1])
        LOG.info('Year %s baseline %.2f%% guard %.2f%%',year,base['return_pct'],guard['return_pct'])
    report=dict(status='COMPLETED_EXPLORATORY',protocol_sha256=digest(output/'exposure-protocol.json'),
        years=reports,thresholds_changed=False,training=False,sql_writes=False,broker_calls=False,
        promoted=False,interpretation='Exploratory paired comparison; no untouched confirmation period',
        audited=True)
    atomic_json(output/'report.json',report)
    lines=['# Oracle TOP50 — réduction progressive du risque','',
        'LONG, TP20/SL10, sans trailing. Trois années déjà explorées : pas de promotion live.','',
        '| Année | Retour baseline | Retour garde | DD baseline | DD garde | Final garde USD |',
        '|---|---:|---:|---:|---:|---:|']
    for r in reports:
        b,g=r['baseline'],r['exposure_guard']
        lines.append(f"| {r['year']} | {b['return_pct']:.2f}% | {g['return_pct']:.2f}% | {b['max_drawdown_pct']:.2f}% | {g['max_drawdown_pct']:.2f}% | {g['final_capital_usd']:.2f} |")
    # Generated result, not a hand-edited source document.
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    verify_hashes(Path('.'),protocol['code_hashes'])
    atomic_json(output/'progress.json',dict(status='COMPLETED_EXPLORATORY',completed=3,total=3))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=SOURCE)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
    if args.prepare_only:
        prepare(args.output,args.source)
    else:
        compare(args.output,args.source)


if __name__=='__main__':
    main()
