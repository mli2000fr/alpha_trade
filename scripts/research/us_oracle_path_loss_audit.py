"""Offline attribution of frozen path-Oracle portfolios, not a new strategy.

Full-window excursions are retrospective. They never replace realised fills or
PnL. Daily OHLC cannot order two intrabar barrier contacts on the same session.
"""
import argparse
from collections import Counter
import json
import logging
from pathlib import Path
import re

import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

LOG = logging.getLogger(__name__)
SOURCE = Path('artifacts/research/us_oracle_path_economic/20261013-v1')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def first_contact(path, entry_price, tp=.2, sl=.1):
    """Opening gap is observable first; same-day double intrabar hit is unknown."""
    upper, lower = entry_price*(1+tp), entry_price*(1-sl)
    for row in path.itertuples():
        day = str(pd.Timestamp(row.date).date())
        if row.open <= lower:
            return dict(first_contact='SL_FIRST', first_contact_date=day, first_contact_at_open=True)
        if row.open >= upper:
            return dict(first_contact='TP_FIRST', first_contact_date=day, first_contact_at_open=True)
        up, down = row.high >= upper, row.low <= lower
        if up or down:
            return dict(first_contact='AMBIGUOUS_SAME_DAY' if up and down else 'TP_FIRST' if up else 'SL_FIRST',
                first_contact_date=day, first_contact_at_open=False)
    return dict(first_contact='NO_CONTACT', first_contact_date=None, first_contact_at_open=False)


def diagnose_path(position, symbol_bars, calendar, events=()):
    entry, exit_day = pd.Timestamp(position['entry_date']), pd.Timestamp(position['exit_date'])
    index = calendar.get_indexer([entry])[0]
    if index < 0 or index+20 >= len(calendar):
        return dict(path_status='INSUFFICIENT_CALENDAR')
    window, expiry = calendar[index:index+20], calendar[index+20]
    symbol = position['entry_identity']
    if any(e['source'] == symbol and entry <= pd.Timestamp(e['day']) <= expiry for e in events):
        # Converted-share prices must not be compared with an unconverted entry.
        return dict(path_status='CORPORATE_ACTION_WINDOW_REQUIRES_REBASING')
    bars = symbol_bars.reindex(window.append(pd.DatetimeIndex([expiry])))
    required = ['open', 'high', 'low', 'close', 'volume']
    if not np.isfinite(bars[required]).all().all() or not bars[required].gt(0).all().all():
        return dict(path_status='MISSING_OR_INVALID_OHLCV')
    if not bars.is_filled.eq(0).all() or bars.instrument_id.isna().any() or bars.instrument_id.nunique() != 1:
        return dict(path_status='FILLED_OR_UNKNOWN_CHANGED_IDENTITY')
    if not (bars.high.ge(bars[['open', 'low', 'close']].max(axis=1)) &
            bars.low.le(bars[['open', 'high', 'close']].min(axis=1))).all():
        return dict(path_status='INCONSISTENT_OHLC')
    price = float(position['entry_price'])
    if not np.isclose(float(bars.iloc[0].open), price, rtol=1e-7, atol=1e-7):
        return dict(path_status='ENTRY_PRICE_BASIS_MISMATCH')
    path = bars.iloc[:20].reset_index(names='date')
    mfe, mae = 100*(path.high.max()/price-1), 100*(path.low.min()/price-1)
    dominance = 'TIE' if np.isclose(mfe, -mae, rtol=1e-9, atol=1e-9) else 'UP' if mfe > -mae else 'DOWN'
    # Exit-day HIGH may occur AFTER a stop/open expiry. Only earlier HIGHs and
    # observed exit fills yield a defensible lower bound on pre-exit upside.
    before = path.loc[path.date.lt(exit_day)]
    known_peak = max(price, float(position['max_executed_exit_price']), float(before.high.max()) if len(before) else price)
    tp_days = path.loc[path.high.ge(price*1.2), 'date']
    stop_days = path.loc[path.low.le(price*.9), 'date']
    result = dict(path_status='QUALIFIED_RETROSPECTIVE', mfe20_pct=float(mfe), mae20_pct=float(mae),
        dominant_direction=dominance, dominant_signed_move_pct=float(mfe if dominance=='UP' else mae) if dominance!='TIE' else None,
        terminal20_close_return_pct=float(100*(path.close.iloc[-1]/price-1)),
        expiry_open_return_pct=float(100*(bars.iloc[20].open/price-1)),
        preexit_upside_lower_bound_pct=float(100*(known_peak/price-1)),
        first_tp_date=str(tp_days.iloc[0].date()) if len(tp_days) else None,
        first_sl_date=str(stop_days.iloc[0].date()) if len(stop_days) else None,
        would_reach_tp20=bool(mfe >= 20-1e-9),
        would_reach_sl10=bool(mae <= -10+1e-9),
        **first_contact(path, price))
    return result


def aggregate_positions(legs):
    """Partial close legs belong to one entry; no CA rebasing is invented."""
    legs = legs.copy()
    legs['entry_identity'] = legs.entry_symbol.fillna(legs.symbol) if 'entry_symbol' in legs else legs.symbol
    gross = (legs.exit_price-legs.entry_price)*legs.quantity
    legs['gross_pnl_usd'] = gross
    legs['trading_cost_usd'] = gross-legs.pnl
    if legs.trading_cost_usd.lt(-1e-6).any():
        raise ValueError('Negative unexplained cost; qualify price/CA units first')
    legs['stop_gap_excess_usd'] = ((legs.replay_initial_stop_price-legs.exit_price).clip(lower=0)*legs.quantity).where(
        legs.exit_reason.eq('initial_stop_gap_open'), 0.)
    rows = []
    for (symbol, day), part in legs.groupby(['entry_identity', 'entry_date']):
        for c in ('entry_price', 'signal_date', 'sector'):
            if part[c].nunique(dropna=False) != 1:
                raise ValueError(f'Position {symbol}/{day} has inconsistent {c}')
        rows.append(dict(entry_identity=symbol, entry_date=day, signal_date=part.signal_date.iloc[0],
            exit_date=part.exit_date.max(), entry_price=float(part.entry_price.iloc[0]),
            max_executed_exit_price=float(part.exit_price.max()), sector=str(part.sector.iloc[0]),
            quantity=float(part.quantity.sum()), entry_notional_usd=float((part.entry_price*part.quantity).sum()),
            pnl=float(part.pnl.sum()), gross_pnl_usd=float(part.gross_pnl_usd.sum()),
            trading_cost_usd=float(part.trading_cost_usd.sum()), stop_gap_excess_usd=float(part.stop_gap_excess_usd.sum()),
            exit_reasons='|'.join(sorted(set(part.exit_reason))), legs=len(part),
            stop_exit=bool(part.exit_reason.str.startswith('initial_stop').any())))
    return pd.DataFrame(rows), legs


def summarize(frame):
    winners, losers = frame.loc[frame.pnl.gt(0)], frame.loc[frame.pnl.lt(0)]
    win_mean = float(winners.pnl.mean()) if len(winners) else None
    loss_mean = float(-losers.pnl.mean()) if len(losers) else None
    known = frame.loc[frame.path_status.eq('QUALIFIED_RETROSPECTIVE')]
    known_losses = known.loc[known.pnl.lt(0)]
    def n(mask):
        return int(mask.sum())
    return dict(positions=len(frame), winning_pct=float(100*frame.pnl.gt(0).mean()),
        net_pnl_usd=float(frame.pnl.sum()), gross_pnl_usd=float(frame.gross_pnl_usd.sum()),
        trading_cost_usd=float(frame.trading_cost_usd.sum()), stop_gap_excess_usd=float(frame.stop_gap_excess_usd.sum()),
        costs_flip_gross_winner_to_net_nonwinner=n(frame.gross_pnl_usd.gt(0) & frame.pnl.le(0)),
        mean_win_usd=win_mean, mean_loss_usd=loss_mean,
        retrospective_break_even_win_pct=100*loss_mean/(loss_mean+win_mean) if win_mean and loss_mean else None,
        mean_winner_notional_usd=float(winners.entry_notional_usd.mean()) if len(winners) else None,
        mean_loser_notional_usd=float(losers.entry_notional_usd.mean()) if len(losers) else None,
        path_status_counts={str(k):int(v) for k,v in frame.path_status.value_counts().items()},
        qualified_path_positions=len(known), qualified_path_losses=len(known_losses),
        first_contact_counts={str(k):int(v) for k,v in known.first_contact.value_counts().items()},
        dominant_direction_counts={str(k):int(v) for k,v in known.dominant_direction.value_counts().items()},
        losses_with_mfe20_ge20=n(known_losses.would_reach_tp20),
        losses_sl_first_then_tp=n(known_losses.first_contact.eq('SL_FIRST') & known_losses.would_reach_tp20),
        losses_ambiguous_contact=n(known_losses.first_contact.eq('AMBIGUOUS_SAME_DAY')),
        losses_down_dominant_no_tp=n(known_losses.dominant_direction.eq('DOWN') & ~known_losses.would_reach_tp20),
        losses_up_dominant_no_tp=n(known_losses.dominant_direction.eq('UP') & ~known_losses.would_reach_tp20),
        losses_known_preexit_upside_ge5=n(known_losses.preexit_upside_lower_bound_pct.ge(5)),
        losses_positive_terminal20=n(known_losses.terminal20_close_return_pct.gt(0)),
        known_path_mean_mfe20_pct=float(known.mfe20_pct.mean()) if len(known) else None,
        known_path_mean_mae20_pct=float(known.mae20_pct.mean()) if len(known) else None)


def groups(frame, column):
    rows = []
    for name, part in frame.groupby(column, dropna=False):
        rows.append(dict(group=str(name), positions=len(part), net_pnl_usd=float(part.pnl.sum()),
            gross_pnl_usd=float(part.gross_pnl_usd.sum()), costs_usd=float(part.trading_cost_usd.sum()),
            win_pct=float(100*part.pnl.gt(0).mean()), losing_amount_usd=float(part.loc[part.pnl.lt(0), 'pnl'].sum())))
    return rows


def monthly_mtm(daily):
    rows, previous = [], 4000.
    frame = daily.assign(month=pd.to_datetime(daily.date).dt.strftime('%Y-%m'))
    for month, part in frame.groupby('month', sort=True):
        final = float(part.equity.iloc[-1])
        rows.append(dict(month=month, sessions=len(part), opening_mark_usd=previous, closing_mark_usd=final,
            mtm_pnl_usd=final-previous, mtm_return_pct=100*(final/previous-1),
            mean_exposure_pct=float(100*(part.gross_notional/part.equity).mean()),
            days_with_positions=int(part.positions.gt(0).sum())))
        previous = final
    return rows


def log_constraints(path):
    """Counts of emitted events, NOT complete candidate rejection accounting."""
    result, key = {}, None
    with Path(path).open(encoding='utf-8', errors='replace') as stream:
        for line in stream:
            start = re.search(r'INFO Starting (\d{4}) TOP(\d+)', line)
            if start:
                key = f'{start[1]}-TOP{start[2]}'
                result.setdefault(key, Counter())
            if key is None:
                continue
            if 'Position reduite pour' in line and ' -> 0 (' in line:
                reason = line.split(' -> 0 (', 1)[1].rsplit(')', 1)[0]
                result[key][reason] += 1
            blocked = re.search(r'Concentration filters: blocked (\d+) \(max trades\) \+ (\d+) \(blacklist\)', line)
            if blocked:
                result[key]['max_trades_logged_candidate_events'] += int(blocked[1])
                result[key]['blacklist_logged_candidate_events'] += int(blocked[2])
    return {k:dict(v) for k,v in result.items()}


def render(report, output):
    lines = ['# Oracle parcours LightGBM — audit des pertes', '',
        'Diagnostic rétrospectif des neuf portefeuilles figés, TP20/SL10 sans trailing.',
        '**Aucun filtre, modèle, protection ou rendement contrefactuel créé.**', '',
        '## PnL et payoffs', '',
        '| Année | TOP | PnL net $ | Brut $ | Coûts $ | Gagnants | Gain moyen $ | Perte moyenne $ | Équilibre rétrospectif |',
        '| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in report['cases']:
        s = r['summary']
        lines.append(f"| {r['year']} | {r['count']} | {s['net_pnl_usd']:+.2f} | {s['gross_pnl_usd']:+.2f} | "
            f"{s['trading_cost_usd']:.2f} | {s['winning_pct']:.2f}% | {s['mean_win_usd']:.2f} | "
            f"{s['mean_loss_usd']:.2f} | {s['retrospective_break_even_win_pct']:.2f}% |")
    lines += ['', 'Le seuil d’équilibre est calculé avec les payoffs moyens observés en dollars,',
        '**pas** un seuil prédictif de score ni une preuve que ces payoffs se répéteront.', '',
        '## Trajectoires des positions exécutées', '',
        '| Année | TOP | Chemins qualifiés | Pertes qualifiées | Pertes : MFE ≥20% | SL avant TP ultérieur | Baisse dominante sans TP | Hausse dominante sans TP |',
        '| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in report['cases']:
        s = r['summary']
        lines.append(f"| {r['year']} | {r['count']} | {s['qualified_path_positions']}/{s['positions']} | "
            f"{s['qualified_path_losses']} | {s['losses_with_mfe20_ge20']} | {s['losses_sl_first_then_tp']} | "
            f"{s['losses_down_dominant_no_tp']} | {s['losses_up_dominant_no_tp']} |")
    lines += ['', 'MFE/MAE : HIGH/LOW des vingt séances depuis l’entrée réelle, en % du fill.',
        'La séance de sortie à l’open après vingt séances est exclue du MFE/MAE.',
        'Le signe dominant mesure le plus grand mouvement absolu, pas une direction prévue.',
        'Le HIGH du jour d’un stop peut survenir après la vente : le diagnostic pré-sortie',
        'n’utilise que les jours antérieurs et les fills constatés (borne basse).',
        'Double contact TP/SL intrabar : chronologie indéterminée, jamais favorable par défaut.',
        'Une remontée après SL ne justifie pas de désactiver celui-ci. Aucune hausse maximale',
        'n’est substituée au prix réellement exécuté. Les compteurs peuvent se recouvrir.', '']
    for r in report['cases']:
        lines += [f"## {r['case']}", '',
            'Mois d’entrée les plus perdants (toutes les sorties de la cohorte incluses) :']
        for row in sorted(r['entry_months'], key=lambda x:x['net_pnl_usd'])[:3]:
            lines.append(f"- {row['group']} : {row['net_pnl_usd']:+.2f} $, {row['positions']} positions.")
        lines += ['', 'Secteurs/industries actuels les plus perdants, **non PIT** :']
        for row in sorted(r['sectors'], key=lambda x:x['net_pnl_usd'])[:3]:
            lines.append(f"- {row['group']} : {row['net_pnl_usd']:+.2f} $.")
        lines += ['', 'Sorties (legs, pas nécessairement positions distinctes) :']
        for row in r['exit_reasons']:
            lines.append(f"- {row['group']} : {row['positions']} legs, {row['net_pnl_usd']:+.2f} $.")
        lines += ['', f"Rang Oracle maximal exécuté : {r['executed_oracle_rank_max']}. "
            f"Rejets qualité J : {r['j_quality_rejections']}. "
            f"Excès des pertes sur gap sous le SL : {r['summary']['stop_gap_excess_usd']:.2f} $.", '']
    lines += ['## TOP20 versus TOP50 en 2024', '',
        json.dumps(report['top20_vs_top50_2024'], ensure_ascii=False, indent=2), '',
        'Les logs de contraintes comptent des événements émis, pas un inventaire exhaustif',
        'des refus pour chaque candidat. Ils ne permettent pas d’attribuer tous les non-trades',
        'à une cause unique. Les transactions/décisions/courbes peuvent en revanche être',
        'comparées exactement.', '', '## Limites', '', *['- '+x for x in report['limitations']], '',
        'Tables détaillées : positions-diagnostic.parquet, monthly-mtm.csv, entry-months.csv,',
        'sectors.csv, regimes.csv, symbols.csv. Aucun SQL ni API fournisseur/courtier appelé.']
    (output/'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


def run(source, output):
    source, output = Path(source), Path(output)
    with exclusive_run(output):
        try:
            original, manifest = read(source/'report.json'), read(source/'manifest.json')
            if original['status'] != 'COMPLETED_EXPLORATORY' or original['completed_runs'] != 9 or not original['source_hashes_verified']:
                raise ValueError('Nine completed verified portfolios required')
            verify_hashes(Path('.'), manifest['source_hashes'])
            verify_hashes(Path('.'), manifest['code_hashes'])
            verify_hashes(source, manifest['files'])
            price_path = Path(manifest['tapes'])/'prices.parquet'
            paths = {source/'report.json', source/'manifest.json', price_path, source/'stderr.log', Path(__file__)}
            for year in (2024,2025,2026):
                for count in (10,20,50):
                    paths.update(source/f'{year}-TOP{count}'/name for name in
                        ('case-report.json','trades.parquet','daily.parquet','candidates.parquet',
                         'decisions.json','regimes.json','executions.json'))
            input_hashes = {str(p):digest(p) for p in sorted(paths)}
            atomic_json(output/'protocol.json', dict(source=str(source), input_hashes=input_hashes,
                tp_pct=.2,sl_pct=.1,horizon_sessions=20,excursion_anchor='actual entry open',
                preexit_high='strictly earlier sessions plus observed exit fills; lower bound',
                retrospective_only=True,no_training=True,no_sql=True,no_broker=True))
            prices = pd.read_parquet(price_path)
            if prices.duplicated(['date', 'symbol']).any():
                raise ValueError('Duplicate price keys')
            bars = {symbol:part.set_index('date').sort_index() for symbol,part in prices.groupby('symbol')}
            calendar = nyse_sessions(pd.Timestamp('2023-01-01').date(), pd.Timestamp(manifest['as_of']).date())
            logged = log_constraints(source/'stderr.log')
            cases, positions, legs_all, mtm_rows, month_rows, sector_rows, regime_rows, symbol_rows = [], [], [], [], [], [], [], []
            expected = {(y,n) for y in (2024,2025,2026) for n in (10,20,50)}
            if {(r['year'],r['count']) for r in original['portfolios']} != expected or len(original['portfolios'])!=9:
                raise ValueError('Duplicated or missing annual cases')
            for i, case in enumerate(original['portfolios']):
                year, count = case['year'], case['count']
                key, root = f'{year}-TOP{count}', source/f'{year}-TOP{count}'
                atomic_json(output/'progress.json', dict(status='RUNNING', completed=i, total=9, current_case=key))
                LOG.info('Auditing %s', key)
                saved = read(root/'case-report.json')
                verify_hashes(root, saved['files'])
                if saved != case or saved['corporate_action_events'] != 0:
                    raise ValueError('Changed case or actual CA requires an explicit rebased cost audit')
                for name in ('case-report.json','trades.parquet','daily.parquet','candidates.parquet',
                             'decisions.json','regimes.json','executions.json'):
                    paths.add(root/name)
                legs = pd.read_parquet(root/'trades.parquet')
                if not legs.side.eq('buy').all():
                    raise ValueError('Expected LONG-only realised trades')
                frame, legs = aggregate_positions(legs)
                candidates = pd.read_parquet(root/'candidates.parquet')
                frame = frame.merge(candidates[['date','symbol','oracle_rank','score_lightgbm']],
                    left_on=['signal_date','entry_identity'], right_on=['date','symbol'],
                    how='left', validate='many_to_one').drop(columns=['date','symbol'])
                if frame.oracle_rank.isna().any():
                    raise ValueError('Executed position is absent from frozen candidate pool')
                diagnostics = pd.DataFrame([diagnose_path(row, bars[row['entry_identity']], calendar, manifest['events'])
                    for row in frame.to_dict('records')])
                for c in ('mfe20_pct','mae20_pct','first_contact','dominant_direction',
                          'preexit_upside_lower_bound_pct','terminal20_close_return_pct'):
                    if c not in diagnostics:
                        diagnostics[c] = np.nan
                for c in ('would_reach_tp20','would_reach_sl10'):
                    if c not in diagnostics:
                        diagnostics[c] = False
                frame = pd.concat([frame.reset_index(drop=True), diagnostics], axis=1)
                frame['case'], frame['year'], frame['count'] = key, year, count
                regimes = pd.DataFrame(read(root/'regimes.json'))
                regimes['date'] = pd.to_datetime(regimes.date)
                frame = frame.merge(regimes[['date','mode','spy_regime','breaker_scale','risk_multiplier']],
                    left_on='signal_date', right_on='date', how='left', validate='many_to_one').drop(columns='date')
                if frame['mode'].isna().any():
                    raise ValueError('Missing same-date decision regime')
                frame = frame.sort_values(['entry_date','entry_identity'])
                frame['reentry'] = frame.groupby('entry_identity').cumcount().gt(0)
                prior_exit = frame.groupby('entry_identity').exit_date.shift()
                prior_pnl = frame.groupby('entry_identity').pnl.shift()
                frame['quick_reentry_after_loss_5_calendar_days'] = prior_pnl.lt(0) & (frame.entry_date-prior_exit).dt.days.between(0,5)
                frame['entry_month'] = frame.entry_date.dt.strftime('%Y-%m')
                frame['exit_month'] = frame.exit_date.dt.strftime('%Y-%m')
                daily = pd.read_parquet(root/'daily.parquet')
                if not np.isclose(frame.pnl.sum()-saved['margin_interest'], saved['annual_metrics']['net_pnl_usd'], atol=1e-6):
                    raise ValueError('Position PnL does not reconcile with account net')
                executions = read(root/'executions.json')
                summary = summarize(frame)
                item = dict(case=key, year=year, count=count, summary=summary, annual_metrics=saved['annual_metrics'],
                    entry_months=groups(frame,'entry_month'), exit_months=groups(frame,'exit_month'),
                    sectors=groups(frame,'sector'), regimes=groups(frame,'mode'), spy_regimes=groups(frame,'spy_regime'),
                    symbols=groups(frame,'entry_identity'), exit_reasons=groups(legs,'exit_reason'),
                    reentries=groups(frame,'reentry'), quick_reentries_after_loss=groups(frame,'quick_reentry_after_loss_5_calendar_days'),
                    monthly_mtm=monthly_mtm(daily), executed_oracle_rank_max=int(frame.oracle_rank.max()),
                    executed_positions_rank_gt10=int(frame.oracle_rank.gt(10).sum()),
                    executed_positions_rank_gt20=int(frame.oracle_rank.gt(20).sum()),
                    j_quality_rejections=int((~candidates.selected).sum()),
                    logged_constraint_events=logged.get(key,{}),
                    approvals=sum(e['approved'] for e in executions), actual_open_events=sum(len(e['opened']) for e in executions),
                    phase3_gap_rejections=sum(len(e['phase3_diagnostics'].get('gap_rejections',[])) for e in executions),
                    max_positions=int(daily.positions.max()), days_at_eight_positions=int(daily.positions.ge(8).sum()),
                    regime_days=regimes['mode'].value_counts().to_dict(),
                    worst_trades=frame.nsmallest(10,'pnl')[['entry_identity','entry_date','exit_date','pnl','exit_reasons',
                        'mfe20_pct','mae20_pct','first_contact','dominant_direction']].to_dict('records'))
                cases.append(item)
                positions.append(frame)
                legs_all.append(legs.assign(case=key,year=year,count=count))
                for rows, target in ((item['monthly_mtm'],mtm_rows),(item['entry_months'],month_rows),
                    (item['sectors'],sector_rows),(item['regimes'],regime_rows),(item['symbols'],symbol_rows)):
                    target.extend(dict(case=key,year=year,count=count,**row) for row in rows)
            a,b = source/'2024-TOP20',source/'2024-TOP50'
            exact = dict(trades_equal=pd.read_parquet(a/'trades.parquet').equals(pd.read_parquet(b/'trades.parquet')),
                daily_equal=pd.read_parquet(a/'daily.parquet').equals(pd.read_parquet(b/'daily.parquet')),
                decisions_equal=read(a/'decisions.json')==read(b/'decisions.json'),
                extra_rank_gt20_executed=next(r['executed_positions_rank_gt20'] for r in cases if r['case']=='2024-TOP50'),
                logged_constraints_top20=logged.get('2024-TOP20',{}), logged_constraints_top50=logged.get('2024-TOP50',{}))
            pd.concat(positions,ignore_index=True).to_parquet(output/'positions-diagnostic.parquet',index=False)
            pd.concat(legs_all,ignore_index=True).to_parquet(output/'closed-legs-costs.parquet',index=False)
            for name,rows in (('monthly-mtm',mtm_rows),('entry-months',month_rows),('sectors',sector_rows),('regimes',regime_rows),('symbols',symbol_rows)):
                pd.DataFrame(rows).to_csv(output/f'{name}.csv',index=False)
            result = dict(status='COMPLETED_RETROSPECTIVE_AUDIT', source=str(source), cases=cases,
                top20_vs_top50_2024=exact, input_hashes=input_hashes,
                limitations=['future paths used for diagnosis only, never an entry/exit decision or substitute PnL',
                    'unknown future paths retained with explicit status, not assumed losing/winning',
                    'same-session intrabar order cannot be inferred from daily bars',
                    'sector/industry metadata current and non PIT; macro publication vintage not certified',
                    '2026 decisions stop September 2, liquidations through October 2; not a full year',
                    'annual reset and January exit tails; monthly entry cohorts differ from monthly marked PnL',
                    'nine related portfolios overlap heavily, not nine independent statistical replications',
                    'regime/sector/month associations are retrospective explanations, not predictive vetoes',
                    'logged constraints are emitted event counts, not exhaustive unique-candidate refusals'],
                no_training=True,no_sql=True,no_broker=True,no_strategy_changes=True)
            render(result,output)
            verify_hashes(Path('.'),input_hashes)
            verify_hashes(Path('.'),manifest['source_hashes'])
            result['inputs_verified_after_audit'] = True
            result['files'] = {p.name:digest(p) for p in output.glob('*') if p.suffix in ('.csv','.parquet','.md')}
            atomic_json(output/'report.json',result)
            atomic_json(output/'progress.json',dict(status='COMPLETED',completed=9,total=9))
            LOG.info('Audit complete: %s',output/'report.md')
            return result
        except Exception as exc:
            atomic_json(output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=SOURCE)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    run(**vars(args))
