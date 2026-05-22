from __future__ import annotations

import argparse
from typing import cast

from backtesting.profiles import apply_profile
from ihm.pages import backtesting as backtesting_page


def test_apply_profile_production_parity_enables_full_replay_chain() -> None:
    args = argparse.Namespace(
        profile="custom",
        engine_mode="research",
        ml_pit_strategy="auto",
        phase2_mode="off",
        phase3_mode="off",
        phase4_mode="off",
        phase5_mode="off",
        phase7_mode="off",
    )

    apply_profile(args, "production-parity", explicit_flags=set())

    assert args.engine_mode == "pipeline"
    assert args.ml_pit_strategy == "use-persisted"
    assert args.phase2_mode == "risk_execution"
    assert args.phase3_mode == "execution_replay"
    assert args.phase4_mode == "protection_replay"
    assert args.phase5_mode == "watcher_replay"
    assert args.phase7_mode == "exit_lifecycle_replay"


def test_ihm_run_configuration_preset_production_parity_matches_cli_chain() -> None:
    preset = backtesting_page._get_run_configuration_preset("production_parity")

    assert preset is not None
    assert preset["label"] == "Production parity — pré-live obligatoire"
    updates = cast(dict[str, object], preset["state_updates"])
    assert updates["bt_run_engine_mode"] == "pipeline"
    assert updates["bt_run_ml_pit_strategy"] == "use-persisted"
    assert updates["bt_run_phase2_mode"] == "risk_execution"
    assert updates["bt_run_phase3_mode"] == "execution_replay"
    assert updates["bt_run_phase4_mode"] == "protection_replay"
    assert updates["bt_run_phase5_mode"] == "watcher_replay"
    assert updates["bt_run_phase7_mode"] == "exit_lifecycle_replay"


