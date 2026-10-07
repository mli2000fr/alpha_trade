"""Isolated launcher for one pre-registered CN_A research/OOS fold."""

from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass, replace
from pathlib import Path

from database.router import resolve_database_route
from ihm.services.pipeline_runner import PROJECT_ROOT

OUTPUT_PARENT = PROJECT_ROOT / "artifacts/ihm_pipeline_runs/cn-research-fold"
STEP_KEY = "cn:research_fold"
MODULES = {
    "oracle": "modelFactory.cn_oracle_walk_forward",
    "ranking": "modelFactory.cn_global_ranking_walk_forward",
}


@dataclass(frozen=True, slots=True)
class CNResearchFoldOptions:
    market_code: str = "CN_A"
    database_alias: str = "cn_primary"
    task: str = "oracle"
    horizon: int = 20
    semester: str = "2025H2"
    model: str = "lightgbm"
    output_root: str | None = None


def fold_choices(task: str) -> dict[str, tuple]:
    from modelFactory.cn_global_ranking_walk_forward import DEFAULT_CONFIG as RANKING_CONFIG
    from modelFactory.cn_global_ranking_walk_forward import RankingProtocol
    from modelFactory.cn_oracle_walk_forward import DEFAULT_CONFIG as ORACLE_CONFIG
    from modelFactory.cn_oracle_walk_forward import Protocol

    if task == "oracle":
        raw = Protocol.load(ORACLE_CONFIG).raw
    elif task == "ranking":
        raw = RankingProtocol.load(RANKING_CONFIG).raw
    else:
        raise ValueError("Tâche CN inconnue")
    return {
        "horizons": tuple(raw["horizons"]),
        "semesters": tuple(raw["test_semesters"]),
        "models": tuple(raw["models"]),
    }


def validate_fold_options(options: CNResearchFoldOptions, *, require_output: bool = False) -> None:
    if options.market_code != "CN_A" or options.database_alias != "cn_primary":
        raise ValueError("Entraînement CN incompatible avec marché/base")
    if options.task not in MODULES:
        raise ValueError("Tâche CN inconnue")
    route = resolve_database_route(options.database_alias, options.market_code)
    if route.database != "alpha_trade_cn":
        raise ValueError("La route CN doit viser exactement alpha_trade_cn")
    choices = fold_choices(options.task)
    if (options.horizon not in choices["horizons"] or options.semester not in choices["semesters"]
            or options.model not in choices["models"]):
        raise ValueError("Fold hors protocole CN pré-enregistré")
    if require_output:
        if not options.output_root:
            raise ValueError("Répertoire de sortie CN absent")
        target = Path(options.output_root).resolve()
        if OUTPUT_PARENT.resolve() not in target.parents:
            raise ValueError("La sortie CN doit rester dans les runs IHM CN")


def preflight_cn_fold(options: CNResearchFoldOptions) -> None:
    """Check CN source lineage and Ranking's two Oracle OOS parents."""
    from modelFactory.cn_oracle_walk_forward import AUDIT_PATH, DEFAULT_CONFIG, Protocol, _sources

    validate_fold_options(options)
    _sources(Protocol.load(DEFAULT_CONFIG))
    if options.task == "ranking":
        from modelFactory import cn_oracle_walk_forward as oracle_runner
        from modelFactory.cn_oracle_aggregate import _find_run
        from modelFactory.cn_oracle_walk_forward import DEFAULT_OUTPUT, _sha

        hashes = (_sha(DEFAULT_CONFIG), _sha(Path(oracle_runner.__file__)), _sha(AUDIT_PATH))
        for model in ("lightgbm", "catboost"):
            if _find_run(DEFAULT_OUTPUT, horizon=options.horizon, semester=options.semester,
                         model=model, config_sha=hashes[0], code_sha=hashes[1], audit_sha=hashes[2]) is None:
                raise ValueError(f"Oracle OOS CN manquant/incompatible : H{options.horizon} {options.semester} {model}")


def build_cn_fold_command(options: CNResearchFoldOptions) -> list[str]:
    validate_fold_options(options, require_output=True)
    return [
        sys.executable, "-u", "-m", "ihm.services.cn_fold_worker",
        "--task", options.task,
        "--horizon", str(options.horizon), "--test-semester", options.semester,
        "--model", options.model, "--output-root", str(Path(options.output_root).resolve()),
        "--log-level", "INFO",
    ]


def start_cn_fold(options: CNResearchFoldOptions):
    from ihm.services.process_registry import list_active_pipeline_runs, start_managed_run

    if any(row.get("step_key") == STEP_KEY and row.get("is_active") for row in list_active_pipeline_runs()):
        raise RuntimeError("Un fold CN est déjà en cours")
    preflight_cn_fold(options)
    run_options = replace(options, output_root=str(OUTPUT_PARENT / uuid.uuid4().hex / "artifacts"))
    command = build_cn_fold_command(run_options)
    return start_managed_run(
        step_key=STEP_KEY, step_label=f"CN_A {options.task} H{options.horizon} {options.semester} {options.model} OOS",
        command=command, db_config=None, notify_on_finish=True,
    )
