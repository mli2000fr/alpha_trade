from pathlib import Path

import pytest

from scripts.maintenance import reset_us_models as reset


@pytest.mark.parametrize('relative', ['artifacts', 'artifacts/cn/oracle/model.txt',
    'artifacts/fr/research/model.txt', 'artifacts/operations/plan.json',
    'artifacts/research/cn_example/model.txt', 'artifacts/research/fr_example/model.txt',
    'backups/ml/model.txt', 'config.yaml'])
def test_protected_paths_rejected(tmp_path, monkeypatch, relative):
    monkeypatch.setattr(reset, 'WORKSPACE', tmp_path)
    with pytest.raises(ValueError):
        reset.safe_target(tmp_path/relative)


def test_models_and_reports_are_distinguished(tmp_path):
    model = tmp_path/'model.txt'
    report = tmp_path/'report.txt'
    model.write_text('tree\nversion=v4\nnum_class=1\n')
    report.write_text('Research results, no model weights')
    assert reset.model_file(model)
    assert not reset.model_file(report)


def test_scope_preserves_sources_and_foreign_models(tmp_path, monkeypatch):
    monkeypatch.setattr(reset, 'WORKSPACE', tmp_path)
    paths = ['artifacts/models/model-factory-us/long_model.txt',
        'artifacts/psv2_f1/model-factory-old/stock/best.ckpt',
        'artifacts/research/us_test/model.txt', 'artifacts/research/us_test/features.parquet',
        'artifacts/research/us_test/prices.parquet', 'artifacts/research/us_test/trades.parquet',
        'artifacts/research/us_test/report.txt', 'artifacts/research/cn_test/model.txt',
        'artifacts/cn/oracle/model.txt', 'artifacts/fr/research/model.txt']
    for relative in paths:
        path = tmp_path/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('tree\nversion=v4\n' if path.name == 'model.txt' else 'source')
    targets = {str(path.relative_to(tmp_path)).replace('\\', '/')
               for path in reset.filesystem_targets({'model_directories': []})}
    assert targets == {'artifacts/models/model-factory-us',
        'artifacts/psv2_f1/model-factory-old',
        'artifacts/research/us_test/model.txt'}


def test_sql_scope_does_not_include_market_or_execution_sources():
    assert set(reset.TABLES).isdisjoint({'stock_bars_daily', 'stock_bars_intraday', 'news_raw',
        'news_ticker_sentiment', 'stock_analyst_consensus_eodhd_history', 'execution_broker_orders',
        'execution_broker_fills', 'execution_positions', 'llm_directional_assessments'})
