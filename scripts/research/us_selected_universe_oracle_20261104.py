"""Dedicated annual amplitude Oracles and LONG TOP5 daily research portfolios.

Frozen ordinary-share lists selected using 2026 outcomes: retrospective universe,
never independent OOS evidence. Local archives only, no SQL/API/order/promotion.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from common.trading_costs import TradingCostModel
from common.daily_bar_sources import select_daily_bars, preferred_daily_source
from modelFactory.oracle_path import target_name
from modelFactory.oracle_path.labels import classify
from modelFactory.oracle_path.train import train_model
from modelFactory.oracle.security_continuity import load_security_discontinuities
from scripts.research.us_predictable_symbols_20261103 import digest, save, label_arrays
from scripts.research.us_winner_per_symbol_long_20261103 import INPUTS
from modelFactory.oracle.build_labels import nyse_sessions

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'artifacts/research/us_predictable_symbols/20261103-v1'
OUT = ROOT/'artifacts/research/us_selected_universe_oracle/20261104-v2'
END = pd.Timestamp('2026-10-19')  # last shared recent archive session, no fake refresh
CASES = {'winner_h10': (10, 32), 'parcours_h20': (20, 37)}
YEARS = (2024, 2025, 2026)
LOG = logging.getLogger(__name__)
PARAMS = dict(learning_rate=.03, max_depth=5, lgbm_num_leaves=31,
    lgbm_min_child_samples=150, lgbm_reg_alpha=.1, lgbm_reg_lambda=.1,
    lgbm_subsample=.8, lgbm_colsample_bytree=.7, n_estimators=200,
    lgbm_early_stopping_rounds=20)
POLICY = dict(initial_equity=4000., top_n=5, leverage=1., stop_loss_pct=.05,
    take_profit_pct=None, trailing_stop_pct=None, initial_position_fraction=1.,
    confirmation_bars=0, reinforcement=False, max_positions=20,
    max_position_weight=.20, risk_per_trade_pct=.0125, min_notional=50.,
    fractional_shares=False, fee_per_leg=TradingCostModel().per_leg_cost_pct,
    production_risk_module=False, portfolio_drawdown_breaker=False,
    entry_timing='Next official session open; no duplicate held symbol',
    entry_quality_policy='Per-entry complete observed path through min(expiry,run end); retrospective data gate',
    dividends='No separate cash dividend credit; use archived adjustment basis',
    accounting='Daily archived OHLC; estimated fees include half-spread, commission, slippage')


def split_year(dataset, year, target):
    validation_start = pd.Timestamp(f'{year-1}-01-01')
    test_start = pd.Timestamp(f'{year}-01-01')
    qualified = dataset[dataset[target].notna()]
    train = qualified[qualified.date.lt(validation_start) & qualified.oracle_available_date.lt(validation_start)]
    val = qualified[qualified.date.ge(validation_start) & qualified.date.lt(test_start)
        & qualified.oracle_available_date.lt(test_start)]
    # Inference has no requirement on future path/label availability.
    test = dataset[dataset.date.ge(test_start) & dataset.date.lt(pd.Timestamp(f'{year+1}-01-01'))]
    return train, val, test


def freeze_top(scores, count=5):
    if scores.duplicated(['date', 'symbol']).any():
        raise ValueError('Duplicate score identity')
    if not scores.score.between(0, 1).all():
        raise ValueError('Invalid amplitude score')
    a = scores.sort_values(['date', 'score', 'symbol'], ascending=[True, False, True]).copy()
    a['oracle_rank'] = a.groupby('date').cumcount()+1
    return a[a.oracle_rank.le(count)].copy()


def build_dataset(names, horizon, calendar):
    frames, bars, hashes = [], {}, {}
    registry = load_security_discontinuities()
    for symbol in names:
        folder = BASE/'symbols'/symbol
        source = folder/'source-bars.parquet'
        features = folder/'winner_h10-panel.parquet'
        receipt = json.loads((folder/'result.json').read_text(encoding='utf-8'))
        if digest(source) != receipt['bars_sha256']:
            raise ValueError('Frozen bars changed: '+symbol)
        raw = select_daily_bars(pd.read_parquet(source)).sort_values('date')
        if raw.date.duplicated().any() or set(raw.symbol) != {symbol}:
            raise ValueError('Ambiguous daily identity: '+symbol)
        raw = raw[raw.date.le(calendar[-1])].copy()
        bars[symbol] = raw
        hashes.update({str(source): digest(source), str(features): digest(features),
            str(folder/'result.json'): digest(folder/'result.json')})
        f = pd.read_parquet(features)[['date', *INPUTS]]
        f = f[f.date.le(END)].copy()
        f[INPUTS] = f[INPUTS].replace([np.inf, -np.inf], np.nan)
        f = f[f[INPUTS].notna().mean(axis=1).ge(.8)]
        p, valid = label_arrays(raw, calendar, horizon+1, registry.get(symbol, ()))
        n = len(calendar)-horizon
        highs = np.lib.stride_tricks.sliding_window_view(p[:, 1], horizon+1)[:, 1:]
        lows = np.lib.stride_tricks.sliding_window_view(p[:, 2], horizon+1)[:, 1:]
        up = np.maximum(0., highs.max(axis=1)/p[:n, 3]-1.)
        down = np.maximum(0., 1.-lows.min(axis=1)/p[:n, 3])
        available = pd.Series(calendar).shift(-(horizon+1)).iloc[:n].to_numpy()
        valid &= ~pd.isna(available)
        paths = pd.DataFrame(dict(date=calendar[:n], path_qualified=valid,
            path_amplitude=np.where(valid, np.maximum(up, down), np.nan),
            oracle_available_date=available))
        f = f.merge(paths, on='date', how='left', validate='one_to_one')
        f['path_qualified'] = f.path_qualified.eq(True)
        f['symbol'] = symbol
        frames.append(f)
    allrows = pd.concat(frames, ignore_index=True)
    # Membership is feature-observable at J, not selected by future valid labels.
    allrows = classify(allrows, min_universe=20, min_coverage=.95, horizon=horizon)
    return allrows, bars, hashes


def fit_case(folder, names, horizon, calendar):
    folder.mkdir(parents=True, exist_ok=False)
    dataset, bars, hashes = build_dataset(names, horizon, calendar)
    dataset.to_parquet(folder/'dataset.parquet', index=False)
    save(folder/'source-hashes.json', hashes)
    target = target_name(horizon)
    models, predictions = [], []
    for year in YEARS:
        save(OUT/'progress.json', dict(status='RUNNING', phase='TRAIN', case=folder.name, year=year))
        train, val, test = split_year(dataset, year, target)
        if train.date.nunique() < 504 or val.date.nunique() < 126:
            raise ValueError(f'Insufficient causal dates {folder.name}/{year}')
        if any(a[target].nunique() != 2 for a in (train, val)) or test.empty:
            raise ValueError('Empty/constant annual model split')
        cfg = SimpleNamespace(baseline=SimpleNamespace(**PARAMS),
            reproducibility=SimpleNamespace(seed=20261104), max_workers=2, oracle_horizon=horizon)
        LOG.info('TRAIN %s %s train=%s val=%s test=%s', folder.name, year, len(train), len(val), len(test))
        model = train_model(train, val, INPUTS, cfg)
        path = folder/f'oracle-path-H{horizon}-{year}.txt'
        model.save_model(str(path))
        vp = model.predict(val[INPUTS], num_threads=2)
        p = model.predict(test[INPUTS], num_threads=2)
        scored = test[['date', 'symbol', target, 'path_amplitude', 'oracle_available_date']].copy()
        scored['score'] = p
        scored['model_year'] = year
        known = scored[scored[target].notna()]
        top = freeze_top(scored)
        known_top = top[top[target].notna()]
        record = dict(year=year, model=str(path), model_sha256=digest(path),
            train_rows=len(train), train_dates=train.date.nunique(),
            train_last_date=str(train.date.max()), train_label_available_max=str(train.oracle_available_date.max()),
            validation_rows=len(val), validation_dates=val.date.nunique(),
            validation_last_date=str(val.date.max()), validation_label_available_max=str(val.oracle_available_date.max()),
            first_test_date=str(test.date.min()), last_test_date=str(test.date.max()),
            best_iteration=model.best_iteration, validation_auc=float(roc_auc_score(val[target], vp)),
            test_auc=float(roc_auc_score(known[target], known.score)) if known[target].nunique()==2 else None,
            test_label_rows=len(known), test_scored_rows=len(scored),
            top5_extreme_precision=float(known_top[target].mean()) if len(known_top) else None,
            top5_path_amplitude_mean_pct=float(known_top.path_amplitude.mean()*100) if len(known_top) else None,
            universe_path_amplitude_mean_pct=float(known.path_amplitude.mean()*100) if len(known) else None)
        assert pd.Timestamp(record['train_label_available_max']) < pd.Timestamp(f'{year-1}-01-01')
        assert pd.Timestamp(record['validation_label_available_max']) < pd.Timestamp(f'{year}-01-01')
        reloaded = __import__('lightgbm').Booster(model_file=str(path))
        assert np.allclose(reloaded.predict(test[INPUTS].head(5), num_threads=2), p[:5], rtol=0, atol=1e-12)
        save(folder/f'model-{year}-receipt.json', record)
        models.append(record)
        predictions.append(scored)
    scored = pd.concat(predictions, ignore_index=True)
    top = freeze_top(scored)
    assert not scored.duplicated(['date', 'symbol']).any()
    scored.to_parquet(folder/'all-scores.parquet', index=False)
    top.to_csv(folder/'daily-top5.csv', index=False)
    save(folder/'training-report.json', dict(models=models, backend='lightgbm',
        features=INPUTS, horizon=horizon, target='Cross-sectional TOP20% of absolute future path amplitude from close J',
        min_universe=20, min_coverage=.95, scores_are_direction_probabilities=False,
        source_2026_selection_bias=True, deployable_production_bundle=False))
    return bars, top, models, hashes


def prepare_prices(bars, calendar):
    """Return same-basis OHLC plus causal validity, no filled price invention."""
    arrays = {}
    for symbol, frame in bars.items():
        a = frame.set_index('date').reindex(calendar)
        factor = a.adj_close.fillna(a.close)/a.close
        p = a[['open', 'high', 'low', 'close']].multiply(factor, axis=0).to_numpy(float)
        good = (np.isfinite(p).all(axis=1) & (p>0).all(axis=1)
            & (p[:, 1]>=np.maximum(p[:, 0], p[:, 3]))
            & (p[:, 2]<=np.minimum(p[:, 0], p[:, 3]))
            & a.volume.gt(0).to_numpy() & a.is_filled.eq(0).to_numpy()
            & a.instrument_id.notna().to_numpy() & a.data_source.notna().to_numpy())
        arrays[symbol] = (p, good, a.instrument_id.to_numpy(), a.data_source.to_numpy())
    return arrays


def summarize_portfolio(daily, trades, initial, open_positions, total_cost):
    d = pd.DataFrame(daily)
    t = pd.DataFrame(trades)
    pnl = t.pnl if len(t) else pd.Series(dtype=float)
    wins = t[t.pnl>0] if len(t) else pd.DataFrame()
    losses = t[t.pnl<0] if len(t) else pd.DataFrame()
    curve = np.r_[initial, d.equity.to_numpy(float)]
    dd = curve/np.maximum.accumulate(curve)-1.
    return dict(initial_equity=initial, final_equity=float(curve[-1]),
        return_pct=float(100*(curve[-1]/initial-1)), max_drawdown_pct=float(100*dd.min()),
        closed_trades=len(t), winners=len(wins), losers=len(losses), breakeven=int(pnl.eq(0).sum()),
        win_pct=float(100*(pnl>0).mean()) if len(t) else None,
        gross_winning_pnl=float(pnl[pnl>0].sum()), gross_losing_pnl=float(pnl[pnl<0].sum()),
        average_winning_pnl=float(wins.pnl.mean()) if len(wins) else None,
        average_losing_pnl=float(losses.pnl.mean()) if len(losses) else None,
        average_winning_holding_sessions=float(wins.holding_sessions.mean()) if len(wins) else None,
        average_losing_holding_sessions=float(losses.holding_sessions.mean()) if len(losses) else None,
        average_gross_capital=float(d.gross.mean()), maximum_gross_capital=float(d.gross.max()),
        average_gross_equity_pct=float(100*(d.gross/d.equity).mean()),
        estimated_transaction_costs=total_cost, open_positions=open_positions,
        realized_pnl=float(pnl.sum()), unrealized_pnl=float(curve[-1]-initial-pnl.sum()),
        drawdown_basis='Daily close including initial deposit; not intraday DD')


def replay(top, prices, calendar, start, end, horizon, policy=None):
    """Cash-constrained LONG OHLC replay; no high/low used for open sizing."""
    cfg = dict(POLICY if policy is None else policy)
    fee, initial = cfg['fee_per_leg'], cfg['initial_equity']
    cash = initial
    positions, trades, daily, audit = {}, [], [], []
    cost = 0.
    registry = load_security_discontinuities()
    day_signals = {d: g.sort_values('oracle_rank').to_dict('records') for d, g in top.groupby('date')}
    indices = np.flatnonzero((calendar>=pd.Timestamp(start)) & (calendar<=pd.Timestamp(end)))
    end_i = indices[-1]

    def sell(symbol, i, price, reason):
        nonlocal cash, cost
        pos = positions.pop(symbol)
        charge = pos['quantity']*price*fee
        proceeds = pos['quantity']*price-charge
        cash += proceeds
        cost += charge
        trades.append(dict(symbol=symbol, signal_date=pos['signal_date'], entry_date=calendar[pos['entry_i']],
            exit_date=calendar[i], quantity=pos['quantity'], entry_price=pos['price'], exit_price=price,
            entry_cost=pos['entry_cost'], exit_cost=charge, pnl=proceeds-pos['basis'],
            net_return_pct=100*(proceeds/pos['basis']-1), reason=reason,
            holding_sessions=(i-pos['entry_i'] if reason in ('TIME_OPEN', 'SL_GAP') else i-pos['entry_i']+1)))

    for i in indices:
        day = calendar[i]
        held_at_open = set(positions)
        for symbol in list(positions):
            p, good, _, _ = prices[symbol]
            if not good[i]:
                raise ValueError(f'Missing held bar despite entry gate: {symbol}/{day}')
            pos = positions[symbol]
            if i-pos['entry_i'] >= horizon:
                sell(symbol, i, float(p[i, 0]), 'TIME_OPEN')
            elif p[i, 0] <= pos['stop']:
                sell(symbol, i, float(p[i, 0]), 'SL_GAP')
        # Opening exits fund opening buys. Intraday stop proceeds do NOT.
        open_equity = cash+sum(v['quantity']*prices[s][0][i, 0] for s, v in positions.items())
        signals = day_signals.get(calendar[i-1], []) if i else []
        for row in signals:
            symbol = row['symbol']
            event = dict(date=day, signal_date=calendar[i-1], symbol=symbol,
                rank=row['oracle_rank'], score=row['score'])
            if symbol in held_at_open or symbol in positions:
                audit.append(dict(event, status='ALREADY_HELD')); continue
            if len(positions) >= cfg['max_positions']:
                audit.append(dict(event, status='MAX_POSITIONS')); continue
            p, good, identity, source = prices[symbol]
            last = min(i+horizon, end_i)
            window = slice(i, last+1)
            missing = calendar[i:last+1][~good[window]]
            valid = good[window].all()
            valid &= len(set(identity[window]))==1 and len(set(source[window]))==1
            valid &= not any(e.crosses(calendar[i], calendar[last]) for e in registry.get(symbol, ()))
            if not valid:
                audit.append(dict(event, status='INCOMPLETE_OBSERVED_HOLDING_WINDOW',
                    missing_dates=','.join(str(d.date()) for d in missing),
                    retrospective_quality_gate=True)); continue
            price = float(p[i, 0])
            budget = min(open_equity*cfg['max_position_weight'],
                open_equity*cfg['risk_per_trade_pct']/(cfg['stop_loss_pct']+2*fee))
            quantity = math.floor(min(budget, cash/(1+fee))/price+1e-12)
            if quantity < 1 or quantity*price < cfg['min_notional']:
                audit.append(dict(event, status='INSUFFICIENT_CASH_OR_SIZING')); continue
            basis = quantity*price*(1+fee)
            assert basis <= cash+1e-8
            cash -= basis
            cost += quantity*price*fee
            positions[symbol] = dict(entry_i=i, price=price, quantity=quantity,
                stop=price*(1-cfg['stop_loss_pct']), basis=basis,
                entry_cost=quantity*price*fee, signal_date=calendar[i-1])
            audit.append(dict(event, status='BOUGHT', quantity=quantity, price=price, notional=quantity*price))
        for symbol in list(positions):
            pos = positions[symbol]
            if prices[symbol][0][i, 2] <= pos['stop']:
                sell(symbol, i, pos['stop'], 'SL')
        gross = sum(v['quantity']*prices[s][0][i, 3] for s, v in positions.items())
        eq = cash+gross
        assert cash >= -1e-7 and gross <= eq+1e-7 and eq > 0
        daily.append(dict(date=day, cash=cash, gross=gross, equity=eq, positions=len(positions)))
    opened = [dict(symbol=s, quantity=v['quantity'], entry_date=str(calendar[v['entry_i']].date()),
        entry_price=v['price'], mark=float(prices[s][0][end_i, 3]), stop=v['stop']) for s, v in positions.items()]
    result = summarize_portfolio(daily, trades, initial, opened, cost)
    result.update(start=str(calendar[indices[0]].date()), end=str(calendar[indices[-1]].date()),
        status='INCOMPLETE_COVERAGE_EXPLORATORY' if any(r['status']=='INCOMPLETE_OBSERVED_HOLDING_WINDOW' for r in audit)
            else 'COMPLETED_RETROSPECTIVE_EXPLORATORY',
        excluded_missing_entry_days=sum(r['status']=='INCOMPLETE_OBSERVED_HOLDING_WINDOW' for r in audit),
        buys=sum(r['status']=='BOUGHT' for r in audit), final_positions=len(opened), full_live_parity=False,
        no_forced_terminal_liquidation=True, policy=cfg, horizon_sessions=horizon,
        audit_status_counts=pd.Series([r['status'] for r in audit],dtype=str).value_counts().to_dict())
    return result, pd.DataFrame(daily), pd.DataFrame(trades), pd.DataFrame(audit)


def main():
    if OUT.exists():
        raise FileExistsError('Fresh campaign required')
    OUT.mkdir(parents=True)
    calendar = nyse_sessions(pd.Timestamp('2016-01-01').date(), END.date())
    files = [ROOT/'config/univers_batch'/f'symbols_{t}_auc_gt060.txt' for t in CASES]
    files += [Path(__file__), ROOT/'common/trading_costs.py', ROOT/'modelFactory/oracle_path/train.py',
        ROOT/'modelFactory/oracle_path/labels.py', ROOT/'scripts/research/us_predictable_symbols_20261103.py',
        ROOT/'config/data_quality/security_discontinuities.json', ROOT/'common/daily_bar_sources.py', ROOT/'config.yaml']
    hashes = {str(p): digest(p) for p in files}
    save(OUT/'protocol.json', dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        cases=CASES, years=YEARS, data_end=str(END.date()), requested_years='2024-2026 partial',
        cutoff_reason='Last shared recent session in existing frozen archives; no new provider downloads',
        daily_bars_preferred_source=preferred_daily_source(),
        supersedes='20261104-v1 failed before training: source exports contain EODHD/SIP pairs; canonical whole-row selection now applied',
        target='Native Oracle path amplitude TOP20% within each dedicated universe, H10 or H20',
        direction='LONG policy, not directional prediction by the amplitude Oracle',
        features=INPUTS, fit=PARAMS, policy=POLICY, source_hashes=hashes,
        annual_split='Train dates/labels before Y-1; validate Y-1 with labels before Y; infer Y',
        universe_bias='Lists selected using OOS2023-2025 plus 2026 outcomes; all economic results retrospective',
        annual_capital='4000 USD separately each year; additional continuous account without reset',
        limitations=['Daily OHLC proxy, no Winner 2x5m confirmation/reinforcement or production risk engine',
            'No portfolio DD circuit breaker, factor/sector/correlation/borrow/spread guards',
            'Missing holding-window data excludes only that symbol/entry date after frozen TOP5; retrospective gate',
            'No refill from ranks6+ when a candidate is held, unqualified or unaffordable',
            'Survivor and hindsight-selected universes, current archive adjustment conventions',
            'No separate cash dividend credit or legal corporate-action continuity certification',
            'Open positions marked at final close, no forced exit before planned horizon',
            'Daily close DD understates possible intraday drawdown'],
        production_changed=False, sql_writes=False, sql_reads=False, provider_calls=0, orders=0))
    rows, cases = [], {}
    try:
        for name, (horizon, expected) in CASES.items():
            names = (ROOT/'config/univers_batch'/f'symbols_{name}_auc_gt060.txt').read_text().strip().split(',')
            assert len(names)==len(set(names))==expected
            folder = OUT/name
            bars, top, models, sources = fit_case(folder, names, horizon, calendar)
            prices = prepare_prices(bars, calendar)
            reports = {}
            for period in [2024, 2025, 2026, 'continuous']:
                save(OUT/'progress.json', dict(status='RUNNING', phase='REPLAY', case=name, period=period))
                start = '2024-01-01' if period=='continuous' else f'{period}-01-01'
                end = END if period in ('continuous', 2026) else pd.Timestamp(f'{period}-12-31')
                report, daily, trades, audit = replay(top, prices, calendar, start, end, horizon)
                dest = folder/str(period)
                dest.mkdir()
                daily.to_csv(dest/'equity.csv', index=False)
                trades.to_csv(dest/'trades.csv', index=False)
                audit.to_csv(dest/'entry-audit.csv', index=False)
                excluded = audit[audit.status.eq('INCOMPLETE_OBSERVED_HOLDING_WINDOW')]
                excluded.to_csv(dest/'missing-entry-days.csv', index=False)
                save(dest/'report.json', report)
                reports[str(period)] = report
                rows.append(dict(case=name, period=period, **{k: v for k, v in report.items()
                    if k not in ('policy', 'open_positions', 'audit_status_counts')}))
                LOG.info('RESULT %s %s return=%.2f DD=%.2f trades=%s',
                    name, period, report['return_pct'], report['max_drawdown_pct'], report['closed_trades'])
            assert all(digest(p)==h for p,h in sources.items())
            cases[name] = dict(models=models, reports=reports, universe=names, horizon=horizon)
        assert all(digest(p)==h for p,h in hashes.items())
        pd.DataFrame(rows).to_csv(OUT/'summary.csv', index=False)
        save(OUT/'report.json', dict(status='COMPLETED_RETROSPECTIVE_EXPLORATORY', cases=cases,
            trained_models=6, portfolio_replays=8, data_end=str(END.date()),
            universe_selection_uses_2026=True, full_live_parity=False,
            sql_writes=False, sql_reads=False, provider_calls=0, orders=0))
        save(OUT/'progress.json', dict(status='COMPLETED_RETROSPECTIVE_EXPLORATORY', trained_models=6, portfolio_replays=8))
    except Exception as exc:
        save(OUT/'progress.json', dict(status='FAILED', error_type=type(exc).__name__, error=str(exc)))
        raise


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    import requests
    def forbidden(*args, **kwargs):
        raise RuntimeError('HTTP forbidden in offline research')
    requests.Session.request = forbidden
    main()
