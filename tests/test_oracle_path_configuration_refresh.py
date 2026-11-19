"""Exercise an already-imported pre-fraction reader, not only a clean process."""
from copy import deepcopy

import pytest


def config():
    return dict(oracle_path=dict(directional=dict(enabled=True, oracle_top_fraction=.10,
        oracle_top_n=20, selected_n=10, stop_loss_pct=.05, horizon_sessions=10, fee_per_leg=.0008)))


def test_stale_reader_reproduces_error_then_refreshes_without_rewriting_config(monkeypatch):
    from modelFactory.oracle_path import directional as module
    from ihm.services.oracle_path_configuration import load_directional_settings
    raw = config();original = deepcopy(raw)
    monkeypatch.setattr('common.config_loader.load_config', lambda: raw)
    def legacy_settings(horizon=None, feature_mode=None):
        return module.Settings(**raw['oracle_path']['directional'])
    monkeypatch.setattr(module, 'settings', legacy_settings)
    monkeypatch.delattr(module, 'CONFIG_READER_VERSION')
    with pytest.raises(TypeError, match='oracle_top_fraction'):
        legacy_settings()
    preview = load_directional_settings()
    assert preview.enabled and preview.selected_n == 10 and preview.oracle_top_n == 20
    trained = load_directional_settings(universe_size=1790, horizon=10)
    assert trained.oracle_top_n == 179 and trained.selected_n == 10
    assert module.CONFIG_READER_VERSION == 2 and raw == original


def test_current_reader_is_not_reloaded_on_every_render(monkeypatch):
    import ihm.services.oracle_path_configuration as ui
    from modelFactory.oracle_path import directional as module
    monkeypatch.setattr('common.config_loader.load_config', config)
    monkeypatch.setattr(ui, 'reload', lambda *_: pytest.fail('Current reader should stay loaded'))
    assert module.CONFIG_READER_VERSION == 2
    assert ui.load_directional_settings().enabled
    assert ui.load_directional_settings(horizon=15).horizon_sessions == 15


def test_invalid_fraction_is_still_rejected(monkeypatch):
    from ihm.services.oracle_path_configuration import load_directional_settings
    raw = config();raw['oracle_path']['directional']['oracle_top_fraction'] = 10
    monkeypatch.setattr('common.config_loader.load_config', lambda: raw)
    with pytest.raises(ValueError, match='fraction'):
        load_directional_settings()
