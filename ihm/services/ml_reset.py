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
from collections.abc import Callable
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
    # Runs pipeline / workflow IHM (registre process_registry → page Pipeline)
    "artifacts/ihm_pipeline_runs",
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

# Répertoires qui contiennent les runs IHM (backtests / pipelines). Ils ne
# peuvent être supprimés qu'après arrêt des runs actifs (fichiers ouverts sous
# Windows) — en phase 1 (stop_active=False) ils sont « bloqués » et reportés.
ML_RESET_RUN_DIRS: tuple[str, ...] = (
    "artifacts/ihm_backtesting_runs",
    "artifacts/ihm_pipeline_runs",
)

# Racine du projet (injectable dans les tests via monkeypatch).
PROJECT_ROOT = Path("F:/projets")


def _active_runs_for_dir(rel: str) -> list[dict[str, object]]:
    """Runs actifs du registre correspondant à un répertoire de runs IHM."""
    if rel == "artifacts/ihm_backtesting_runs":
        from ihm.services.backtesting_registry import list_active_backtesting_runs

        return list_active_backtesting_runs()
    if rel == "artifacts/ihm_pipeline_runs":
        from ihm.services.process_registry import list_active_pipeline_runs

        return list_active_pipeline_runs()
    return []


def reset_ml_data(
    *,
    stop_active: bool = True,
    dry_run: bool = False,
    runs_only: bool = False,
    on_step: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Vide les données ML + supprime les répertoires ML/backtests/pipelines.

    Deux phases possibles :

    - Phase 1 (``stop_active=False``, défaut côté IHM) : exécute tout ce qui ne
      nécessite PAS d'arrêter les runs actifs — vidage des tables, suppression
      des répertoires ML non bloqués. Les répertoires de runs encore utilisés
      par un run actif sont conservés et listés dans ``blocked_dirs`` /
      ``blocked_runs`` (l'UI propose alors un bouton « arrêter et continuer »).
    - Phase 2 (``stop_active=True, runs_only=True``) : arrête les runs actifs
      puis supprime les répertoires de runs restants + réinitialise les index.

    ``runs_only`` : si True, se limite aux répertoires de runs (phase 2) — les
    tables ne sont pas re-vidées.

    ``on_step`` (optionnel) : callback appelé après chaque étape avec un message
    humain lisible (avancement / erreurs), utile pour un affichage temps réel.
    Un journal complet est aussi renvoyé dans la clé ``log`` du résultat.

    Retourne ``{"tables_cleared": [...], "dirs_deleted": [...], "errors": [...],
    "log": [...], "blocked_dirs": [...], "blocked_runs": [...]}``.
    """
    engine = get_sqlalchemy_engine()
    tables_cleared: list[str] = []
    dirs_deleted: list[str] = []
    errors: list[str] = []
    steps: list[str] = []
    blocked_dirs: list[str] = []
    blocked_runs: list[dict[str, str]] = []

    def _report(msg: str) -> None:
        """Enregistre l'étape et notifie le callback UI (jamais bloquant)."""
        steps.append(msg)
        if on_step is not None:
            try:
                on_step(msg)
            except Exception:  # noqa: BLE001
                LOGGER.debug("échec du callback on_step", exc_info=True)

    # 1. Arrêter les runs actifs (backtests IHM + pipelines IHM) pour pouvoir
    #    supprimer leurs répertoires sans conflit de fichiers ouverts.
    if stop_active:
        _report("🔎 Recherche des runs IHM actifs (backtests + pipelines)…")

        # 1a. Backtests IHM
        try:
            from ihm.services.backtesting_registry import (
                list_active_backtesting_runs,
                stop_backtesting_run,
            )

            active_runs = list_active_backtesting_runs()
            if not active_runs:
                _report("  ✓ Aucun run backtest actif.")
            for snapshot in active_runs:
                run_id = str(snapshot.get("run_id") or "")
                if not run_id:
                    continue
                _report(f"  ⏹ Arrêt du run backtest {run_id}…")
                try:
                    stop_backtesting_run(run_id)
                    _report(f"    ✓ Run {run_id} arrêté.")
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"stop backtest {run_id}: {exc}")
                    _report(f"    ✗ Échec arrêt {run_id} : {exc}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"stop active backtests: {exc}")
            _report(f"  ✗ Erreur lors de la détection des runs backtest : {exc}")

        # 1b. Pipelines IHM (registre process_registry → page Pipeline)
        try:
            from ihm.services.process_registry import (
                list_active_pipeline_runs,
                stop_pipeline_run,
            )

            active_pipelines = list_active_pipeline_runs()
            if not active_pipelines:
                _report("  ✓ Aucun run pipeline actif.")
            for snapshot in active_pipelines:
                run_id = str(snapshot.get("run_id") or "")
                if not run_id:
                    continue
                _report(f"  ⏹ Arrêt du run pipeline {run_id}…")
                try:
                    stop_pipeline_run(run_id)
                    _report(f"    ✓ Run pipeline {run_id} arrêté.")
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"stop pipeline {run_id}: {exc}")
                    _report(f"    ✗ Échec arrêt {run_id} : {exc}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"stop active pipelines: {exc}")
            _report(f"  ✗ Erreur lors de la détection des runs pipeline : {exc}")

    # 2. Vider les tables (sautée en phase 2 : runs_only=True)
    if not runs_only:
        _report(f"🗄️ Vidage de {len(ML_RESET_TABLES)} tables SQL (FK checks désactivés)…")
        if not dry_run:
            try:
                with engine.begin() as conn:
                    # Désactive les checks FK temporairement pour éviter tout blocage
                    # d'ordre, puis les réactive à la fin du reset.
                    conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                    try:
                        for idx, table in enumerate(ML_RESET_TABLES, start=1):
                            _report(f"  [{idx}/{len(ML_RESET_TABLES)}] DELETE FROM `{table}`…")
                            try:
                                conn.execute(text(f"DELETE FROM `{table}`"))
                                tables_cleared.append(table)
                                _report(f"    ✓ `{table}` vidée.")
                            except Exception as exc:  # noqa: BLE001
                                errors.append(f"table {table}: {exc}")
                                _report(f"    ✗ `{table}` : {exc}")
                    finally:
                        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"reset DB: {exc}")
                _report(f"  ✗ Erreur globale du reset DB : {exc}")
        else:
            tables_cleared = list(ML_RESET_TABLES)
            _report(f"  ✓ dry-run : {len(tables_cleared)} tables simulées (aucun DELETE).")

    # 3. Supprimer les répertoires (en phase 2, uniquement les répertoires de runs)
    scope_dirs = ML_RESET_RUN_DIRS if runs_only else ML_RESET_DIRS
    _report(f"🗑️ Suppression de {len(scope_dirs)} répertoires / fichiers…")
    for rel in scope_dirs:
        target = PROJECT_ROOT / rel
        if not target.exists():
            if dry_run:
                # Dry-run = plan complet : on liste ce qui serait traité.
                dirs_deleted.append(rel)
                _report(f"  ✓ {rel}/ : planifié (absent sur disque — dry-run).")
            else:
                _report(f"  - {rel}/ : absent, ignoré.")
            continue
        if dry_run:
            dirs_deleted.append(rel)
            _report(f"  ✓ {rel}/ : suppression simulée (dry-run).")
            continue
        # Un répertoire de runs utilisé par un run actif ne peut pas être
        # supprimé sans l'arrêter d'abord (fichiers ouverts) → reporté en phase 2.
        if rel in ML_RESET_RUN_DIRS and not stop_active:
            active = _active_runs_for_dir(rel)
            if active:
                blocked_dirs.append(rel)
                for snap in active:
                    blocked_runs.append(
                        {
                            "run_id": str(snap.get("run_id") or ""),
                            "label": str(
                                snap.get("step_label")
                                or snap.get("run_label")
                                or snap.get("step_key")
                                or ""
                            ),
                            "registry": "pipeline"
                            if rel.endswith("ihm_pipeline_runs")
                            else "backtest",
                        }
                    )
                _report(
                    f"  ⛔ {rel}/ : {len(active)} run(s) actif(s) — suppression "
                    "différée (bouton « arrêter et continuer »)."
                )
                continue
        try:
            _report(f"  Suppression de {rel}/…")
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                target.unlink(missing_ok=True)
            if not target.exists():
                dirs_deleted.append(rel)
                _report(f"    ✓ {rel}/ supprimé.")
            else:
                errors.append(f"dir {rel}: suppression incomplète")
                _report(f"    ✗ {rel}/ : suppression incomplète.")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"dir {rel}: {exc}")
            _report(f"    ✗ {rel}/ : {exc}")

    # 4. Réinitialiser les index d'historique IHM (backtests + pipelines),
    #    sauf ceux dont le répertoire est encore bloqué par un run actif.
    _report("🔄 Réinitialisation des index d'historique IHM…")
    if not dry_run:
        for rel_index in (
            "artifacts/ihm_backtesting_runs/history_index.json",
            "artifacts/ihm_pipeline_runs/history_index.json",
        ):
            parent_rel = rel_index.rsplit("/", 1)[0]
            if parent_rel in blocked_dirs:
                _report(f"  - `{rel_index}` : différé (répertoire de runs actifs).")
                continue
            index_path = PROJECT_ROOT / rel_index
            try:
                if index_path.exists():
                    index_path.write_text("{}", encoding="utf-8")
                    _report(f"  ✓ `{rel_index}` réinitialisé.")
                else:
                    _report(f"  - `{rel_index}` absent, ignoré.")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"history_index reset {rel_index}: {exc}")
                _report(f"  ✗ `{rel_index}` : {exc}")
    else:
        _report("  - dry-run : index d'historique non modifiés.")

    _report("🏁 Reset ML terminé.")
    return {
        "tables_cleared": tables_cleared,
        "dirs_deleted": dirs_deleted,
        "errors": errors,
        "log": steps,
        "blocked_dirs": blocked_dirs,
        "blocked_runs": blocked_runs,
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
