"""Sprint S5 — Tests de l'orchestrateur ``flows.daily_pipeline``."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pytest

from common.config_loader import CONFIG_PATH_ENV
from flows.daily_pipeline import (
    FlowResult,
    StepResult,
    _run_step,
    daily_pipeline,
    main,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MOCK_STEPS: tuple[tuple[str, str, str], ...] = (
    ("step_a", "flows._mock_a", "run_a"),
    ("step_b", "flows._mock_b", "run_b"),
    ("step_c", "flows._mock_c", "run_c"),
)


# ---------------------------------------------------------------------------
# Tests StepResult
# ---------------------------------------------------------------------------


def test_step_result_to_dict_has_expected_keys() -> None:
    r = StepResult(step="screener", status="OK", duration_seconds=1.23)
    d = r.to_dict()
    assert d["step"] == "screener"
    assert d["status"] == "OK"
    assert d["duration_seconds"] == 1.23
    assert d["error"] is None


# ---------------------------------------------------------------------------
# Tests _run_step
# ---------------------------------------------------------------------------


def test_run_step_none_fn_returns_skipped() -> None:
    result = _run_step("missing_step", None, date(2026, 5, 17), "paper1")
    assert result.status == "SKIPPED"
    assert result.step == "missing_step"


def test_run_step_ok_fn_returns_ok() -> None:
    def _fn(d, a):
        return {"candidates_count": 10}

    result = _run_step("screener", _fn, date(2026, 5, 17), "paper1")
    assert result.status == "OK"
    assert result.metadata == {"candidates_count": 10}
    assert result.error is None
    assert result.duration_seconds >= 0.0


def test_run_step_raises_fn_returns_failed() -> None:
    def _failing(d, a):
        raise RuntimeError("DB down")

    result = _run_step("import_bars", _failing, date(2026, 5, 17), "paper1")
    assert result.status == "FAILED"
    assert "DB down" in (result.error or "")


# ---------------------------------------------------------------------------
# Tests daily_pipeline
# ---------------------------------------------------------------------------


def test_daily_pipeline_dry_run_all_skipped() -> None:
    result = daily_pipeline(
        run_date=date(2026, 5, 17),
        account_id="paper1",
        dry_run=True,
    )
    assert isinstance(result, FlowResult)
    assert result.status == "SKIPPED"
    assert result.errors == []
    for step_data in result.steps.values():
        assert step_data["status"] == "SKIPPED"


def test_daily_pipeline_dry_run_metadata() -> None:
    result = daily_pipeline(
        run_date=date(2026, 5, 17),
        account_id="paper1",
        dry_run=True,
    )
    assert result.account_id == "paper1"
    assert result.run_date == "2026-05-17"
    assert result.started_at != ""
    assert result.finished_at != ""
    assert result.duration_seconds >= 0.0


def test_daily_pipeline_steps_override_all_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avec des stubs OK, le status global doit être OK."""
    def _ok(d, a):
        return {}

    CUSTOM_STEPS: tuple[tuple[str, str, str], ...] = (
        ("step_a", "flows._stub", "run_ok"),
        ("step_b", "flows._stub", "run_ok"),
    )

    monkeypatch.setattr(
        "flows.daily_pipeline._safe_import_step",
        lambda module, fn: _ok,
    )

    result = daily_pipeline(
        run_date=date(2026, 5, 17),
        account_id="paper1",
        steps_override=CUSTOM_STEPS,
    )
    assert result.status == "OK"
    assert result.errors == []
    assert len(result.steps) == 2


def test_daily_pipeline_one_step_fails_status_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si une étape échoue, le status doit être PARTIAL (pas toutes failed)."""
    call_count = {"n": 0}

    def _stub_fn(module, fn_name):
        call_count["n"] += 1
        if call_count["n"] == 2:

            def _fail(d, a):
                raise RuntimeError("simulated failure")

            return _fail

        def _ok(d, a):
            return {}

        return _ok

    CUSTOM_STEPS: tuple[tuple[str, str, str], ...] = (
        ("step_a", "m", "f"),
        ("step_b", "m", "f"),
        ("step_c", "m", "f"),
    )

    monkeypatch.setattr("flows.daily_pipeline._safe_import_step", _stub_fn)

    result = daily_pipeline(
        run_date=date(2026, 5, 17),
        account_id="paper1",
        steps_override=CUSTOM_STEPS,
    )
    assert result.status == "PARTIAL"
    assert len(result.errors) == 1


def test_daily_pipeline_all_steps_fail_status_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tous failed → status FAILED."""

    def _fail_fn(d, a):
        raise RuntimeError("always fails")

    monkeypatch.setattr(
        "flows.daily_pipeline._safe_import_step",
        lambda m, f: _fail_fn,
    )

    CUSTOM_STEPS: tuple[tuple[str, str, str], ...] = (
        ("step_a", "m", "f"),
        ("step_b", "m", "f"),
    )

    result = daily_pipeline(
        run_date=date(2026, 5, 17),
        account_id="paper1",
        steps_override=CUSTOM_STEPS,
    )
    assert result.status == "FAILED"
    assert len(result.errors) == 2


def test_daily_pipeline_metrics_emitted_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les métriques pipeline_steps_total sont incrémentées pour chaque étape."""
    inc_calls: list[tuple[str, str]] = []

    class _MockCounter:
        def labels(self_inner, step: str, status: str):
            inc_calls.append((step, status))
            return self_inner

        def inc(self_inner):
            pass

    mock_counter = _MockCounter()
    monkeypatch.setattr("flows.daily_pipeline._steps_total", mock_counter)

    def _ok(d, a):
        return {}

    monkeypatch.setattr(
        "flows.daily_pipeline._safe_import_step",
        lambda m, f: _ok,
    )

    CUSTOM_STEPS: tuple[tuple[str, str, str], ...] = (("step_x", "m", "f"),)
    daily_pipeline(
        run_date=date(2026, 5, 17),
        account_id="paper1",
        steps_override=CUSTOM_STEPS,
    )

    assert any(step == "step_x" and status == "OK" for step, status in inc_calls)


def test_daily_pipeline_applies_config_path_to_steps_and_restores_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "override.yaml"
    config_path.write_text("market_regimes:\n  enabled: true\n", encoding="utf-8")
    monkeypatch.delenv(CONFIG_PATH_ENV, raising=False)

    def _ok(_d, _a):
        assert os.environ.get(CONFIG_PATH_ENV) == str(config_path)
        return {}

    monkeypatch.setattr("flows.daily_pipeline._safe_import_step", lambda _m, _f: _ok)

    result = daily_pipeline(
        run_date=date(2026, 5, 17),
        account_id="paper1",
        steps_override=(("step_cfg", "m", "f"),),
        config_path=config_path,
    )

    assert result.status == "OK"
    assert os.environ.get(CONFIG_PATH_ENV) is None


def test_daily_pipeline_flow_result_to_dict_is_json_serializable() -> None:
    result = daily_pipeline(
        run_date=date(2026, 5, 17),
        account_id="paper1",
        dry_run=True,
    )
    payload = json.dumps(result.to_dict())
    parsed = json.loads(payload)
    assert parsed["status"] == "SKIPPED"


# ---------------------------------------------------------------------------
# Tests CLI main()
# ---------------------------------------------------------------------------


def test_main_dry_run_outputs_json(capsys) -> None:
    rc = main(["--date", "2026-05-17", "--account-id", "paper1", "--dry-run"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["status"] == "SKIPPED"
    assert payload["account_id"] == "paper1"
    assert payload["run_date"] == "2026-05-17"


def test_main_invalid_date_returns_2(capsys) -> None:
    rc = main(["--date", "not-a-date", "--dry-run"])
    assert rc == 2


def test_main_report_out_writes_file(tmp_path: Path) -> None:
    out_file = tmp_path / "report.json"
    rc = main(["--date", "2026-05-17", "--dry-run", "--report-out", str(out_file)])
    assert rc == 0
    assert out_file.exists()
    payload = json.loads(out_file.read_text())
    assert payload["status"] == "SKIPPED"

