"""Read-only canonical price and archived factor inputs for Winner replay."""
import pandas as pd
from sqlalchemy import bindparam, text

from common.daily_bar_sources import select_daily_bars


def daily_bars(conn, symbols, start, end):
    query=text('SELECT symbol,date,open,high,low,close,volume,is_filled,data_source,data_adjustment '
        'FROM stock_bars_daily WHERE symbol IN :symbols AND date BETWEEN :start AND :end '
        "AND data_source IN ('eodhd_eod','alpaca_sip') ORDER BY date,symbol").bindparams(bindparam('symbols',expanding=True))
    frame=pd.read_sql(query,conn,params=dict(symbols=symbols,start=start,end=end))
    if frame.empty:raise ValueError('Aucune barre daily canonique pour Winner')
    frame['date']=pd.to_datetime(frame.date)
    frame=select_daily_bars(frame)
    # A preferred but invalid row is not replaced by a different price feed.
    numeric=frame[['open','high','low','close','volume']].apply(pd.to_numeric,errors='coerce')
    valid=(numeric.gt(0).all(axis=1)&frame.is_filled.eq(0)&frame.data_adjustment.eq('split')
           &numeric.high.ge(numeric[['open','close']].max(axis=1))
           &numeric.low.le(numeric[['open','close']].min(axis=1)))
    return frame.loc[valid].copy()


class HistoricalFactorSource:
    """No refresh, CREATE, invented timestamps or current-cap historical fallback."""
    def __init__(self,conn,close):
        self.conn,self.close=conn,close
        self.cache={};self.receipts=[]

    def __call__(self,day,required,now,cfg):
        from risk_management.live_factor_context import qualify_factor_context
        required=tuple(sorted(set(required)))
        key=(day,required)
        if key not in self.cache:
            try:
                query=text('SELECT * FROM stock_risk_factor_inputs WHERE asof_date=:day '
                    'AND observed_at<=:cutoff ORDER BY observed_at DESC,id DESC')
                frame=pd.DataFrame([dict(r) for r in self.conn.execute(query,dict(day=day,
                    cutoff=pd.Timestamp(now).tz_convert('UTC').tz_localize(None).to_pydatetime())).mappings()])
                if frame.empty:raise ValueError(f'Aucun snapshot factoriel reçu avant décision pour {day}')
                frame['asof_date']=pd.to_datetime(frame.asof_date).dt.date
                proxies=self.close.loc[self.close.index<=pd.Timestamp(day),['SPY','IWM','MTUM']].tail(cfg.factor_lookback_days+1)
                returns=self.close.loc[self.close.index<=pd.Timestamp(day),list(required)].pct_change(fill_method=None).iloc[1:]
                candidates=frame.groupby(['run_id','universe_sha256'],sort=False)
                errors=[];context=None
                for _,part in candidates:
                    try:
                        context=qualify_factor_context(part,proxies,returns,required,day,now,cfg)
                        break
                    except ValueError as exc:errors.append(str(exc))
                if context is None:raise ValueError('; '.join(errors[:3]))
                self.cache[key]=context
                self.receipts.append(dict(day=str(day),symbols=list(required),qualified=True,
                    snapshot_hash=context['snapshot_hash'],observed_at=str(context['observed_at'])))
            except Exception as exc:
                self.cache[key]=str(exc)
                self.receipts.append(dict(day=str(day),symbols=list(required),qualified=False,error=str(exc)))
        cached=self.cache[key]
        if isinstance(cached,str):raise ValueError('Facteurs historiques non qualifiés : '+cached)
        # Same immutable archived observations, freshly read from the replay cache.
        return dict(cached,captured_at=now)


class HistoricalOptionsSource:
    """Use exact production features/selection, with genuine receipt cutoffs."""
    def __init__(self,conn,config):
        self.conn,self.config=conn,config
        self.receipts=[]

    def __call__(self,day,oracle,cutoff):
        from service.options_directional.history import read_options_evidence
        from service.options_directional.features import select_top
        from service.options_directional.store import digest
        oracle=oracle.rename(columns={'rank':'oracle_rank'}).to_dict('records')
        oracle=sorted(oracle,key=lambda r:(-float(r['proba_extreme']),r['symbol']))[:self.config.oracle_top_n]
        features,inputs=read_options_evidence(self.conn,[r['symbol'] for r in oracle],day,cutoff)
        rows=select_top(oracle,features,self.config)
        covered=sum(r['reason']!='MISSING_OR_STALE_OPTIONS' for r in rows)
        report=dict(trade_date=str(day),cutoff_utc=cutoff.isoformat(),rows=rows,
            selected=[r['symbol'] for r in rows if r['selected']],covered=covered,
            incomplete=covered<self.config.min_covered,inputs_sha256=digest(inputs))
        self.receipts.append(report)
        return report
