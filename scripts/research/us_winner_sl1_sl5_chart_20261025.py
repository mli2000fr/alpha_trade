"""Render verified daily capital curves without changing completed studies."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter,MaxNLocator
import numpy as np
import pandas as pd

OUTPUT=Path('artifacts/research/us_winner_sl1_sl5_visuals/20261025-v1')
CASES=[
    ('SL 1 %',Path('artifacts/research/us_winner_sl1_min70/20261025-v1'),
     'FIXED_SL1_H20_MIN70','#2176c1',.01,'--'),
    ('SL 5 %',Path('artifacts/research/us_winner_min70_4000/20261025-v1'),
     'FIXED_REFERENCE_MIN70','#cf6016',.05,'-'),
]


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def money(value):return f'{value:,.0f}'.replace(',',' ')


def main():
    series=[];sources={}
    for label,root,arm,color,stop,style in CASES:
        report=root/'report.json';payload=json.loads(report.read_text(encoding='utf-8'))
        if payload['status']!='COMPLETED_AUDITED_EXPLORATORY':raise ValueError('Incomplete study')
        case=payload['case'];folder=root/'cases'/arm
        if (case['initial_equity']!=4000. or case['minimum_notional']!=70.
                or case['actual_campaign_policy']['stop_loss_pct']!=stop):
            raise ValueError('Unexpected treatment')
        if case['audit']['status']!='PASS_EXPLICIT_DEPOSIT_CASH_FEES_SCALAR_EXITS_ENTRIES_COVERAGE':
            raise ValueError('Unaudited output')
        file=folder/'equity-daily.parquet'
        if digest(file)!=case['files'][file.name]:raise ValueError('Capital curve checksum mismatch')
        values=pd.read_parquet(file)['equity']
        values.index=pd.to_datetime(values.index)
        if values.index.has_duplicates or not values.index.is_monotonic_increasing or not np.isfinite(values).all():
            raise ValueError('Invalid daily curve')
        if not np.isclose(values.iloc[-1],case['final_equity'],atol=1e-7,rtol=0):
            raise ValueError('Final capital mismatch')
        sources[str(file)]=digest(file);sources[str(report)]=digest(report)
        series.append((label,values,color,style,case))
    if not series[0][1].index.equals(series[1][1].index):raise ValueError('Mismatched dates')
    OUTPUT.mkdir(parents=True,exist_ok=False)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,
        'axes.spines.right':False,'axes.edgecolor':'#bac3cf','axes.labelcolor':'#344054',
        'xtick.color':'#475467','ytick.color':'#475467','savefig.facecolor':'white'})
    fig,ax=plt.subplots(figsize=(12.8,7.2),dpi=160)
    fig.subplots_adjust(left=.09,right=.80,top=.78,bottom=.20)
    fig.text(.09,.945,'Évolution du capital : SL1 contre SL5',fontsize=21,weight='bold',color='#172b4d')
    fig.text(.09,.887,'TOP20 Oracle · 4 000 $ au départ · minimum par position : 70 $',fontsize=12,color='#344054')
    fig.text(.09,.85,'2020–2024 · sans levier · sans TP ni trailing · sortie après vingt séances',fontsize=11,color='#667085')
    for label,values,color,style,case in series:
        ax.plot(values.index,values.values,label=label,color=color,lw=1.7,linestyle=style)
        ax.plot(values.index[-1],values.iloc[-1],marker='o',color=color,ms=5)
        end=f'{label}  |  {money(values.iloc[-1])} $\n+{case["return_pct"]:.2f} %'.replace('.',',')
        ax.annotate(end,xy=(values.index[-1],values.iloc[-1]),xytext=(14,0),
            textcoords='offset points',va='center',ha='left',color=color,fontsize=12,weight='bold',
            annotation_clip=False)
    ax.axhline(4000.,color='#98a2b3',lw=1.,linestyle=':',zorder=0)
    ax.set_ylim(bottom=0)
    ax.set_xlim(series[0][1].index[0],series[0][1].index[-1])
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v,_:money(v)))
    ax.set_ylabel('Capital du portefeuille ($)',labelpad=12)
    ax.set_xlabel('Date',labelpad=12)
    ax.grid(axis='y',color='#e4e7ec',lw=.7);ax.set_axisbelow(True)
    ax.legend(loc='upper left',frameon=False,ncol=2)
    fig.text(.09,.095,'Capital valorisé à chaque clôture : liquidités + positions ouvertes. Frais inclus.',
        fontsize=10,color='#475467')
    fig.text(.09,.055,'Courbes quotidiennes réelles des replays archivés ; recherche exploratoire, pas une prévision.',
        fontsize=10,color='#667085')
    image=OUTPUT/'evolution-capital-sl1-sl5.png'
    vector=OUTPUT/'evolution-capital-sl1-sl5.svg'
    fig.savefig(image,dpi=160);fig.savefig(vector);plt.close(fig)
    receipt=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        source_script={str(Path(__file__)):digest(__file__)},observations_per_curve=len(series[0][1]),
        frequency='daily_close',currency='USD',includes_open_positions=True,fees_included=True,
        no_new_backtest=True,files={p.name:digest(p) for p in [image,vector]})
    (OUTPUT/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(str(image.resolve()))


if __name__=='__main__':main()
