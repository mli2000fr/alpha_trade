from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ml_diagnostics_partitions_bundle_metrics_by_training_role() -> None:
    source = (ROOT / "ihm" / "pages" / "ml_diagnostics.py").read_text(encoding="utf-8")

    assert "Branche directionnelle à diagnostiquer" in source
    assert "mtr.model_role = :model_role" in source
    assert "mtr_gov.model_role = mtr.model_role" in source
    assert "Bundle directionnel LONG/SHORT" in source
    assert "direction_long_run_id" in source
    assert "direction_short_run_id" in source
    assert "Direction conditionnelle" in source
    assert "Oracle OOF TOP20" in source
    assert "bundle historique entraînait la direction sur toutes les journées" in source
    assert "entraînés / {len(servable_long)} éligibles" in source
    assert "entraînées / {len(servable_paired)} servables" in source
    assert "Paires servables" in source


def test_prediction_periods_has_a_dedicated_bundle_contract_view() -> None:
    source = (ROOT / "ihm" / "pages" / "ml_diagnostics.py").read_text(encoding="utf-8")

    assert "BUNDLE_PREDICTION_COVERAGE_QUERY" in source
    assert "Direction LONG/SHORT consolidée" in source
    assert "Oracle Extreme (amplitude)" in source
    assert "double_lineage_rows" in source
    assert "Double filiation complète" in source
    assert "Aucune période Oracle exploitable" in source


def test_training_role_schema_is_kept_in_alembic_and_reference_sql() -> None:
    migration = (ROOT / "alembic" / "versions" / "0070_add_model_training_run_role.py").read_text(encoding="utf-8")
    schema = (ROOT / "database" / "sql" / "ml" / "model_training_run.sql").read_text(encoding="utf-8")

    assert 'down_revision: Union[str, None] = "0069_directional_bundle_lineage"' in migration
    assert "model_role" in migration
    assert "idx_batch_role_symbol" in migration
    assert "model_role" in schema
    assert "idx_batch_role_symbol" in schema


def test_directional_candidate_view_can_switch_strict_and_discovery() -> None:
    source = (ROOT / "ihm" / "pages" / "ml_diagnostics.py").read_text(encoding="utf-8")

    assert "Niveau de sélection" in source
    assert "DISCOVERY / HIGH POTENTIAL" in source
    assert "STRICT / STABLE" in source
    assert "discovery_classification" in source


def test_bundle_diagnostics_exposes_realized_directional_performance() -> None:
    source = (ROOT / "ihm" / "pages" / "ml_diagnostics.py").read_text(encoding="utf-8")

    assert "BUNDLE_DIRECTIONAL_REALIZED_QUERY" in source
    assert "BUNDLE_ORACLE_REALIZED_QUERY" in source
    assert "oracle_top_pool" in source
    assert "long_train_end_date" in source
    assert "short_train_end_date" in source
    assert "Contrôle PIT" in source
    assert "Couverture Oracle encore partielle" in source
    assert "Comment lire chaque colonne ?" in source
    assert "Lift vs univers (pp)" in source
    assert "Une baisse réelle de −4 % devient donc +4 %" in source
    assert "Calculer / actualiser la performance réalisée" in source
    assert "Oracle TOP20 — mission réelle" in source
    assert "Tout l'univers directionnel" in source
    assert "SUPPORTED_HORIZONS" in source
    assert "evaluate_directional_top_decile" in source
    assert "_render_directional_prediction_performance(batch_id)" in source
