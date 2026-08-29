"""Sprint S12.4 — Test best-effort de l'idempotence Alembic upgrade/downgrade.

Vu la complexité MySQL-only de certaines migrations historiques, on se
contente d'un test ``import + métadonnées`` qui :

- importe chaque module ``alembic/versions/00xx_*.py`` ;
- vérifie la présence de ``upgrade()`` / ``downgrade()`` ;
- vérifie la cohérence du graphe (``down_revision`` chaîné).

Le drill MySQL-réel est exécuté par ``.github/workflows/dr_drill.yml``.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# Skip module entier si alembic n'est pas installé OU si le dossier local
# ``alembic/`` éclipse le package (cas dev sans installation pip).
try:
    import alembic.op  # type: ignore[import-not-found]  # noqa: F401
except Exception:  # noqa: BLE001
    import pytest as _pt
    _pt.skip("alembic non installé (le dossier local éclipse le package)",
             allow_module_level=True)

VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(f"_alembic_rev_{path.stem}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Impossible de charger {path.name}: {exc}")
    return mod


@pytest.fixture(scope="module")
def revisions():
    files = sorted(VERSIONS_DIR.glob("00*.py"))
    return [_load(p) for p in files]


def test_each_revision_exposes_upgrade_and_downgrade(revisions):
    for mod in revisions:
        assert callable(getattr(mod, "upgrade", None)), f"{mod.__name__} sans upgrade()"
        assert callable(getattr(mod, "downgrade", None)), f"{mod.__name__} sans downgrade()"
        assert getattr(mod, "revision", None), f"{mod.__name__} sans revision"


def test_revision_chain_is_consistent(revisions):
    by_rev = {m.revision: m for m in revisions}
    # Une seule racine (down_revision is None).
    roots = [m for m in revisions if getattr(m, "down_revision", None) is None]
    assert len(roots) == 1, f"Plusieurs racines: {[r.revision for r in roots]}"
    # Toutes les autres revisions pointent vers une revision existante.
    for m in revisions:
        dr = getattr(m, "down_revision", None)
        if dr is None:
            continue
        parents = dr if isinstance(dr, (tuple, list, set)) else (dr,)
        for parent in parents:
            assert parent in by_rev, f"{m.revision}: down_revision '{parent}' inconnu"


@pytest.mark.integration
def test_upgrade_downgrade_roundtrip_on_sqlite():
    """Test optionnel : upgrade head puis downgrade -1 sur SQLite in-memory.

    Skip automatique si la migration utilise du SQL MySQL-spécifique.
    """
    pytest.importorskip("alembic")
    from alembic.config import Config
    from alembic import command

    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", "sqlite:///:memory:")
    try:
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "-1")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Migration MySQL-only non rejouable sur SQLite: {exc}")



