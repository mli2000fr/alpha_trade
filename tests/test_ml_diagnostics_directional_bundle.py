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
