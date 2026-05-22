from __future__ import annotations

import pytest

from corporate_actions import cli
from corporate_actions.provider import EodhdCorporateActionProvider


class _DummyRepo:
    pass


class _DummyEngine:
    def sync(self, **kwargs):  # pragma: no cover - ne doit jamais être appelé
        raise AssertionError("engine.sync ne doit pas être appelé quand le scope EODHD est invalide")


def test_run_sync_blocks_global_eodhd_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    args = cli._build_parser().parse_args(["sync", "--all-symbols"])

    monkeypatch.setattr(cli, "build_corporate_action_provider", lambda account_id=None: EodhdCorporateActionProvider(tracker=object()))
    monkeypatch.setattr(cli, "CorporateActionRepository", lambda: _DummyRepo())
    monkeypatch.setattr(cli, "CorporateActionEngine", lambda provider, repo, account_id=None: _DummyEngine())

    with pytest.raises(ValueError, match="Sync globale EODHD interdite"):
        cli._run_sync(args)


def test_validate_sync_scope_allows_explicit_eodhd_symbol_scope() -> None:
    cli._validate_sync_scope_or_raise(EodhdCorporateActionProvider(tracker=object()), ["AAPL", "MSFT"])


