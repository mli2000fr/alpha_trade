"""Read-only audit of repeated stops; no blacklist, fits or economic replays."""
from datetime import datetime,timezone
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_q051_sl_recurrence/20261116-v1')
SOURCE=Path('artifacts/research/us_q051_feature_groups/20261116-lot1')
CASES=[v+'_'+p for v in ['T0','A','B'] for p in ['SIMPLE','VOL20_REGIME']]
RULES={'zero_win_min5':dict(min_trades=5,zero_wins=True),
       'sl80_min10_negative':dict(min_trades=10,min_sl_rate=.8,negative_pnl=True)}
SPLIT=pd.Timestamp('2025-01-01',tz='UTC')


def read(path):
    import json
    return json.loads(Path(path).read_text(encoding='utf-8'))


def longest_run(values):
    best=current=0
    for value in values:
        current=current+1 if value else 0;best=max(best,current)
    return best


def prepare_trades(frame,case):
    f=frame.copy();f['case']=case
    f['entry_at']=pd.to_datetime(f.entry_date,utc=True);f['exit_at']=pd.to_datetime(f.exit_date,utc=True)
    if f[['entry_at','exit_at']].isna().any().any() or f.exit_at.lt(f.entry_at).any():raise ValueError('Invalid trade timestamps')
    if not f.side.eq('buy').all():raise ValueError('This audit is LONG only')
    reasons=set(f.exit_reason)
    if reasons-{'STOP','STOP_GAP','HORIZON_OPEN'}:raise ValueError('Unreviewed exit reason: '+str(reasons))
    f['is_sl']=f.exit_reason.isin(['STOP','STOP_GAP']);f['is_gap_sl']=f.exit_reason.eq('STOP_GAP')
    f['win']=f.pnl.gt(0);f['loss']=f.pnl.lt(0);f['net_return_pct']=100*pd.to_numeric(f.return_pct)
    keys=(f.symbol.astype(str)+'|'+f.entry_at.astype(str)+'|'+f.entry_price.map(lambda x:f'{x:.8f}')+'|'+f.side)
    f['episode']=keys.map(lambda x:hashlib.sha256(x.encode()).hexdigest()[:24])
    if f.episode.duplicated().any():raise ValueError('Partial lots need consolidation before counting repetitions')
    return f.sort_values(['symbol','exit_at','entry_at']).reset_index(drop=True)


def per_symbol(frame,sequences=True):
    rows=[]
    for symbol,g in frame.groupby('symbol',sort=True):
        g=g.sort_values(['exit_at','entry_at']);stops=g[g.is_sl]
        row=dict(symbol=symbol,trades=len(g),wins=int(g.win.sum()),losses=int(g.loss.sum()),flat=int((~g.win&~g.loss).sum()),
            sl=int(g.is_sl.sum()),gap_sl=int(g.is_gap_sl.sum()),win_pct=100*g.win.mean(),sl_pct=100*g.is_sl.mean(),
            net_pnl=float(g.pnl.sum()),mean_net_return_pct=float(g.net_return_pct.mean()),
            median_net_return_pct=float(g.net_return_pct.median()),min_net_return_pct=float(g.net_return_pct.min()),
            max_net_return_pct=float(g.net_return_pct.max()),active_years=int(g.exit_at.dt.year.nunique()),
            losing_years=int(g.groupby(g.exit_at.dt.year).pnl.sum().lt(0).sum()),
            first_entry=str(g.entry_at.min()),last_exit=str(g.exit_at.max()),
            always_loss=bool(g.loss.all()),no_winner=not bool(g.win.any()),all_stops=bool(g.is_sl.all()))
        if sequences:
            row.update(max_consecutive_sl=longest_run(g.is_sl),max_consecutive_losses=longest_run(g.loss))
            gaps=stops.exit_at.diff().dt.total_seconds()/86400
            row['median_days_between_sl']=float(gaps.median()) if len(stops)>1 else None
            for days in [30,90,180]:
                row[f'max_sl_{days}d']=int(pd.Series(1,index=pd.DatetimeIndex(stops.exit_at)).rolling(f'{days}D',closed='both').sum().max()) if len(stops) else 0
        rows.append(row)
    return pd.DataFrame(rows)


def causal_prior_sl(frame):
    pieces=[]
    for symbol,g in frame.groupby('symbol'):
        g=g.sort_values(['exit_at','entry_at']).copy();counts=[];previous=[];runs=[]
        for row in g.itertuples():
            # Strictly earlier: do not use the current trade or ambiguous same-open outcomes.
            history=g[g.exit_at.lt(row.entry_at)]
            counts.append(int(history.is_sl.sum()))
            previous.append(bool(history.is_sl.iloc[-1]) if len(history) else False)
            run=0
            for stop in reversed(history.is_sl.tolist()):
                if not stop:break
                run+=1
            runs.append(run)
        g['known_prior_sl']=counts;g['previous_resolved_trade_sl']=previous;g['known_prior_sl_streak']=runs;pieces.append(g)
    return pd.concat(pieces,ignore_index=True)


def frozen_history_rules(frame):
    history=per_symbol(frame[frame.exit_at.lt(SPLIT)])
    future=frame[frame.entry_at.ge(SPLIT)]
    rows=[];lists=[]
    for name,r in RULES.items():
        mask=history.trades.ge(r['min_trades'])
        if r.get('zero_wins'):mask &= history.wins.eq(0)
        if 'min_sl_rate' in r:mask &= history.sl_pct.ge(100*r['min_sl_rate'])
        if r.get('negative_pnl'):mask &= history.net_pnl.lt(0)
        names=set(history.loc[mask,'symbol']);chosen=future[future.symbol.isin(names)]
        rows.append(dict(rule=name,history_symbols=len(names),future_symbols=int(chosen.symbol.nunique()),
            future_trades=len(chosen),future_wins=int(chosen.win.sum()),future_losses=int(chosen.loss.sum()),
            future_sl=int(chosen.is_sl.sum()),future_net_pnl=float(chosen.pnl.sum()),
            future_win_pct=100*float(chosen.win.mean()) if len(chosen) else None,
            future_mean_return_pct=float(chosen.net_return_pct.mean()) if len(chosen) else None,
            future_all_trades=len(future),future_all_win_pct=100*float(future.win.mean()) if len(future) else None))
        a=history[history.symbol.isin(names)].copy();a['rule']=name;lists.append(a)
    return pd.DataFrame(rows),pd.concat(lists,ignore_index=True)


def unique_episodes(frame):
    rows=[];conflicts=[]
    for key,g in frame.groupby('episode',sort=False):
        # Quantity/PnL differ with the account path. Compare normalized outcomes.
        consistent=(g.symbol.nunique()==1 and g.exit_at.nunique()==1 and g.is_sl.nunique()==1
            and g.win.nunique()==1 and g.loss.nunique()==1 and g.net_return_pct.max()-g.net_return_pct.min()<1e-5)
        if not consistent:
            conflicts.extend(g.to_dict('records'));continue
        row=g.iloc[0].copy();row['cases_observed']='|'.join(sorted(g['case'].unique()));row['case_observations']=len(g)
        # Never sum dollar PnL across model variants as if they formed one portfolio.
        row['pnl']=float(row.net_return_pct);rows.append(row)
    return pd.DataFrame(rows),pd.DataFrame(conflicts)


def run():
    ROOT.mkdir(parents=True,exist_ok=True);sources={};case_frames={}
    for name in CASES:
        folder=SOURCE/'variants'/name.split('_')[0]/'cases'/name
        if read(folder/'progress.json')['status']!='COMPLETED_EXPLORATORY':raise ValueError('Audit only completed cases')
        for relative in ['result/trades.csv','result/report.json','protocol.json']:
            path=folder/relative;sources[str(path)]=digest(path)
        policy=read(folder/'protocol.json')['reference']['winner_policy']
        if policy['stop_loss_pct']!=.05 or policy['horizon_sessions']!=10 or policy['trailing_stop_pct'] is not None:
            raise ValueError('Stop policies differ')
    plan=dict(status='SEALED',cases=CASES,sources=sources,rules=RULES,history_cutoff=str(SPLIT),
        scope='Completed T0/A/B six portfolios, closed trades only; C/D and AB remain running',
        duplicate_policy='Separate cases; union is de-duplicated by symbol+entry timestamp+entry price+side; conflicting outcomes excluded from union',
        time_policy='Prior SL known only after an exit strictly earlier than this entry',
        interpretation='Descriptive trade audit, not a replay after exclusion or an independent validation',
        provider_calls=0,SQL_writes=0,orders=0,source_sha256=digest(Path(__file__)),created_at_utc=datetime.now(timezone.utc).isoformat())
    if (ROOT/'protocol.json').exists():
        old=read(ROOT/'protocol.json')
        if old['sources']!=sources:raise ValueError('Use a new audit folder for different sources')
    else:atomic_json(ROOT/'protocol.json',plan)
    summaries=[];stats=[];year_parts=[];repeat_parts=[];conditional=[];history_results=[];history_lists=[];distributions=[]
    for name in CASES:
        f=prepare_trades(pd.read_csv(SOURCE/'variants'/name.split('_')[0]/'cases'/name/'result/trades.csv'),name)
        case_frames[name]=f;s=per_symbol(f);s['case']=name;stats.append(s)
        yearly=[]
        for year,g in f.groupby(f.exit_at.dt.year):
            a=per_symbol(g);a['year']=int(year);a['case']=name;yearly.append(a)
        year_parts.extend(yearly)
        by_prior=causal_prior_sl(f);repeat_parts.append(by_prior)
        by_prior['prior_sl_band']=pd.cut(by_prior.known_prior_sl,[-1,0,1,2,4,np.inf],labels=['0','1','2','3-4','5+'])
        for band,g in by_prior.groupby('prior_sl_band',observed=True):
            conditional.append(dict(case=name,prior_sl_band=str(band),trades=len(g),symbols=g.symbol.nunique(),
                win_pct=100*g.win.mean(),sl_pct=100*g.is_sl.mean(),net_pnl=g.pnl.sum(),mean_return_pct=g.net_return_pct.mean()))
        hist,names=frozen_history_rules(f);hist['case']=name;names['case']=name;history_results.append(hist);history_lists.append(names)
        s['sl_band']=pd.cut(s.sl,[-1,0,1,2,3,5,9,np.inf],labels=['0','1','2','3','4-5','6-9','10+'])
        for band,g in s.groupby('sl_band',observed=True):
            distributions.append(dict(case=name,sl_band=str(band),symbols=len(g),sl=int(g.sl.sum()),trades=int(g.trades.sum())))
        row=dict(case=name,trades=len(f),symbols=f.symbol.nunique(),stops=int(f.is_sl.sum()),stop_gap=int(f.is_gap_sl.sum()),
            sl_pct=100*f.is_sl.mean(),winners=int(f.win.sum()),losers=int(f.loss.sum()),win_pct=100*f.win.mean(),
            symbols_repeated_sl=int(s.sl.ge(2).sum()),symbols_3plus_sl=int(s.sl.ge(3).sum()),
            sl_after_known_prior_sl=int((by_prior.is_sl&by_prior.known_prior_sl.ge(1)).sum()),
            symbols_net_negative=int(s.net_pnl.lt(0).sum()))
        for n in [1,5,10,20]:
            row[f'symbols_min{n}']=int(s.trades.ge(n).sum())
            row[f'always_loss_min{n}']=int((s.trades.ge(n)&s.always_loss).sum())
            row[f'all_stops_min{n}']=int((s.trades.ge(n)&s.all_stops).sum())
        summaries.append(row)
    symbol_stats=pd.concat(stats,ignore_index=True);symbols_year=pd.concat(year_parts,ignore_index=True)
    repeated=pd.concat(repeat_parts,ignore_index=True);history=pd.concat(history_results,ignore_index=True)
    outputs={'summary.csv':pd.DataFrame(summaries),'per-symbol.csv':symbol_stats,'per-symbol-year.csv':symbols_year,
        'sl-count-distribution.csv':pd.DataFrame(distributions),'conditional-prior-sl.csv':pd.DataFrame(conditional),
        'trades-with-prior-history.csv':repeated,'frozen-history-check.csv':history,
        'history-only-symbol-lists.csv':pd.concat(history_lists,ignore_index=True)}
    episodes,conflicts=unique_episodes(pd.concat(case_frames.values(),ignore_index=True))
    union=per_symbol(episodes,sequences=False).rename(columns={'net_pnl':'sum_normalized_returns_not_portfolio_pnl'})
    episode_export=episodes.drop(columns=['pnl','quantity','entry_fees','exit_fees','dividends'],errors='ignore').rename(columns={'case':'representative_case'})
    outputs.update({'unique-episodes.csv':episode_export,'conflicting-episodes.csv':conflicts,'per-symbol-unique-episodes.csv':union})
    for file,f in outputs.items():f.to_csv(ROOT/file,index=False)
    labels={'T0_SIMPLE':'T0 témoin','A_SIMPLE':'A marché témoin','B_SIMPLE':'B volatilité témoin',
        'T0_VOL20_REGIME':'T0 vol20/régime','A_VOL20_REGIME':'A vol20/régime','B_VOL20_REGIME':'B vol20/régime'}
    lines=['# Q051 — répétitions des SL par symbole','',
        'Audit des six portefeuilles T0/A/B terminés, 2021–1er octobre 2026, LONG SL5/open11, trades clôturés uniquement.',
        '`STOP` et `STOP_GAP` comptent comme SL. Une perte à open11 est comptée séparément. Aucun filtre, entraînement, ordre ou nouveau backtest n’est appliqué.','',
        '| Cas | Trades | Titres | SL | Taux SL | Titres ≥2 SL | Toujours perdants ≥5 trades | Toujours perdants ≥10 trades |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in summaries:lines.append(f"| {labels[r['case']]} | {r['trades']} | {r['symbols']} | {r['stops']} | {r['sl_pct']:.2f} % | {r['symbols_repeated_sl']} | {r['always_loss_min5']} | {r['always_loss_min10']} |")
    for name in ['T0_SIMPLE','B_SIMPLE']:
        s=symbol_stats[symbol_stats['case'].eq(name)]
        lines+=['','## '+labels[name]+' — titres avec le plus de SL','',
            '| Symbole | Trades | SL | Gagnants | Résultat net | Série SL max | Années perdantes / actives |',
            '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
        for r in s.sort_values(['sl','trades','symbol'],ascending=[False,False,True]).head(12).itertuples():
            lines.append(f'| {r.symbol} | {r.trades} | {r.sl} | {r.win_pct:.2f} % | {r.net_pnl:+.2f} $ | {r.max_consecutive_sl} | {r.losing_years}/{r.active_years} |')
        loss=s[s.trades.ge(5)&s.always_loss].sort_values(['trades','net_pnl'],ascending=[False,True])
        lines+=['','### Tous les trades perdants, au moins cinq entrées','',
            '| Symbole | Trades | SL | Résultat net | Années actives |','| --- | ---: | ---: | ---: | ---: |']
        for r in loss.itertuples():lines.append(f'| {r.symbol} | {r.trades} | {r.sl} | {r.net_pnl:+.2f} $ | {r.active_years} |')
    lines+=['','## Persistance après 2024','',
        'Les listes ci-dessous sont établies exclusivement avec les trades sortis avant le 1er janvier 2025, puis observées sur les entrées 2025–2026.',
        'Règle 1 : au moins cinq trades historiques, aucun gagnant. Règle 2 : au moins dix trades, ≥80 % de SL et PnL historique négatif.',
        'Cela mesure les trades observés ensuite sur ces titres, pas le capital final d’une stratégie les excluant. Aucune réallocation, nouvelle entrée ou capital libéré n’a été rejoué.','',
        '| Cas | Règle historique | Titres signalés | Titres revus ensuite | Trades futurs | Gagnants futurs | PnL futur observé |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for r in history.itertuples():
        rate=f'{r.future_win_pct:.2f} %' if pd.notna(r.future_win_pct) else '—'
        lines.append(f'| {labels[r.case]} | {r.rule} | {r.history_symbols} | {r.future_symbols} | {r.future_trades} | {rate} | {r.future_net_pnl:+.2f} $ |')
    lines+=['','## Unités et limites','',
        f"Les {sum(r['trades'] for r in summaries)} lignes des variantes correspondent à {len(episodes)} épisodes cohérents distincts et {conflicts.episode.nunique() if len(conflicts) else 0} épisodes à issues divergentes, exclus du résumé dédupliqué.",
        'Une même entrée apparaît dans plusieurs variantes : ces observations ne sont pas des preuves indépendantes. Les dollars des variantes ne sont jamais additionnés en un portefeuille fictif.',
        'Le PnL par titre reprend les frais et dividendes attribués aux trades, sans réaffecter les éventuels frais globaux de financement du portefeuille.',
        'Le résumé par épisode dédupliqué utilise un rendement net normalisé, pas un cumul de PnL en dollars. Ce périmètre réunit des sélections qui ne seraient pas toutes détenues simultanément dans un seul compte.',
        'Un titre sans gagnant sur une ou deux entrées n’est pas établi comme durablement perdant. Les seuils descriptifs de 5/10/20 trades sont fournis explicitement.',
        'Les pertes sont dépendantes des dates, du marché et de la sélection Oracle ; les séries de SL comptent uniquement les trades de ce titre, et non les pertes consécutives de tout le portefeuille.',
        'Pour les statistiques conditionnelles, seuls les résultats strictement connus avant l’entrée suivante sont utilisés ; les sorties à l’instant exact de l’entrée sont écartées de cette connaissance préalable.',
        'L’audit porte sur les symboles des archives : changements d’identité/ticker, univers contemporain, cours révisés et repli OHLC restent des limites. Les positions encore ouvertes ne sont pas déclarées gagnantes ou perdantes.',
        'Les règles historiques sont descriptives, préspécifiées pour cet audit ; 2025–2026 a déjà été observé dans les expériences antérieures. Aucun univers d’exclusion n’est activé.',
        'Détails : `per-symbol.csv`, `per-symbol-year.csv`, `sl-count-distribution.csv`, `conditional-prior-sl.csv`, `frozen-history-check.csv` et `unique-episodes.csv`.']
    report='\n'.join(lines)+'\n';(ROOT/'results.md').write_text(report,encoding='utf-8')
    atomic_json(ROOT/'validation.json',dict(status='COMPLETED_READ_ONLY_DESCRIPTIVE',cases=len(CASES),
        raw_rows=sum(r['trades'] for r in summaries),unique_consistent_episodes=len(episodes),
        conflicting_episodes=int(conflicts.episode.nunique()) if len(conflicts) else 0,
        dollars_not_pooled=True,history_rules=RULES,filter_activated=False,performance_replay=False))
    file=Path('doc/ml/q051_sl_recurrence_audit_20261116.md');file.write_text(report,encoding='utf-8')
    done=Path('doc/ml/experiences_done.md');prior=done.read_text(encoding='utf-8');marker='<!-- Q051_SL_RECURRENCE_AUDIT_20261116 -->'
    if marker not in prior:
        with done.open('a',encoding='utf-8') as stream:stream.write('\n'+marker+'\n\n'+report+'\nArchives : `'+str(ROOT)+'`.\n')
    print(pd.DataFrame(summaries).to_string(index=False));print(history.to_string(index=False))


if __name__=='__main__':run()
