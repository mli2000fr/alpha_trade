"""Audit TOP20->LONG TOP5 membership, annual lineage and every replay cashflow."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

from scripts.research.us_selected_universe_per_symbol_selection_20261104 import OUT,ORACLE,PREVIOUS,select
from scripts.research.us_selected_universe_oracle_20261104 import CASES,POLICY,digest,save,nyse_sessions
from common.winner_pyramiding import regular_bounds


def csv(path):
    try:return pd.read_csv(path)
    except pd.errors.EmptyDataError:return pd.DataFrame()


def day(stamp):
    x=pd.Timestamp(stamp)
    return x.tz_convert('America/New_York').tz_localize(None).normalize() if x.tzinfo else x.normalize()


def verify_account(folder,chosen,allowed,horizon,intraday,winner=False,dd=False):
    r=json.loads((folder/'report.json').read_text())
    if intraday:assert all(digest(folder/f)==h for f,h in r['files'].items())
    d=csv(folder/'equity.csv');t=csv(folder/'trades.csv')
    assert len(t)==r['closed_trades']
    assert np.allclose(d.cash+d.gross,d.equity,rtol=0,atol=1e-7)
    assert d.cash.min()>=-1e-7 and (d.gross<=d.equity+1e-7).all()
    cal=nyse_sessions(pd.Timestamp('2023-12-01').date(),pd.Timestamp('2026-12-31').date())
    realized=0.;costs=0.;entries=[]
    for x in t.itertuples():
        ed,xd=day(x.entry_date),day(x.exit_date)
        signal=pd.Timestamp(x.signal_date)
        assert cal[cal.get_loc(ed)-1]==signal
        assert (signal,x.symbol) in chosen
        if intraday:assert (ed,x.symbol) in allowed
        assert 0<=cal.get_loc(xd)-cal.get_loc(ed)<=horizon
        assert x.quantity>0 and x.quantity==int(x.quantity)
        if x.reason=='TIME_OPEN':
            assert cal.get_loc(xd)-cal.get_loc(ed)==horizon
            if intraday:assert pd.Timestamp(x.exit_date)==pd.Timestamp(regular_bounds(xd.date())[0])
        if x.reason=='SL':assert np.isclose(x.exit_price,x.entry_price*.95)
        if x.reason=='SL_GAP':assert x.exit_price<=x.entry_price*.95+1e-8
        pnl=x.quantity*(x.exit_price*(1-POLICY['fee_per_leg'])-x.entry_price*(1+POLICY['fee_per_leg']))
        assert np.isclose(x.pnl,pnl,rtol=0,atol=1e-7)
        realized+=pnl;costs+=x.entry_cost+x.exit_cost
        entries.append((x.symbol,pd.Timestamp(x.entry_date),x.quantity,x.entry_price))
    unrealized=0.
    for x in r['open_positions']:
        ed=day(x['entry_date']);signal=cal[cal.get_loc(ed)-1]
        assert (signal,x['symbol']) in chosen
        if intraday:assert (ed,x['symbol']) in allowed
        unrealized+=x['quantity']*(x['mark']-x['entry_price']*(1+POLICY['fee_per_leg']))
        costs+=x['quantity']*x['entry_price']*POLICY['fee_per_leg']
        entries.append((x['symbol'],pd.Timestamp(x['entry_date']),x['quantity'],x['entry_price']))
    assert np.isclose(4000+realized+unrealized,r['final_equity'],rtol=0,atol=1e-7)
    assert np.isclose(costs,r['estimated_transaction_costs'],rtol=0,atol=1e-7)
    values=pd.read_parquet(folder/'marks.parquet') if intraday else d
    curve=np.r_[4000.,values.equity.to_numpy()]
    assert np.isclose(100*(curve[-1]/4000.-1),r['return_pct'])
    assert np.isclose(100*(curve/np.maximum.accumulate(curve)-1).min(),r['max_drawdown_pct'])
    if intraday:
        assert r['confirmation']==winner and r['dd15']==dd
        assert values.cash.min()>=-1e-7 and np.allclose(values.cash+values.gross,values.equity,atol=1e-7,rtol=0)
        orders=json.loads((folder/'confirmation-orders.json').read_text())
        filled=[o for o in orders if o['status']=='FILLED']
        if winner:
            assert len(filled)==r['buys']==len(entries)
            for o in filled:
                decision,fill=pd.Timestamp(o['decided_at']),pd.Timestamp(o['fill_time'])
                evidence=pd.Timestamp(o['evidence_last_end'])
                assert (decision-evidence).total_seconds()>=930 and fill>decision
                assert day(decision)==day(fill) and o['fill_price']<=o['ceiling']+1e-9
                assert o['reference']>o['prior_high']
                assert any(s==o['symbol'] and stamp==fill and q==o['filled_quantity'] and np.isclose(price,o['fill_price'])
                    for s,stamp,q,price in entries)
        else:
            assert not filled
            assert all(stamp==pd.Timestamp(regular_bounds(day(stamp).date())[0]) for _,stamp,_,_ in entries)
        for event in r['liquidation']['events']:
            assert dd and event['force_close_pct']==.5 and event['drawdown_at_detection_pct']<=-15+1e-6
            assert pd.Timestamp(event['executed_at'])>=pd.Timestamp(event['detected_at'])
            for s,q in event['quantities'].items():
                matched=t[t.symbol.eq(s)&t.reason.eq('GLOBAL_DD15')&pd.to_datetime(t.exit_date,utc=True).eq(pd.Timestamp(event['executed_at']))]
                assert len(matched)==1 and matched.iloc[0].quantity==q
    return dict(folder=str(folder),trades=len(t),report_sha256=digest(folder/'report.json'),status='PASS')


def main():
    protocol=json.loads((OUT/'protocol.json').read_text())
    selection=json.loads((OUT/'selection-report.json').read_text())
    assert all(digest(p)==h for p,h in protocol['sources'].items())
    assert all(digest(p)==h for p,h in selection['source_hashes'].items())
    models=json.loads((OUT/'models-reused.json').read_text())['models']
    assert len(models)==207
    for m in models:
        assert digest(m['model'])==m['model_sha256']
        assert pd.Timestamp(m['fit_label_available_max'])<pd.Timestamp(f"{m['year']-1}-01-01")
        assert pd.Timestamp(m['calibration_label_available_max'])<pd.Timestamp(f"{m['year']}-01-01")
    checks=[];coverage=[]
    arms={'BASE':(False,False),'WINNER':(True,False),'DD15':(False,True),'WINNER_DD15':(True,True)}
    for case,(horizon,_) in CASES.items():
        oracle=pd.read_parquet(ORACLE/case/'all-scores.parquet')
        probabilities=pd.read_parquet(OUT/case/'per-symbol-long-scores.parquet')
        joined=oracle.merge(probabilities,on=['date','symbol'],how='left',validate='one_to_one')
        pool,expected=select(joined)
        stored=pd.read_csv(OUT/case/'daily-top5.csv',parse_dates=['date'])
        assert expected[['date','symbol']].reset_index(drop=True).equals(stored[['date','symbol']])
        assert stored.groupby('date').size().eq(5).all() and stored.oracle_amplitude_rank.le(20).all()
        assert np.allclose(stored.long_probability,expected.long_probability,rtol=0,atol=1e-12)
        assert stored.oracle_rank.equals(stored.long_rank)
        proof=stored[['date','symbol','oracle_amplitude_rank','score','long_probability','long_rank',
            'model_year_per_symbol','model_sha256']].rename(columns={'score':'oracle_amplitude_score',
                'model_year_per_symbol':'per_symbol_model_year'})
        proof.to_csv(OUT/case/'selection-proof.csv',index=False)
        for method in ('ORACLE_TOP5','PER_SYMBOL_LONG_TOP5'):
            actual=stored if method=='PER_SYMBOL_LONG_TOP5' else pd.read_csv(ORACLE/case/'daily-top5.csv',parse_dates=['date'])
            keys=set(zip(actual.date,actual.symbol))
            gate=pd.read_csv(OUT/f'{case}-{method}-entry-quality.csv',parse_dates=['entry_date'])
            assert not gate.duplicated(['entry_date','symbol']).any()
            allowed=set(zip(gate[gate.eligible].entry_date,gate[gate.eligible].symbol))
            for year,g in gate.groupby(gate.entry_date.dt.year):
                coverage.append(dict(case=case,selection=method,year=int(year),proposed=len(g),
                    eligible=int(g.eligible.sum()),eligible_pct=float(100*g.eligible.mean())))
            for period in ('2024','2025','2026','continuous'):
                if method=='PER_SYMBOL_LONG_TOP5':
                    checks.append(verify_account(OUT/'daily'/case/period,keys,None,horizon,False))
                for arm,(winner,dd) in arms.items():
                    checks.append(verify_account(OUT/'intraday'/method/'runs'/case/period/arm,
                        keys,allowed,horizon,True,winner,dd))
                    if method=='ORACLE_TOP5':
                        before=json.loads((PREVIOUS/'runs'/case/period/arm/'report.json').read_text())
                        after=json.loads((OUT/'intraday'/method/'runs'/case/period/arm/'report.json').read_text())
                        for field in ('final_equity','return_pct','max_drawdown_pct','closed_trades','estimated_transaction_costs'):
                            assert np.isclose(before[field],after[field],rtol=0,atol=1e-8)
                for base,protected in [('BASE','DD15'),('WINNER','WINNER_DD15')]:
                    path=OUT/'intraday'/method/'runs'/case/period
                    a=pd.read_parquet(path/base/'marks.parquet');b=pd.read_parquet(path/protected/'marks.parquet')
                    r=json.loads((path/protected/'report.json').read_text())
                    events=r['liquidation']['events']
                    mask=(pd.to_datetime(a.timestamp,utc=True)<pd.Timestamp(events[0]['detected_at'])) if events else np.ones(len(a),bool)
                    assert a.timestamp.equals(b.timestamp)
                    assert np.allclose(a.loc[mask,'equity'],b.loc[mask,'equity'],rtol=0,atol=1e-7)
    assert len(checks)==72
    pd.DataFrame(checks).to_csv(OUT/'verification-cases.csv',index=False)
    pd.DataFrame(coverage).to_csv(OUT/'coverage-summary.csv',index=False)
    save(OUT/'verification.json',dict(status='PASS_WITH_RETROSPECTIVE_SELECTION_AND_COVERAGE_LIMITS',
        accounts=len(checks),trades_checked=sum(x['trades'] for x in checks),annual_models_verified=207,
        top20_before_top5_long_verified=True,execution_priority_is_long_score=True,
        predecessor_oracle_controls_reproduced=32,
        cached_model_probabilities_reproduced=selection['cached_predictions_reproduced'],
        no_future_label_required_for_inference=True,no_hindsight_in_daily_ranking=True,
        universe_selection_uses_2026=True,sql_writes=False,orders=0,
        independent_human_review=False,script_sha256=digest(__file__)))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(11,8),sharex=True)
    for ax,case in zip(axes,CASES):
        for root,label,color in [(ORACLE,'TOP5 Oracle seuls','#777777'),
            (OUT/'daily','TOP20 Oracle → TOP5 LONG per-symbol','#2677bb')]:
            p=root/case/'continuous/equity.csv' if root!=ORACLE else root/case/'continuous/equity.csv'
            a=pd.read_csv(p,parse_dates=['date'])
            ax.plot(a.date,a.equity,label=label,color=color,lw=1.5)
        ax.axhline(4000,color='#bbbbbb',ls='--',lw=.8)
        ax.set(title=('H10 — 32 titres' if case=='winner_h10' else 'H20 — 37 titres'),ylabel='Capital valorisé ($)')
        ax.grid(alpha=.2);ax.legend(fontsize=9)
    fig.suptitle('Replay daily — SL5 %, sans TP/trailing — 4 000 $, sans levier')
    fig.text(.5,.01,'Univers choisis avec les résultats de 2026 : comparaison rétrospective, pas validation indépendante',ha='center',fontsize=8)
    fig.tight_layout(rect=[0,.04,1,.96]);fig.savefig(OUT/'daily-comparison.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(11,8),sharex=True)
    colors={'BASE':'#777777','WINNER':'#2677bb','DD15':'#db9332','WINNER_DD15':'#159477'}
    labels={'BASE':'Sans confirmation/DD15','WINNER':'Confirmation Winner','DD15':'DD15/B4','WINNER_DD15':'Winner + DD15/B4'}
    for ax,case in zip(axes,CASES):
        for arm in arms:
            a=pd.read_csv(OUT/'intraday/PER_SYMBOL_LONG_TOP5/runs'/case/'continuous'/arm/'equity.csv',parse_dates=['date'])
            ax.plot(a.date,a.equity,label=labels[arm],color=colors[arm],lw=1.4)
        ax.axhline(4000,color='#bbbbbb',ls='--',lw=.8)
        ax.set(title=('H10 — TOP20 Oracle → TOP5 LONG' if case=='winner_h10' else 'H20 — TOP20 Oracle → TOP5 LONG'),ylabel='Capital valorisé ($)')
        ax.grid(alpha=.2);ax.legend(ncol=2,fontsize=8)
    fig.suptitle('Variantes intraday sur le même périmètre de données qualifiées')
    fig.text(.5,.01,'Couverture partielle et sélection rétrospective ; 4 000 $, sans levier, frais inclus',ha='center',fontsize=8)
    fig.tight_layout(rect=[0,.04,1,.96]);fig.savefig(OUT/'intraday-comparison.png',dpi=160);plt.close(fig)
    print(json.dumps(dict(status='PASS',accounts=len(checks),trades=sum(x['trades'] for x in checks))))


if __name__=='__main__':main()
