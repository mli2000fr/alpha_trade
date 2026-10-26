"""Extend the completed-account chart after both pause20 audits, without reruns."""
from datetime import datetime,timezone
from pathlib import Path
import json

import numpy as np
import pandas as pd

from scripts.research import us_winner_completed_spy_chart_20261026 as prior

OUTPUT=Path('artifacts/research/us_winner_completed_spy_visuals/20261026-v2')
NEW=[('SL5 · pause20', 'us_winner_cycle15_pause20_min70/20261026-v1', '#148276', '-'),
     ('SL5 · pause20 / reprise SL1', 'us_winner_pause20_restart_sl1/20261026-v1', '#a47716', '--')]


def verify(mapping):
    for file,expected in mapping.items():
        if prior.digest(file)!=expected:raise ValueError(f'Archive checksum mismatch: {file}')


def main():
    series,summary,sources=prior.load_cases()
    reference_index=series[0][1].index
    for label,relative,color,style in NEW:
        root=Path('artifacts/research')/relative
        report=prior.read(root/'report.json');protocol=prior.read(root/'protocol.json')
        if report['status']!='COMPLETED_AUDITED_EXPLORATORY':raise ValueError('Incomplete replay')
        verify(report['sources']);verify(report['files'])
        case=report['case']
        if (case['start'],case['end'],case['initial_equity'],case['minimum_notional'])!=(
                '2020-01-02','2024-12-31',4000.,70.):raise ValueError('Account mismatch')
        if not case['audit']['status'].startswith('PASS_CYCLE15_PAUSE20'):raise ValueError('Missing pause audit')
        policies=([case['actual_campaign_policy']] if 'actual_campaign_policy' in case else
                  [protocol['normal_policy'],protocol['defensive_policy']])
        for p in policies:
            if p['stop_loss_pct'] not in [.01,.05] or (p['take_profit_pct'],p['trailing_stop_pct'],
                    p['horizon_sessions'],p['initial_position_fraction'],p['reinforcement_enabled'])!=(
                        None,None,20,1.,False):raise ValueError('Exit/entry policy drift')
        files=list((root/'cases').glob('*/equity-daily.parquet'))
        if len(files)!=1:raise ValueError('Ambiguous daily curve')
        file=files[0];verify({file:case['files'][file.name]})
        values=pd.read_parquet(file)['equity'];values.index=pd.to_datetime(values.index)
        if not values.index.equals(reference_index) or not np.isfinite(values).all() or (values<=0).any():
            raise ValueError('Mismatched calendar or invalid curve')
        np.testing.assert_allclose(values.iloc[-1],case['final_equity'],rtol=0,atol=1e-7)
        series.append((label,values,color,style))
        summary.append(dict(label=label,final_equity=case['final_equity'],return_pct=case['return_pct'],
            max_drawdown_intraday_pct=case['max_drawdown_pct'],source=str(root),win_pct=case['win_pct'],
            closed_lot_trades=case['closed_lot_trades']))
        for f in [root/'report.json',root/'protocol.json',file]:sources[str(f)]=prior.digest(f)
    comparison_path=Path('artifacts/research')/NEW[-1][1]/'comparison.json'
    comparison=prior.read(comparison_path)
    if comparison['status']!='READY' or comparison['pre_first_restart_curve_parity'] is not True:
        raise ValueError('Unfinished phase comparator')
    sources[str(comparison_path)]=prior.digest(comparison_path)
    spy,benchmark,spy_sources=prior.spy_curve(reference_index);sources.update(spy_sources)
    series.append(('SPY · hors dividendes',spy,'#424b57',':'))
    summary.append(dict(label=series[-1][0],final_equity=benchmark['final_equity'],
        return_pct=benchmark['return_pct'],max_drawdown_intraday_pct=None,source=benchmark['source']))
    OUTPUT.mkdir(parents=True,exist_ok=False)
    plt,mdates=prior.plt,prior.mdates
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'text.parse_math':False,
        'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#b8c1cd',
        'xtick.color':'#475467','ytick.color':'#475467','savefig.facecolor':'white'})
    fig,ax=plt.subplots(figsize=(15,11.5),dpi=155)
    fig.subplots_adjust(left=.085,right=.965,top=.745,bottom=.36)
    fig.text(.085,.95,'Évolution du capital — six variantes terminées et SPY',fontsize=21,weight='bold',color='#172b4d')
    fig.text(.085,.91,'02/01/2020 → 31/12/2024 · départ 4 000 $ · TOP20 LONG · sans levier · minimum 70 $',color='#344054')
    fig.text(.085,.875,'Positions complètes · sans TP ni trailing · détention 20 séances / sortie open21 · frais inclus',fontsize=11,color='#475467')
    for label,values,color,style in series:
        ax.plot(values.index,values.values,label=label,color=color,lw=1.6,linestyle=style)
    ax.axhline(4000.,color='#98a2b3',lw=.8,linestyle=':',zorder=0)
    ax.set_ylim(bottom=0);ax.set_xlim(reference_index[0],reference_index[-1])
    ax.xaxis.set_major_locator(mdates.YearLocator());ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.yaxis.set_major_locator(prior.MaxNLocator(nbins=6))
    ax.yaxis.set_major_formatter(prior.FuncFormatter(lambda v,_:f'{v:,.0f}'.replace(',',' ')))
    ax.set_ylabel('Capital valorisé ($)',labelpad=12);ax.set_xlabel('Date',labelpad=8)
    ax.grid(axis='y',color='#e4e7ec',lw=.7);ax.set_axisbelow(True)
    ax.legend(loc='lower left',bbox_to_anchor=(-.005,1.015),ncol=3,frameon=False,fontsize=10.5)
    fig.text(.085,.289,'Variante',color='#475467',fontsize=11)
    for x,title in [(.64,'Capital final'),(.79,'Rendement cumulé'),(.95,'DD maximal*')]:
        fig.text(x,.289,title,color='#475467',fontsize=11,ha='right')
    for i,((label,_,color,style),s) in enumerate(zip(series,summary)):
        y=.26-i*.025
        fig.lines.append(plt.Line2D([.085,.11],[y,y],transform=fig.transFigure,color=color,linestyle=style,lw=2))
        fig.text(.12,y,label,va='center',fontsize=11,color='#344054')
        fig.text(.64,y,prior.money(s['final_equity'])+' $',va='center',ha='right',fontsize=11,color='#344054')
        fig.text(.79,y,f"{s['return_pct']:+.2f} %".replace('.',','),va='center',ha='right',fontsize=11,color='#344054')
        dd=s['max_drawdown_intraday_pct']
        fig.text(.95,y,'—' if dd is None else f'{dd:.2f} %'.replace('.',','),va='center',ha='right',fontsize=11,color='#344054')
    fig.text(.085,.072,'Pause20 : 20 séances complètes après liquidation DD15. Reprise SL1 : SL1 sur les nouvelles entrées pendant 20 séances, puis SL5.',fontsize=10,color='#475467')
    fig.text(.085,.052,'* DD historique des replays mesuré en 5 minutes ; les courbes représentent les clôtures. DD15 de cycle ≠ plafond historique de 15 %. ',fontsize=10,color='#475467')
    fig.text(.085,.032,'SPY : cours hors dividendes, achat à l’ouverture initiale, frais d’entrée 0,08 %, position non liquidée. Recherche exploratoire, non vierge.',fontsize=10,color='#475467')
    image=OUTPUT/'variantes-terminees-et-spy.png';vector=OUTPUT/'variantes-terminees-et-spy.svg'
    fig.savefig(image,dpi=155);fig.savefig(vector);plt.close(fig)
    pd.DataFrame({label:values for label,values,_,_ in series}).to_csv(OUTPUT/'capital-daily.csv',index_label='date')
    pd.DataFrame(summary).to_csv(OUTPUT/'summary.csv',index=False)
    receipt=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        source_script={str(Path(__file__)):prior.digest(__file__),str(Path(prior.__file__)):prior.digest(prior.__file__)},
        benchmark=benchmark,summary=summary,frequency='daily_close',points=1258,initial_equity=4000.,
        no_new_backtest=True,full_live_parity=False,independent_holdout=False,
        files={p.name:prior.digest(p) for p in OUTPUT.iterdir() if p.is_file()})
    (OUTPUT/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(str(image.resolve()))


if __name__=='__main__':main()
