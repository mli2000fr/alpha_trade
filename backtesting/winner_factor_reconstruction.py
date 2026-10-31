"""Run-local factor reconstruction. SQL SELECT only; never backdate live snapshots.

Daily prices use the canonical history available today (revisions remain a
research limitation). Capitalizations must be genuinely dated AND collected
before the historical source cutoff; no current cap or metadata substitution.
"""
from datetime import UTC, datetime, timedelta
import hashlib
import gzip
import json
import logging

import pandas as pd
from sqlalchemy import bindparam, text

from common.market_calendar import get_market_calendar
from common.winner_pyramiding import aware, regular_bounds
from risk_management.factor_inputs import (calculate_inputs, expected_sessions, select_caps,
                                           universe_hash, CAP_MAX_AGE_DAYS)

LOG=logging.getLogger(__name__)
MODE='RECONSTRUCTED_HISTORICAL_INPUTS'


class FactorReconstruction:
    def __init__(self, conn, universe, start, end, *, output=None,market_cap_check=True):
        self.conn=conn
        self.universe=tuple(sorted(set(universe)))
        self.start,self.end=start,end
        self.output=output
        self.market_cap_check=market_cap_check
        self.bars=None
        self.key=None
        self.frame=None
        self.error=None
        self.receipts=[]
        self.sec=None

    def inputs(self, day, now):
        # Freeze sources at the following session open, including genuine
        # overnight publications but no later candidate time/computation time.
        bounds=regular_bounds(day)
        if bounds is None:
            raise ValueError('Reconstruction requires an official US session')
        calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        source_cutoff=regular_bounds(calendar.next_session(day))[0]
        if aware(now)<source_cutoff:
            raise ValueError('Reconstruction source cutoff is the following official session open')
        if self.key!=day:
            self.key=day;self.frame=None;self.error=None
            receipt=dict(day=str(day),mode=MODE,source_cutoff=source_cutoff.isoformat(),
                reconstructed_at=datetime.now(UTC).isoformat(),universe_count=len(self.universe),
                daily_close_minimum_delay_seconds=1800,
                universe_sha256=universe_hash(self.universe),qualified=False,
                price_assumption='CURRENT_CANONICAL_HISTORY_NOT_ARCHIVED_PRICE_VINTAGES',
                capitalizations='OBSERVED_OR_PUBLIC_SEC_AS_REPORTED_X_RAW_CLOSE')
            receipt['market_cap_check_enabled']=self.market_cap_check
            try:
                from backtesting.winner_data import daily_bars
                sessions=expected_sessions(day)
                query=text('SELECT id,symbol,market_cap,source,currency,observation_date,available_date,computed_at '
                    'FROM stock_market_cap_daily WHERE symbol IN :symbols '
                    'AND observation_date BETWEEN :start AND :end AND available_date<=:available '
                    'AND computed_at<=:cutoff').bindparams(bindparam('symbols',expanding=True))
                raw=[dict(r) for r in self.conn.execute(query,dict(symbols=self.universe,
                    start=day-timedelta(days=CAP_MAX_AGE_DAYS),end=day,available=source_cutoff.date(),
                    cutoff=source_cutoff.replace(tzinfo=None))).mappings()] if self.market_cap_check else []
                for row in raw:
                    for field in ('observation_date','available_date'):
                        row[field]=pd.Timestamp(row[field]).date()
                    row['computed_at']=pd.Timestamp(row['computed_at']).to_pydatetime()
                caps=select_caps(raw,day,source_cutoff)
                receipt['dated_cap_symbols']=len(caps)
                rebuilt_caps=[]
                if self.market_cap_check and len(caps)<len(self.universe):
                    if self.sec is None:
                        from backtesting.historical_sec_capitalization import HistoricalSecCapitalizations
                        from common.market_cap import load_market_cap_config
                        self.sec=HistoricalSecCapitalizations(self.conn,self.universe,
                            max_age_days=load_market_cap_config().max_age_days)
                    rebuilt_caps=self.sec.reconstruct(day,source_cutoff,set(self.universe)-set(caps))
                    raw+=rebuilt_caps
                    caps=select_caps(raw,day,source_cutoff,allow_reconstructed=True)
                receipt['sec_reconstructed_cap_symbols']=len(rebuilt_caps)
                if self.market_cap_check and len(caps)<20:
                    raise ValueError(f'Capitalisations historiques datées insuffisantes : {len(caps)}/20 minimum ; '
                        'aucune capitalisation actuelle substituée')
                if self.bars is None:
                    self.bars=daily_bars(self.conn,sorted(set(self.universe)|{'SPY'}),self.start,self.end)
                    self.bars=self.bars.set_index('date',drop=False).rename_axis('_session').sort_index()
                bars=self.bars.loc[pd.Timestamp(sessions[0]):pd.Timestamp(day)].copy()
                records=calculate_inputs(bars,raw,list(self.universe),day,source_cutoff,sessions,
                    require_market_cap=self.market_cap_check,allow_reconstructed_caps=True)
                digest=hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest()
                frame=pd.DataFrame(records)
                # Keep the real computation timestamp. The historical availability
                # bound is a separate, explicitly modeled field used ONLY by replay.
                computed=datetime.now(UTC)
                frame['observed_at']=computed;frame['reconstructed_at']=computed
                frame['asof_date']=day;frame['run_id']='reconstructed-'+digest
                frame['evidence_kind']=MODE
                frame['input_available_at']=source_cutoff
                frame['universe_sha256']=universe_hash(self.universe)
                complete=frame.quality.eq('QUALIFIED')
                receipt.update(input_sha256=digest,qualified_symbols=int(complete.sum()),
                    incomplete_symbols=int((~complete).sum()),dated_cap_symbols=len(caps),
                    reconstructed_at=computed.isoformat(),qualified=bool(complete.sum()>=20),
                    incomplete_reasons={r.symbol:json.loads(r.details_json)['reasons']
                        for r in frame.loc[~complete].itertuples()})
                if self.output is not None:
                    folder=self.output/'factor-reconstructions'
                    folder.mkdir(exist_ok=True)
                    path=folder/(str(day)+'.json.gz')
                    serializable=frame.astype(object).where(frame.notna(),None)
                    with gzip.open(path,'xt',encoding='utf-8') as stream:
                        json.dump(dict(receipt=receipt,inputs=serializable.to_dict('records'),sec_capitalization_proofs=rebuilt_caps),stream,
                            ensure_ascii=False,indent=2,default=str,allow_nan=False)
                self.frame=frame
                LOG.info('Facteurs replay reconstruits %s : %d/%d titres qualifiés, %d capitalisations datées',
                    day,int(complete.sum()),len(frame),len(caps))
            except Exception as exc:
                self.error=str(exc)
                receipt['error']=self.error
                LOG.warning('Reconstruction factorielle %s impossible : %s',day,self.error)
            self.receipts.append(receipt)
        if self.error:
            raise ValueError('Reconstruction factorielle indisponible : '+self.error)
        return self.frame
