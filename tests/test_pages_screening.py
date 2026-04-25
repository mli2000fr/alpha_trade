from ihm.pages import screening

def test_pages_screening_importable():
    assert hasattr(screening, "__doc__")


def test_build_quality_summary_rows_exposes_recent_pipeline_context() -> None:
    runs = [
        {
            "run_id": "wf-1",
            "run_kind": "workflow",
            "step_key": "pipeline_workflow",
            "status": "completed",
            "run_summary": {"workflow_steps_with_summary": 2, "targeted_symbols": 6, "successful_symbols": 5},
        },
        {
            "run_id": "imp-1",
            "run_kind": "step",
            "step_key": "import_alpaca_bar",
            "status": "completed",
            "run_summary": {"targeted_symbols": 3, "successful_symbols": 2},
        },
    ]

    rows = screening._build_quality_summary_rows(runs)

    assert list(rows["scope"]) == ["Import Alpaca Bar", "Workflow complet"]


def test_build_objective_recommendation_rows_formats_phase7_snapshot() -> None:
    rows = screening._build_objective_recommendation_rows(
        {
            "objective_rows_df": screening.pd.DataFrame(
                [
                    {
                        "objective_label": "robuste",
                        "scenario_name": "steady",
                        "objective_scope": "cross_regime",
                        "objective_score": 0.77,
                        "overall_score": 0.75,
                        "reason": "Stable sur tous les régimes.",
                    }
                ]
            )
        }
    )

    assert list(rows.columns) == [
        "Objectif",
        "Scénario recommandé",
        "Périmètre",
        "Score objectif",
        "Score global",
        "Pourquoi",
    ]
    assert rows.iloc[0]["Scénario recommandé"] == "steady"


def test_build_artifact_history_dataframe_exposes_global_screener_inventory() -> None:
    history_df = screening._build_artifact_history_dataframe(
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

    assert list(history_df.columns) == [
        "Répertoire",
        "Disponible",
        "Couverture",
        "MAJ",
        "Baseline",
        "Reco objectifs",
        "Scénarios",
        "Fichiers",
        "Régimes",
        "Runs IHM",
        "Dernier run",
        "Statut",
        "Origines",
        "Chemin",
    ]
    assert history_df.iloc[0]["Répertoire"] == "artifacts/screener_a"


