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


