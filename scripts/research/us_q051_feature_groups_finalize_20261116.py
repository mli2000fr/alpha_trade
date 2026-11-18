"""Observed-price scope review and final note, without changing replay outputs."""
from datetime import datetime,timezone
from pathlib import Path
import json

import pandas as pd

from scripts.research.us_q051_feature_groups_20261116 import ROOT,PRICES,GROUPS,read
from scripts.research.us_q051_features173_finalize_20261116 import observed_windows
from scripts.research.us_q051_features173_sip_replay_20261116 import provider_frame
from scripts.research.us_h10_price_readiness import FLAGGED
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def main():
    plan=read(ROOT/'protocol.json')
    for file,h in plan['sources'].items():
        if digest(Path(file))!=h:raise ValueError('Sealed source changed: '+file)
    evidence={p.stem:provider_frame(p) for p in (PRICES/'evidence').glob('*.json')}
    checks=[];reserves=[];histories=[]
    for variant in GROUPS:
        for profile in ['SIMPLE','VOL20_REGIME']:
            name=variant+'_'+profile;folder=ROOT/'variants'/variant/'cases'/name;out=folder/'result'
            trades=pd.read_csv(out/'trades.csv');events=pd.read_csv(out/'events.csv')
            days=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).index
            windows=observed_windows(trades,events,pd.Timestamp(days[-1]).tz_localize('America/New_York')+pd.Timedelta(hours=16))
            entered=pd.to_datetime(windows.entry_date,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
            exited=pd.to_datetime(windows.exit_date,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
            cross=windows.symbol.eq('DD')&entered.lt('2025-11-03')&exited.ge('2025-11-03')
            for i in windows.index[cross]:reserves.append(dict(case=name,symbol='DD',reason='UNQUALIFIED_QNITY_ENTITLEMENT',entry=str(entered[i].date()),exit=str(exited[i].date())))
            uncertain=windows.symbol.eq('TOELY')&exited.ge('2026-07-13')
            for i in windows.index[uncertain]:reserves.append(dict(case=name,symbol='TOELY',reason='UNSUPPORTED_ADR_BASIS',entry=str(entered[i].date()),exit=str(exited[i].date())))
            for symbol,g in windows.groupby('symbol'):
                if symbol not in FLAGGED:continue
                if symbol not in evidence or evidence[symbol].empty:
                    reserves.append(dict(case=name,symbol=symbol,reason='FLAGGED_WITHOUT_SIP_EVIDENCE',windows=len(g)));continue
                known=set(evidence[symbol].date)
                for i in g.index:
                    missing=[str(d.date()) for d in days[(days>=entered[i])&(days<=exited[i])] if d not in known]
                    if missing:reserves.append(dict(case=name,symbol=symbol,reason='SIP_HOLDING_WINDOW_GAP',dates=missing))
            scoped=[r for r in reserves if r['case']==name]
            checks.append(dict(case=name,status='OBSERVED_PRICE_SCOPE_PASS_RESEARCH_ONLY' if not scoped else 'PRICE_RESERVES_REMAIN',
                holding_windows=len(windows),open_lots=int(windows.open_at_end.sum()),reserves=len(scoped)))
            histories.append((read(folder/'ihm.json')['run_id'],checks[-1]['status']))
    audit=dict(status='OBSERVED_PRICE_SCOPE_PASS_RESEARCH_ONLY' if not reserves else 'PRICE_RESERVES_REMAIN',
        checks=checks,reserves=reserves,pre_existing_flagged_symbols=FLAGGED,
        entire_corpus_certified=False,strict_pit=False,full_live_parity=False,source_sha256=digest(Path(__file__)),
        checked_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(ROOT/'price-window-validation.json',audit)
    from ihm.services import backtesting_registry as reg
    for rid,status in histories:
        file=reg.RUNS_DIR/'run'/rid/'artifacts/report.json';r=read(file)
        r.setdefault('diagnostics',{})['feature_group_price_scope']=status
        r.setdefault('run_metadata',{})['price_scope_review']=str(ROOT/'price-window-validation.json')
        warning='Recherche : intraday partiel/repli OHLC ; contrôle SIP limité aux titres déjà signalés et aux fenêtres détenues, sans certification PIT.'
        if warning not in r.setdefault('limitations',[]):r['limitations'].append(warning)
        atomic_json(file,r)
    with reg._REGISTRY_LOCK:
        index=reg._read_history_index()
        for rid,status in histories:index[rid]['price_qualification']=status
        reg._write_history_index(index)
    frame=pd.read_csv(ROOT/'comparison.csv');annual=pd.read_csv(ROOT/'annual-comparison.csv')
    labels={'T0_SIMPLE':'24 — témoin','A_SIMPLE':'24 + marché — témoin','B_SIMPLE':'24 + volatilité — témoin',
        'T0_VOL20_REGIME':'24 — vol20 + régime','A_VOL20_REGIME':'24 + marché — vol20 + régime','B_VOL20_REGIME':'24 + volatilité — vol20 + régime'}
    lines=['# Q051 — ajouts ciblés aux 24 variables : premier lot terminé','',
        'Six replays terminés et publiés dans l’historique IHM. Production inchangée.',
        '2021-01-01–2026-10-01, capital continu 4 000 $, Oracle TOP10 % → TOP10 LONG, probabilité >0,50 et AUC de calibration ≥0,50, sans remplacement.',
        'Entrée J+1, position complète, SL5/open11, sans TP/trailing/confirmation/B4 ; plafond d’achat 1×, capacité margin 2× ; frais et financement inclus.','',
        '| Profil | Capital final | Rendement | DD max | Taux gagnant | Trades | Capital engagé moyen |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name in labels:
        r=frame.set_index('case').loc[name]
        lines.append(f"| {labels[name]} | {r.final_equity:.2f} $ | {r.return_pct:+.2f} % | {r.max_drawdown_pct:.2f} % | {r.win_pct:.2f} % | {r.closed_lot_trades} | {r.average_gross_capital:.2f} $ |")
    lines+=['','## Lecture','',
        'A (bêta, R², alpha et momentum relatif au marché sur 252 séances) améliore le témoin simple : +160,22 % contre +129,06 %, DD −32,96 % contre −39,12 %.',
        'B (cinq variables de volatilité longue et normalisée) augmente davantage le rendement simple : +297,35 %, mais le DD se dégrade à −40,99 %.',
        'Avec vol20 + régime, A et B font moins bien que T0 à la fois en rendement et en DD : conserver les 24 variables pour ce profil à ce stade.',
        'Les expositions brutes moyennes rapportées au capital courant sont proches entre témoins simples (environ 88 %) et entre cas protégés (environ 46 %).',
        'Les trois références ont été réentraînées sur une population et des lignes communes ; ces chiffres ne remplacent pas rétroactivement les anciennes références à 24 variables.','',
        '## Rendements annuels','',
        '| Année | T0 témoin | A témoin | B témoin | T0 vol20/régime | A vol20/régime | B vol20/régime |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    table=annual.pivot(index='year',columns='case',values='return_pct')
    for year,r in table.iterrows():lines.append('| '+str(year)+' | '+' | '.join(f'{r[c]:+.2f} %' for c in labels)+' |')
    lines+=['','## Contrôles et limites','',
        '431 blocs et 9 267 modèles LONG vérifiés après entraînement ; les trois branches partagent les mêmes lignes fit/calibration, avec 24, 28 et 29 entrées.',
        'Quatre tests ciblés passent. Les six bilans passent les vérifications de PnL, de capital annuel et de drawdown. Les prix d’exécution communs sont figés avant les replays.',
        f"Qualification ciblée de prix : **{audit['status']}**, réserves observées : {len(reserves)}. Voir `price-window-validation.json` (positions clôturées et ouvertes).",
        'Cette revue porte uniquement sur la liste préexistante de titres signalés et ses fenêtres réellement détenues, pas sur la qualification de tout le corpus.',
        'Intraday partiel avec repli OHLC, prix historiques révisés et unités ajustées, univers contemporain. Aucune certification PIT ni parité d’exécution live.',
        'Les années 2021–2026 ont déjà été explorées dans d’autres expériences ; pas de nouvelle validation indépendante. Les gains observés ne justifient pas une activation automatique.',
        'La contre-performance sous vol20 + régime ne permet pas à elle seule de séparer l’effet du budget de volatilité de celui du filtre de régime.',
        'Les erreurs de préparation ont été corrigées sans réentraînement ; anciens protocoles et journaux conservés. Aucune modification de production, aucun ordre, appel fournisseur/LLM ou écriture SQL.','',
        'Archives : `artifacts/research/us_q051_feature_groups/20261116-lot1/`.',
        'Courbes : `capital-comparison.png`. Détails : `comparison.csv`, `annual-comparison.csv`, `classification-by-year.csv`, `history.json`.']
    result='\n'.join(lines)+'\n';(ROOT/'results.md').write_text(result,encoding='utf-8')
    for file in [Path('doc/ml/q051_feature_groups_proposal_20261116.md'),Path('doc/ml/experiences_done.md')]:
        prior=file.read_text(encoding='utf-8');marker='<!-- Q051_FEATURE_GROUPS_LOT1_RESULTS_20261116 -->'
        if marker not in prior:
            with file.open('a',encoding='utf-8') as stream:stream.write('\n'+marker+'\n\n'+result)
    print(json.dumps(dict(status=audit['status'],cases=len(checks),reserves=reserves),ensure_ascii=False))


if __name__=='__main__':main()
