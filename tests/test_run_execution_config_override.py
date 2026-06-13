from __future__ import annotations

import os
import sys
from pathlib import Path

import run_execution
from common.config_loader import CONFIG_PATH_ENV


def test_main_propagates_config_path_override(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "regime_r13a_final.yaml"
    config_path.write_text("market_regimes:\n  enabled: true\n", encoding="utf-8")
    seen: dict[str, str | None] = {}

    monkeypatch.delenv(CONFIG_PATH_ENV, raising=False)
    monkeypatch.setattr(run_execution, "_apply_feature_flags", lambda _args: None)

    def _fake_abort_missing_env(*, account_id=None, mode=None) -> None:
        seen["abort"] = os.environ.get(CONFIG_PATH_ENV)

    def _fake_run(*args, **kwargs) -> None:
        seen["run"] = os.environ.get(CONFIG_PATH_ENV)

    monkeypatch.setattr(run_execution, "abort_missing_env", _fake_abort_missing_env)
    monkeypatch.setattr(run_execution, "run", _fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_execution.py", "simulate", "--config-path", str(config_path)],
    )

    run_execution.main()

    assert seen["abort"] == str(config_path)
    assert seen["run"] == str(config_path)
    assert os.environ.get(CONFIG_PATH_ENV) is None

