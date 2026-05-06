"""Sprint S2 / A-008 — check env contextuel par compte / mode dans run_execution.

Vérifie que :
- mode ``simulate`` ne demande que LOGIN_DB / PASSWORD_DB (pas de creds Alpaca),
- mode ``paper``/``live`` lève si LOGIN_DB manque,
- ``--account <id>`` inconnu produit un message ciblé,
- ``--account <paper>`` mais ``mode=live`` produit un message ciblé,
- ``mode=live`` sans aucun compte live configuré → message clair.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_execution
from service.alpaca.accounts import AccountRegistry, BrokerAccount


@pytest.fixture(autouse=True)
def _reset_registry():
    AccountRegistry.reset_for_tests()
    yield
    AccountRegistry.reset_for_tests()


def _patch_registry(monkeypatch, accounts: list[BrokerAccount]):
    class _Stub:
        @classmethod
        def get(cls):
            return cls()

        def list_accounts(self):
            return list(accounts)

        def resolve(self, aid):
            for a in accounts:
                if a.account_id == aid:
                    return a
            raise KeyError(aid)

    monkeypatch.setattr("service.alpaca.accounts.AccountRegistry", _Stub)


def _account(aid="paper1", mode="paper"):
    return BrokerAccount(
        account_id=aid,
        label=aid,
        api_key="k" * 8,
        secret_key="s" * 8,
        mode=mode,
    )


def test_simulate_mode_only_requires_db(monkeypatch):
    monkeypatch.setenv("LOGIN_DB", "u")
    monkeypatch.setenv("PASSWORD_DB", "p")
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    assert run_execution.check_env(account_id=None, mode="simulate") == []


def test_simulate_mode_flags_missing_db(monkeypatch):
    monkeypatch.delenv("LOGIN_DB", raising=False)
    monkeypatch.setenv("PASSWORD_DB", "p")
    missing = run_execution.check_env(account_id=None, mode="simulate")
    assert "LOGIN_DB" in missing


def test_paper_mode_unknown_account_yields_targeted_error(monkeypatch):
    monkeypatch.setenv("LOGIN_DB", "u")
    monkeypatch.setenv("PASSWORD_DB", "p")
    _patch_registry(monkeypatch, [_account("paper1", "paper")])
    missing = run_execution.check_env(account_id="ghost", mode="paper")
    assert any("ghost" in entry for entry in missing), missing


def test_live_mode_with_paper_account_blocked(monkeypatch):
    monkeypatch.setenv("LOGIN_DB", "u")
    monkeypatch.setenv("PASSWORD_DB", "p")
    _patch_registry(monkeypatch, [_account("paper1", "paper")])
    missing = run_execution.check_env(account_id="paper1", mode="live")
    assert any("live" in entry.lower() for entry in missing), missing


def test_live_mode_without_any_live_account(monkeypatch):
    monkeypatch.setenv("LOGIN_DB", "u")
    monkeypatch.setenv("PASSWORD_DB", "p")
    _patch_registry(monkeypatch, [_account("paper1", "paper"), _account("paper2", "paper")])
    missing = run_execution.check_env(account_id=None, mode="live")
    assert any("live" in entry.lower() for entry in missing), missing


def test_paper_mode_with_valid_account_passes(monkeypatch):
    monkeypatch.setenv("LOGIN_DB", "u")
    monkeypatch.setenv("PASSWORD_DB", "p")
    _patch_registry(monkeypatch, [_account("paper1", "paper")])
    assert run_execution.check_env(account_id="paper1", mode="paper") == []


def test_abort_missing_env_exits_with_clear_message(monkeypatch, capsys):
    monkeypatch.setenv("LOGIN_DB", "u")
    monkeypatch.setenv("PASSWORD_DB", "p")
    _patch_registry(monkeypatch, [_account("paper1", "paper")])
    with pytest.raises(SystemExit) as exc:
        run_execution.abort_missing_env(account_id="ghost", mode="paper")
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "ghost" in err
    assert "FATAL" in err

