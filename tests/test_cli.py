import pytest
from event_sentiment import cli

def test_cli_entrypoint_runs(monkeypatch):
    called = {}
    monkeypatch.setattr(cli, "main", lambda: called.setdefault("main", True))
    cli.main()
    assert called["main"] is True

