"""cleanup_incomplete_batches.py — Nettoie les batchs (DB + fichiers).

Usage :
    python cleanup_incomplete_batches.py [--dry-run] [--all]
    from modelFactory.cleanup_incomplete_batches import cleanup_batches, list_batches
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def _is_safe_batch_id(batch_id: str) -> bool:
    """Garde-fou : un batch_id malformé ne doit JAMAIS déclencher un rmtree
    sur artifacts/ (ex. '', '.', '..', ou contenant '/' ou '\\')."""
    b = str(batch_id or "").strip()
    if not b:
        return False
    if b in (".", ".."):
        return False
    if "/" in b or "\\" in b:
        return False
    return True


def list_batches(include_completed: bool = False) -> list[str]:
    """Retourne la liste des batch_id.

    Les batchs en cours (``running``) sont TOUJOURS exclus : on ne supprime jamais
    un batch pendant son entraînement.

    Args:
        include_completed: Si True, retourne tous les batchs sauf les ``running``
                           (terminés + échoués + à supprimer).
                           Si False (défaut), seulement les non terminés et non
                           en cours (``failed``, ``to delete``, statut NULL).
    """
    from ihm.services.db import get_engine
    from sqlalchemy import text
    engine = get_engine()
    if include_completed:
        query = (
            "SELECT batch_id FROM alpha_trade.model_training_batch "
            "WHERE status IS NULL OR status != 'running'"
        )
    else:
        query = (
            "SELECT batch_id FROM alpha_trade.model_training_batch "
            "WHERE status IS NULL OR status NOT IN ('completed', 'running')"
        )
    with engine.connect() as conn:
        rows = conn.execute(text(query)).mappings().fetchall()
    return [str(r["batch_id"]) for r in rows]


# ── Rétrocompatibilité ──
list_incomplete_batches = list_batches


def cleanup_batches(dry_run: bool = False, include_completed: bool = False) -> dict:
    """Supprime les batchs (DB + fichiers).

    Args:
        dry_run: Si True, liste seulement sans supprimer.
        include_completed: Si True, supprime AUSSI les batchs terminés.
    """
    batch_ids = list_batches(include_completed=include_completed)
    if not batch_ids:
        LOGGER.info("Aucun batch trouvé.")
        return {"deleted_batches": 0, "deleted_db_rows": 0, "deleted_dirs": 0}
    # Garde-fou : ne jamais traiter un batch_id malformé (protection anti-suppression à tort).
    _unsafe = [b for b in batch_ids if not _is_safe_batch_id(b)]
    if _unsafe:
        LOGGER.warning("cleanup_batches ignore %d batch_id malformé(s) : %s", len(_unsafe), _unsafe)
    batch_ids = [b for b in batch_ids if _is_safe_batch_id(b)]
    if not batch_ids:
        return {"deleted_batches": 0, "deleted_db_rows": 0, "deleted_dirs": 0}

    label = "terminés et non terminés" if include_completed else "non terminés"
    LOGGER.info("Trouvé %d batch(s) %s : %s", len(batch_ids), label, batch_ids)

    if dry_run:
        return {"deleted_batches": len(batch_ids), "deleted_db_rows": 0, "deleted_dirs": 0}

    from ihm.services.db import get_engine
    from modelFactory.db_registry import delete_batch_rows
    engine = get_engine()

    total_rows = 0
    deleted_batches = 0
    failed_batches: list[str] = []
    for bid in batch_ids:
        try:
            deleted = delete_batch_rows(engine, bid)
            total_rows += sum(deleted.values())
            deleted_batches += 1
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("cleanup_batches batch_id=%s failed: %s", bid, exc)
            failed_batches.append(bid)

    artifacts_base = Path("artifacts") / "models"
    dirs_deleted = 0
    if artifacts_base.exists():
        for bid in batch_ids:
            batch_dir = artifacts_base / bid
            if batch_dir.exists():
                shutil.rmtree(batch_dir)
                dirs_deleted += 1
            # Champions Oracle Extreme — dossier dédié (hors artifacts_base/<bid>).
            _champ_dir = artifacts_base / "oracle" / "champions" / bid
            if _champ_dir.exists():
                shutil.rmtree(_champ_dir)
                dirs_deleted += 1

    LOGGER.info(
        "Nettoyage terminé — %d/%d batch(s), %d lignes DB, %d répertoires, échecs=%s",
        deleted_batches, len(batch_ids), total_rows, dirs_deleted, failed_batches or "aucun",
    )
    return {"deleted_batches": deleted_batches, "deleted_db_rows": total_rows, "deleted_dirs": dirs_deleted}


# ── Rétrocompatibilité ──
cleanup_incomplete_batches = cleanup_batches


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Cleanup batches")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all", action="store_true",
                        help="Inclure les batchs terminés (les batchs en cours 'running' sont toujours exclus)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = cleanup_batches(dry_run=args.dry_run, include_completed=args.all)
    print(result)


if __name__ == "__main__":
    main()
