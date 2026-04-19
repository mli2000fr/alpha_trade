import io
import sys
import os
from unittest import mock
import contextlib
import types

import pytest
from corporate_actions import cli

# Ajout du dossier parent au sys.path pour import corporate_actions
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def make_args(command, **kwargs):
    parser = cli._build_parser()
    args_list = [command]
    for k, v in kwargs.items():
        if isinstance(v, bool):
            if v:
                args_list.append(f'--{k.replace("_", "-")}')
        elif v is not None:
            args_list.append(f'--{k.replace("_", "-")}')
            args_list.append(str(v))
    return parser.parse_args(args_list)

class DummyProvider:
    def __init__(self):
        self.called = {}
    def fetch_events(self, symbols=None, start_date=None, end_date=None):
        self.called['symbols'] = symbols
        self.called['start_date'] = start_date
        self.called['end_date'] = end_date
        return []

class DummyRepo:
    def load_latest_position_symbols(self):
        return ['AAPL', 'MSFT']
    def load_bars_available_symbols(self):
        return ['AAPL', 'MSFT']
    def get_total_dividends(self, symbol=None):
        return 42.0
    @property
    def engine(self):
        class DummyEngine:
            def connect(self):
                class DummyConn:
                    def execute(self, *a, **kw):
                        class DummyResult:
                            def mappings(self):
                                class DummyAll:
                                    def all(self):
                                        return [
                                            {'status': 'pending', 'ca_type': 'CASH_DIVIDEND', 'cnt': 2},
                                            {'status': 'applied', 'ca_type': 'SPLIT', 'cnt': 1},
                                        ]
                                return DummyAll()
                        return DummyResult()
                    def __enter__(self): return self
                    def __exit__(self, *a): pass
                return DummyConn()
        return DummyEngine()

def test_run_sync_invokes_engine(monkeypatch):
    args = make_args('sync', symbols=['AAPL'], batch_size=10)
    called = {}
    class DummyEngine:
        def sync(self, **kwargs):
            called.update(kwargs)
            return {'ok': True}
    monkeypatch.setattr(cli, 'AlpacaCorporateActionProvider', lambda **kw: None)
    monkeypatch.setattr(cli, 'CorporateActionRepository', lambda: DummyRepo())
    monkeypatch.setattr(cli, 'CorporateActionEngine', lambda provider, repo, account_id=None: DummyEngine())
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        cli._run_sync(args)
    out = f.getvalue()
    assert 'Sync termine' in out
    assert called['symbols'] == ['AAPL']
    assert called['batch_size'] == 10

def test_run_apply_invokes_engine(monkeypatch):
    args = make_args('apply', as_of='2026-04-19')
    called = {}
    class DummyEngine:
        def apply(self, as_of=None):
            called['as_of'] = as_of
            return {'ok': True}
    monkeypatch.setattr(cli, 'AlpacaCorporateActionProvider', lambda **kw: None)
    monkeypatch.setattr(cli, 'CorporateActionEngine', lambda provider, account_id=None: DummyEngine())
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        cli._run_apply(args)
    out = f.getvalue()
    assert 'Apply termine' in out
    assert str(called['as_of']) == '2026-04-19'

def test_run_status_prints(monkeypatch):
    monkeypatch.setattr(cli, 'CorporateActionRepository', lambda: DummyRepo())
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        cli._run_status(types.SimpleNamespace())
    out = f.getvalue()
    assert 'Status' in out and 'Total dividendes' in out

def test_run_all_invokes_both(monkeypatch):
    args = make_args('run', symbols=['AAPL'], batch_size=5, as_of='2026-04-19')
    sync_called = {}
    apply_called = {}
    class DummyEngine:
        def sync(self, **kwargs):
            sync_called.update(kwargs)
            return {'ok': True}
        def apply(self, as_of=None):
            apply_called['as_of'] = as_of
            return {'ok': True}
    monkeypatch.setattr(cli, 'AlpacaCorporateActionProvider', lambda **kw: None)
    monkeypatch.setattr(cli, 'CorporateActionRepository', lambda: DummyRepo())
    monkeypatch.setattr(cli, 'CorporateActionEngine', lambda provider, repo, account_id=None: DummyEngine())
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        cli._run_all(args)
    out = f.getvalue()
    assert 'Sync termine' in out and 'Apply termine' in out
    assert sync_called['symbols'] == ['AAPL']
    assert sync_called['batch_size'] == 5
    assert str(apply_called['as_of']) == '2026-04-19'
