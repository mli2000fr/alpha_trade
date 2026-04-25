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


