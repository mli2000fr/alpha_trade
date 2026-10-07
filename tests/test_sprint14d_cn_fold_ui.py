"""Sprint 14-D: CN folds must never launch US training or prediction."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from ihm.services import cn_fold_launch, cn_fold_worker, cn_research_market


@pytest.fixture
def cn_contract(monkeypatch):
    monkeypatch.setattr(cn_fold_launch, "resolve_database_route",
                        lambda alias, market: SimpleNamespace(database="alpha_trade_cn"))
    monkeypatch.setattr(cn_fold_launch, "fold_choices",
                        lambda task: {"horizons": (20,), "semesters": ("2025H2",),
                                      "models": ("lightgbm", "catboost")})


@pytest.mark.parametrize("task", ["oracle", "ranking"])
def test_cn_fold_command_is_isolated(cn_contract, task):
    options = replace(cn_fold_launch.CNResearchFoldOptions(), task=task,
                      output_root=str(cn_fold_launch.OUTPUT_PARENT / "one" / "artifacts"))
    command = cn_fold_launch.build_cn_fold_command(options)
    assert command[command.index("-m") + 1] == "ihm.services.cn_fold_worker"
    assert command[command.index("--task") + 1] == task
    assert command[command.index("--horizon") + 1] == "20"
    assert command[command.index("--test-semester") + 1] == "2025H2"
    assert "modelFactory" not in command
    assert "backtesting" not in command


@pytest.mark.parametrize("changes", [
    {"market_code": "US_EQ"}, {"database_alias": "us_primary"},
    {"task": "per_symbol"}, {"horizon": 60}, {"semester": "2026H1"},
    {"model": "lstm_attention"},
])
def test_cn_fold_rejects_cross_market_and_unregistered_values(cn_contract, changes):
    with pytest.raises(ValueError):
        cn_fold_launch.validate_fold_options(replace(cn_fold_launch.CNResearchFoldOptions(), **changes))


def test_cn_fold_rejects_us_database_and_output_escape(cn_contract, monkeypatch, tmp_path):
    monkeypatch.setattr(cn_fold_launch, "resolve_database_route",
                        lambda alias, market: SimpleNamespace(database="alpha_trade"))
    with pytest.raises(ValueError, match="alpha_trade_cn"):
        cn_fold_launch.validate_fold_options(cn_fold_launch.CNResearchFoldOptions())
    monkeypatch.setattr(cn_fold_launch, "resolve_database_route",
                        lambda alias, market: SimpleNamespace(database="alpha_trade_cn"))
    with pytest.raises(ValueError, match="sortie"):
        cn_fold_launch.build_cn_fold_command(replace(cn_fold_launch.CNResearchFoldOptions(), output_root=str(tmp_path)))


def test_cn_fold_preflight_requires_both_oracle_parents(cn_contract, monkeypatch):
    import modelFactory.cn_oracle_aggregate as aggregate
    import modelFactory.cn_oracle_walk_forward as oracle

    monkeypatch.setattr(oracle, "_sources", lambda protocol: ({}, {}))
    monkeypatch.setattr(aggregate, "_find_run", lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match="Oracle OOS CN manquant"):
        cn_fold_launch.preflight_cn_fold(replace(cn_fold_launch.CNResearchFoldOptions(), task="ranking"))


def test_cn_fold_start_refuses_duplicate_and_keeps_scoped_history(cn_contract, monkeypatch):
    from ihm.services import process_registry

    monkeypatch.setattr(process_registry, "list_active_pipeline_runs",
                        lambda: [{"step_key": cn_fold_launch.STEP_KEY, "is_active": True}])
    with pytest.raises(RuntimeError, match="déjà en cours"):
        cn_fold_launch.start_cn_fold(cn_fold_launch.CNResearchFoldOptions())


def test_cn_panel_not_reused_for_us():
    source = Path(cn_research_market.__file__).read_text(encoding="utf-8")
    assert "_render_cn_fold_panel()" in source
    assert "prédiction future servable" in source


def test_cn_worker_emits_initial_and_final_progress_without_changing_model(monkeypatch, tmp_path, capsys):
    import modelFactory.cn_oracle_walk_forward as oracle

    monkeypatch.setattr(oracle, "run", lambda **kwargs: {"status": "OOS_RESEARCH_ONLY"})
    result = cn_fold_worker.run_worker(task="oracle", horizon=20, semester="2025H1",
                                       model="lightgbm", output_root=tmp_path, heartbeat_seconds=0.01)
    assert result["status"] == "OOS_RESEARCH_ONLY"
    journal = capsys.readouterr().out
    assert cn_fold_worker.PROGRESS_PREFIX in journal
    assert cn_fold_worker.latest_progress_event(journal)["stage"] == "completed"


def test_cn_worker_milestones_and_bad_events(tmp_path):
    root = tmp_path / "artifacts"
    assert cn_fold_worker.progress_stage(root, "lightgbm") == "initializing"
    folder = root / "experiment" / "h20" / "2025H1" / "lightgbm"
    folder.mkdir(parents=True)
    assert cn_fold_worker.progress_stage(root, "lightgbm") == "sources_verified"
    (folder / "model.txt").write_text("model", encoding="utf-8")
    assert cn_fold_worker.progress_stage(root, "lightgbm") == "model_written"
    (folder / "report.json").write_text("{}", encoding="utf-8")
    assert cn_fold_worker.progress_stage(root, "lightgbm") == "report_written"
    assert cn_fold_worker.latest_progress_event("bad ::cn_fold_progress::{oops") is None
