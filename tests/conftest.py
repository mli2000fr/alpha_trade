# conftest.py
#
# Le projet est idéalement installé via : pip install -e ".[dev]".
# En pratique, certains lancements pytest locaux ne résolvent pas toujours
# les modules top-level (ex: `run_execution.py`). On sécurise donc ici la
# racine du repo dans sys.path pour rendre la collecte déterministe.

from pathlib import Path
import logging
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _restore_logging_state_between_tests():
    """Empêche une configuration CLI de désactiver les logs des tests suivants."""
    logging.disable(logging.NOTSET)
    logging.getLogger().disabled = False
    for logger in logging.Logger.manager.loggerDict.values():
        if isinstance(logger, logging.Logger):
            logger.disabled = False
    yield
    logging.disable(logging.NOTSET)
    logging.getLogger().disabled = False


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
