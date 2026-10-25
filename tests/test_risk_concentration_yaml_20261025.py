"""Concentration YAML defaults, preset merging and explicit override priority."""
from pathlib import Path

import pytest
import yaml

from risk_management.config import RiskConfig, load_risk_config

CONFIG = Path(__file__).resolve().parents[1] / 'config.yaml'


@pytest.fixture(autouse=True)
def project_config(monkeypatch):
    # Use the ordinary production loading path with its supported environment
    # override; no alternative-file branch is needed for this YAML-only change.
    monkeypatch.setenv('ALPHA_TRADE_CONFIG_PATH',str(CONFIG))


def test_project_yaml_defines_ten_entries_over_one_hundred_calendar_days():
    section = yaml.safe_load(CONFIG.read_text(encoding='utf-8'))['risk_management']
    assert section['concentration_max_trades_per_symbol'] == 10
    assert section['concentration_window_calendar_days'] == 100


@pytest.mark.parametrize('equity', [1500.,4000.,8000.,15000.,30000.,60000.,150000.])
def test_capital_presets_keep_global_concentration_when_not_overridden(equity):
    cfg = load_risk_config(equity=equity)
    assert cfg.concentration_max_trades_per_symbol == 10
    assert cfg.concentration_window_calendar_days == 100


def test_explicit_overrides_still_take_priority_and_dataclass_defaults_are_unchanged():
    cfg = load_risk_config(equity=4000.,cli_overrides={
        'concentration_max_trades_per_symbol':2,'concentration_window_calendar_days':30})
    assert cfg.concentration_max_trades_per_symbol == 2
    assert cfg.concentration_window_calendar_days == 30
    assert RiskConfig().concentration_max_trades_per_symbol == 5
    assert RiskConfig().concentration_window_calendar_days == 180
