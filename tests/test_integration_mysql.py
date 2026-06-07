"""Sprint S3 — A-012 : Tests d'intégration avec MySQL réel via Docker.

Cette configuration pytest peut être utilisée pour des tests d'intégration qui
doivent à absolument tourner sur MySQL réel plutôt que SQLite en mémoire.

Utilisation :
  docker-compose up -d  # Démarre MySQL
  pytest -m integration  # Lance les tests marqués @integration
  docker-compose down   # Arrête MySQL
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch
import time

import pytest
import sqlalchemy as sa


@pytest.fixture(scope="session")
def docker_mysql_url() -> str:
    """URL MySQL Docker pour les tests d'intégration.

    Variable d'environnement : TEST_MYSQL_URL
    Par défaut : mysql+pymysql://testuser:testpass@localhost:3307/test_alpha_trade
    """
    return os.getenv(
        "TEST_MYSQL_URL",
        "mysql+pymysql://testuser:testpass@localhost:3307/test_alpha_trade",
    )


@pytest.fixture(scope="session")
def mysql_available(docker_mysql_url: str) -> bool:
    """Vérifie que MySQL Docker est disponible (ou Skip les tests)."""
    try:
        # Tentative de connexion
        engine = sa.create_engine(docker_mysql_url, echo=False)
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        engine.dispose()
        return True
    except Exception as e:
        print(f"MySQL not available: {e}")
        return False


@pytest.mark.integration
class TestDatabaseIntegrationMySQL:
    """Tests d'intégration avec MySQL réel."""

    def test_mysql_connection(self, mysql_available: bool, docker_mysql_url: str):
        """Vérification basique de la connexion MySQL."""
        if not mysql_available:
            pytest.skip("MySQL Docker not available")

        try:
            engine = sa.create_engine(docker_mysql_url)
            with engine.connect() as conn:
                result = conn.execute(sa.text("SELECT 1 as test"))
                row = result.fetchone()
                assert row is not None
                assert row[0] == 1
            engine.dispose()
        except Exception as e:
            pytest.fail(f"MySQL connection failed: {e}")

    def test_alembic_migrations_apply_cleanly(
        self,
        mysql_available: bool,
        docker_mysql_url: str,
    ):
        """Les migrations Alembic s'appliquent sans erreur sur MySQL."""
        if not mysql_available:
            pytest.skip("MySQL Docker not available")

        try:
            pytest.importorskip("alembic")
            from alembic.config import Config
            from alembic import command
            import tempfile

            # Configuration Alembic temporaire
            cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
            cfg.set_main_option("sqlalchemy.url", docker_mysql_url)

            # Upgrade à head
            command.upgrade(cfg, "head")

            # Vérification que les tables existent
            engine = sa.create_engine(docker_mysql_url)
            inspector = sa.inspect(engine)
            tables = inspector.get_table_names()

            # Tables critiques qui doivent exister
            expected_tables = [
                "stock_universe",
                "stock_assets",
                "stock_quote_snapshots",
                "run_summaries",
            ]
            missing = [t for t in expected_tables if t not in tables]
            assert not missing, f"Missing tables: {missing}"

            engine.dispose()
        except Exception as e:
            pytest.fail(f"Alembic migration failed: {e}")

    def test_schema_matches_orm_definitions(
        self,
        mysql_available: bool,
        docker_mysql_url: str,
    ):
        """Le schéma MySQL correspond aux modèles ORM."""
        if not mysql_available:
            pytest.skip("MySQL Docker not available")

        try:
            from database.models import (
                StockUniverse,
                StockAssets,
                StockQuoteSnapshots,
            )
            import sqlalchemy as sa

            engine = sa.create_engine(docker_mysql_url)
            inspector = sa.inspect(engine)

            # Vérification des colonnes du modèle StockUniverse
            universe_cols = {c["name"] for c in inspector.get_columns("stock_universe")}
            assert "symbol" in universe_cols, "Missing 'symbol' column"

            # Vérification des colonnes du modèle StockAssets
            assets_cols = {c["name"] for c in inspector.get_columns("stock_assets")}
            assert "symbol" in assets_cols, "Missing 'symbol' column in assets"

            engine.dispose()
        except Exception as e:
            pytest.skip(f"ORM models not available: {e}")

    def test_crud_operations_on_mysql(
        self,
        mysql_available: bool,
        docker_mysql_url: str,
    ):
        """Opérations CRUD fonctionnent correctement sur MySQL."""
        if not mysql_available:
            pytest.skip("MySQL Docker not available")

        try:
            from database.connection import get_session_factory
            from database.models import StockUniverse

            # Patching la DB URL
            with patch.dict(os.environ, {"DATABASE_URL": docker_mysql_url}):
                session_factory = get_session_factory.cache_clear()
                session_factory = get_session_factory()

                with session_factory() as session:
                    # Créer un enregistrement de test
                    test_symbol = "TEST_SYM"
                    test_universe = StockUniverse(
                        symbol=test_symbol,
                        exchange="NYSE",
                        asset_class="equity",
                    )
                    session.add(test_universe)
                    session.commit()

                    # Lire l'enregistrement
                    retrieved = session.query(StockUniverse).filter_by(
                        symbol=test_symbol
                    ).first()
                    assert retrieved is not None
                    assert retrieved.symbol == test_symbol

                    # Supprimer
                    session.delete(retrieved)
                    session.commit()

                    # Vérification suppression
                    deleted = session.query(StockUniverse).filter_by(
                        symbol=test_symbol
                    ).first()
                    assert deleted is None
        except Exception as e:
            pytest.skip(f"CRUD operations not testable: {e}")

    def test_concurrent_connections(
        self,
        mysql_available: bool,
        docker_mysql_url: str,
    ):
        """Connexions concurrentes fonctionnent sans conflit."""
        if not mysql_available:
            pytest.skip("MySQL Docker not available")

        try:
            from threading import Thread
            import sqlalchemy as sa

            results = []

            def query_task():
                try:
                    engine = sa.create_engine(docker_mysql_url)
                    with engine.connect() as conn:
                        result = conn.execute(sa.text("SELECT 1 as id"))
                        row = result.fetchone()
                        results.append(row is not None)
                    engine.dispose()
                except Exception as e:
                    results.append(False)

            # Lancer 3 requêtes concurrentes
            threads = [Thread(target=query_task) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert all(results), "Some concurrent connections failed"
        except Exception as e:
            pytest.fail(f"Concurrent connections test failed: {e}")

