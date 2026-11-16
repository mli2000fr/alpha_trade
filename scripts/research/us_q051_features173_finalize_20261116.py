"""Independent arithmetic/observed-price checks and serialized history publication."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import time
import json

import numpy as np
import pandas as pd

from scripts.research.us_q051_features173_sip_replay_20261116 import ROOT,RAW,CASES,provider_frame
from scripts.research.us_q051_features173_20261116 import read
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def publish(folder,name):
    case=folder/'cases'/name
    if not (case/'ihm.json').is_file():
        if not (case/'import-ready.json').is_file():raise ValueError('Case not ready for publication: '+str(case))
        atomic_json(case/'import-release.json',dict(released_at_utc=datetime.now(timezone.utc).isoformat()))
        start=time.monotonic()
        while not (case/'ihm.json').is_file():
            if time.monotonic()-start>120:raise TimeoutError('History import did not finish: '+name)
            time.sleep(1)
    return read(case/'ihm.json')['run_id']


def annotate_history(ids,raw=False):
    from ihm.services import backtesting_registry as registry
    warning=('PRIX NON QUALIFIÉS : anciens niveaux DD incohérents ; bilan brut non utilisable pour choisir un modèle.' if raw
        else 'Prix recoupés SIP sur les titres signalés ; signaux et modèles figés. Lire le périmètre et les réserves de qualification.')
    validation={} if raw else read(ROOT/'validation.json')
    qualifications={}
    for rid in ids:
        folder=registry.RUNS_DIR/'run'/rid
        file=folder/'artifacts/report.json';r=read(file)
        case=read(folder/'artifacts/source-report.json').get('case')
        qualification=('FAILED_PRICE_BASIS' if raw else validation.get('case_qualification',{}).get(case,validation['status']))
        qualifications[rid]=qualification
        limitations=r.setdefault('limitations',[])
        if warning not in limitations:limitations.insert(0,warning)
        r.setdefault('diagnostics',{})['price_qualification']=qualification
        r.setdefault('run_metadata',{})['price_qualification_report']=str((RAW/'price-quality-incident.json') if raw else (ROOT/'validation.json'))
        atomic_json(file,r)
    with registry._REGISTRY_LOCK:
        records=registry._read_history_index()
        for rid in ids:
            if rid not in records:raise ValueError('Missing history entry: '+rid)
            if raw and not str(records[rid].get('run_label','')).startswith('⚠ BRUT'):
                records[rid]['run_label']='⚠ BRUT — prix non qualifiés — '+str(records[rid].get('run_label',''))
            if not raw and qualifications[rid]=='ARITHMETIC_PASS_PRICE_RESERVES_REMAIN' and not str(records[rid].get('run_label','')).startswith('⚠ RÉSERVE'):
                records[rid]['run_label']='⚠ RÉSERVE TOELY — '+str(records[rid].get('run_label',''))
            records[rid]['price_qualification']=qualifications[rid]
        registry._write_history_index(records)


def mark_raw():
    ids=[publish(RAW,name) for name in CASES]
    annotate_history(ids,raw=True)
    atomic_json(RAW/'history-price-warning.json',dict(status='RAW_HISTORIES_MARKED_UNQUALIFIED',run_ids=ids))


def observed_windows(trades,events,end):
    """Audit final open lots too; a marked holding need not be a closed trade."""
    windows=trades[['symbol','entry_date','exit_date','quantity']].copy()
    windows['open_at_end']=False
    closed=trades.assign(entry_date=pd.to_datetime(trades.entry_date,utc=True)).groupby(['symbol','entry_date']).quantity.sum()
    buys=events.loc[events.event.eq('BUY_FILL')].copy()
    buys['entry_date']=pd.to_datetime(buys.time,utc=True)
    rows=[]
    for (symbol,entered),g in buys.groupby(['symbol','entry_date']):
        remaining=float(g.quantity.sum())-float(closed.get((symbol,entered),0.))
        if remaining < -1e-7:raise ValueError('Closed quantity exceeds its entry')
        if remaining>1e-7:
            rows.append(dict(symbol=symbol,entry_date=entered,exit_date=end,quantity=remaining,open_at_end=True))
    if rows:windows=pd.concat([windows,pd.DataFrame(rows)],ignore_index=True)
    return windows


def compare():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    old_result=(ROOT/'results.md').read_text(encoding='utf-8') if (ROOT/'results.md').is_file() else None
    labels={'SIMPLE':'173 — témoin','VOL20_REGIME':'173 — vol20 + régime',
        'CONTROL_SIMPLE':'24 — témoin recalculé','CONTROL_VOL20_REGIME':'24 — vol20 + régime recalculé'}
    colors={'SIMPLE':'#2563eb','VOL20_REGIME':'#7c3aed','CONTROL_SIMPLE':'#15803d','CONTROL_VOL20_REGIME':'#0f766e'}
    columns=['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct','winners','losers',
        'average_winning_pnl','average_losing_pnl','average_winning_holding_days','average_losing_holding_days',
        'average_gross_capital','maximum_gross_capital','average_gross_equity_ratio','costs','margin_interest']
    inputs=ROOT/'inputs';plan=read(ROOT/'replay-protocol.json')
    for file,h in plan['sources'].items():
        if digest(Path(file))!=h:raise ValueError('Sealed source changed: '+file)
    for file in ['signals.parquet','control-signals.parquet']:
        if digest(inputs/file)!=digest(RAW/'inputs'/file):raise ValueError('Signal selection changed during price requalification')
    evidence={read(p)['symbol']:provider_frame(p) for p in (ROOT/'evidence').glob('*.json')}
    checks=[];rows=[];annual=[];curves=[];reserves=[];big_trades=[];window_audits=[]
    fig,(ax,ddax)=plt.subplots(2,1,figsize=(13,9),sharex=True,gridspec_kw={'height_ratios':[2,1]})
    for name in CASES:
        folder=ROOT/'cases'/name;out=folder/'result'
        if read(folder/'progress.json').get('status')!='COMPLETED_EXPLORATORY':raise ValueError('Incomplete replay: '+name)
        if read(folder/'isolation.json').get('status')!='COMPLETED':raise ValueError('Isolation unfinished')
        r=read(out/'report.json');e=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity
        m=pd.read_parquet(out/'equity-5m.parquet');t=pd.read_csv(out/'trades.csv');a=pd.read_csv(out/'annual-summary.csv')
        cfg=read(out/'configuration.json')['portfolio'];old=read(RAW/'cases'/name/'result/configuration.json')['portfolio']
        if cfg!=old:raise ValueError('Portfolio conditions changed')
        v=pd.concat([pd.Series([4000.]),m.equity],ignore_index=True);dd=100*(v/v.cummax()-1).min()
        assert np.isclose(dd,r['max_drawdown_pct'],atol=1e-9)
        assert np.isclose(4000*np.prod(1+a.return_pct/100),r['final_equity'],atol=1e-6)
        assert np.isclose(e.iloc[-1],r['final_equity'],atol=1e-7)
        assert len(t)==r['closed_lot_trades'] and int(t.pnl.gt(0).sum())==r['winners']
        assert t.side.eq('buy').all()
        equation=(t.exit_price-t.entry_price)*t.quantity-t.entry_fees-t.exit_fees+t.dividends
        if not np.allclose(equation,t.pnl,atol=1e-6,rtol=1e-9):raise ValueError('Closed-trade cashflow equation differs')
        if not np.isclose(m.gross.mean(),r['average_gross_capital'],atol=1e-7):raise ValueError('Average capital differs')
        events=pd.read_csv(out/'events.csv')
        windows=observed_windows(t,events,pd.Timestamp(e.index[-1]).tz_localize('America/New_York')+pd.Timedelta(hours=16))
        entered=pd.to_datetime(windows.entry_date,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
        exited=pd.to_datetime(windows.exit_date,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
        windows['case']=name;window_audits.append(windows)
        # Never invent the Qnity entitlement for a DD position crossing its distribution.
        cross=windows.symbol.eq('DD')&entered.lt('2025-11-03')&exited.ge('2025-11-03')
        for i in windows.index[cross]:reserves.append(dict(case=name,symbol='DD',entry=str(entered[i].date()),exit=str(exited[i].date()),reason='UNQUALIFIED_QNITY_ENTITLEMENT'))
        uncertain=windows.symbol.eq('TOELY')&exited.ge('2026-07-13')
        for i in windows.index[uncertain]:reserves.append(dict(case=name,symbol='TOELY',entry=str(entered[i].date()),exit=str(exited[i].date()),reason='UNSUPPORTED_ADR_BASIS'))
        flagged=set(plan['price_requalification']['pre_existing_flags'])
        for symbol,g in windows.groupby('symbol'):
            if symbol not in flagged:continue
            if symbol not in evidence or evidence[symbol].empty:
                reserves.append(dict(case=name,symbol=symbol,reason='FLAGGED_SYMBOL_WITHOUT_SIP_EVIDENCE',holding_windows=len(g)))
                continue
            known=set(evidence[symbol].date)
            for i in g.index:
                days=e.index[(e.index>=entered[i])&(e.index<=exited[i])]
                missing=[str(d.date()) for d in days if d not in known]
                if missing:reserves.append(dict(case=name,symbol=symbol,entry=str(entered[i].date()),exit=str(exited[i].date()),reason='PROVIDER_EVIDENCE_GAP',dates=missing))
        biggest=t.sort_values('pnl',ascending=False).head(10).copy();biggest['case']=name;big_trades.extend(biggest.to_dict('records'))
        checks.append(dict(case=name,arithmetic='PASS',equation_rows=len(t),recomputed_dd_pct=float(dd),
            fees_included=True,configuration_matches_raw=True,signals_unchanged=True,
            open_lots_reviewed=int(windows.open_at_end.sum()),holding_windows_reviewed=len(windows)))
        row=dict(case=name,label=labels[name],**{c:r.get(c) for c in columns});rows.append(row)
        a['case']=name;annual.append(a)
        e.loc[pd.Timestamp('2021-01-01')]=4000.;e=e.sort_index();curves.append(e.rename(labels[name]))
        ax.plot(e.index,e,label=labels[name],color=colors[name]);ddax.plot(e.index,100*(e/e.cummax().clip(lower=4000)-1),color=colors[name])
    study=Path('artifacts/research/us_winner_q051_risk_budget/20261109-v1')
    spy=pd.read_csv(study/'charts/q051-temoin-volatilite20-regime-vs-spy-2021-2026.csv',index_col=0,parse_dates=True)['SPY_hors_dividendes_frais_USD'].astype(float)
    ax.plot(spy.index,spy,label='SPY — sans dividendes/frais',color='#df871e',alpha=.8)
    ddax.plot(spy.index,100*(spy/spy.cummax()-1),color='#df871e',alpha=.8);curves.append(spy.rename('SPY'))
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(ROOT/'annual-comparison.csv',index=False)
    pd.concat(curves,axis=1).to_csv(ROOT/'capital-curves.csv')
    pd.DataFrame(big_trades).to_csv(ROOT/'largest-winning-trades.csv',index=False)
    pd.concat(window_audits,ignore_index=True).to_csv(ROOT/'observed-holding-windows.csv',index=False)
    price_sources=read(ROOT/'price-input-audit.json')
    price_sources.update(preparation_status=price_sources['status'],
        status='OBSERVED_HOLDING_WINDOWS_CHECKED',remaining_reserves=len(reserves))
    case_qualification={name:('ARITHMETIC_PASS_PRICE_RESERVES_REMAIN' if any(x['case']==name for x in reserves)
        else 'OBSERVED_CHECKS_PASS_RESEARCH_ONLY') for name in CASES}
    affected=[]
    for name in CASES:
        symbols={x['symbol'] for x in reserves if x['case']==name}
        trades=pd.read_csv(ROOT/'cases'/name/'result/trades.csv')
        for row in trades.loc[trades.symbol.isin(symbols)].to_dict('records'):
            affected.append(dict(case=name,**{key:None if pd.isna(value) else value for key,value in row.items()}))
    validation=dict(status='OBSERVED_CHECKS_PASS_RESEARCH_ONLY' if not reserves else 'ARITHMETIC_PASS_PRICE_RESERVES_REMAIN',
        checks=checks,reserves=reserves,price_sources=price_sources,case_qualification=case_qualification,
        affected_closed_trades=affected,
        flagged_symbols_predeclared_before_this_experiment=True,signals_unchanged=True,model_refits=0,
        strict_pit=False,full_live_parity=False,source_sha256=digest(Path(__file__)))
    atomic_json(ROOT/'validation.json',validation)
    ax.set_title('Q051 TOP10 — 24 / 173 variables par titre — prix recoupés SIP')
    ax.set_ylabel('Capital valorisé ($)');ax.grid(alpha=.2);ax.legend(fontsize=9)
    ddax.set_ylabel('DD aux clôtures (%)');ddax.grid(alpha=.2)
    fig.text(.06,.01,'2021–1 octobre 2026 · 4 000 $ · Oracle commun, règles identiques, classement LONG propre à chaque branche.\nSL5/open11, frais inclus. Réserve TOELY : témoin 173. Archives 5m partielles, repli OHLC ; pas de certification PIT/live.',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,1));fig.savefig(ROOT/'capital-comparison.png',dpi=145);plt.close(fig)
    lines=['# Q051 — 173 variables par titre : replays avec prix recoupés SIP','',
        '2021-01-01–2026-10-01 ; 4 000 $ continus ; Oracle TOP10 % → TOP10 LONG ; score >0,50 ; AUC calibration ≥0,50.',
        'SL5/open11 ; entrée J+1 ; positions complètes ; plafond d’achat 1× ; capacité margin 2× ; sans B4/TP/trailing.',
        'Les deux cas protégés ajoutent seulement le budget de volatilité 20 % et le filtre SPY/SMA200.','',
        '| Profil | Capital final | Rendement | DD intraday max | Trades | Gagnants | Capital engagé moyen |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:lines.append(f"| {r['label']} | {r['final_equity']:.2f} $ | {r['return_pct']:+.2f} % | {r['max_drawdown_pct']:.2f} % | {r['closed_lot_trades']} | {r['win_pct']:.2f} % | {r['average_gross_capital']:.2f} $ |")
    lines+=['','## Qualification','',
        'Le premier replay brut utilisait une série DD alternant entre environ 48 $ et 145 $, ce qui créait un faux gain proche de +200 %.',
        'Il est conservé et marqué non qualifié. Les historiques SIP ont été lus pour les 11 titres de la liste déjà signalée par l’audit antérieur,',
        'puis substitués sur leurs dates exactes disponibles, sans suppression de titre, modification des signaux, réglage de risque ou réentraînement.',
        'Source officielle du regroupement DD 1 pour 3 effectif le 24 juin 2026 :',
        'https://www.dupont.com/news/dupont-announces-reverse-stock-split-and-reaffirms-2026-financial-guidance.html','',
        f"État des contrôles : **{validation['status']}** ; réserves de fenêtres : {len(reserves)}.",
        'Les contrôles concernent les données recoupées et les positions réellement observées, pas une certification de tout le corpus.',
        'Les variables d’entraînement et les probabilités restent celles des archives initiales : ce replay isole la réparation des prix d’exécution/valorisation,',
        'il ne constitue pas un nouvel entraînement sur un historique intégralement requalifié.','',
        'La période a déjà été explorée. Les poids sont annuels et hors entraînement pour leurs signaux, mais le protocole n’est pas une période de validation inédite.',
        'Limites : univers contemporain, révisions des prix, secteurs actuels, archives 5m partielles et repli OHLC ; frais forfaitaires et quantités historiques en unités ajustées.',
        'Les anciennes références à +280,94 % / +150,90 % et les nouveaux résultats bruts ne doivent pas être mélangés à ce tableau.','',
        'Détails : `comparison.csv`, `annual-comparison.csv`, `validation.json`, `inputs/normalization-ledger.csv`.']
    if reserves:
        lines+=['','**Réserves encore présentes : ne pas conclure à une performance économiquement qualifiée sur les fenêtres signalées.**',
            f"Les {len(reserves)} mentions correspondent à {len(affected)} trade(s) clôturé(s) concerné(s) ; détail dans `validation.json`."]
        for row in affected:lines.append(f"- {row['case']} : {row['symbol']}, {row['entry_date']} → {row['exit_date']}, PnL enregistré {row['pnl']:+.2f} $. Ce PnL n'est pas une correction contrefactuelle du capital final.")
    text='\n'.join(lines)+'\n';(ROOT/'results.md').write_text(text,encoding='utf-8')
    for file in [Path('doc/ml/q051_features173_20261116.md'),Path('doc/ml/experiences_done.md')]:
        marker='<!-- SIP_REPLAY_173_20261116 -->';prior=file.read_text(encoding='utf-8')
        if marker not in prior:
            with file.open('a',encoding='utf-8') as stream:stream.write('\n'+marker+'\n\n'+text+'\nArchives : `'+str(ROOT)+'`.\n')
        elif old_result and old_result in prior:
            file.write_text(prior.replace(old_result,text,1),encoding='utf-8')
    atomic_json(ROOT/'completion.json',dict(status='COMPLETED_EXPLORATORY',qualification=validation['status'],comparison=rows))
    return rows


def publish_sip():
    if not (ROOT/'validation.json').is_file():raise ValueError('Validate economics before IHM publication')
    ids=[publish(ROOT,name) for name in CASES]
    annotate_history(ids)
    atomic_json(ROOT/'history.json',dict(status='PUBLISHED',run_ids=ids))
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',
        qualification=read(ROOT/'validation.json')['status'],history_published=True,
        finished_at_utc=datetime.now(timezone.utc).isoformat()))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['mark-raw','compare','publish'],required=True);a=p.parse_args()
    if a.phase=='mark-raw':mark_raw()
    elif a.phase=='compare':print(json.dumps(compare(),ensure_ascii=False))
    else:publish_sip()
