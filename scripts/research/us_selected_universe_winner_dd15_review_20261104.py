"""Review matched replay cashflows, event chronology, source seals and coverage."""
import json
import gzip
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.research.us_selected_universe_winner_dd15_20261104 import OUT,PRIOR,ARMS,CASES,POLICY,digest,save
from common.winner_pyramiding import regular_bounds
from modelFactory.oracle.build_labels import nyse_sessions


def ny_day(stamp):
    return pd.Timestamp(stamp).tz_convert('America/New_York').tz_localize(None).normalize()


def main():
    protocol=json.loads((OUT/'protocol.json').read_text())
    assert all(digest(p)==h for p,h in protocol['sources'].items())
    final=json.loads((OUT/'report.json').read_text())
    assert final['runs']==32
    calendar=nyse_sessions(pd.Timestamp('2023-12-01').date(),pd.Timestamp('2026-12-31').date())
    checks=[];coverage=[]
    recovery=json.loads((OUT/'recovery/report.json').read_text())
    response_bodies=0
    for item in recovery['cases']:
        for page in item['pages']:
            body=gzip.decompress((OUT/'recovery'/item['symbol']/page['file']).read_bytes())
            assert hashlib.sha256(body).hexdigest()==page['sha256']
            response_bodies+=1
    for case,(horizon,_) in CASES.items():
        top=pd.read_csv(PRIOR/case/'daily-top5.csv',parse_dates=['date'])
        selected=set(zip(top.date,top.symbol))
        gates=pd.read_csv(OUT/f'{case}-matched-entry-quality.csv',parse_dates=['entry_date'])
        assert not gates.duplicated(['entry_date','symbol']).any()
        allowed=set(zip(gates[gates.eligible].entry_date,gates[gates.eligible].symbol))
        for year,g in gates.groupby(gates.entry_date.dt.year):
            coverage.append(dict(case=case,year=int(year),proposed=len(g),eligible=int(g.eligible.sum()),
                eligible_pct=float(100*g.eligible.mean())))
        for period in ('2024','2025','2026','continuous'):
            for arm,(winner,dd) in ARMS.items():
                folder=OUT/'runs'/case/period/arm
                r=json.loads((folder/'report.json').read_text())
                assert r['confirmation']==winner and r['dd15']==dd
                assert all(digest(folder/f)==h for f,h in r['files'].items())
                try:t=pd.read_csv(folder/'trades.csv')
                except pd.errors.EmptyDataError:t=pd.DataFrame(columns=['pnl','entry_cost','exit_cost'])
                d=pd.read_csv(folder/'equity.csv')
                m=pd.read_parquet(folder/'marks.parquet')
                assert len(t)==r['closed_trades']
                assert np.allclose(m.cash+m.gross,m.equity,rtol=0,atol=1e-7)
                assert m.cash.min()>=-1e-7 and (m.gross<=m.equity+1e-7).all()
                curve=np.r_[4000.,m.equity.to_numpy()]
                assert np.isclose(100*(curve[-1]/4000.-1),r['return_pct'])
                assert np.isclose(100*(curve/np.maximum.accumulate(curve)-1).min(),r['max_drawdown_pct'])
                assert np.isclose(d.equity.iloc[-1],r['final_equity'])
                expected_pnl=0.
                entries=[]
                for row in t.itertuples():
                    assert row.quantity>0 and row.quantity==int(row.quantity)
                    entry=pd.Timestamp(row.entry_date);exit=pd.Timestamp(row.exit_date)
                    assert entry.tzinfo is not None and exit>=entry
                    ed,xd=ny_day(entry),ny_day(exit)
                    signal=pd.Timestamp(row.signal_date)
                    assert calendar[calendar.get_loc(ed)-1]==signal
                    assert (signal,row.symbol) in selected and (ed,row.symbol) in allowed
                    assert 0<=calendar.get_loc(xd)-calendar.get_loc(ed)<=horizon
                    if row.reason=='TIME_OPEN':
                        assert calendar.get_loc(xd)-calendar.get_loc(ed)==horizon
                        assert exit==pd.Timestamp(regular_bounds(xd.date())[0])
                    if row.reason=='SL':assert np.isclose(row.exit_price,row.entry_price*.95)
                    if row.reason=='SL_GAP':assert row.exit_price<=row.entry_price*.95+1e-8
                    if not winner:assert entry==pd.Timestamp(regular_bounds(ed.date())[0])
                    pnl=row.quantity*(row.exit_price*(1-POLICY['fee_per_leg'])-row.entry_price*(1+POLICY['fee_per_leg']))
                    assert np.isclose(pnl,row.pnl,rtol=0,atol=1e-7)
                    expected_pnl+=pnl
                    entries.append((row.symbol,entry,row.quantity,row.entry_price))
                unrealized=0.
                for row in r['open_positions']:
                    entry=pd.Timestamp(row['entry_date']);ed=ny_day(entry)
                    signal=calendar[calendar.get_loc(ed)-1]
                    assert (signal,row['symbol']) in selected and (ed,row['symbol']) in allowed
                    unrealized+=row['quantity']*(row['mark']-row['entry_price']*(1+POLICY['fee_per_leg']))
                    entries.append((row['symbol'],entry,row['quantity'],row['entry_price']))
                assert np.isclose(4000+expected_pnl+unrealized,r['final_equity'],rtol=0,atol=1e-7)
                costs=float(t.entry_cost.sum()+t.exit_cost.sum())+sum(
                    row['quantity']*row['entry_price']*POLICY['fee_per_leg'] for row in r['open_positions'])
                assert np.isclose(costs,r['estimated_transaction_costs'],rtol=0,atol=1e-7)
                orders=json.loads((folder/'confirmation-orders.json').read_text())
                filled=[o for o in orders if o['status']=='FILLED']
                if winner:
                    assert len(filled)==r['buys']==len(entries)
                    for order in filled:
                        decision=pd.Timestamp(order['decided_at']);fill=pd.Timestamp(order['fill_time'])
                        evidence=pd.Timestamp(order['evidence_last_end'])
                        assert (decision-evidence).total_seconds()>=930
                        assert fill>decision and ny_day(fill)==ny_day(decision)
                        assert order['fill_price']<=order['ceiling']+1e-9
                        assert 0<order['filled_quantity']<=order['quantity']
                        assert order['reference']>order['prior_high']
                        assert any(s==order['symbol'] and stamp==fill and qty==order['filled_quantity']
                            and np.isclose(price,order['fill_price']) for s,stamp,qty,price in entries)
                else:assert not filled
                events=r['liquidation']['events']
                global_trades=t[t.reason.eq('GLOBAL_DD15')] if len(t) else t
                if not dd:assert not events and global_trades.empty
                for event in events:
                    assert event['force_close_pct']==.5
                    assert pd.Timestamp(event['executed_at'])>=pd.Timestamp(event['detected_at'])
                    assert event['drawdown_at_detection_pct']<=-15+1e-6
                    for symbol,quantity in event['quantities'].items():
                        matches=global_trades[global_trades.symbol.eq(symbol)&pd.to_datetime(
                            global_trades.exit_date,utc=True).eq(pd.Timestamp(event['executed_at']))]
                        assert len(matches)==1 and matches.iloc[0].quantity==quantity
                checks.append(dict(case=case,period=period,arm=arm,trades=len(t),
                    filled_confirmation_orders=len(filled),dd_trips=len(events),global_liquidation_trades=len(global_trades),
                    report_sha256=digest(folder/'report.json')))
            # DD is the only changing mechanism: pre-trip paths must coincide.
            for original,protected in [('BASE','DD15'),('WINNER','WINNER_DD15')]:
                a=pd.read_parquet(OUT/'runs'/case/period/original/'marks.parquet')
                b=pd.read_parquet(OUT/'runs'/case/period/protected/'marks.parquet')
                r=json.loads((OUT/'runs'/case/period/protected/'report.json').read_text())
                events=r['liquidation']['events']
                before=(pd.to_datetime(a.timestamp,utc=True)<pd.Timestamp(events[0]['detected_at'])) if events else np.ones(len(a),bool)
                assert a.timestamp.equals(b.timestamp)
                assert np.allclose(a.loc[before,'equity'],b.loc[before,'equity'],rtol=0,atol=1e-7)
    pd.DataFrame(coverage).to_csv(OUT/'coverage-summary.csv',index=False)
    pd.DataFrame(checks).to_csv(OUT/'verification-cases.csv',index=False)
    save(OUT/'verification.json',dict(status='PASS_WITH_MATERIAL_COVERAGE_LIMIT',cases=checks,
        portfolios=32,closed_trades_checked=sum(c['trades'] for c in checks),cash_and_fees_verified=True,
        next_session_entries_verified=True,confirmation_delay_and_ioc_verified=True,
        native_dd15_event_journal_verified=True,source_hashes_unchanged=True,
        unchanged_until_first_dd_trip=True,provider_response_bodies_verified=response_bodies,
        complete_universe_backtest=False,independent_validation=False,independent_human_review=False,
        script_sha256=digest(__file__)))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(11,8),sharex=True)
    labels={'BASE':'Référence intraday','WINNER':'Confirmation Winner','DD15':'DD15 / B4',
        'WINNER_DD15':'Winner + DD15 / B4'}
    colors={'BASE':'#777777','WINNER':'#2677bb','DD15':'#db9332','WINNER_DD15':'#159477'}
    for ax,case in zip(axes,CASES):
        for arm in ARMS:
            d=pd.read_csv(OUT/'runs'/case/'continuous'/arm/'equity.csv',parse_dates=['date'])
            ax.plot(d.date,d.equity,label=labels[arm],color=colors[arm],lw=1.4)
        ax.axhline(4000,color='#aaaaaa',ls='--',lw=.8)
        ax.set(title=('32 titres — H10' if case=='winner_h10' else '37 titres — H20'),ylabel='Capital valorisé ($)')
        ax.grid(alpha=.2);ax.legend(ncol=2,fontsize=9)
    fig.suptitle('TOP5 LONG — comparaison sur fenêtres intraday qualifiées uniquement',fontsize=13)
    fig.text(.5,.01,'Univers sélectionnés avec 2026 ; couverture partielle ; 4 000 $ sans levier, frais inclus',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.035,1,.96])
    fig.savefig(OUT/'comparison-continuous.png',dpi=160)
    print(json.dumps(dict(status='PASS_WITH_MATERIAL_COVERAGE_LIMIT',runs=32,
        trades=sum(c['trades'] for c in checks))))


if __name__=='__main__':main()
