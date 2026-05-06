"""Sprint S26 — service générique d'exécution de commandes ops depuis l'IHM.

Ce module unifie le lancement, depuis Streamlit, des commandes CLI qui
n'appartiennent ni au pipeline (cf. ``pipeline_runner.py``) ni au
backtesting (cf. ``backtesting_runner.py``) :

- ``execution_engine cancel-all`` (kill switch)
- ``corporate_actions status`` / ``apply``
- ``scripts/run_pre_live_checklist.py``
- ``scripts/run_daily_parity.py``
- ``scripts/run_broker_reconciliation.py``
- ``scripts/run_monthly_broker_report.py``
- ``scripts/run_quarterly_weights_calibration.py``
- ``scripts/scan_cves.py``
- ``scripts/verify_audit_chain.py``
- ``scripts/verify_vault_rotation.py``
- ``scripts/prune_artifacts.py``
- ``scripts/restore_from_backup.py``
- ``dataIntegrityEngine.cross_check_stooq``
- ``dataIntegrityEngine.data_source_health``

Chaque appel délègue à :func:`ihm.services.process_registry.start_managed_run`,
ce qui réutilise le registre + la rotation + l'audit + l'export logs déjà
en place pour le pipeline.

Le module est volontairement pur (pas d'import Streamlit) afin de pouvoir
être testé en isolation et appelé aussi en headless/scripting.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from ihm.services.pipeline_runner import PROJECT_ROOT, build_subprocess_env
from ihm.services.process_registry import (
    PipelineRunRecord,
    list_active_pipeline_runs,
    start_managed_run,
)

OpsCommandKey = Literal[
    "execution_kill_switch",
    "corporate_actions_status",
    "corporate_actions_apply",
    "pre_live_checklist",
    "daily_parity",
    "broker_reconciliation",
    "monthly_broker_report",
    "quarterly_weights_calibration",
    "scan_cves",
    "verify_audit_chain",
    "verify_vault_rotation",
    "prune_artifacts",
    "restore_from_backup",
    "cross_check_stooq",
    "data_source_health",
]


@dataclass(frozen=True, slots=True)
class OpsCommandSpec:
    """Métadonnées d'une commande ops (catalogue UI)."""

    key: OpsCommandKey
    label: str
    description: str
    icon: str
    danger: bool = False  # affichage badge rouge + double confirmation
    requires_account: bool = False  # certains scripts attendent --account


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

OPS_COMMAND_CATALOG: dict[OpsCommandKey, OpsCommandSpec] = {
    "execution_kill_switch": OpsCommandSpec(
        key="execution_kill_switch",
        label="Kill switch — annuler tous les ordres",
        description=(
            "Annule immédiatement tous les ordres OPEN du compte sélectionné via "
            "`python -m execution_engine cancel-all`. Persiste un kill_switch_run."
        ),
        icon="🛑",
        danger=True,
        requires_account=True,
    ),
    "corporate_actions_status": OpsCommandSpec(
        key="corporate_actions_status",
        label="Corporate Actions — status",
        description="Affiche un résumé synthétique des événements CA en attente / appliqués.",
        icon="📑",
    ),
    "corporate_actions_apply": OpsCommandSpec(
        key="corporate_actions_apply",
        label="Corporate Actions — apply",
        description="Applique les événements pending (sans relancer le sync).",
        icon="✅",
    ),
    "pre_live_checklist": OpsCommandSpec(
        key="pre_live_checklist",
        label="Pré-live checklist",
        description=(
            "Exécute `scripts/run_pre_live_checklist.py` : 12 vérifications obligatoires "
            "(secrets vault, smoke tests, audit chain, watcher, etc.) avant tout passage live."
        ),
        icon="🚦",
        requires_account=True,
    ),
    "daily_parity": OpsCommandSpec(
        key="daily_parity",
        label="Parité quotidienne backtest ↔ live",
        description="`scripts/run_daily_parity.py` — relance le job de parité du jour.",
        icon="🔀",
        requires_account=True,
    ),
    "broker_reconciliation": OpsCommandSpec(
        key="broker_reconciliation",
        label="Réconciliation broker",
        description="`scripts/run_broker_reconciliation.py` — recalcule positions broker vs DB.",
        icon="🧮",
        requires_account=True,
    ),
    "monthly_broker_report": OpsCommandSpec(
        key="monthly_broker_report",
        label="Rapport mensuel broker",
        description="`scripts/run_monthly_broker_report.py` — génère le rapport PDF/JSON mensuel.",
        icon="📅",
        requires_account=True,
    ),
    "quarterly_weights_calibration": OpsCommandSpec(
        key="quarterly_weights_calibration",
        label="Calibration trimestrielle des poids",
        description="`scripts/run_quarterly_weights_calibration.py`.",
        icon="🎛️",
    ),
    "scan_cves": OpsCommandSpec(
        key="scan_cves",
        label="Scan CVE des dépendances",
        description="`scripts/scan_cves.py` — détecte les vulnérabilités connues dans `requirements.txt`.",
        icon="🛡️",
    ),
    "verify_audit_chain": OpsCommandSpec(
        key="verify_audit_chain",
        label="Vérification audit chain",
        description="`scripts/verify_audit_chain.py` — recalcule la chaîne SHA256 des décisions.",
        icon="🔐",
    ),
    "verify_vault_rotation": OpsCommandSpec(
        key="verify_vault_rotation",
        label="Vérification rotation des secrets",
        description="`scripts/verify_vault_rotation.py` — vérifie l'âge des clés.",
        icon="🗝️",
    ),
    "prune_artifacts": OpsCommandSpec(
        key="prune_artifacts",
        label="Nettoyage des artefacts",
        description=(
            "`scripts/prune_artifacts.py` — supprime les artefacts plus vieux que la "
            "rétention. Mode dry-run par défaut."
        ),
        icon="🧹",
    ),
    "restore_from_backup": OpsCommandSpec(
        key="restore_from_backup",
        label="Restauration depuis backup",
        description="`scripts/restore_from_backup.py` — restaure la base depuis un dump SQL.",
        icon="♻️",
        danger=True,
    ),
    "cross_check_stooq": OpsCommandSpec(
        key="cross_check_stooq",
        label="Cross-check OHLCV Stooq",
        description="`python -m dataIntegrityEngine.cross_check_stooq` — compare OHLCV principal vs Stooq.",
        icon="📊",
    ),
    "data_source_health": OpsCommandSpec(
        key="data_source_health",
        label="Health providers data",
        description="`python -m dataIntegrityEngine.data_source_health` — santé Alpaca / EODHD / Stooq.",
        icon="💚",
    ),
}


# ---------------------------------------------------------------------------
# Builders de commande
# ---------------------------------------------------------------------------


def _python(*tail: str) -> list[str]:
    return [sys.executable, "-u", *tail]


def _script(script_relpath: str, *tail: str) -> list[str]:
    return _python(str(PROJECT_ROOT / script_relpath), *tail)


def _module(module_name: str, *tail: str) -> list[str]:
    return _python("-m", module_name, *tail)


def build_ops_command(key: OpsCommandKey, **kwargs: Any) -> list[str]:
    """Construit la commande shell-safe (``list[str]``) pour la commande ops *key*.

    ``kwargs`` autorisés (selon la commande) :

    - ``account``, ``account_id`` : compte Alpaca cible (cancel-all, parity…)
    - ``broker_mode`` : ``paper`` / ``live`` (cancel-all, pre-live)
    - ``confirm_account`` : équivalent ``--confirm-account`` cancel-all
    - ``dry_run`` : bool
    - ``reason`` : str
    - ``trade_date`` : YYYY-MM-DD
    - ``apply_changes`` : pour prune (sinon dry-run)
    - ``backup_path`` : pour restore_from_backup
    - ``extra_args`` : ``list[str]`` injecté tel quel en fin
    """
    extra: list[str] = list(kwargs.get("extra_args") or [])

    if key == "execution_kill_switch":
        account = str(kwargs.get("account") or kwargs.get("account_id") or "").strip()
        if not account:
            raise ValueError("execution_kill_switch requiert `account`.")
        broker_mode = str(kwargs.get("broker_mode") or "paper").strip()
        confirm = str(kwargs.get("confirm_account") or account).strip()
        reason = str(kwargs.get("reason") or "manual kill switch from IHM").strip()
        cmd = _module(
            "execution_engine",
            "cancel-all",
            "--account", account,
            "--confirm-account", confirm,
            "--broker-mode", broker_mode,
            "--reason", reason,
        )
        if bool(kwargs.get("dry_run", False)):
            cmd.append("--dry-run")
        return cmd + extra

    if key == "corporate_actions_status":
        return _module("corporate_actions", "status") + extra

    if key == "corporate_actions_apply":
        cmd = _module("corporate_actions", "apply")
        as_of = str(kwargs.get("as_of") or "").strip()
        if as_of:
            cmd.extend(["--as-of", as_of])
        account = str(kwargs.get("account") or "").strip()
        if account:
            cmd.extend(["--account", account])
        return cmd + extra

    if key == "pre_live_checklist":
        account = str(kwargs.get("account") or "").strip()
        if not account:
            raise ValueError("pre_live_checklist requiert `account`.")
        broker_mode = str(kwargs.get("broker_mode") or "live").strip()
        cmd = _script(
            "scripts/run_pre_live_checklist.py",
            "--account", account,
            "--broker-mode", broker_mode,
        )
        if bool(kwargs.get("skip_network", False)):
            cmd.append("--skip-network")
        return cmd + extra

    if key == "daily_parity":
        cmd = _script("scripts/run_daily_parity.py")
        trade_date = str(kwargs.get("trade_date") or "").strip()
        if trade_date:
            cmd.extend(["--trade-date", trade_date])
        account = str(kwargs.get("account") or "").strip()
        if account:
            cmd.extend(["--account", account])
        if bool(kwargs.get("no_alert", False)):
            cmd.append("--no-alert")
        return cmd + extra

    if key == "broker_reconciliation":
        cmd = _script("scripts/run_broker_reconciliation.py")
        account = str(kwargs.get("account") or "").strip()
        if account:
            cmd.extend(["--account", account])
        return cmd + extra

    if key == "monthly_broker_report":
        cmd = _script("scripts/run_monthly_broker_report.py")
        account = str(kwargs.get("account") or "").strip()
        if account:
            cmd.extend(["--account", account])
        month = str(kwargs.get("month") or "").strip()
        if month:
            cmd.extend(["--month", month])
        return cmd + extra

    if key == "quarterly_weights_calibration":
        return _script("scripts/run_quarterly_weights_calibration.py") + extra

    if key == "scan_cves":
        return _script("scripts/scan_cves.py") + extra

    if key == "verify_audit_chain":
        return _script("scripts/verify_audit_chain.py") + extra

    if key == "verify_vault_rotation":
        return _script("scripts/verify_vault_rotation.py") + extra

    if key == "prune_artifacts":
        cmd = _script("scripts/prune_artifacts.py")
        if bool(kwargs.get("apply_changes", False)):
            cmd.append("--apply")
        return cmd + extra

    if key == "restore_from_backup":
        backup_path = str(kwargs.get("backup_path") or "").strip()
        if not backup_path:
            raise ValueError("restore_from_backup requiert `backup_path`.")
        cmd = _script("scripts/restore_from_backup.py", "--dump-path", backup_path)
        if bool(kwargs.get("dry_run", False)):
            cmd.append("--dry-run")
        if bool(kwargs.get("skip_alembic", False)):
            cmd.append("--skip-alembic")
        if bool(kwargs.get("skip_audit", False)):
            cmd.append("--skip-audit")
        return cmd + extra

    if key == "cross_check_stooq":
        return _module("dataIntegrityEngine.cross_check_stooq") + extra

    if key == "data_source_health":
        return _module("dataIntegrityEngine.data_source_health") + extra

    raise KeyError(f"Commande ops inconnue : {key}")


# ---------------------------------------------------------------------------
# Lancement
# ---------------------------------------------------------------------------


def start_ops_command(
    key: OpsCommandKey,
    *,
    account_id: str | None = None,
    db_config: dict[str, str | None] | None = None,
    timeout_seconds: int | None = None,
    **command_kwargs: Any,
) -> PipelineRunRecord:
    """Lance la commande ops `key` en arrière-plan via le registre IHM.

    Le run est tracé sous ``step_key="ops:<key>"`` pour cohabiter avec les
    pipelines sans collision dans ``list_active_pipeline_runs()``.
    """
    spec = OPS_COMMAND_CATALOG[key]
    if spec.requires_account and not (command_kwargs.get("account") or command_kwargs.get("account_id") or account_id):
        raise ValueError(f"La commande `{key}` requiert un compte (account_id).")

    if spec.requires_account and not command_kwargs.get("account"):
        command_kwargs["account"] = account_id

    command = build_ops_command(key, **command_kwargs)
    return start_managed_run(
        step_key=f"ops:{key}",
        step_label=f"{spec.icon} {spec.label}",
        command=command,
        account_id=account_id,
        db_config=db_config,
        timeout_seconds=timeout_seconds,
    )


def list_active_ops_runs(key: OpsCommandKey | None = None) -> list[dict[str, object]]:
    """Filtre ``list_active_pipeline_runs`` sur les runs ops (préfixe ``ops:``)."""
    target = f"ops:{key}" if key else None
    out: list[dict[str, object]] = []
    for run in list_active_pipeline_runs():
        sk = str(run.get("step_key", ""))
        if target is None and sk.startswith("ops:"):
            out.append(run)
        elif target is not None and sk == target:
            out.append(run)
    return out


__all__ = [
    "OpsCommandKey",
    "OpsCommandSpec",
    "OPS_COMMAND_CATALOG",
    "build_ops_command",
    "start_ops_command",
    "list_active_ops_runs",
]

