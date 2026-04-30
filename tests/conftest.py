# conftest.py
#
# Le sys.path hack a été supprimé (fix P1 — Engineering Quality).
# Le projet est maintenant installable via : pip install -e ".[dev]"
# ce qui enregistre tous les packages dans l'environnement et rend
# toute manipulation manuelle de sys.path inutile.
#
# Si vous voyez des ModuleNotFoundError en lançant pytest :
#   cd C:\Users\PC MLI\PycharmProjects\alpha_trade
#   pip install -e ".[dev]"

import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def _isolate_finnhub_cache(monkeypatch, tmp_path):
    """Phase 2.3 : isole le cache disque Finnhub par test pour éviter les
    fuites entre tests (audit_service §cache, _finnhub_cache.py)."""
    cache_dir = tmp_path / "finnhub_cache"
    cache_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("FINNHUB_CACHE_DIR", str(cache_dir))


@pytest.fixture(autouse=True)
def _reset_http_circuit_breaker():
    """Phase 2.3 : reset du circuit breaker HTTP partagé entre tests."""
    try:
        from service._http_retry import DEFAULT_CIRCUIT_BREAKER

        DEFAULT_CIRCUIT_BREAKER._states.clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    yield
    try:
        from service._http_retry import DEFAULT_CIRCUIT_BREAKER

        DEFAULT_CIRCUIT_BREAKER._states.clear()  # type: ignore[attr-defined]
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _reset_db_engine_cache():
    """Phase 2.2 : invalide le ``lru_cache`` de ``get_sqlalchemy_engine`` /
    ``get_database_url`` / ``get_session_factory`` entre tests pour éviter
    qu'un monkeypatch de ``create_engine`` soit ignoré au profit d'une
    instance mise en cache par un test précédent."""
    try:
        from database import connection
        connection.get_sqlalchemy_engine.cache_clear()
        connection.get_database_url.cache_clear()
        connection.get_session_factory.cache_clear()
    except Exception:
        pass
    yield
