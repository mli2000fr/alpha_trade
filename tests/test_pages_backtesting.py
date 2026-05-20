import pandas as pd

from ihm.pages import backtesting


def test_pages_backtesting_importable() -> None:
    assert hasattr(backtesting, "__doc__")


def test_parameter_reference_rows_include_screener_commands() -> None:
    diagnose_rows = backtesting._parameter_reference_rows("diagnose-screener")
    recommend_rows = backtesting._parameter_reference_rows("recommend-screener")

    assert any(row["Paramètre"] == "output_dir" for row in diagnose_rows)
    assert any(row["Paramètre"] == "max_scenarios" for row in diagnose_rows)
    assert any(row["Paramètre"] == "input_dir" for row in recommend_rows)
    assert any(row["Paramètre"] == "target_horizon" for row in recommend_rows)


def test_parameter_reference_rows_include_walk_forward_run_options() -> None:
    run_rows = backtesting._parameter_reference_rows("run")

    assert any(row["Paramètre"] == "score_column" for row in run_rows)
    assert any(row["Paramètre"] == "walk_forward_artifacts_dir" for row in run_rows)
    assert any(row["Paramètre"] == "capital_preset_key" for row in run_rows)
    assert any(row["Paramètre"] == "engine_mode" for row in run_rows)
    assert any(row["Paramètre"] == "ml_pit_strategy" for row in run_rows)
    assert any(row["Paramètre"] == "phase2_mode" for row in run_rows)
    assert any(row["Paramètre"] == "phase3_mode" for row in run_rows)
    assert any(row["Paramètre"] == "phase4_mode" for row in run_rows)
    assert any(row["Paramètre"] == "phase5_mode" for row in run_rows)
    assert any(row["Paramètre"] == "phase7_mode" for row in run_rows)


def test_run_configuration_preset_pipeline_live_like_exposes_expected_phase_chain() -> None:
    preset = backtesting._get_run_configuration_preset("pipeline_live_like")

    assert preset is not None
    assert preset["label"] == "Replay le plus proche du pipeline live aujourd'hui"
    updates = preset["state_updates"]
    assert updates["bt_run_engine_mode"] == "pipeline"
    assert updates["bt_run_ml_pit_strategy"] == "use-persisted"
    assert updates["bt_run_phase2_mode"] == "risk_execution"
    assert updates["bt_run_phase3_mode"] == "execution_replay"
    assert updates["bt_run_phase4_mode"] == "protection_replay"
    assert updates["bt_run_phase5_mode"] == "watcher_replay"
    assert updates["bt_run_phase7_mode"] == "exit_lifecycle_replay"


def test_build_pipeline_pit_status_message_warns_when_history_is_missing() -> None:
    level, message = backtesting._build_pipeline_pit_status_message(
        {
            "status": "missing",
            "start": "2024-01-01",
            "end": "2024-01-31",
            "capital_preset_key": "capital_50001_100000",
            "capital_preset_filtered": True,
            "rows": 0,
            "snapshot_days": 0,
        }
    )

    assert level == "error"
    assert "stock_scores_history" in message
    assert "Backfill scores history" in message
    assert "capital_50001_100000" in message


def test_build_pipeline_pit_status_message_confirms_when_history_is_available() -> None:
    level, message = backtesting._build_pipeline_pit_status_message(
        {
            "status": "available",
            "start": "2024-01-01",
            "end": "2025-04-29",
            "capital_preset_key": "capital_50001_100000",
            "capital_preset_filtered": True,
            "rows": 42,
            "snapshot_days": 7,
            "first_snapshot_date": "2024-01-01",
            "last_snapshot_date": "2025-04-29",
        }
    )

    assert level == "success"
    assert "42 ligne(s)" in message
    assert "7 séance(s)" in message


def test_parameter_reference_rows_include_backfill_capital_preset_options() -> None:
    backfill_rows = backtesting._parameter_reference_rows("backfill")

    assert any(row["Paramètre"] == "capital" for row in backfill_rows)
    assert any(row["Paramètre"] == "capital_preset_key" for row in backfill_rows)


def test_build_fidelity_component_rows_formats_expected_columns() -> None:
    rows = backtesting._build_fidelity_component_rows(
        {
            "components": ["bars", "scores", "sentiment"],
            "component_status": {
                "bars": {"status": "ok", "enabled": True, "degraded_reasons": []},
                "scores": {
                    "status": "degraded",
                    "enabled": True,
                    "degraded_reasons": ["stock_scores_history_missing"],
                },
                "sentiment": {"status": "disabled", "enabled": False, "degraded_reasons": []},
            },
        }
    )

    assert list(rows.columns) == ["Composant", "État", "Activé", "Motifs"]
    assert rows.iloc[0]["État"] == "🟢 OK"
    assert rows.iloc[1]["Motifs"] == "stock_scores_history_missing"
    assert rows.iloc[2]["Activé"] == "non"


def test_build_fidelity_coverage_rows_exposes_missing_symbols() -> None:
    rows = backtesting._build_fidelity_coverage_rows(
        {
            "coverage": {
                "sentiment": {
                    "rows_input": 10,
                    "coverage_ratio_after": 0.9,
                    "rows_missing_after": 1,
                    "missing_symbols_after": ["AAPL"],
                },
                "ml": {
                    "rows_input": 10,
                    "coverage_ratio_after": 0.8,
                    "rows_missing_after": 2,
                    "missing_symbols_after": ["MSFT", "NVDA"],
                },
            }
        }
    )

    assert list(rows["Couverture"]) == ["sentiment", "ml"]
    assert rows.iloc[0]["Couverture finale"] == "90.0%"
    assert rows.iloc[1]["Symboles dégradants"] == "MSFT, NVDA"


def test_build_fidelity_provenance_rows_exposes_sources_and_tags() -> None:
    rows = backtesting._build_fidelity_provenance_rows(
        {
            "provenance": {
                "scores": {
                    "provenance_kind": "persisted_history",
                    "source_table": "stock_scores_history",
                    "score_column_requested": "auto",
                },
                "sentiment": {
                    "requested_mode": "auto",
                    "source_tags": ["persisted_scores_snapshot", "walk_forward_overlay"],
                    "walk_forward_artifact_path": "artifacts/wf/run_1/latest_best_weights.json",
                },
                "ml": {
                    "effective_strategy": "rebuild-missing",
                    "source_tags": ["persisted_predictions", "rebuilt_predictions"],
                },
            }
        }
    )

    assert list(rows["Composant"]) == ["scores", "sentiment", "ml"]
    assert rows.iloc[0]["Type"] == "persisted_history"
    assert "walk_forward_overlay" in rows.iloc[1]["Source / tags"]
    assert rows.iloc[2]["Détail clé"] == "rebuild-missing"


def test_build_fidelity_ml_cause_rows_exposes_breakdown() -> None:
    rows = backtesting._build_fidelity_ml_cause_rows(
        {
            "provenance": {
                "ml": {
                    "missing_cause_breakdown": {
                        "prediction_missing": 3,
                        "artifact_missing": 1,
                    }
                }
            }
        }
    )

    assert list(rows["Cause ML"]) == ["prediction_missing", "artifact_missing"]
    assert list(rows["Occurrences"]) == [3, 1]


def test_build_screener_artifact_objective_rows_formats_expected_columns() -> None:
    rows = backtesting._build_screener_artifact_objective_rows(
        {
            "objective_recommendations": [
                {
                    "objective_label": "robuste",
                    "objective_scope": "cross_regime",
                    "scenario_name": "steady",
                    "objective_score": 0.82,
                    "overall_score": 0.78,
                    "reason": "Stable sur tous les régimes.",
                }
            ]
        }
    )

    assert list(rows.columns) == [
        "Objectif",
        "Périmètre",
        "Scénario recommandé",
        "Score objectif",
        "Score global",
        "Pourquoi",
    ]
    assert rows.iloc[0]["Scénario recommandé"] == "steady"


def test_build_screener_artifact_metric_rows_includes_inventory_counts() -> None:
    metrics = dict(
        backtesting._build_screener_artifact_metric_rows(
            {
                "scenario_count": 12,
                "trading_days": 20,
                "file_count": 7,
                "objective_count": 4,
                "baseline_name": "baseline",
                "summary_rows": 12,
                "daily_rows": 240,
                "market_regimes": ["bull", "bear"],
            }
        )
    )

    assert metrics["Scénarios"] == "12"
    assert metrics["Reco objectifs"] == "4"
    assert metrics["Régimes"] == "2"


def test_build_global_screener_history_dataframe_exposes_transverse_inventory() -> None:
    history_df = backtesting._build_global_screener_history_dataframe(
        [
            {
                "artifacts_dir": "C:/tmp/screener_a",
                "artifacts_dir_label": "artifacts/screener_a",
                "available": True,
                "coverage_label": "2026-04-01 → 2026-04-03 (3 séance(s))",
                "updated_at_label": "2026-04-25 10:02",
                "baseline_name": "baseline",
                "objective_count": 4,
                "scenario_count": 12,
                "file_count": 7,
                "market_regime_count": 2,
                "run_count": 3,
                "last_run_label": "Recommandation screener",
                "last_run_status": "completed",
                "source_tags": ["runs IHM"],
            }
        ]
    )

    assert history_df.iloc[0]["Répertoire"] == "artifacts/screener_a"
    assert history_df.iloc[0]["Disponible"] == "oui"


def test_resolve_history_selected_run_id_returns_selected_run(monkeypatch) -> None:
    history_df = pd.DataFrame(
        [
            {"run_id": "run_a", "libellé": "A"},
            {"run_id": "run_b", "libellé": "B"},
        ]
    )

    monkeypatch.setattr(backtesting, "_selected_dataframe_row_index", lambda table_key: 1)

    assert backtesting._resolve_history_selected_run_id(history_df) == "run_b"


def test_resolve_history_selected_run_id_returns_none_when_selection_is_invalid(monkeypatch) -> None:
    history_df = pd.DataFrame([{"run_id": "run_a"}])

    monkeypatch.setattr(backtesting, "_selected_dataframe_row_index", lambda table_key: 3)

    assert backtesting._resolve_history_selected_run_id(history_df) is None


