"""Pilotage local du watcher de protections depuis l'IHM.

Ces helpers démarrent/arrêtent uniquement des processus lancés par l'IHM.
Ils ne pilotent ni Task Scheduler ni NSSM, afin de ne pas remplacer
accidentellement le packaging Windows d'exploitation.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

from ihm.services.pipeline_runner import PROJECT_ROOT
from ihm.services.process_registry import (
    build_log_download_name,
    PipelineRunRecord,
    get_pipeline_run_record,
    list_active_pipeline_runs,
    load_pipeline_history,
    read_pipeline_logs,
    start_managed_run,
    stop_pipeline_run,
)

WATCHER_ONCE_STEP_KEY = "execution_protection_watch_once"
WATCHER_SERVICE_STEP_KEY = "execution_protection_watch_service_local"
WATCHER_RUNTIME_STEP_KEYS: tuple[str, ...] = (
    WATCHER_ONCE_STEP_KEY,
    WATCHER_SERVICE_STEP_KEY,
)

DEFAULT_WATCHER_LIMIT = 100
DEFAULT_SERVICE_INTERVAL_SECONDS = 30.0
DEFAULT_IDLE_INTERVAL_SECONDS = 120.0
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 300.0
DEFAULT_WATCHER_TASK_NAME = "AlphaTrade-ProtectionWatcher"
DEFAULT_WATCHER_SERVICE_NAME = "AlphaTradeProtectionWatcher"
WATCHER_DOC_PATH = PROJECT_ROOT / "doc" / "watcher.md"
LOGGER = logging.getLogger(__name__)


def _watcher_leader_lock_account(account_id: str | None = None) -> str:
    return f"watcher:{account_id or 'default'}"


def _force_release_local_watcher_leader_lock(account_id: str | None = None) -> None:
    try:
        from execution_engine.db_io import ExecutionRepository

        released = ExecutionRepository().force_release_execution_lock(
            account_id=_watcher_leader_lock_account(account_id),
        )
        if released:
            LOGGER.info(
                "Verrou leader watcher local IHM nettoyé après arrêt forcé: %s",
                _watcher_leader_lock_account(account_id),
            )
    except Exception:
        LOGGER.debug("Nettoyage verrou leader watcher local IHM impossible", exc_info=True)


def build_watcher_doc_reference() -> dict[str, str]:
    return {
        "label": "📘 Guide watcher complet",
        "relative_path": "doc/watcher.md",
        "absolute_path": str(WATCHER_DOC_PATH),
        "uri": WATCHER_DOC_PATH.as_uri(),
    }


def build_watcher_command(
    *,
    mode: str,
    account_id: str | None = None,
    exec_run_id: str | None = None,
    limit: int = DEFAULT_WATCHER_LIMIT,
    broker_mode: str = "paper",
    profit_taker_pct: float = 0.08,
    trailing_stop_pct: float = 0.05,
    manual_buy_stop_loss_pct: float = 0.05,
    trailing_activation_trigger: str = "multiple_r",
    trailing_activation_r_multiple: float = 1.0,
    trailing_activation_profit_pct: float = 0.03,
    service_interval_seconds: float = DEFAULT_SERVICE_INTERVAL_SECONDS,
    idle_interval_seconds: float = DEFAULT_IDLE_INTERVAL_SECONDS,
    heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    log_level: str = "INFO",
) -> list[str]:
    command = [
        sys.executable,
        "-u",
        str(PROJECT_ROOT / "execution_engine" / "protection_watcher.py"),
        "--mode",
        mode,
        "--limit",
        str(limit),
        "--broker-mode",
        broker_mode,
        "--profit-taker-pct",
        str(profit_taker_pct),
        "--trailing-stop-pct",
        str(trailing_stop_pct),
        "--manual-buy-stop-loss-pct",
        str(manual_buy_stop_loss_pct),
        "--trailing-activation-trigger",
        trailing_activation_trigger,
        "--trailing-activation-r-multiple",
        str(trailing_activation_r_multiple),
        "--trailing-activation-profit-pct",
        str(trailing_activation_profit_pct),
        "--log-level",
        log_level,
    ]
    if account_id:
        command.extend(["--account", account_id])
    if exec_run_id:
        command.extend(["--exec-run-id", exec_run_id])
    if mode == "service":
        command.extend(
            [
                "--service-interval-seconds",
                str(service_interval_seconds),
                "--idle-interval-seconds",
                str(idle_interval_seconds),
                "--heartbeat-interval-seconds",
                str(heartbeat_interval_seconds),
            ]
        )
    return command


def list_active_watcher_runs(*, account_id: str | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for run in list_active_pipeline_runs():
        if str(run.get("step_key", "") or "") not in WATCHER_RUNTIME_STEP_KEYS:
            continue
        if account_id and str(run.get("account_id", "") or "") not in {"", account_id}:
            continue
        rows.append(dict(run))
    return rows


def list_watcher_run_history(*, account_id: str | None = None, limit: int = 50) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for run in load_pipeline_history():
        if str(run.get("step_key", "") or "") not in WATCHER_RUNTIME_STEP_KEYS:
            continue
        if account_id and str(run.get("account_id", "") or "") not in {"", account_id}:
            continue
        rows.append(dict(run))
        if len(rows) >= limit:
            break
    return rows


def get_watcher_run_record(run_id: str) -> dict[str, object] | None:
    record = get_pipeline_run_record(run_id)
    if record is None:
        return None
    if str(record.get("step_key", "") or "") not in WATCHER_RUNTIME_STEP_KEYS:
        return None
    return record


def read_watcher_run_logs(run_id: str, *, stream: str = "all") -> str:
    if get_watcher_run_record(run_id) is None:
        return ""
    return read_pipeline_logs(run_id, stream=stream)  # type: ignore[arg-type]


def build_watcher_log_download_name(run_id: str, *, stream: str = "all") -> str:
    if get_watcher_run_record(run_id) is None:
        return f"watcher_{run_id}_{stream}.log"
    return build_log_download_name(run_id, stream=stream)  # type: ignore[arg-type]


def build_windows_integration_rows(*, account_id: str | None = None) -> list[dict[str, str]]:
    effective_account = account_id or "default"
    return [
        {
            "mode": "Task Scheduler",
            "target": "Scan périodique `once`",
            "when_to_use": "Recommandé si vous voulez un scan périodique simple sans service persistant.",
            "command": (
                "powershell -ExecutionPolicy Bypass -File .\\scripts\\windows\\install_protection_watcher_task.ps1 "
                f"-TaskName \"{DEFAULT_WATCHER_TASK_NAME}\" -FrequencyMinutes 5 -Account {effective_account}"
            ),
        },
        {
            "mode": "NSSM",
            "target": "Service persistant",
            "when_to_use": "À utiliser si vous voulez un vrai service Windows long-lived avec heartbeat continu.",
            "command": (
                "powershell -ExecutionPolicy Bypass -File .\\scripts\\windows\\install_protection_watcher_service_nssm.ps1 "
                "-NssmExePath \"C:\\tools\\nssm\\win64\\nssm.exe\" "
                f"-ServiceName \"{DEFAULT_WATCHER_SERVICE_NAME}\" -Account {effective_account} -StartAfterInstall"
            ),
        },
        {
            "mode": "Lanceur manuel",
            "target": "Diagnostic local",
            "when_to_use": "Pratique pour un test manuel ou une vérification opérateur ponctuelle sans modifier le packaging machine.",
            "command": (
                "powershell -ExecutionPolicy Bypass -File .\\scripts\\windows\\protection_watcher_launcher.ps1 "
                f"-Mode once -Account {effective_account}"
            ),
        },
    ]


def get_active_local_watcher_service(*, account_id: str | None = None) -> dict[str, object] | None:
    for run in list_active_watcher_runs(account_id=account_id):
        if str(run.get("step_key", "") or "") == WATCHER_SERVICE_STEP_KEY:
            return run
    return None


def get_active_watcher_once_run(*, account_id: str | None = None) -> dict[str, object] | None:
    for run in list_active_watcher_runs(account_id=account_id):
        if str(run.get("step_key", "") or "") == WATCHER_ONCE_STEP_KEY:
            return run
    return None


def launch_watcher_once(
    *,
    db_config: dict[str, str | None] | None = None,
    account_id: str | None = None,
    exec_run_id: str | None = None,
    limit: int = DEFAULT_WATCHER_LIMIT,
    broker_mode: str = "paper",
    profit_taker_pct: float = 0.08,
    trailing_stop_pct: float = 0.05,
    manual_buy_stop_loss_pct: float = 0.05,
    trailing_activation_trigger: str = "multiple_r",
    trailing_activation_r_multiple: float = 1.0,
    trailing_activation_profit_pct: float = 0.03,
    log_level: str = "INFO",
) -> PipelineRunRecord:
    if get_active_local_watcher_service(account_id=account_id) is not None:
        raise RuntimeError("Un service watcher local IHM est déjà actif. Arrêtez-le avant un run once.")
    if get_active_watcher_once_run(account_id=account_id) is not None:
        raise RuntimeError("Un run watcher once est déjà en cours depuis l'IHM.")
    return start_managed_run(
        step_key=WATCHER_ONCE_STEP_KEY,
        step_label="Watcher protections — once",
        command=build_watcher_command(
            mode="once",
            account_id=account_id,
            exec_run_id=exec_run_id,
            limit=limit,
            broker_mode=broker_mode,
            profit_taker_pct=profit_taker_pct,
            trailing_stop_pct=trailing_stop_pct,
            manual_buy_stop_loss_pct=manual_buy_stop_loss_pct,
            trailing_activation_trigger=trailing_activation_trigger,
            trailing_activation_r_multiple=trailing_activation_r_multiple,
            trailing_activation_profit_pct=trailing_activation_profit_pct,
            log_level=log_level,
        ),
        account_id=account_id,
        db_config=db_config,
    )


def start_local_watcher_service(
    *,
    db_config: dict[str, str | None] | None = None,
    account_id: str | None = None,
    exec_run_id: str | None = None,
    limit: int = DEFAULT_WATCHER_LIMIT,
    broker_mode: str = "paper",
    service_interval_seconds: float = DEFAULT_SERVICE_INTERVAL_SECONDS,
    idle_interval_seconds: float = DEFAULT_IDLE_INTERVAL_SECONDS,
    heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    profit_taker_pct: float = 0.08,
    trailing_stop_pct: float = 0.05,
    manual_buy_stop_loss_pct: float = 0.05,
    trailing_activation_trigger: str = "multiple_r",
    trailing_activation_r_multiple: float = 1.0,
    trailing_activation_profit_pct: float = 0.03,
    log_level: str = "INFO",
) -> PipelineRunRecord:
    if get_active_local_watcher_service(account_id=account_id) is not None:
        raise RuntimeError("Un service watcher local IHM est déjà actif.")
    if get_active_watcher_once_run(account_id=account_id) is not None:
        raise RuntimeError("Un run watcher once est déjà actif. Attendez sa fin avant de démarrer un service local.")
    return start_managed_run(
        step_key=WATCHER_SERVICE_STEP_KEY,
        step_label="Watcher protections — service local IHM",
        command=build_watcher_command(
            mode="service",
            account_id=account_id,
            exec_run_id=exec_run_id,
            limit=limit,
            broker_mode=broker_mode,
            service_interval_seconds=service_interval_seconds,
            idle_interval_seconds=idle_interval_seconds,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
            profit_taker_pct=profit_taker_pct,
            trailing_stop_pct=trailing_stop_pct,
            manual_buy_stop_loss_pct=manual_buy_stop_loss_pct,
            trailing_activation_trigger=trailing_activation_trigger,
            trailing_activation_r_multiple=trailing_activation_r_multiple,
            trailing_activation_profit_pct=trailing_activation_profit_pct,
            log_level=log_level,
        ),
        account_id=account_id,
        db_config=db_config,
    )


def stop_local_watcher_service(run_id: str) -> bool:
    record = get_pipeline_run_record(run_id)
    if record is None:
        return False
    if str(record.get("step_key", "") or "") != WATCHER_SERVICE_STEP_KEY:
        raise RuntimeError("Seuls les services watcher lancés depuis l'IHM peuvent être arrêtés ici.")
    stopped = stop_pipeline_run(run_id)
    if stopped:
        _force_release_local_watcher_leader_lock(str(record.get("account_id") or "") or None)
    return stopped


def restart_local_watcher_service(
    *,
    db_config: dict[str, str | None] | None = None,
    account_id: str | None = None,
    exec_run_id: str | None = None,
    limit: int = DEFAULT_WATCHER_LIMIT,
    broker_mode: str = "paper",
    service_interval_seconds: float = DEFAULT_SERVICE_INTERVAL_SECONDS,
    idle_interval_seconds: float = DEFAULT_IDLE_INTERVAL_SECONDS,
    heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    profit_taker_pct: float = 0.08,
    trailing_stop_pct: float = 0.05,
    manual_buy_stop_loss_pct: float = 0.05,
    trailing_activation_trigger: str = "multiple_r",
    trailing_activation_r_multiple: float = 1.0,
    trailing_activation_profit_pct: float = 0.03,
    log_level: str = "INFO",
) -> PipelineRunRecord:
    active_service = get_active_local_watcher_service(account_id=account_id)
    if active_service is not None:
        stop_local_watcher_service(str(active_service.get("run_id", "") or ""))
    return start_local_watcher_service(
        db_config=db_config,
        account_id=account_id,
        exec_run_id=exec_run_id,
        limit=limit,
        broker_mode=broker_mode,
        service_interval_seconds=service_interval_seconds,
        idle_interval_seconds=idle_interval_seconds,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        profit_taker_pct=profit_taker_pct,
        trailing_stop_pct=trailing_stop_pct,
        manual_buy_stop_loss_pct=manual_buy_stop_loss_pct,
        trailing_activation_trigger=trailing_activation_trigger,
        trailing_activation_r_multiple=trailing_activation_r_multiple,
        trailing_activation_profit_pct=trailing_activation_profit_pct,
        log_level=log_level,
    )


def serialize_local_watcher_control_state(*, account_id: str | None = None) -> dict[str, Any]:
    service_run = get_active_local_watcher_service(account_id=account_id)
    once_run = get_active_watcher_once_run(account_id=account_id)
    return {
        "local_service_active": service_run is not None,
        "local_service_run_id": str((service_run or {}).get("run_id", "") or ""),
        "local_once_active": once_run is not None,
        "local_once_run_id": str((once_run or {}).get("run_id", "") or ""),
    }


# ---------------------------------------------------------------------------
# Multi-comptes (Issue 1, 2026-05) — boucle sur tous les comptes Alpaca pour
# poser les TP/SL si besoin via le watcher. Côté IHM, on **spawn un processus
# par compte** (plutôt qu'un seul processus qui itère) afin que :
#   - chaque compte conserve son propre verrou leader (pas de conflit) ;
#   - les logs et le statut Supervision Ops restent ségrégués par compte ;
#   - l'arrêt d'un compte n'arrête pas les autres ;
#   - le packaging Windows (Task Scheduler / NSSM) reste agnostique.
# ---------------------------------------------------------------------------

ALL_ACCOUNTS_SENTINEL = "__all__"


def list_alpaca_account_ids() -> list[str]:
    """Liste tous les comptes Alpaca déclarés (config.yaml + env vars)."""
    try:
        from service.alpaca.accounts import AccountRegistry
    except Exception:
        LOGGER.debug("AccountRegistry indisponible", exc_info=True)
        return []
    try:
        return list(AccountRegistry.get().list_account_ids())
    except Exception:
        LOGGER.debug("AccountRegistry.list_account_ids échoué", exc_info=True)
        return []


def _resolve_target_account_ids(account_id: str | None) -> list[str | None]:
    """Si ``account_id`` vaut ``ALL_ACCOUNTS_SENTINEL``, retourne tous les
    comptes Alpaca déclarés ; sinon retourne ``[account_id]``."""
    if account_id == ALL_ACCOUNTS_SENTINEL:
        ids = list_alpaca_account_ids()
        if not ids:
            raise RuntimeError(
                "Aucun compte Alpaca déclaré : impossible de lancer le watcher pour 'tous les comptes'.",
            )
        return list(ids)  # already list[str]
    return [account_id]


def launch_watcher_once_for_all_accounts(
    *,
    db_config: dict[str, str | None] | None = None,
    **kwargs: Any,
) -> list[PipelineRunRecord]:
    """Lance un ``run once`` du watcher pour chaque compte Alpaca déclaré.

    Boucle sur ``AccountRegistry.list_account_ids()`` et délègue à
    :func:`launch_watcher_once`. Les comptes qui ont déjà un service / once
    actif sont **ignorés** (loggués) plutôt que de faire échouer toute la
    chaîne.
    """
    records: list[PipelineRunRecord] = []
    errors: list[str] = []
    for aid in list_alpaca_account_ids():
        try:
            records.append(launch_watcher_once(db_config=db_config, account_id=aid, **kwargs))
        except RuntimeError as exc:
            errors.append(f"{aid}: {exc}")
            LOGGER.info("Watcher once ignoré pour compte %s : %s", aid, exc)
        except Exception as exc:  # pragma: no cover - défense IHM
            errors.append(f"{aid}: {exc}")
            LOGGER.warning("Watcher once a échoué pour compte %s", aid, exc_info=True)
    if not records and errors:
        raise RuntimeError(
            "Aucun watcher once n'a pu être lancé pour les comptes Alpaca : " + " | ".join(errors)
        )
    return records


def start_local_watcher_service_for_all_accounts(
    *,
    db_config: dict[str, str | None] | None = None,
    **kwargs: Any,
) -> list[PipelineRunRecord]:
    """Démarre un service watcher local IHM par compte Alpaca déclaré.

    Idempotent par compte : un compte déjà couvert par un service local est
    ignoré (log info) ; les autres sont démarrés.
    """
    records: list[PipelineRunRecord] = []
    errors: list[str] = []
    for aid in list_alpaca_account_ids():
        try:
            records.append(start_local_watcher_service(db_config=db_config, account_id=aid, **kwargs))
        except RuntimeError as exc:
            errors.append(f"{aid}: {exc}")
            LOGGER.info("Service watcher local ignoré pour compte %s : %s", aid, exc)
        except Exception as exc:  # pragma: no cover - défense IHM
            errors.append(f"{aid}: {exc}")
            LOGGER.warning("Service watcher local a échoué pour compte %s", aid, exc_info=True)
    if not records and errors:
        raise RuntimeError(
            "Aucun service watcher local n'a pu être démarré pour les comptes Alpaca : " + " | ".join(errors)
        )
    return records


def serialize_all_accounts_watcher_control_state() -> dict[str, Any]:
    """Vue agrégée multi-comptes pour décider de l'activation des boutons
    « tous les comptes »."""
    per_account: dict[str, dict[str, Any]] = {}
    for aid in list_alpaca_account_ids():
        per_account[aid] = serialize_local_watcher_control_state(account_id=aid)
    return {
        "accounts": per_account,
        "any_service_active": any(state.get("local_service_active") for state in per_account.values()),
        "any_once_active": any(state.get("local_once_active") for state in per_account.values()),
        "all_service_active": bool(per_account) and all(
            state.get("local_service_active") for state in per_account.values()
        ),
    }


