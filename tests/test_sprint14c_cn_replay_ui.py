"""Sprint 14-C cannot launch a US command or a mismatched CN replay."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from ihm.services import (
    backtesting_registry,
    backtesting_runner,
    cn_replay_launch,
    cn_replay_worker,
    cn_research_market,
)


@pytest.fixture
def cn_contract(monkeypatch):
    monkeypatch.setattr(
        cn_replay_launch,
        "resolve_database_route",
        lambda alias, market: SimpleNamespace(database="alpha_trade_cn"),
    )
    monkeypatch.setattr(
        cn_replay_launch,
        "replay_choices",
        lambda: {
            "semesters": ("2024H1",),
            "policies": ("oracle_all",),
            "seeds": (0,),
            "scenarios": ("base",),
            "cost_profiles": ("cn_a_research",),
        },
    )


def test_cn_command_uses_only_cn_module_and_scoped_output(cn_contract):
    output = cn_replay_launch.OUTPUT_PARENT / "20260927_120000_abcdef12" / "artifacts"
    options = replace(cn_replay_launch.CNResearchReplayOptions(), output_root=str(output))
    command = backtesting_runner.build_backtesting_command("cn-research-replay", options)
    assert command[command.index("-m") + 1] == "ihm.services.cn_replay_worker"
    assert command[command.index("--market-code") + 1] == "CN_A"
    assert command[command.index("--database-alias") + 1] == "cn_primary"
    assert command[command.index("--semesters") + 1] == "2024H1"
    assert "backtesting" not in command
    assert "--output-root" in command


@pytest.mark.parametrize(
    "changes",
    [
        {"market_code": "US_EQ"},
        {"database_alias": "us_primary"},
        {"semester": "2026H1"},
        {"policy": "short_live"},
        {"seed": 99},
    ],
)
def test_cn_contract_rejects_cross_market_and_unregistered_values(cn_contract, changes):
    options = replace(cn_replay_launch.CNResearchReplayOptions(), **changes)
    with pytest.raises(ValueError):
        cn_replay_launch.validate_replay_options(options)


def test_cn_contract_refuses_us_schema_and_output_escape(cn_contract, monkeypatch, tmp_path):
    monkeypatch.setattr(
        cn_replay_launch,
        "resolve_database_route",
        lambda alias, market: SimpleNamespace(database="alpha_trade"),
    )
    with pytest.raises(ValueError, match="alpha_trade_cn"):
        cn_replay_launch.validate_replay_options(cn_replay_launch.CNResearchReplayOptions())
    monkeypatch.setattr(
        cn_replay_launch,
        "resolve_database_route",
        lambda alias, market: SimpleNamespace(database="alpha_trade_cn"),
    )
    with pytest.raises(ValueError, match="sortie"):
        cn_replay_launch.build_cn_replay_command(
            replace(cn_replay_launch.CNResearchReplayOptions(), output_root=str(tmp_path))
        )


def test_registry_preflight_blocks_before_process_or_storage(monkeypatch):
    def blocked(_options):
        raise ValueError("Route CN incompatible")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Aucun processus ou registre ne doit démarrer")

    monkeypatch.setattr(cn_replay_launch, "preflight_cn_replay", blocked)
    monkeypatch.setattr(backtesting_registry, "_ensure_storage", forbidden)
    monkeypatch.setattr(backtesting_registry.subprocess, "Popen", forbidden)
    with pytest.raises(ValueError, match="Route CN incompatible"):
        backtesting_registry.start_backtesting_run(
            "cn-research-replay", "Recherche CN", cn_replay_launch.CNResearchReplayOptions()
        )


def test_cn_panel_is_read_only_until_click(monkeypatch, cn_contract):
    seen = []
    monkeypatch.setattr(cn_research_market.st, "subheader", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cn_research_market.st, "warning", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cn_research_market.st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cn_research_market.st, "code", lambda command: seen.append(command))
    monkeypatch.setattr(cn_research_market.st, "button", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(cn_research_market.st, "selectbox", lambda _label, options, **_kwargs: options[0])
    monkeypatch.setattr(backtesting_registry, "list_active_backtesting_runs_by_kind", lambda _kind: [])
    monkeypatch.setattr(backtesting_registry, "load_backtesting_history", lambda: [])
    monkeypatch.setattr(cn_research_market.st, "info", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(backtesting_registry, "start_backtesting_run", lambda *_args, **_kwargs: pytest.fail("Launch"))
    cn_research_market._render_cn_replay_panel.__wrapped__()
    assert "ihm.services.cn_replay_worker" in seen[0]


def test_cn_replay_worker_progress_without_running_database(monkeypatch, tmp_path, capsys):
    import modelFactory.cn_economic_replay_13b as replay

    monkeypatch.setattr(replay, "run", lambda **kwargs: {"status": "COMPLETE_RESEARCH_BLOCKED_OR_PARTIAL"})
    result = cn_replay_worker.run_worker(
        market_code="CN_A", database_alias="cn_primary", semester="2025H2",
        policy="oracle_all", seed=0, scenario="base", cost_profile="cn_a_research",
        evidence=tmp_path / "evidence.json", output_root=tmp_path, heartbeat_seconds=0.01,
    )
    assert result["status"] == "COMPLETE_RESEARCH_BLOCKED_OR_PARTIAL"
    assert cn_replay_worker.latest_progress_event(capsys.readouterr().out)["stage"] == "completed"


def test_cn_replay_worker_milestones_and_route(tmp_path):
    assert cn_replay_worker.progress_stage(tmp_path) == "initializing"
    folder = tmp_path / "sprint13b-fingerprint"
    folder.mkdir()
    assert cn_replay_worker.progress_stage(tmp_path) == "replaying"
    cell = folder / "2025H2__oracle_all__seed0__base__cn_a_research"
    cell.mkdir()
    (cell / "report.json").write_text("{}", encoding="utf-8")
    assert cn_replay_worker.progress_stage(tmp_path) == "cell_written"
    (folder / "report.json").write_text("{}", encoding="utf-8")
    assert cn_replay_worker.progress_stage(tmp_path) == "report_written"
    assert cn_replay_worker.latest_progress_event("::cn_replay_progress::{bad") is None
    with pytest.raises(ValueError, match="CN_A"):
        cn_replay_worker.run_worker(
            market_code="US_EQ", database_alias="cn_primary", semester="2025H2",
            policy="oracle_all", seed=0, scenario="base", cost_profile="cn_a_research",
            evidence=tmp_path / "evidence.json", output_root=tmp_path,
        )


def test_cn_registry_smoke_starts_dedicated_command_without_real_process(tmp_path, monkeypatch, cn_contract):
    from ihm.services import pipeline_lock

    class FakeProcess:
        pid = 4242
        stdout = None
        stderr = None

        def poll(self):
            return 0

    class FakeThread:
        def __init__(self, *_args, **_kwargs):
            pass

        def start(self):
            pass

        def join(self, timeout=None):
            pass

    runs_dir = tmp_path / "ihm_runs"
    launched = []
    monkeypatch.setattr(backtesting_registry, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(backtesting_registry, "HISTORY_INDEX_PATH", runs_dir / "history_index.json")
    monkeypatch.setattr(backtesting_registry, "_ACTIVE_RUNS", {})
    monkeypatch.setattr(cn_replay_launch, "OUTPUT_PARENT", runs_dir / "cn-research-replay")
    monkeypatch.setattr(cn_replay_launch, "preflight_cn_replay", lambda _options: None)
    monkeypatch.setattr(backtesting_registry, "build_subprocess_env", lambda db_config=None: {})
    monkeypatch.setattr(
        backtesting_registry.subprocess,
        "Popen",
        lambda command, **_kwargs: (launched.append(command), FakeProcess())[1],
    )
    monkeypatch.setattr(backtesting_registry.threading, "Thread", FakeThread)
    pipeline_lock.set_locks_dir_for_tests(tmp_path / "locks")
    try:
        record = backtesting_registry.start_backtesting_run(
            "cn-research-replay", "Recherche CN", cn_replay_launch.CNResearchReplayOptions()
        )
        assert launched[0][launched[0].index("-m") + 1] == "ihm.services.cn_replay_worker"
        output = launched[0][launched[0].index("--output-root") + 1]
        assert record.run_id in output
        assert record.run_kind == "cn-research-replay"
        assert backtesting_registry.poll_backtesting_run(record.run_id)["status"] == "completed"
    finally:
        pipeline_lock.set_locks_dir_for_tests(None)
