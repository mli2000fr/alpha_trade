"""Bounded read-only follow-up of the completed H20 dataset quality audit."""
import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from modelFactory.factor_features import compute_factor_features
from modelFactory.features import _build_adjusted_price_frame
from scripts.research.us_concentrated_historical_tapes import atomic_json


def run(root):
    report = json.loads((root / 'report.json').read_text())
    if report['status'] != 'COMPLETED_READ_ONLY_AUDIT':
        raise ValueError('Completed audit required')
    checks = Counter()
    current_checks = Counter()
    reasons = Counter()
    for item in report['yearly']:
        reasons.update(item['labels']['quality_reasons'])
        checks.update({name: values['original_batch'] for name, values in item['labels']['checks'].items()})
        current_checks.update({name: values['current_universe'] for name, values in item['labels']['checks'].items()})
    counter = Counter()
    examples = {}
    loss_distribution = Counter()
    for marker in sorted(root.glob('features-*.json')):
        payload = json.loads(marker.read_text())
        loss_distribution.update(payload['not_emitted_by_symbol'].values())
        frame = pd.read_parquet(marker.with_suffix('.parquet'), columns=[
            'date', 'symbol', 'rsi_14_div_volatility_20', 'rsi_14', 'rolling_volatility_20',
            'log_return_div_intraday_range', 'log_return', 'intraday_range',
            'selector_short_score'])
        conditions = {
            'rsi_vol_ratio_abs_gt_1e6': frame.rsi_14_div_volatility_20.abs().gt(1e6),
            'rsi_vol_ratio_abs_gt_1e6_with_floor': frame.rsi_14_div_volatility_20.abs().gt(1e6) & frame.rolling_volatility_20.le(1e-8),
            'log_range_ratio_abs_gt_1e6': frame.log_return_div_intraday_range.abs().gt(1e6),
            'log_range_ratio_abs_gt_1e6_with_floor': frame.log_return_div_intraday_range.abs().gt(1e6) & frame.intraday_range.le(1e-8),
            'nonpositive_intraday_range': frame.intraday_range.le(0),
            'negative_intraday_range': frame.intraday_range.lt(0),
            'short_score_zero': frame.selector_short_score.eq(0),
        }
        for name, mask in conditions.items():
            counter[name] += int(mask.sum())
            if name not in examples:
                examples[name] = []
            if len(examples[name]) < 5:
                for row in frame.loc[mask].head(5 - len(examples[name])).to_dict('records'):
                    row['date'] = str(pd.Timestamp(row['date']).date())
                    examples[name].append(row)
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database != 'alpha_trade':
        raise ValueError('US database required')
    with engine.connect() as conn:
        conn.exec_driver_sql('SET TRANSACTION READ ONLY')
        benchmark = pd.read_sql(text('''SELECT `date`,`open`,high,low,`close`,adj_close,
            volume,vwap,daily_return,is_filled FROM stock_bars_daily
            WHERE symbol='SPY' AND `date` BETWEEN '2012-12-27' AND '2024-12-31'
            ORDER BY `date`'''), conn, parse_dates=['date'])
        endpoint_samples = []
        for symbol, day in [('FLUT', '2016-01-11'), ('BWLP', '2020-02-04'), ('EVVTY', '2019-06-05')]:
            raw = pd.read_sql(text('''SELECT symbol,`date`,`open`,high,low,`close`,adj_close,volume,vwap,data_source
                FROM stock_bars_daily WHERE symbol=:symbol AND `date`=:day'''), conn,
                params=dict(symbol=symbol, day=day))
            endpoint_samples.extend(json.loads(raw.to_json(orient='records', date_format='iso')))
    price = _build_adjusted_price_frame(benchmark)
    stock = pd.DataFrame(dict(date=benchmark.date, daily_return=price.close.pct_change(fill_method=None).fillna(0)))
    actual = compute_factor_features(stock, benchmark)
    derived = benchmark.copy()
    derived['daily_return'] = stock.daily_return
    counterfactual = compute_factor_features(stock, derived)
    factors = ['beta_252', 'alpha_252', 'r_squared_252', 'momentum_252_vs_market']
    result = dict(status='COMPLETED_READ_ONLY_INTERPRETATION',
        rows=report['rows'], original_label_rows=sum(y['labels']['rows'] for y in report['yearly']),
        valid_label_rows=sum(y['labels']['valid'] for y in report['yearly']),
        label_quality_reasons=dict(reasons), label_checks=dict(checks), current_universe_label_checks=dict(current_checks),
        feature_tail_counts=dict(counter), examples=examples,
        missing_feature_rows_distribution={str(k): v for k, v in sorted(loss_distribution.items())},
        benchmark_rows=len(benchmark), benchmark_stored_daily_return_null=int(benchmark.daily_return.isna().sum()),
        benchmark_derived_return_std=float(stock.daily_return.std()),
        spy_self_factor_actual_last=json.loads(actual[factors].tail(1).to_json(orient='records')),
        spy_self_factor_with_derived_benchmark_return_last=json.loads(counterfactual[factors].tail(1).to_json(orient='records')),
        local_bar_examples=endpoint_samples,
        interpretation='Offline counterfactual only: no application source, model, SQL data or profile modified; 1e6 is a diagnostic threshold, not a trading gate')
    atomic_json(root / 'interpretation.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('examples', 'missing_feature_rows_distribution')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    run(parser.parse_args().root)
