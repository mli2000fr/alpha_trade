import sys
import os
# Ajout du dossier parent au sys.path pour import corporate_actions
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import io
import contextlib
import types
import logging
import pytest
from unittest import mock

from corporate_actions import corporate_action_run

def test_main_run_inject(monkeypatch):
    # Simule sys.argv sans sous-commande
    argv = ['corporate_action_run.py']
    called = {}
    monkeypatch.setattr(sys, 'argv', argv[:])
    monkeypatch.setattr(corporate_action_run, 'configure_root_logging', lambda **kw: None)
    monkeypatch.setattr(corporate_action_run, '_build_parser', lambda: types.SimpleNamespace(parse_args=lambda: types.SimpleNamespace()))
    monkeypatch.setattr(corporate_action_run, '_run_all', lambda args: called.setdefault('run', True))
    corporate_action_run.main()
    assert called['run']
    assert sys.argv[1] == 'run'

def test_main_run_passthrough(monkeypatch):
    argv = ['corporate_action_run.py', 'run']
    called = {}
    monkeypatch.setattr(sys, 'argv', argv[:])
    monkeypatch.setattr(corporate_action_run, 'configure_root_logging', lambda **kw: None)
    monkeypatch.setattr(corporate_action_run, '_build_parser', lambda: types.SimpleNamespace(parse_args=lambda: types.SimpleNamespace()))
    monkeypatch.setattr(corporate_action_run, '_run_all', lambda args: called.setdefault('run', True))
    corporate_action_run.main()
    assert called['run']
    assert sys.argv[1] == 'run'

def test_main_other_command(monkeypatch):
    argv = ['corporate_action_run.py', 'sync']
    monkeypatch.setattr(sys, 'argv', argv[:])
    monkeypatch.setattr(corporate_action_run, 'configure_root_logging', lambda **kw: None)
    # _run_all ne doit pas être appelé
    monkeypatch.setattr(corporate_action_run, '_run_all', lambda args: (_ for _ in ()).throw(AssertionError("_run_all ne doit pas être appelé")))
    called = {}
    def fake_parse_args():
        called['ok'] = True
        return types.SimpleNamespace()
    monkeypatch.setattr(corporate_action_run, '_build_parser', lambda: types.SimpleNamespace(parse_args=fake_parse_args))
    # On attend juste que main() ne lance pas AssertionError
    corporate_action_run.main()
    assert called['ok']
