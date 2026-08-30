from pathlib import Path


def test_symbol_source_column_accepts_dynamic_universe_identifiers() -> None:
    ddl = Path("database/sql/ml/model_training_batch.sql").read_text(encoding="utf-8")
    assert "symbol_source          VARCHAR(255)" in ddl


def test_symbol_source_migration_is_available() -> None:
    migration = Path(
        "database/sql/ml/alter_model_training_batch_symbol_source.sql"
    ).read_text(encoding="utf-8")
    assert "MODIFY COLUMN symbol_source VARCHAR(255) NOT NULL" in migration
