import json
from pathlib import Path

import pytest

from service.fr.research_catalog_14a import CATALOG, economic_rows, load_campaign


def write_ml(tmp_path, **updates):
    path = tmp_path / CATALOG['oracle_h5'][1]
    path.parent.mkdir(parents=True)
    report = {'config': {'market_code': 'FR_EQ', 'horizon': 5},
              'serving_enabled': False, 'canonical_writes': False,
              'verdict': 'NO_GO'}
    report.update(updates)
    path.write_text(json.dumps(report), encoding='utf-8')
    return path


def test_scoped_catalog_and_export(tmp_path):
    write_ml(tmp_path)
    result = load_campaign('oracle_h5', root=tmp_path)
    assert result['market_code'] == 'FR_EQ'
    assert result['currency'] == 'EUR'
    assert result['database'] == 'alpha_trade_fr'
    assert result['live_enabled'] is False
    assert len(result['report_sha256']) == 64
    assert economic_rows(result) == []


@pytest.mark.parametrize('updates', [
    {'serving_enabled': True}, {'canonical_writes': True},
    {'config': {'market_code': 'US_EQ', 'horizon': 5}},
    {'config': {'market_code': 'FR_EQ', 'horizon': 20}},
])
def test_incompatible_reports_rejected(tmp_path, updates):
    write_ml(tmp_path, **updates)
    with pytest.raises(ValueError):
        load_campaign('oracle_h5', root=tmp_path)


def test_missing_unknown_no_fallback(tmp_path):
    with pytest.raises(ValueError):
        load_campaign('../US_EQ', root=tmp_path)
    with pytest.raises(FileNotFoundError):
        load_campaign('oracle_h5', root=tmp_path)


def test_economic_fields_keep_zero_and_unknown_separate():
    cell = dict(fold=6, policy='oracle', variant='baseline',
                tax_scenario='unknown_taxed', cost_scenario='nominal', status='complete',
                metrics={'net_return_pct': 0, 'costs_eur': {'commission': '1', 'taxes': '2'}})
    rows = economic_rows({'kind': 'economic', 'report': {'cells': [cell]}})
    assert rows[0]['Rendement net %'] == 0
    assert rows[0]['Commission EUR'] == '1'
    assert rows[0]['Taxes EUR'] == '2'
    assert rows[0]['Spread EUR'] is None


@pytest.mark.parametrize('module,kind,forbidden', [
    ('pipeline', 'pipeline', '_build_launch_options'),
    ('ml_diagnostics', 'diagnostic', 'db_available'),
    ('backtesting', 'backtest', 'get_runtime_db_config'),
])
def test_fr_returns_before_us_access(monkeypatch, module, kind, forbidden):
    import importlib
    from ihm.services import fr_research_market
    page = importlib.import_module(f'ihm.pages.{module}')
    observed = []
    monkeypatch.setattr(page.st, 'header', lambda *a, **k: None)
    monkeypatch.setattr(page.st, 'caption', lambda *a, **k: None)
    monkeypatch.setattr(page, 'select_market', lambda chosen: 'FR_EQ')
    monkeypatch.setattr(fr_research_market, 'render_fr_research_view', lambda chosen: observed.append(chosen))
    def reject(*a, **k):
        raise AssertionError('US path used from FR')
    monkeypatch.setattr(page, forbidden, reject)
    page.render()
    assert observed == [kind]


def test_fr_batches_dont_query_or_install_us(monkeypatch):
    from ihm.pages import batches
    from ihm.services import fr_batch_view
    rendered = []
    monkeypatch.setattr(fr_batch_view, 'render_fr_batches', lambda: rendered.append('FR_EQ'))
    monkeypatch.setattr(batches.st, 'title', lambda *a, **k: None)
    monkeypatch.setattr(batches.st, 'selectbox', lambda *a, **k: 'FR_EQ')
    monkeypatch.setattr(batches.st, 'warning', lambda *a, **k: None)
    monkeypatch.setattr(batches.st, 'info', lambda *a, **k: None)
    def reject(*a, **k):
        raise AssertionError('US/CN batch catalogue touched')
    monkeypatch.setattr(batches, 'load_batch_specs', reject)
    batches.render()
    assert rendered == ['FR_EQ']
