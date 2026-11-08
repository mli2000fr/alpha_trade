"""Verify archived models, chronology, trade barriers, accounting and output curves."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import lightgbm as lgb

from scripts.research.us_selected_universe_oracle_20261104 import (
    OUT, BASE, INPUTS, END, POLICY, CASES, digest, save, split_year,
    freeze_top, prepare_prices, summarize_portfolio, replay, nyse_sessions)
from common.daily_bar_sources import select_daily_bars


def main():
    protocol=json.loads((OUT/'protocol.json').read_text())
    report=json.loads((OUT/'report.json').read_text())
    assert report['trained_models']==6 and report['portfolio_replays']==8
    assert report['universe_selection_uses_2026']
    assert all(digest(p)==h for p,h in protocol['source_hashes'].items())
    calendar=nyse_sessions(pd.Timestamp('2016-01-01').date(),END.date())
    verified=[]
    score_rows=0
    for case,(horizon,count) in CASES.items():
        folder=OUT/case
        sources=json.loads((folder/'source-hashes.json').read_text())
        assert all(digest(p)==h for p,h in sources.items())
        dataset=pd.read_parquet(folder/'dataset.parquet')
        scores=pd.read_parquet(folder/'all-scores.parquet')
        training=json.loads((folder/'training-report.json').read_text())
        universe=report['cases'][case]['universe']
        assert dataset.symbol.nunique()==count and set(dataset.symbol)==set(universe)
        assert not dataset.duplicated(['date','symbol']).any()
        for record in training['models']:
            year=record['year']
            target=f'oracle_path_extreme{horizon}'
            # Use the actual recorded target name, not an assumed name variant.
            targets=[c for c in dataset if c.startswith('oracle_path_extreme')]
            assert len(targets)==1
            train,val,test=split_year(dataset,year,targets[0])
            assert train.oracle_available_date.max()<pd.Timestamp(f'{year-1}-01-01')
            assert val.oracle_available_date.max()<pd.Timestamp(f'{year}-01-01')
            assert train.date.max()<val.date.min() and val.date.max()<test.date.min()
            assert digest(record['model'])==record['model_sha256']
            model=lgb.Booster(model_file=record['model'])
            expected=scores[scores.model_year.eq(year)]
            assert expected[['date','symbol']].reset_index(drop=True).equals(test[['date','symbol']].reset_index(drop=True))
            actual=model.predict(test[INPUTS],num_threads=2)
            assert np.allclose(actual,expected.score,rtol=0,atol=1e-12)
            score_rows+=len(actual)
        top=freeze_top(scores)
        original=pd.read_csv(folder/'daily-top5.csv',parse_dates=['date'])
        assert top[['date','symbol']].reset_index(drop=True).equals(original[['date','symbol']])
        assert top.groupby('date').size().le(5).all()
        keys=set(zip(top.date,top.symbol))
        raw={s:select_daily_bars(pd.read_parquet(BASE/'symbols'/s/'source-bars.parquet'))
             for s in universe}
        prices=prepare_prices(raw,calendar)
        for period in ('2024','2025','2026','continuous'):
            p=folder/period
            r=json.loads((p/'report.json').read_text())
            d=pd.read_csv(p/'equity.csv',parse_dates=['date'])
            t=pd.read_csv(p/'trades.csv',parse_dates=['entry_date','exit_date','signal_date'])
            exclusions=pd.read_csv(p/'missing-entry-days.csv',parse_dates=['date'])
            quality=[]
            for excluded in exclusions.itertuples():
                i=calendar.get_loc(excluded.date)
                last=min(i+horizon,calendar.get_loc(pd.Timestamp(r['end'])))
                values,good,identities,providers=prices[excluded.symbol]
                window=slice(i,last+1)
                reasons=[]
                if not good[window].all():reasons.append('INVALID_OR_MISSING_OHLCV')
                if len(set(identities[window]))!=1:reasons.append('IDENTITY_CHANGE')
                if len(set(providers[window]))!=1:reasons.append('PROVIDER_CHANGE')
                assert reasons
                quality.append(dict(symbol=excluded.symbol,entry_date=excluded.date,
                    last_checked_date=calendar[last],reason=';'.join(reasons),
                    providers=';'.join(sorted(set(map(str,providers[window])))),
                    missing_dates=';'.join(str(d.date()) for d in calendar[i:last+1][~good[window]])))
            pd.DataFrame(quality,columns=['symbol','entry_date','last_checked_date','reason','providers','missing_dates']).to_csv(
                p/'data-quality-entry-exclusions.csv',index=False)
            assert d.date.is_monotonic_increasing and d.date.is_unique
            assert (d.cash>=-1e-7).all() and (d.gross<=d.equity+1e-7).all()
            assert np.allclose(d.cash+d.gross,d.equity,rtol=0,atol=1e-7)
            for trade in t.itertuples():
                entry=calendar.get_loc(trade.entry_date)
                exit=calendar.get_loc(trade.exit_date)
                assert calendar[entry-1]==trade.signal_date
                assert (trade.signal_date,trade.symbol) in keys
                assert 0<=exit-entry<=horizon
                assert trade.quantity>0 and trade.quantity==int(trade.quantity)
                bars=prices[trade.symbol][0]
                assert np.isclose(trade.entry_price,bars[entry,0])
                floor=trade.entry_price*.95
                hits=[i for i in range(entry,min(entry+horizon,exit+1)) if bars[i,2]<=floor]
                if trade.reason=='TIME_OPEN':
                    assert exit-entry==horizon and not hits
                    assert np.isclose(trade.exit_price,bars[exit,0])
                else:
                    assert hits and hits[0]==exit
                    assert np.isclose(trade.exit_price,min(bars[exit,0],floor))
                basis=trade.quantity*trade.entry_price*(1+POLICY['fee_per_leg'])
                proceeds=trade.quantity*trade.exit_price*(1-POLICY['fee_per_leg'])
                assert np.isclose(proceeds-basis,trade.pnl,rtol=0,atol=1e-7)
            assert np.isclose(t.pnl.sum(),r['realized_pnl'],rtol=0,atol=1e-7)
            unrealized=sum(pos['quantity']*(pos['mark']-pos['entry_price']*(1+POLICY['fee_per_leg']))
                for pos in r['open_positions'])
            assert np.isclose(4000+t.pnl.sum()+unrealized,r['final_equity'],rtol=0,atol=1e-7)
            expected=summarize_portfolio(d.to_dict('records'),t.to_dict('records'),4000.,
                r['open_positions'],r['estimated_transaction_costs'])
            for field in ('return_pct','max_drawdown_pct','win_pct','average_gross_capital'):
                assert np.isclose(expected[field],r[field],rtol=0,atol=1e-9)
            # Full deterministic rerun also verifies cash timing/open holdings.
            again,again_daily,again_trades,again_audit=replay(top,prices,calendar,r['start'],r['end'],horizon)
            assert np.isclose(again['final_equity'],r['final_equity'],rtol=0,atol=1e-9)
            assert len(again_trades)==len(t) and np.allclose(again_daily.equity,d.equity,atol=1e-8,rtol=0)
            verified.append(dict(case=case,period=period,trades=len(t),status=r['status'],
                quality_exclusion_counts=pd.Series([x['reason'] for x in quality],dtype=str).value_counts().to_dict(),
                report_sha256=digest(p/'report.json'),daily_sha256=digest(p/'equity.csv'),
                trades_sha256=digest(p/'trades.csv')))
    save(OUT/'verification.json',dict(status='PASS',models=6,predictions_reproduced=score_rows,
        portfolios=verified,trade_count=sum(x['trades'] for x in verified),
        source_hashes_unchanged=True,causal_model_dates=True,top5_reproduced=True,
        complete_replays_reproduced=True,cash_pnl_and_barriers_verified=True,
        independent_human_review=False,full_live_parity=False,
        script_sha256=digest(__file__)))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(11,5))
    for case,label,color in [('winner_h10','32 titres — Oracle H10 / sortie open11','#2677bb'),
        ('parcours_h20','37 titres — Oracle H20 / sortie open21','#159477')]:
        d=pd.read_csv(OUT/case/'continuous/equity.csv',parse_dates=['date'])
        ax.plot(d.date,d.equity,label=label,color=color,lw=1.6)
    ax.axhline(4000,color='#888888',ls='--',lw=.8)
    ax.set(title='TOP5 LONG quotidiens — SL5 %, sans TP ni trailing — sans levier',
        ylabel='Capital valorisé ($)',xlabel='Univers sélectionnés avec les résultats 2026 : simulation rétrospective')
    ax.grid(alpha=.2)
    ax.legend(loc='upper left')
    fig.tight_layout()
    fig.savefig(OUT/'capital-continuous.png',dpi=160)
    plt.close(fig)
    print(json.dumps(dict(status='PASS',models=6,predictions_reproduced=score_rows,
        portfolios=len(verified),trades=sum(x['trades'] for x in verified))))


if __name__=='__main__':
    main()
