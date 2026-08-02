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


def list_batches(include_completed: bool = False) -> list[str]:
    """Retourne la liste des batch_id.

    Args:
        include_completed: Si True, retourne TOUS les batchs (y compris terminés).
                           Si False (défaut), seulement les non terminés.
    """
    from ihm.services.db import get_engine
    from sqlalchemy import text
    engine = get_engine()
    if include_completed:
        query = "SELECT batch_id FROM alpha_trade.model_training_batch"
    else:
        query = "SELECT batch_id FROM alpha_trade.model_training_batch WHERE status != 'completed'"
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

    label = "terminés et non terminés" if include_completed else "non terminés"
    LOGGER.info("Trouvé %d batch(s) %s : %s", len(batch_ids), label, batch_ids)

    if dry_run:
        return {"deleted_batches": len(batch_ids), "deleted_db_rows": 0, "deleted_dirs": 0}

    from ihm.services.db import get_engine
    from sqlalchemy import text
    engine = get_engine()

    # ── Tables avec batch_id direct ──
    tables_direct = [
        "model_batch_diagnostics",
        "global_rank_history",
    ]
    # ── Tables qui n'ont que run_id ──
    tables_via_run = [
        "model_metrics",
        "model_governance",
        "model_predictions",
    ]

    total_rows = 0
    with engine.begin() as conn:
        for bid in batch_ids:
            # 1. Supprimer les tables liées via run_id (enfants de model_training_run)
            for table in tables_via_run:
                result = conn.execute(
                    text(
                        f"DELETE FROM alpha_trade.{table} "
                        f"WHERE run_id IN ("
                        f"  SELECT run_id FROM alpha_trade.model_training_run "
                        f"  WHERE batch_id = :bid"
                        f")"
                    ),
                    {"bid": bid},
                )
                total_rows += result.rowcount

            # 2. Supprimer model_training_run (parent de model_metrics/governance/predictions)
            result = conn.execute(
                text("DELETE FROM alpha_trade.model_training_run WHERE batch_id = :bid"),
                {"bid": bid},
            )
            total_rows += result.rowcount

            # 3. Supprimer les tables avec batch_id direct
            for table in tables_direct:
                result = conn.execute(
                    text(f"DELETE FROM alpha_trade.{table} WHERE batch_id = :bid"),
                    {"bid": bid},
                )
                total_rows += result.rowcount

            # 4. Supprimer le batch lui-même en dernier
            result = conn.execute(
                text("DELETE FROM alpha_trade.model_training_batch WHERE batch_id = :bid"),
                {"bid": bid},
            )
            total_rows += result.rowcount

    artifacts_base = Path("artifacts") / "models"
    dirs_deleted = 0
    if artifacts_base.exists():
        for bid in batch_ids:
            batch_dir = artifacts_base / bid
            if batch_dir.exists():
                shutil.rmtree(batch_dir)
                dirs_deleted += 1

    LOGGER.info("Nettoyage terminé — %d batch(s), %d lignes DB, %d répertoires",
                len(batch_ids), total_rows, dirs_deleted)
    return {"deleted_batches": len(batch_ids), "deleted_db_rows": total_rows, "deleted_dirs": dirs_deleted}


# ── Rétrocompatibilité ──
cleanup_incomplete_batches = cleanup_batches


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Cleanup batches")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all", action="store_true", help="Inclure les batchs terminés")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = cleanup_batches(dry_run=args.dry_run, include_completed=args.all)
    print(result)


if __name__ == "__main__":
    main()
