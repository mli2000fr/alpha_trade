"""Prospective cohorts only: realized gross returns, never used by selection."""
import argparse
import json
import math
from datetime import date, timedelta
from sqlalchemy import text, select
from .repository import Repository, evaluations, utcnow, dumps, digest


def evaluate(engine, run_id, *, as_of=None, horizons=(5, 10, 20)):
    from common.market_calendar import _get_nyse_calendar
    as_of = as_of or utcnow().date()
    repo = Repository(engine)
    run, items = repo.get(run_id)
    if run['status'] != 'COMPLETED':
        raise ValueError('Analyse LLM non finalisée')
    day = run['trade_date']
    from zoneinfo import ZoneInfo
    from datetime import timezone
    if run['completed_at'].replace(tzinfo=timezone.utc).astimezone(ZoneInfo('America/New_York')).date() != day:
        raise ValueError('Analyse hors journée de décision : évaluation non qualifiée')
    calendar = _get_nyse_calendar()
    if calendar is None:
        raise ValueError('Calendrier NYSE officiel indisponible')
    schedule = calendar.schedule(start_date=day, end_date=day+timedelta(days=100))
    sessions = [index.date() for index in schedule.index if index.date() >= day]
    if not sessions or sessions[0] != day:
        raise ValueError('Date décision absente du calendrier')
    completed, pending, rejected = [], [], []
    for item in items:
        for horizon in horizons:
            if type(horizon) is not int or horizon < 1 or horizon >= len(sessions):
                raise ValueError('Horizon invalide')
            entry_day, exit_day = sessions[1], sessions[horizon]
            if exit_day >= as_of:  # Wait until a later day, never use an unfinished session.
                pending.append([item['symbol'], horizon])
                continue
            with engine.connect() as conn:
                exists = conn.execute(select(evaluations.c.run_id).where(
                    evaluations.c.run_id == run_id, evaluations.c.symbol == item['symbol'],
                    evaluations.c.horizon == horizon)).first()
                if exists:
                    continue  # Immutable already observed evaluation, no overwrite.
                bars = conn.execute(text('''SELECT date, open, close, adj_close, is_filled
                    FROM stock_bars_daily WHERE symbol=:symbol AND date>=:start AND date<=:end
                    ORDER BY date'''), {'symbol': item['symbol'], 'start': day, 'end': exit_day}).mappings().all()
                label = conn.execute(text('''SELECT oracle_decile, oracle_available_date, target_quality_valid
                    FROM global_oracle_labels WHERE batch_id=:batch AND symbol=:symbol
                    AND prediction_date=:day AND horizon=:horizon'''),
                    {'batch': run['batch_id'], 'symbol': item['symbol'], 'day': day, 'horizon': horizon}).mappings().first()
            expected_dates = sessions[:horizon+1]
            if [date.fromisoformat(str(b['date'])[:10]) for b in bars] != expected_dates or any(b['is_filled'] for b in bars):
                rejected.append([item['symbol'], horizon, 'missing_or_filled_bars'])
                continue
            if any(not math.isfinite(float(b[k] or 0)) or float(b[k] or 0) <= 0
                   for b in bars for k in ('open', 'close', 'adj_close')):
                rejected.append([item['symbol'], horizon, 'invalid_prices'])
                continue
            # Adjust opening price on the same scale as adjusted closing prices.
            adjusted_entry = float(bars[1]['open']) * float(bars[1]['adj_close']) / float(bars[1]['close'])
            gross = (float(bars[-1]['adj_close']) / adjusted_entry - 1) * 100
            signal = (float(bars[-1]['adj_close']) / float(bars[0]['adj_close']) - 1) * 100
            decile = None
            if (label and label['target_quality_valid'] and label['oracle_available_date']
                    and date.fromisoformat(str(label['oracle_available_date'])[:10]) <= as_of):
                decile = label['oracle_decile']
            values = dict(run_id=run_id, symbol=item['symbol'], horizon=horizon,
                evaluated_at=utcnow(), entry_date=entry_day, exit_date=exit_day,
                return_pct=gross, signal_return_pct=signal, selected=bool(item['selected']),
                oracle_decile=decile, lineage_json=dumps({'basis': 'adjusted_close_and_adjusted_next_open',
                    'bars_sha256': digest([dict(b) for b in bars]),
                    'gross_not_economic_backtest': True, 'as_of': str(as_of),
                    'label_available_date': str(label['oracle_available_date']) if label else None}))
            with engine.begin() as conn:
                conn.execute(evaluations.insert().values(**values))
            completed.append([item['symbol'], horizon, gross, decile, bool(item['selected'])])
    return {'run_id': run_id, 'evaluated': completed, 'pending': pending, 'rejected': rejected,
            'note': 'Rendements bruts ajustés, sans frais ni sizing; aucune conclusion de profitabilité'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--as-of', type=date.fromisoformat)
    args = parser.parse_args()
    if args.as_of and args.as_of > utcnow().date():
        raise ValueError('as-of future interdite')
    from database.connection import get_sqlalchemy_engine
    print(dumps(evaluate(get_sqlalchemy_engine(), **vars(args))))


if __name__ == '__main__':
    main()
