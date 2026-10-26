"""Plot completed fixed shadow accounts without changing active research outputs."""
from pathlib import Path
import hashlib
import json
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


ROOT=Path(__file__).resolve().parents[2]
CASES=ROOT/'artifacts/research/us_winner_monthly_selector/20261024-v1/cases'
OUTPUT=ROOT/'artifacts/research/us_winner_monthly_selector/charts-20261024-v1'
PROFILES=[
    ('SHADOW_SL5_TROFF_H20_TPOFF','Sans trailing','#1767a6'),
    ('SHADOW_SL5_TR15_H20_TPOFF','Trailing 15 %','#dc7a16'),
]


def number(value,decimals=0):
    return f'{value:,.{decimals}f}'.replace(',',' ').replace('.',',')


def main():
    curves=[]
    for name,label,color in PROFILES:
        folder=CASES/name
        report=json.loads((folder/'report.json').read_text(encoding='utf-8'))
        source=folder/'equity-daily.parquet'
        actual=hashlib.sha256(source.read_bytes()).hexdigest()
        if actual!=report['files']['equity-daily.parquet']:
            raise ValueError('Daily curve differs from the completed report')
        frame=pd.read_parquet(source)
        series=frame['equity']
        series.index=pd.to_datetime(series.index)
        if (report['status']!='COMPLETED_EXPLORATORY' or not series.index.is_unique
                or not series.index.is_monotonic_increasing or series.isna().any()
                or not math.isclose(float(series.iloc[-1]),report['final_equity'],abs_tol=1e-7)
                or report['initial_equity']!=4000 or report['start']!='2019-07-01'
                or report['end']!='2024-12-31'):
            raise ValueError('Curve/report contract invalid')
        curves.append((series,report,label,color))
    if not curves[0][0].index.equals(curves[1][0].index):
        raise ValueError('Non-comparable calendars')

    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,
        'axes.spines.right':False,'axes.spines.left':False,'axes.spines.bottom':False})
    fig,ax=plt.subplots(figsize=(14,7.8),facecolor='#f8fafc')
    fig.subplots_adjust(left=.085,right=.81,top=.77,bottom=.19)
    ax.set_facecolor('#f8fafc')
    fig.text(.085,.94,'Évolution du capital valorisé',fontsize=23,weight='bold',color='#152d43')
    fig.text(.085,.892,'Deux profils fixes préparatoires — pas encore les sélections mensuelles 30 / 50 séances',
             fontsize=12,color='#46586b')
    fig.text(.085,.847,'TOP20 Oracle • LONG • 01/07/2019 → 31/12/2024 • Capital initial : 4 000 $',
             fontsize=11,color='#46586b')

    for series,report,label,color in curves:
        ax.plot(series.index,series.values,color=color,lw=1.9,label=label,zorder=3)
        last=float(series.iloc[-1])
        ax.scatter(series.index[-1],last,color=color,s=32,zorder=4)
        ax.text(1.022,last,number(last,2)+' $',transform=ax.get_yaxis_transform(),
                color=color,weight='bold',fontsize=13,va='center',clip_on=False)
        ax.annotate('+'+number(report['return_pct'],2)+' % cumulés',xy=(1.022,last),
            xycoords=ax.get_yaxis_transform(),xytext=(0,-20),textcoords='offset points',
            fontsize=10,color=color,annotation_clip=False)

    ax.axhline(4000,color='#8292a3',lw=1,ls=(0,(4,4)),label='Capital initial : 4 000 $',zorder=1)
    ax.set_xlim(curves[0][0].index[0],curves[0][0].index[-1])
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda value,_:number(value)+' $'))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.grid(axis='y',color='#dce3eb',lw=.7,zorder=0)
    ax.tick_params(axis='both',length=0,labelcolor='#46586b',pad=9)
    ax.legend(loc='upper left',frameon=False,fontsize=10)
    fig.text(.085,.113,'Commun aux deux : SL 5 % • aucun TP • horizon 20 séances • positions complètes • sans levier',
             fontsize=10,color='#46586b')
    fig.text(.085,.077,'Frais inclus ; positions ouvertes valorisées à la clôture. Échelle linéaire. Capital continu, sans remise à zéro annuelle.',
             fontsize=9,color='#627185')
    fig.text(.085,.042,'Résultats exploratoires : biais de couverture future, secteurs actuels et univers survivant ; pas de garantie de performance.',
             fontsize=9,color='#627185')
    OUTPUT.mkdir(parents=True,exist_ok=True)
    target=OUTPUT/'capital-deux-profils-fixes-2019-2024.png'
    fig.savefig(target,dpi=170,facecolor=fig.get_facecolor())
    plt.close(fig)
    print(str(target))
    print(json.dumps({'sessions':len(curves[0][0]),'final_equities':[r['final_equity'] for _,r,_,_ in curves],
        'source_hashes_verified':True,'active_run_outputs_changed':False}))


if __name__=='__main__':
    main()
