"""Scope parent runs, registries, serving and universes by market.

Revision ID: 0085_market_scope_parents
Revises: 0084_market_instrument_foundation
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "0085_market_scope_parents"
down_revision: str | None = "0084_market_instrument_foundation"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

US_FINGERPRINT = "ac71a3039fb43e25ac732d0393a7748bca85272db35ee89472d46368809546e2"


def upgrade() -> None:
    op.add_column("model_training_batch", sa.Column("market_code", sa.String(16, collation="utf8mb4_unicode_ci"), nullable=True))
    op.add_column("model_training_batch", sa.Column("calendar_id", sa.String(32), nullable=True))
    op.add_column("model_training_batch", sa.Column("base_currency", sa.String(3), nullable=True))
    op.add_column("model_training_batch", sa.Column("benchmark_instrument_id", mysql.BIGINT(unsigned=True), nullable=True))
    op.add_column("model_training_batch", sa.Column("universe_id", sa.String(255), nullable=True))
    op.add_column("model_training_batch", sa.Column("universe_fingerprint", sa.String(64), nullable=True))
    op.add_column("model_training_batch", sa.Column("sector_taxonomy", sa.String(32), nullable=True))
    op.add_column("model_training_batch", sa.Column("market_context_fingerprint", sa.String(64), nullable=True))
    op.execute(
        "UPDATE model_training_batch SET market_code='US_EQ', calendar_id='NYSE', "
        "base_currency='USD', sector_taxonomy='GICS', "
        f"market_context_fingerprint='{US_FINGERPRINT}' WHERE market_code IS NULL"
    )
    for name, kind, length in (
        ("market_code", sa.String, 16), ("calendar_id", sa.String, 32),
        ("base_currency", sa.String, 3), ("sector_taxonomy", sa.String, 32),
        ("market_context_fingerprint", sa.String, 64),
    ):
        op.alter_column("model_training_batch", name, existing_type=kind(length), nullable=False)
    op.execute("ALTER TABLE model_training_batch MODIFY market_code VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL")
    op.create_index("idx_mtb_market_status_started", "model_training_batch", ["market_code", "status", "started_at"])
    op.create_foreign_key("fk_mtb_market", "model_training_batch", "markets", ["market_code"], ["market_code"])
    op.create_foreign_key("fk_mtb_benchmark", "model_training_batch", "instruments", ["benchmark_instrument_id"], ["instrument_id"])

    op.add_column("model_registry", sa.Column("market_code", sa.String(16, collation="utf8mb4_unicode_ci"), nullable=True))
    op.execute("UPDATE model_registry SET market_code='US_EQ' WHERE market_code IS NULL")
    op.alter_column("model_registry", "market_code", existing_type=sa.String(16, collation="utf8mb4_unicode_ci"), nullable=False)
    op.execute("ALTER TABLE model_registry MODIFY market_code VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL")
    op.drop_constraint("uq_symbol_arch_version", "model_registry", type_="unique")
    op.create_unique_constraint("uq_market_symbol_arch_version", "model_registry", ["market_code", "symbol", "architecture", "version"])
    op.create_index("idx_registry_market_active", "model_registry", ["market_code", "is_active", "symbol"])
    op.create_foreign_key("fk_registry_market", "model_registry", "markets", ["market_code"], ["market_code"])

    op.add_column("model_training_run", sa.Column("market_code", sa.String(16, collation="utf8mb4_unicode_ci"), nullable=True))
    op.execute(
        "UPDATE model_training_run r LEFT JOIN model_training_batch b ON b.batch_id=r.batch_id "
        "SET r.market_code=COALESCE(b.market_code,'US_EQ') WHERE r.market_code IS NULL"
    )
    op.alter_column("model_training_run", "market_code", existing_type=sa.String(16, collation="utf8mb4_unicode_ci"), nullable=False)
    op.execute("ALTER TABLE model_training_run MODIFY market_code VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL")
    op.create_index("idx_mtr_market_batch_status", "model_training_run", ["market_code", "batch_id", "status"])
    op.create_foreign_key("fk_mtr_market", "model_training_run", "markets", ["market_code"], ["market_code"])

    op.add_column("model_serving_batch", sa.Column("market_code", sa.String(16, collation="utf8mb4_unicode_ci"), nullable=True))
    op.execute("UPDATE model_serving_batch SET market_code='US_EQ' WHERE market_code IS NULL")
    op.alter_column("model_serving_batch", "market_code", existing_type=sa.String(16, collation="utf8mb4_unicode_ci"), nullable=False)
    op.execute("ALTER TABLE model_serving_batch MODIFY market_code VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL")
    op.execute("ALTER TABLE model_serving_batch DROP PRIMARY KEY, ADD PRIMARY KEY (market_code, scope)")
    op.create_foreign_key("fk_serving_market", "model_serving_batch", "markets", ["market_code"], ["market_code"])

    for column, length in (
        ("market_code", 16), ("calendar_id", 32), ("base_currency", 3),
        ("sector_taxonomy", 32), ("market_context_fingerprint", 64),
        ("universe_fingerprint", 64),
    ):
        op.add_column("tradable_universe_runs", sa.Column(column, sa.String(length), nullable=True))
    op.execute(
        "UPDATE tradable_universe_runs SET market_code='US_EQ', calendar_id='NYSE', "
        "base_currency='USD', sector_taxonomy='GICS', "
        f"market_context_fingerprint='{US_FINGERPRINT}', universe_fingerprint=config_fingerprint "
        "WHERE market_code IS NULL"
    )
    for column, length in (
        ("market_code", 16), ("calendar_id", 32), ("base_currency", 3),
        ("sector_taxonomy", 32), ("market_context_fingerprint", 64),
        ("universe_fingerprint", 64),
    ):
        op.alter_column("tradable_universe_runs", column, existing_type=sa.String(length), nullable=False)
    op.execute("ALTER TABLE tradable_universe_runs MODIFY market_code VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL")
    op.create_index("idx_tur_market_status_started", "tradable_universe_runs", ["market_code", "status", "started_at"])
    op.create_foreign_key("fk_tur_market", "tradable_universe_runs", "markets", ["market_code"], ["market_code"])

    op.add_column("execution_runs", sa.Column("market_code", sa.String(16, collation="utf8mb4_unicode_ci"), nullable=True))
    op.add_column("execution_runs", sa.Column("calendar_id", sa.String(32), nullable=True))
    op.add_column("execution_runs", sa.Column("base_currency", sa.String(3), nullable=True))
    op.add_column("execution_runs", sa.Column("market_context_fingerprint", sa.String(64), nullable=True))
    op.execute(
        "UPDATE execution_runs SET market_code='US_EQ', calendar_id='NYSE', base_currency='USD', "
        f"market_context_fingerprint='{US_FINGERPRINT}' WHERE market_code IS NULL"
    )
    for column, length in (("market_code", 16), ("calendar_id", 32), ("base_currency", 3), ("market_context_fingerprint", 64)):
        op.alter_column("execution_runs", column, existing_type=sa.String(length), nullable=False)
    op.execute("ALTER TABLE execution_runs MODIFY market_code VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL")
    op.create_index("idx_execution_market_status_started", "execution_runs", ["market_code", "status", "started_at"])
    op.create_foreign_key("fk_execution_market", "execution_runs", "markets", ["market_code"], ["market_code"])

    bind = op.get_bind()
    if bind.dialect.name in {"mysql", "mariadb"}:
        op.execute("DROP TRIGGER IF EXISTS trg_mtr_market_guard_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_mtr_market_guard_update")
        op.execute("""
        CREATE TRIGGER trg_mtr_market_guard_insert BEFORE INSERT ON model_training_run FOR EACH ROW
        BEGIN
          IF NEW.batch_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM model_training_batch b WHERE b.batch_id=NEW.batch_id AND b.market_code<>NEW.market_code
          ) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='training run market differs from batch'; END IF;
          IF EXISTS (
            SELECT 1 FROM model_registry r WHERE r.registry_id=NEW.registry_id AND r.market_code<>NEW.market_code
          ) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='training run market differs from registry'; END IF;
        END
        """)
        op.execute("""
        CREATE TRIGGER trg_mtr_market_guard_update BEFORE UPDATE ON model_training_run FOR EACH ROW
        BEGIN
          IF NEW.batch_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM model_training_batch b WHERE b.batch_id=NEW.batch_id AND b.market_code<>NEW.market_code
          ) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='training run market differs from batch'; END IF;
          IF EXISTS (
            SELECT 1 FROM model_registry r WHERE r.registry_id=NEW.registry_id AND r.market_code<>NEW.market_code
          ) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='training run market differs from registry'; END IF;
        END
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name in {"mysql", "mariadb"}:
        op.execute("DROP TRIGGER IF EXISTS trg_mtr_market_guard_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_mtr_market_guard_update")
    op.drop_constraint("fk_execution_market", "execution_runs", type_="foreignkey")
    op.drop_index("idx_execution_market_status_started", table_name="execution_runs")
    for column in ("market_context_fingerprint", "base_currency", "calendar_id", "market_code"):
        op.drop_column("execution_runs", column)
    op.drop_constraint("fk_tur_market", "tradable_universe_runs", type_="foreignkey")
    op.drop_index("idx_tur_market_status_started", table_name="tradable_universe_runs")
    for column in ("universe_fingerprint", "market_context_fingerprint", "sector_taxonomy", "base_currency", "calendar_id", "market_code"):
        op.drop_column("tradable_universe_runs", column)
    op.drop_constraint("fk_serving_market", "model_serving_batch", type_="foreignkey")
    op.execute("ALTER TABLE model_serving_batch DROP PRIMARY KEY, ADD PRIMARY KEY (scope)")
    op.drop_column("model_serving_batch", "market_code")
    op.drop_constraint("fk_mtr_market", "model_training_run", type_="foreignkey")
    op.drop_index("idx_mtr_market_batch_status", table_name="model_training_run")
    op.drop_column("model_training_run", "market_code")
    op.drop_constraint("fk_registry_market", "model_registry", type_="foreignkey")
    op.drop_index("idx_registry_market_active", table_name="model_registry")
    op.drop_constraint("uq_market_symbol_arch_version", "model_registry", type_="unique")
    op.create_unique_constraint("uq_symbol_arch_version", "model_registry", ["symbol", "architecture", "version"])
    op.drop_column("model_registry", "market_code")
    op.drop_constraint("fk_mtb_benchmark", "model_training_batch", type_="foreignkey")
    op.drop_constraint("fk_mtb_market", "model_training_batch", type_="foreignkey")
    op.drop_index("idx_mtb_market_status_started", table_name="model_training_batch")
    for column in ("market_context_fingerprint", "sector_taxonomy", "universe_fingerprint", "universe_id", "benchmark_instrument_id", "base_currency", "calendar_id", "market_code"):
        op.drop_column("model_training_batch", column)
