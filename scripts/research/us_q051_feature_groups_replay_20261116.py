"""Common frozen market tape and six native Winner replays for T0/A/B."""
from datetime import date,datetime,timezone
from functools import lru_cache
from pathlib import Path
import json
import time
from unittest.mock import patch

import numpy as np
import pandas as pd
from sqlalchemy import text,bindparam

from scripts.research.us_q051_feature_groups_20261116 import ROOT,PRICES,GROUPS,read,shared,no_http
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def prepare_market():
    from database.connection import get_sqlalchemy_engine
    from backtesting.winner_data import daily_bars
    from backtesting.winner_campaign_replay import SqlIntradaySource
    from backtesting.isolation import ReadOnlyReplay
    from common.config_loader import replay_market_registry
    from scripts.research.us_winner_vol20_extensions_20261109 import ExtendedPrices,ROOT as EXT
    inputs=ROOT/'inputs';inputs.mkdir(exist_ok=True)
    if (inputs/'manifest.json').exists():return
    pivots={c:pd.read_parquet(PRICES/'inputs'/(c+'.parquet')) for c in ['open','high','low','close','volume']}
    sectors=pd.read_parquet(PRICES/'inputs/sectors.parquet');actions=pd.read_parquet(PRICES/'inputs/actions.parquet')
    selections=[pd.read_parquet(ROOT/'variants'/v/'signals.parquet') for v in GROUPS]
    names=set().union(*(set(f.symbol) for f in selections));extra=sorted(names-set(pivots['close']))
    sessions=[d.date() for d in pivots['close'].index if date(2021,1,1)<=d.date()<=date(2026,10,1)]
    windows=shared.supplemental_windows(selections,sessions,set(),horizon=10)
    old=ExtendedPrices(EXT);tape=inputs/'intraday';tape.mkdir(exist_ok=True)
    engine=get_sqlalchemy_engine(db_name='alpha_trade');records=[]
    with ReadOnlyReplay(ROOT).install(),replay_market_registry(shared.restore_registry(shared.ROOT)),engine.connect() as conn,conn.begin():
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        if extra:
            pieces=[daily_bars(conn,extra[i:i+100],pivots['close'].index.min().date(),date(2026,10,1)) for i in range(0,len(extra),100)]
            daily=pd.concat(pieces,ignore_index=True)
            daily.to_parquet(inputs/'additional-daily.parquet',index=False)
            query=lambda sql:pd.read_sql(text(sql).bindparams(bindparam('symbols',expanding=True)),conn,params=dict(symbols=extra))
            sec=query('SELECT symbol,sector FROM stock_metadata WHERE symbol IN :symbols')
            ca=query("SELECT symbol,ca_type,ex_date,payable_date,amount_per_share,currency FROM corporate_actions_events WHERE symbol IN :symbols AND ex_date BETWEEN '2021-01-01' AND '2026-10-01'")
            for c in pivots:pivots[c]=pd.concat([pivots[c],daily.pivot(index='date',columns='symbol',values=c)],axis=1).sort_index()
            sectors=pd.concat([sectors,sec],ignore_index=True);actions=pd.concat([actions,ca],ignore_index=True)
        if set(names)-set(sectors.symbol):raise ValueError('New symbol sector identity missing')
        source=SqlIntradaySource(conn,discard_unqualified=True,allow_daily_fallback=True)
        for i,day in enumerate(sessions):
            path=tape/(str(day)+'.parquet');receipt=tape/(str(day)+'.json')
            if not receipt.exists():
                missing=sorted(windows[day]-set(old.day(day)))
                pieces=[source(day,missing[j:j+100]) for j in range(0,len(missing),100)]
                pieces=[f for f in pieces if not f.empty]
                f=pd.concat(pieces,ignore_index=True) if pieces else pd.DataFrame()
                f.to_parquet(path,index=False)
                atomic_json(receipt,dict(day=str(day),requested=missing,rows=len(f),provider_calls=0,SQL_writes=0))
            records.append(read(receipt))
            atomic_json(ROOT/'progress.json',dict(status='FREEZING_COMMON_MARKET_READ_ONLY',completed=i+1,total=len(sessions),last_date=str(day)))
    for c,f in pivots.items():f.to_parquet(inputs/(c+'.parquet'))
    sectors.to_parquet(inputs/'sectors.parquet',index=False);actions.to_parquet(inputs/'actions.parquet',index=False)
    atomic_json(inputs/'market-receipts.json',records)
    files={str(p):digest(p) for p in inputs.rglob('*') if p.is_file() and p.name!='manifest.json'}
    atomic_json(inputs/'manifest.json',dict(files=files,extra_daily_symbols=extra,SQL_writes=0,provider_calls=0))
    plan=read(ROOT/'protocol.json');sources=dict(plan['sources']);sources.update(files)
    # The native base runner is unchanged; only research-owned reference metadata
    # and the common signal/price inputs are supplied to it.
    from scripts.research import us_q051_features173_replay_20261116 as base
    sources[str(Path(base.__file__))]=digest(Path(base.__file__))
    for variant in GROUPS:
        vroot=ROOT/'variants'/variant;(vroot/'inputs').mkdir(exist_ok=True)
        from scripts.research.us_q051_features173_20261116 import link
        link(vroot/'signals.parquet',vroot/'inputs/signals.parquet')
        annual=read(vroot/'models.json')
        for y,item in annual.items():
            item['model_manifest_sha256']=digest(vroot/'models.json');item['model_protocol_sha256']=digest(ROOT/'protocol.json')
        source_signals=vroot/'inputs/signals.parquet'
        source_hashes={**sources,str(source_signals):digest(source_signals)}
        atomic_json(vroot/'replay-protocol.json',dict(start=plan['start'],end=plan['end'],initial_equity=4000.,
            annual_models=annual,reference=plan['reference'],sources=source_hashes,
            selection=plan['selection'],group=variant,research_features=plan['features'][variant],
            provider_calls=0,SQL_writes=0,orders=0,production_changes=False))


def market_data():
    return ({c:pd.read_parquet(ROOT/'inputs'/(c+'.parquet')) for c in ['open','high','low','close','volume']},
        pd.read_parquet(ROOT/'inputs/sectors.parquet'),pd.read_parquet(ROOT/'inputs/actions.parquet'))


def validate_case(folder):
    out=Path(folder)/'result';r=read(out/'report.json');m=pd.read_parquet(out/'equity-5m.parquet')
    t=pd.read_csv(out/'trades.csv');a=pd.read_csv(out/'annual-summary.csv')
    initial=pd.concat([pd.Series([4000.]),m.equity],ignore_index=True)
    if not np.isclose(100*(initial/initial.cummax()-1).min(),r['max_drawdown_pct']):raise ValueError('DD mismatch')
    if not np.isclose(4000*np.prod(1+a.return_pct/100),r['final_equity']):raise ValueError('Annual equity mismatch')
    if not (len(t)==r['closed_lot_trades'] and t.side.eq('buy').all()):raise ValueError('Trade count/side mismatch')
    if not np.allclose((t.exit_price-t.entry_price)*t.quantity-t.entry_fees-t.exit_fees+t.dividends,t.pnl):raise ValueError('Trade PnL mismatch')
    if read(Path(folder)/'isolation.json')['status']!='COMPLETED':raise ValueError('Incomplete isolation')
    return r


def run_case(name):
    from scripts.research import us_q051_features173_replay_20261116 as base
    from scripts.research import us_q051_vol20_regime_h5_20261115 as market
    from scripts.research.us_winner_vol20_extensions_20261109 import ExtendedPrices
    from ihm.services import backtesting_import
    variant=name.split('_',1)[0];vroot=ROOT/'variants'/variant;folder=vroot/'cases'/name
    class Tape(ExtendedPrices):
        @lru_cache(maxsize=6)
        def day(self,day):
            groups=dict(super().day(day));f=pd.read_parquet(ROOT/'inputs/intraday'/(str(day)+'.parquet'))
            for symbol,g in f.groupby('symbol') if not f.empty else []:
                if symbol in groups:raise ValueError('Intraday supplement would overwrite an existing cached group')
                groups[symbol]=g
            return groups
    original=backtesting_import.import_continuous_winner
    def deferred(source,**kw):
        # Fix research metadata before import; economic outputs are untouched.
        protocol=read(folder/'protocol.json');reference=protocol['reference']
        reference['directional_feature_count']=len(read(ROOT/'protocol.json')['features'][variant])
        reference['settings_profile']='Q051_FEATURE_GROUP_'+name
        reference['research_directional_contract']='LONG_ONLY_COMMON_FIT_ROWS'
        atomic_json(folder/'protocol.json',protocol)
        kw['run_id']='20261116_q051_feature_groups_'+name.lower();kw['label']='Q051 groupe '+variant+' — '+name+' — 2021–2026'
        validate_case(folder)
        atomic_json(folder/'import-ready.json',dict(run_id=kw['run_id'],arithmetic='PASS'))
        # Cross-process file lock serializes this campaign's history imports.
        import msvcrt
        with (ROOT/'history-import.lock').open('a+b') as lock:
            if lock.tell()==0:lock.write(b'0');lock.flush()
            while True:
                lock.seek(0)
                try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);break
                except OSError:time.sleep(1)
            try:return original(source,**kw)
            finally:
                lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
    with patch.object(base,'ROOT',vroot),patch.object(market,'market_data',market_data),\
            patch('scripts.research.us_winner_vol20_extensions_20261109.ExtendedPrices',Tape),\
            patch.object(backtesting_import,'import_continuous_winner',deferred):
        base.run_case(name)


def finish():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from ihm.services import backtesting_import
    rows=[];annual=[];checks=[];curves=[];ids=[]
    for variant in GROUPS:
        for profile in ['SIMPLE','VOL20_REGIME']:
            name=variant+'_'+profile;folder=ROOT/'variants'/variant/'cases'/name;out=folder/'result'
            r=read(out/'report.json');m=pd.read_parquet(out/'equity-5m.parquet');t=pd.read_csv(out/'trades.csv');a=pd.read_csv(out/'annual-summary.csv')
            e=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity
            initial=pd.concat([pd.Series([4000.]),m.equity],ignore_index=True)
            assert np.isclose(100*(initial/initial.cummax()-1).min(),r['max_drawdown_pct'])
            assert np.isclose(4000*np.prod(1+a.return_pct/100),r['final_equity'])
            assert len(t)==r['closed_lot_trades'] and t.side.eq('buy').all()
            assert np.allclose((t.exit_price-t.entry_price)*t.quantity-t.entry_fees-t.exit_fees+t.dividends,t.pnl)
            if read(folder/'isolation.json')['status']!='COMPLETED':raise ValueError('Incomplete replay isolation')
            checks.append(dict(case=name,arithmetic='PASS',coverage=r['status']))
            row={k:r.get(k) for k in ['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct','average_gross_capital','average_gross_equity_ratio','average_winning_pnl','average_losing_pnl']}
            rows.append(dict(case=name,variant=variant,profile=profile,**row));a['case']=name;annual.append(a)
            curves.append(e.rename(name))
            if not (folder/'ihm.json').exists():
                atomic_json(folder/'import-release.json',dict(released_at_utc=datetime.now(timezone.utc).isoformat()))
                start=time.monotonic()
                while not (folder/'ihm.json').exists():
                    if time.monotonic()-start>120:raise TimeoutError('History publication '+name)
                    time.sleep(1)
            ids.append(read(folder/'ihm.json')['run_id'])
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False);pd.concat(annual,ignore_index=True).to_csv(ROOT/'annual-comparison.csv',index=False)
    data=pd.concat(curves,axis=1);data.to_csv(ROOT/'capital-curves.csv');ax=data.plot(figsize=(13,7),title='Q051 — 24 variables seules / + marché / + volatilité')
    ax.set_ylabel('Capital valorisé ($)');ax.grid(alpha=.2);ax.figure.tight_layout();ax.figure.savefig(ROOT/'capital-comparison.png',dpi=140);plt.close(ax.figure)
    atomic_json(ROOT/'validation.json',dict(status='ARITHMETIC_CHECKS_PASS_RESEARCH_ONLY',checks=checks,
        price_reserves_inherited_from=str(PRICES/'validation.json'),full_live_parity=False,strict_pit=False))
    atomic_json(ROOT/'history.json',dict(status='PUBLISHED',run_ids=ids))
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',cases=rows,history_published=True))
