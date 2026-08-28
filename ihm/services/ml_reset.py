"""ihm/services/ml_reset.py — Reset complet des données ML + backtests (T5.5).

Vide toutes les tables liées aux batchs d'entraînement et aux prédictions
(per-symbol, per-sector, Oracle Extreme, Global Rank), ainsi que tous les
backtests — y compris leurs répertoires/fichiers sur disque.

⚠️ Opération DESTRUCTIVE et irréversible. La page IHM exige une double
confirmation avant d'appeler ``reset_ml_data``.
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

LOGGER = logging.getLogger(__name__)

# ── Tables à vider (ordre : dépendances FK d'abord) ─────────────────────────
# Ordre sûr : on vide d'abord les tables qui référencent d'autres tables.
ML_RESET_TABLES: list[str] = [
    # FK vers model_training_run (à vider avant)
    "model_directional_oos_metrics",
    # Prédictions (toutes sources)
    "model_predictions",
    "global_rank_history",
    "oracle_extreme_predictions",
    "global_oracle_labels",
    # Métadonnées / métriques des runs
    "model_governance",
    "model_metrics",
    "model_metrics_full",
    # Runs + batchs
    "model_training_run",
    "model_training_batch",
    "model_serving_batch",
    "model_batch_diagnostics",
]

# ── Répertoires à supprimer (relatifs à PROJECT_ROOT) ───────────────────────
ML_RESET_DIRS: list[str] = [
    # Backtests IHM (tous) + index
    "artifacts/ihm_backtesting_runs",
    # Modèles entraînés + caches ML
    "artifacts/models",
    "artifacts/per_sector_cache",
    "artifacts/per_symbol_v2",
    # Résultats / chantiers ML
    "artifacts/global_oracle_complementarity",
    "artifacts/parity",
    "artifacts/parity_runs",
    "artifacts/baselines",
    "artifacts/benchmarks",
]


def reset_ml_data(*, stop_active: bool = True, dry_run: bool = False) -> dict[str, object]:
    """Vide toutes les tables ML + supprime les répertoires ML/backtests.

    Étapes :
    1. Arrête les runs backtest IHM encore actifs (si ``stop_active``).
    2. Supprime le contenu des tables ``ML_RESET_TABLES``.
    3. Supprime les répertoires ``ML_RESET_DIRS`` (et ``history_index.json``).

    Retourne ``{"tables_cleared": [...], "dirs_deleted": [...], "errors": [...]}``.
    """
    engine = get_sqlalchemy_engine()
    tables_cleared: list[str] = []
    dirs_deleted: list[str] = []
    errors: list[str] = []

    # 1. Arrêter les runs backtest actifs
    if stop_active:
        try:
            from ihm.services.backtesting_registry import (
                list_active_backtesting_runs,
                stop_backtesting_run,
            )

            for snapshot in list_active_backtesting_runs():
                run_id = str(snapshot.get("run_id") or "")
                if run_id:
                    try:
                        stop_backtesting_run(run_id)
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"stop backtest {run_id}: {exc}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"stop active backtests: {exc}")

    # 2. Vider les tables
    if not dry_run:
        try:
            with engine.begin() as conn:
                # Désactive les checks FK temporairement pour éviter tout blocage
                # d'ordre, puis les réactive à la fin du reset.
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                try:
                    for table in ML_RESET_TABLES:
                        try:
                            conn.execute(text(f"DELETE FROM `{table}`"))
                            tables_cleared.append(table)
                        except Exception as exc:  # noqa: BLE001
                            errors.append(f"table {table}: {exc}")
                finally:
                    conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"reset DB: {exc}")
    else:
        tables_cleared = list(ML_RESET_TABLES)

    # 3. Supprimer les répertoires
    project_root = Path("F:/projets")
    for rel in ML_RESET_DIRS:
        target = project_root / rel
        if not target.exists():
            continue
        if dry_run:
            dirs_deleted.append(rel)
            continue
        try:
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                target.unlink(missing_ok=True)
            if not target.exists():
                dirs_deleted.append(rel)
            else:
                errors.append(f"dir {rel}: suppression incomplète")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"dir {rel}: {exc}")

    # 4. Réinitialiser l'index d'historique backtest (table JSON)
    if not dry_run:
        try:
            index_path = project_root / "artifacts" / "ihm_backtesting_runs" / "history_index.json"
            if index_path.exists():
                index_path.write_text("{}", encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"history_index reset: {exc}")

    return {
        "tables_cleared": tables_cleared,
        "dirs_deleted": dirs_deleted,
        "errors": errors,
    }


def build_reset_explanation() -> str:
    """Construit le texte d'explication du reset (tables + répertoires concernés)."""
    tables_lines = "\n".join(f"- `{t}`" for t in ML_RESET_TABLES)
    dirs_lines = "\n".join(f"- `{d}/`" for d in ML_RESET_DIRS)
    return (
        "**Tables vides (batchs d'entraînement + prédictions) :**\n"
        f"{tables_lines}\n\n"
        "**Répertoires / fichiers supprimés :**\n"
        f"{dirs_lines}\n\n"
        "⚠️ Cette action est **irréversible** : elle efface tous les modèles "
        "entraînés, toutes les prédictions (per-symbol, per-sector, Oracle "
        "Extreme, Global Rank) et tous les backtests. Pensez à faire un backup "
        "(T5.3 / T5.4) avant de confirmer."
    )
