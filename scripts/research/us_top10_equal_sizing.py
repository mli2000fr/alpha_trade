"""Offline research: equal proposed dollars, same aggregate ATR proposal budget.

Research-only builder replacement scoped to one synchronous decide call.
Native risk checks, allocation factors and opening execution remain active.
No claim of exactly equal final weights or exactly matched final exposure.
"""
import argparse
from dataclasses import asdict
import json
import logging
import math
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from common.config_loader import load_config
from common.quantity_utils import normalize_share_quantity
from risk_management.models import SizingResult
from risk_management.position_sizer import PositionSizer
from risk_management.portfolio_builder import PortfolioBuilder
from backtesting.oracle_portfolio_session import OraclePortfolioSession
from scripts.research.us_concentrated_contract_audit import frozen_configs
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro,run_portfolio
from service.market import parse_market_regimes


class EqualProposalSizer:
    def __init__(self,config,prices):
        self.config = config
        self.native = PositionSizer(config)
        self.original = {s:self.native.compute(p) for s,p in prices.items()}
        positive = [r.proposed_shares*prices[s].last_close for s,r in self.original.items()
                    if r.proposed_shares > 0]
        self.target = sum(positive)/len(positive) if positive else 0.

    def compute(self,price):
        original = self.original[price.symbol]
        # No revival of candidates rejected by the original ATR/minimum rules.
        if original.proposed_shares <= 0 or self.target <= 0:
            return original
        quantity = self.target/price.last_close
        quantity = normalize_share_quantity(quantity) if self.config.allow_fractional_shares else float(math.floor(quantity))
        if quantity*price.last_close < self.config.effective_min_notional:
            return SizingResult(symbol=price.symbol,proposed_shares=0.,method=original.method)
        # Method enum retained for native compatibility; explicit arm/audits
        # identify this as equal proposed dollars, not native ATR sizing.
        return SizingResult(symbol=price.symbol,proposed_shares=quantity,method=original.method)


class EqualProposalBuilder(PortfolioBuilder):
    def build(self,candidates,prices,*args,**kwargs):
        self._sizer = EqualProposalSizer(self._cfg,prices)
        return super().build(candidates,prices,*args,**kwargs)


class EqualProposalSession(OraclePortfolioSession):
    def decide(self,*args,**kwargs):
        # Isolated research process, sequential calls. Restored even on failure.
        with patch('backtesting.oracle_portfolio_session.PortfolioBuilder',EqualProposalBuilder):
            return super().decide(*args,**kwargs)


def audit_sizes(source):
    trades = pd.read_parquet(source/'baseline'/'trades.parquet')
    trades['entry_notional'] = trades.entry_price*trades.quantity
    trades['theoretical_sl7_loss'] = trades.entry_notional*.07
    groups = []
    for group,t in trades.groupby(pd.qcut(trades.entry_notional,4,duplicates='drop'),observed=True):
        groups.append(dict(notional_quartile=str(group),count=len(t),pnl=float(t.pnl.sum()),
                           mean_gross_return_pct=float(t.return_pct.mean())))
    return dict(entry_notional=trades.entry_notional.describe().to_dict(),
                theoretical_sl7_loss=trades.theoretical_sl7_loss.describe().to_dict(),quartiles=groups,
                warning='Descriptive dollar quartiles, confounded by changing equity/date/asset; no causal sizing conclusion')


def run(source,output):
    output.mkdir(parents=True,exist_ok=False)
    atomic_json(output/'progress.json',dict(status='PREPARING'))
    contract = json.loads(Path('artifacts/research/us_concentrated_replay/fixed-sl7-oracle_top10-20261007-v1/contract.json').read_text())
    market = parse_market_regimes((load_config() or {}).get('market_regimes'))
    risk,_ = frozen_configs()
    for key,value in [('market',market),('risk',risk)]:
        if json.loads(json.dumps(asdict(value),default=str)) != contract[key]:
            raise ValueError(f'Changed {key} contract')
    if risk.enable_kelly_sizing:
        raise ValueError('Equal proposal experiment requires native ATR path, not Kelly')
    sector = Path('artifacts/research/us_concentrated_replay/live-parity-preflight-current-sectors-20261007-v1/current-sector-mapping.parquet')
    if digest(sector) != contract['sector_sha256']:
        raise ValueError('Changed sectors')
    atomic_json(output/'protocol.json',dict(start='2023-01-01',end='2024-12-31',
        rule='Equal proposed dollars across native-positive prices for current TOP10; sum native proposals preserved before downstream allocation/constraints',
        initial_stop_pct=.07,tp=False,trailing=False,expiry_sessions_after_entry=20,
        no_future_labels=True,sql_reads=False,sql_writes=False,training=False,threshold_search=False,
        sources={str(source/f):digest(source/f) for f in ['bars.parquet','scores.parquet','macro.parquet','protocol.json']},
        caveats=['Final exposure not matched by future scaling','Current universe/sectors NON-PIT',
            'OOF full provenance not certified','Macro publication vintage not certified',
            'Native sizing_method and initial risk metadata remain ATR legacy; actual protection SL7 and experimental arm authoritative',
            'Candidates already held or later filtered participate in proposal normalization; final accepted totals can differ',
            'Research exploratory: compare risk and exposure, not just raw return']))
    atomic_json(output/'size-audit.json',audit_sizes(source))
    bars = pd.read_parquet(source/'bars.parquet')
    scores = pd.read_parquet(source/'scores.parquet')
    macro = pd.read_parquet(source/'macro.parquet')
    sectors = pd.read_parquet(sector).set_index('symbol').sector.to_dict()
    calendar = pd.DatetimeIndex(bars.loc[bars.symbol.eq('SPY') & bars.volume.gt(0),'date']).sort_values()
    frames = {key:bars.pivot(index='date',columns='symbol',values=col).reindex(calendar)
        for key,col in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
    reports = []
    for arm,factory in [('BASELINE',OraclePortfolioSession),('EQUAL_PROPOSALS',EqualProposalSession)]:
        atomic_json(output/'progress.json',dict(status='RUNNING',active_arm=arm,completed=len(reports),total=2))
        result = run_portfolio(frames=frames,scores=scores,sectors=sectors,macro=ArchivedMacro(macro),
            market_config=market,policy='ORACLE_TOP10',variant='NO_TP_FIXED_SL_20_AFTER_ENTRY',
            output=output/arm,quality=bars[['date','symbol','is_filled','instrument_id']],
            initial_stop_pct=.07,reject_constrained_entries=True,start_date='2023-01-01',
            end_date='2024-12-31',session_factory=factory)
        if arm == 'BASELINE':
            pd.testing.assert_frame_equal(pd.read_parquet(source/'baseline'/'daily.parquet'),
                                          pd.read_parquet(output/arm/'daily.parquet'))
        reports.append(dict(result,arm=arm))
    atomic_json(output/'report.json',dict(status='COMPLETED',baseline_daily_parity=True,runs=reports))
    atomic_json(output/'progress.json',dict(status='COMPLETED',completed=2,total=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('artifacts/research/us_concentrated_replay/top10-early-weakness-2023-2024-20261007-v1'))
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        run(args.source,args.output)
    except Exception as exc:
        if args.output.exists():
            atomic_json(args.output/'progress.json',dict(status='FAILED',error=str(exc)))
        raise
