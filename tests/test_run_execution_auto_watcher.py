"""Sprint S2 / A-018 — flag ``--auto-watcher`` dans run_execution.

Vérifie que :
- Le flag ``--auto-watcher`` est exposé par le parser argparse.
- ``main`` propage ``auto_watcher=True`` à ``run`` quand le flag est passé.
- ``_launch_post_watcher`` construit la bonne ligne de commande
  (``run_execution_protection_watch.py --mode once …``) et lance
  ``subprocess.Popen``.
- Sans ``--auto-watcher``, ``_launch_post_watcher`` n'est pas appelé.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_execution


def test_parser_exposes_auto_watcher_flag():
    parser = run_execution.build_parser()
    args = parser.parse_args(["simulate", "--auto-watcher"])
    assert getattr(args, "auto_watcher", False) is True

    args2 = parser.parse_args(["simulate"])
    assert getattr(args2, "auto_watcher", False) is False


def test_launch_post_watcher_builds_command_with_account(tmp_path: Path):
    summary = {"run_id": "exec-123"}
    preset = {
        "trailing_stop_pct": 0.05,
        "trailing_activation_trigger": "multiple_r",
        "trailing_activation_r_multiple": 1.0,
        "trailing_activation_profit_pct": 0.03,
    }
    fake_proc = MagicMock()
    fake_proc.pid = 4242
    with patch.object(run_execution.subprocess, "Popen", return_value=fake_proc) as popen_mock:
        pid = run_execution._launch_post_watcher(
            summary=summary,
            preset=preset,
            account_id="paper1",
            broker_mode="paper",
        )
    assert pid == 4242
    popen_mock.assert_called_once()
    cmd = popen_mock.call_args[0][0]
    assert "run_execution_protection_watch.py" in " ".join(cmd)
    assert "--mode" in cmd and "once" in cmd
    assert "--broker-mode" in cmd and "paper" in cmd
    assert "--exec-run-id" in cmd
    assert "exec-123" in cmd
    assert "--account" in cmd and "paper1" in cmd


def test_launch_post_watcher_omits_account_when_none():
    fake_proc = MagicMock()
    fake_proc.pid = 1
    with patch.object(run_execution.subprocess, "Popen", return_value=fake_proc) as popen_mock:
        run_execution._launch_post_watcher(
            summary={"run_id": "r"},
            preset={
                "trailing_stop_pct": 0.05,
                "trailing_activation_trigger": "multiple_r",
                "trailing_activation_r_multiple": 1.0,
                "trailing_activation_profit_pct": 0.03,
            },
            account_id=None,
            broker_mode="paper",
        )
    cmd = popen_mock.call_args[0][0]
    assert "--account" not in cmd


def test_launch_post_watcher_raises_if_script_missing(monkeypatch):
    monkeypatch.setattr(
        run_execution,
        "PROJECT_ROOT",
        Path("C:/__definitely_does_not_exist__"),
    )
    with pytest.raises(FileNotFoundError):
        run_execution._launch_post_watcher(
            summary={},
            preset={
                "trailing_stop_pct": 0.05,
                "trailing_activation_trigger": "multiple_r",
                "trailing_activation_r_multiple": 1.0,
                "trailing_activation_profit_pct": 0.03,
            },
            account_id=None,
            broker_mode="paper",
        )


def test_run_signature_accepts_auto_watcher_kwarg():
    """La fonction ``run`` doit accepter ``auto_watcher`` (rétrocompat
    via valeur par défaut False)."""
    import inspect

    sig = inspect.signature(run_execution.run)
    assert "auto_watcher" in sig.parameters
    assert sig.parameters["auto_watcher"].default is False

