from ihm.services import fr_operations_view_18 as view
from service.fr.operations_preparation_18 import build_report


class Container:
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass


def setup_ui(monkeypatch):
    observed = []
    monkeypatch.setattr(view.st, 'expander', lambda *a, **kw: Container())
    for name in ('warning', 'caption', 'dataframe', 'json', 'code', 'error', 'success', 'download_button'):
        monkeypatch.setattr(view.st, name,
            lambda *a, _name=name, **kw: observed.append((_name, a, kw)))
    return observed


def test_view_missing_configuration_does_not_promote_or_fallback(monkeypatch):
    observed = setup_ui(monkeypatch)
    monkeypatch.setattr(view, 'build_report', lambda: (_ for _ in ()).throw(ValueError('private-secret')))
    view.render_operations_preparation('pipeline')
    assert any(name == 'error' for name, _, _ in observed)
    assert 'private-secret' not in str(observed)
    assert not any(name == 'download_button' for name, _, _ in observed)


def test_view_exports_blockers_and_runs_only_offline_drills(monkeypatch):
    observed = setup_ui(monkeypatch)
    monkeypatch.setattr(view, 'build_report', lambda: build_report())
    monkeypatch.setattr(view.st, 'button', lambda *a, **kw: True)
    view.render_operations_preparation('pipeline')
    assert any(name == 'success' and 'aucun GO' in args[0] for name, args, _ in observed)
    exports = [args for name, args, _ in observed if name == 'download_button']
    assert len(exports) == 1 and 'BLOCKED_NO_LIVE_RELEASE' in exports[0][1]


def test_panel_visible_before_missing_campaign(monkeypatch):
    from ihm.services import fr_research_market as market
    observed = []
    monkeypatch.setattr(view, 'render_operations_preparation', lambda page: observed.append(page))
    for name in ('warning', 'caption', 'info', 'error'):
        monkeypatch.setattr(market.st, name, lambda *a, **kw: None)
    monkeypatch.setattr(market.st, 'selectbox', lambda *a, **kw: 'oracle_h5')
    monkeypatch.setattr(market, 'load_campaign', lambda *a: (_ for _ in ()).throw(FileNotFoundError()))
    market.render_fr_research_view('pipeline')
    assert observed == ['pipeline']
