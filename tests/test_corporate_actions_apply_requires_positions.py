from __future__ import annotations

from types import SimpleNamespace

from corporate_actions import cli


class _DummyRepo:
    def load_pending_events(self, as_of=None):
        return [SimpleNamespace(ca_type="CASH_DIVIDEND")]

    def load_latest_positions(self, account_id=None):
        return []


class _DummyEngine:
    def __init__(self, repo):
        self.repo = repo

    def apply(self, as_of=None):  # pragma: no cover - ne doit pas être appelé
        raise AssertionError("engine.apply ne doit pas être appelé quand le préflight est bloquant")


def test_run_apply_blocks_when_positions_snapshot_is_missing(monkeypatch, capsys) -> None:
    args = cli._build_parser().parse_args(["apply", "--as-of", "2026-05-05"])
    captured: dict[str, object] = {}
    repo = _DummyRepo()

    monkeypatch.setattr(cli, "build_corporate_action_provider", lambda account_id=None: object())
    monkeypatch.setattr(cli, "CorporateActionRepository", lambda: repo)
    monkeypatch.setattr(cli, "CorporateActionEngine", lambda provider, repo=None, account_id=None: _DummyEngine(repo))
    monkeypatch.setattr(
        cli,
        "_emit_and_persist_summary",
        lambda **kwargs: captured.update(kwargs),
    )

    cli._run_apply(args)

    out = capsys.readouterr().out
    assert "snapshot" in out.lower()
    assert captured["status"] == "failed"
    summary = captured["summary"]
    assert isinstance(summary, dict)
    assert summary["failed_events"] == 1
    assert summary["apply_preflight"]["status"] == "blocked_no_positions_snapshot"

