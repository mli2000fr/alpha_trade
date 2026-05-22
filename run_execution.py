#!/usr/bin/env python
"""
Alpha Trade -- Production Executor -- Point d'entree simplifie

Usage rapide :
  python run_execution.py                      <- menu interactif
  python run_execution.py simulate             <- simulation pure (dry-run)
  python run_execution.py paper                <- paper trading (Alpaca)
  python run_execution.py live                 <- live trading (argent reel !)
  python run_execution.py paper --date 2026-04-18
  python run_execution.py paper --run-id abc123def4567890
  python run_execution.py simulate --run-id abc123 --debug
  python run_execution.py check                <- verifie les variables d'env

Variables d'environnement requises :
  LOGIN_DB           -> utilisateur MySQL
  PASSWORD_DB        -> mot de passe MySQL
  ALPACA_API_KEY     -> cle API Alpaca
  ALPACA_SECRET_KEY  -> secret Alpaca
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
from collections.abc import Iterable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal, cast

from common.utils import configure_root_logging
from database.run_business_summaries import emit_run_summary, persist_run_business_summary

PROJECT_ROOT = Path(__file__).resolve().parent

# active les sequences ANSI sur Windows
os.system("")

GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

SEP = "-" * 60
LIVE_APPROVAL_TOKEN_ENV = "ALPHA_TRADE_LIVE_APPROVAL_TOKEN"

BANNER = f"""
{CYAN}{BOLD}
  _    _       _           _____              _
 / \\  | |_ __ | |__   __ |_   _| __ __ _  __| | ___
/ _ \\ | | '_ \\| '_ \\ / _` || || '__/ _` |/ _` |/ _ \\
/ ___ \\| | |_) | | | | (_| || || | | (_| | (_| |  __/
/_/   \\_\\_| .__/|_| |_|\\__,_||_||_|  \\__,_|\\__,_|\\___|
          |_|   Production Executor -- OMS/EMS
{RESET}"""


# ---------------------------------------------------------------------------
# Verification des prerequis
# ---------------------------------------------------------------------------

def check_env(account_id: str | None = None, mode: str | None = None) -> list[str]:
    """Vérifie les variables d'environnement requises selon le contexte.

    Sprint S2 / A-008 :
    - ``LOGIN_DB`` / ``PASSWORD_DB`` toujours requis.
    - En mode ``simulate`` : credentials Alpaca optionnelles (dry-run pur).
    - En mode ``paper`` / ``live`` : on tente de résoudre le compte via le
      ``AccountRegistry`` (config.yaml + env vars). Si ``account_id`` fourni
      mais introuvable -> erreur explicite.
    """
    missing: list[str] = []
    for var in ("LOGIN_DB", "PASSWORD_DB"):
        if not os.getenv(var):
            missing.append(var)

    if mode == "simulate":
        return missing

    # Modes paper/live (ou inconnu/check) : on s'appuie sur le registre.
    try:
        from service.alpaca.accounts import AccountRegistry

        registry = AccountRegistry.get()
        accounts = registry.list_accounts()
    except Exception:
        accounts = []

    if not accounts:
        # Fallback sur les variables historiques pour compatibilite.
        for var in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
            if not os.getenv(var):
                missing.append(var)
        return missing

    if account_id:
        try:
            from service.alpaca.accounts import AccountRegistry

            acct = AccountRegistry.get().resolve(account_id)
        except Exception as exc:
            missing.append(f"compte '{account_id}' introuvable ({exc})")
            return missing
        if mode == "live" and getattr(acct, "mode", "paper") != "live":
            missing.append(
                f"compte '{account_id}' configure en mode '{acct.mode}', "
                "incompatible avec --mode live"
            )
        return missing

    if mode == "live":
        live_accounts = [a for a in accounts if getattr(a, "mode", "") == "live"]
        if not live_accounts:
            missing.append("aucun compte mode='live' configure (config.yaml/env)")
    return missing


def print_env_status() -> bool:
    missing = check_env()
    print(f"\n{BOLD}{SEP}{RESET}")
    print(f"{BOLD}  Variables d'environnement{RESET}")
    print(f"{BOLD}{SEP}{RESET}")
    all_vars = {
        "LOGIN_DB":          "Utilisateur MySQL",
        "PASSWORD_DB":       "Mot de passe MySQL",
        "ALPACA_API_KEY":    "Cle API Alpaca",
        "ALPACA_SECRET_KEY": "Secret Alpaca",
    }
    for var, desc in all_vars.items():
        val = os.getenv(var)
        if val:
            masked = val[:4] + "****" if len(val) > 4 else "****"
            print(f"  {GREEN}[OK]{RESET}  {var:<22} {desc} ({masked})")
        else:
            print(f"  {RED}[KO]{RESET}  {var:<22} {RED}{desc} -- MANQUANT{RESET}")
    print()
    return len(missing) == 0


def abort_missing_env(account_id: str | None = None, mode: str | None = None) -> None:
    """Avorte le run si une dépendance critique manque pour le contexte donné.

    Sprint S2 / A-008 : message d'erreur clair indiquant le compte/mode
    concerné, exit code 1 — supprime le fail silencieux ALPACA_API_KEY générique.
    """
    missing = check_env(account_id=account_id, mode=mode)
    if missing:
        ctx = f"compte={account_id or '(defaut)'} mode={mode or '(?)'}"
        print(
            f"\n{RED}{BOLD}[FATAL] credentials/configuration manquantes pour {ctx} : "
            f"{', '.join(missing)}{RESET}",
            file=sys.stderr,
        )
        print("\nDefinis-les dans PowerShell avec :", file=sys.stderr)
        for v in missing:
            if v.startswith("compte ") or v.startswith("aucun compte"):
                continue
            print(f'  $env:{v} = "ta_valeur"', file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Menu interactif
# ---------------------------------------------------------------------------

def interactive_menu() -> tuple[
    str,
    str | None,
    str | None,
    bool,
    bool,
    bool,
    str | None,
    str,
    str,
    bool,
    str,
    str | None,
    str | None,
]:
    print(BANNER)
    print_env_status()

    print(f"{BOLD}{SEP}{RESET}")
    print(f"{BOLD}  Choisir un mode{RESET}")
    print(f"{BOLD}{SEP}{RESET}")
    print(f"  {CYAN}1{RESET}  Simulation    -- dry-run, aucun ordre envoye")
    print(f"  {YELLOW}2{RESET}  Paper trading -- ordres reels sur compte fictif Alpaca")
    print(f"  {RED}3{RESET}  Live trading  -- ordres reels sur compte reel {RED}[ARGENT REEL]{RESET}")
    print(f"  {BOLD}0{RESET}  Quitter\n")

    choice = input("Ton choix [1/2/3/0] : ").strip()
    mode_map = {"1": "simulate", "2": "paper", "3": "live"}
    if choice == "0" or choice not in mode_map:
        print("Au revoir.")
        sys.exit(0)
    mode = mode_map[choice]

    if mode == "live":
        # Phase 1 sécurité : confirmation renforcée — l'opérateur doit ressaisir
        # exactement le label du compte live qu'il s'apprête à utiliser.
        # On charge la liste des comptes live pour proposer le label attendu.
        expected_label: str | None = None
        try:
            from service.alpaca.accounts import AccountRegistry
            for acct in AccountRegistry.get().list_accounts():
                if getattr(acct, "mode", "") == "live":
                    expected_label = acct.label
                    break
        except Exception:
            pass

        confirm = input(
            f"\n{RED}{BOLD}[ATTENTION] Confirmes-tu le lancement en LIVE (argent reel) ? [oui/non] : {RESET}"
        ).strip().lower()
        if confirm != "oui":
            print("Annule.")
            sys.exit(0)
        if expected_label:
            typed = input(
                f"{RED}{BOLD}Tape EXACTEMENT le label du compte live "
                f"pour confirmer (attendu: '{expected_label}') : {RESET}"
            ).strip()
            if typed != expected_label:
                print(f"{RED}Label incorrect : '{typed}' != '{expected_label}'. Abandon.{RESET}")
                sys.exit(1)
        else:
            print(f"{YELLOW}[!] Aucun compte live configuré dans config.yaml.{RESET}")
            sys.exit(1)

    print(f"\n{BOLD}{SEP}{RESET}")
    print(f"{BOLD}  Source des cibles{RESET}")
    print(f"{BOLD}{SEP}{RESET}")
    print("  1  Par date         (charge le dernier run de la date choisie)")
    print("  2  Par risk_run_id  (charge un run precis)")
    print("  3  Dernier run dispo (aucun filtre)\n")
    src = input("Ton choix [1/2/3] : ").strip()

    run_id: str | None = None
    trade_date: str | None = None

    if src == "1":
        trade_date = input(f"Date [Entree = aujourd'hui {date.today()}] : ").strip()
        if not trade_date:
            trade_date = str(date.today())
    elif src == "2":
        run_id = input("risk_run_id : ").strip()

    debug = input("\nActiver les logs DEBUG ? [o/N] : ").strip().lower() == "o"
    outside_rth = input("Forcer execution hors horaires marche ? [o/N] : ").strip().lower() == "o"
    rebalance = input("Activer reequilibrage auto sur reconciliation ? [o/N] : ").strip().lower() == "o"

    raw_account_type = input("Type de compte [margin/cash, defaut cash] : ").strip().lower()
    account_type = raw_account_type if raw_account_type in {"margin", "cash"} else "cash"
    raw_pdt_rule = input("Regle PDT [auto/off, defaut off] : ").strip().lower()
    pdt_rule = raw_pdt_rule if raw_pdt_rule in {"auto", "off"} else "off"
    swing_only = input("Interdire les sorties le jour meme (swing_only) ? [O/n] : ").strip().lower() != "n"
    raw_submission_window = input("Fenetre de soumission [post_close/pre_open/both, defaut both] : ").strip().lower()
    submission_window = raw_submission_window if raw_submission_window in {"post_close", "pre_open", "both"} else "both"
    approval_token: str | None = None
    run_plan_file: str | None = None
    if mode == "live":
        approval_token = input("Token d'approbation live (obligatoire) : ").strip() or None
        run_plan_file = input("Chemin du run plan immuable [Entrée = auto] : ").strip() or None

    # Sélection du compte multi-comptes
    account_id: str | None = None
    try:
        from service.alpaca.accounts import AccountRegistry
        accounts = AccountRegistry.get().list_accounts()
        if len(accounts) > 1:
            print(f"\n{BOLD}{SEP}{RESET}")
            print(f"{BOLD}  Choisir un compte Alpaca{RESET}")
            print(f"{BOLD}{SEP}{RESET}")
            for i, acct in enumerate(accounts, 1):
                print(f"  {CYAN}{i}{RESET}  {acct.label} ({acct.account_id}, {acct.mode})")
            acct_choice = input(f"Ton choix [1-{len(accounts)}] : ").strip()
            try:
                idx = int(acct_choice) - 1
                if 0 <= idx < len(accounts):
                    account_id = accounts[idx].account_id
            except (ValueError, IndexError):
                pass
    except Exception:
        pass

    return (
        mode,
        run_id,
        trade_date,
        debug,
        outside_rth,
        rebalance,
        account_id,
        account_type,
        pdt_rule,
        swing_only,
        submission_window,
        approval_token,
        run_plan_file,
    )


# ---------------------------------------------------------------------------
# Presets de configuration
# ---------------------------------------------------------------------------

PRESETS: dict[str, dict] = {
    "simulate": {
        "broker_mode": "paper",
        "dry_run": True,
        "entry_order_type": "market",
        "profit_taker_pct": 0.08,
        "trailing_stop_pct": 0.05,
        "trailing_activation_trigger": "multiple_r",
        "trailing_activation_r_multiple": 1.0,
        "trailing_activation_profit_pct": 0.03,
        "protection_transition_timeout_seconds": 0,
        "protection_transition_poll_interval_seconds": 2.0,
        "max_slippage_bps": 30,
        "max_order_retries": 3,
        "poll_interval_seconds": 2.0,
        "fill_timeout_seconds": 120,
        "allow_outside_rth": True,   # overnight-only : soumission nominale hors seance
        "inter_order_delay_ms": 0,   # dry-run : pas de throttle
        "account_type": "cash",
        "pdt_rule": "off",
        "swing_only": True,
        "execution_profile": "overnight_cash_swing",
        "submission_window": "both",
    },
    "paper": {
        "broker_mode": "paper",
        "dry_run": False,
        "entry_order_type": "market",
        "profit_taker_pct": 0.08,
        "trailing_stop_pct": 0.05,
        "trailing_activation_trigger": "multiple_r",
        "trailing_activation_r_multiple": 1.0,
        "trailing_activation_profit_pct": 0.03,
        "protection_transition_timeout_seconds": 30,
        "protection_transition_poll_interval_seconds": 2.0,
        "max_slippage_bps": 30,
        "max_order_retries": 3,
        "poll_interval_seconds": 2.0,
        "fill_timeout_seconds": 120,
        "allow_outside_rth": True,
        "inter_order_delay_ms": 350,
        "account_type": "cash",
        "pdt_rule": "off",
        "swing_only": True,
        "execution_profile": "overnight_cash_swing",
        "submission_window": "both",
    },
    "live": {
        "broker_mode": "live",
        "dry_run": False,
        "entry_order_type": "market",
        "profit_taker_pct": 0.08,
        "trailing_stop_pct": 0.05,
        "trailing_activation_trigger": "multiple_r",
        "trailing_activation_r_multiple": 1.0,
        "trailing_activation_profit_pct": 0.03,
        "protection_transition_timeout_seconds": 30,
        "protection_transition_poll_interval_seconds": 2.0,
        "max_slippage_bps": 20,      # plus strict en live
        "max_order_retries": 3,
        "poll_interval_seconds": 1.5,
        "fill_timeout_seconds": 180,
        "allow_outside_rth": True,
        "inter_order_delay_ms": 350,
        "account_type": "cash",
        "pdt_rule": "off",
        "swing_only": True,
        "execution_profile": "overnight_cash_swing",
        "submission_window": "both",
    },
}


# ---------------------------------------------------------------------------
# Lancement
# ---------------------------------------------------------------------------


def resolve_mode_from_broker_mode(*, broker_mode: str, dry_run: bool) -> str:
    """Convertit le contrat historique executor (`broker_mode` + `dry_run`) en mode canonique."""
    return "simulate" if dry_run else str(broker_mode)


def _build_execution_run_plan(
    *,
    mode: str,
    run_id: str | None,
    trade_date: str | None,
    account_id: str | None,
    preset: dict,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "mode": mode,
        "account_id": str(account_id or "default"),
        "risk_run_id": str(run_id or ""),
        "trade_date": str(trade_date or ""),
        "preset": preset,
    }


def _fingerprint_execution_run_plan(plan: dict[str, object]) -> str:
    payload = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _resolve_run_plan_path(account_id: str | None, run_plan_file: str | None) -> Path:
    if run_plan_file:
        return Path(run_plan_file)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return PROJECT_ROOT / "artifacts" / "execution_run_plans" / f"{stamp}_{account_id or 'default'}_live.json"


def _validate_live_approval_token(approval_token: str | None) -> str:
    expected = str(os.getenv(LIVE_APPROVAL_TOKEN_ENV) or "").strip()
    provided = str(approval_token or "").strip()
    if not expected:
        raise RuntimeError(
            f"aucun token d'approbation configuré dans {LIVE_APPROVAL_TOKEN_ENV}"
        )
    if not provided:
        raise RuntimeError("token d'approbation live manquant (--approval-token)")
    if provided != expected:
        raise RuntimeError("token d'approbation live invalide")
    return provided


def _validate_live_secret_policy() -> None:
    from common.config_vault import is_live_secret_policy_satisfied

    ok, details = is_live_secret_policy_satisfied()
    if not ok:
        raise RuntimeError(str(details.get("message") or "policy secrets live invalide"))


def _ensure_immutable_run_plan(
    *,
    mode: str,
    run_id: str | None,
    trade_date: str | None,
    account_id: str | None,
    preset: dict,
    approval_token: str,
    run_plan_file: str | None,
) -> tuple[Path, str]:
    plan = _build_execution_run_plan(
        mode=mode,
        run_id=run_id,
        trade_date=trade_date,
        account_id=account_id,
        preset=preset,
    )
    fingerprint = _fingerprint_execution_run_plan(plan)
    plan_path = _resolve_run_plan_path(account_id, run_plan_file)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "plan_fingerprint": fingerprint,
        "plan": plan,
        "approval": {
            "token_env": LIVE_APPROVAL_TOKEN_ENV,
            "provided_token_sha256": hashlib.sha256(approval_token.encode("utf-8")).hexdigest(),
        },
    }
    if plan_path.exists():
        try:
            existing = json.loads(plan_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"run plan illisible: {plan_path} ({exc})") from exc
        existing_plan = existing.get("plan")
        existing_fingerprint = str(existing.get("plan_fingerprint") or "")
        if existing_plan != plan or existing_fingerprint != fingerprint:
            raise RuntimeError(
                f"run plan immutable mismatch pour {plan_path}; régénérer/vider le fichier avant relance"
            )
        return plan_path, fingerprint
    plan_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan_path, fingerprint


def _build_runtime_preset(
    mode: str,
    *,
    allow_outside_rth: bool = False,
    auto_rebalance: bool = False,
    account_type: str = "cash",
    pdt_rule: str = "off",
    swing_only: bool = True,
    submission_window: str | None = None,
    take_profit_pct: float | None = None,
    trailing_stop_pct: float | None = None,
    trailing_activation_trigger: str | None = None,
    trailing_activation_r_multiple: float | None = None,
    trailing_activation_profit_pct: float | None = None,
    protection_transition_timeout_seconds: int | None = None,
    protection_transition_poll_interval_seconds: float | None = None,
    entry_order_type: str | None = None,
    limit_price_buffer_bps: int | None = None,
    max_order_retries: int | None = None,
    poll_interval_seconds: float | None = None,
    fill_timeout_seconds: int | None = None,
    cancel_timeout_seconds: int | None = None,
    max_slippage_bps: int | None = None,
    execution_batch_size: int | None = None,
    inter_order_delay_ms: int | None = None,
) -> dict:
    preset = dict(PRESETS[mode])
    if allow_outside_rth:
        preset["allow_outside_rth"] = True
    if auto_rebalance:
        preset["auto_rebalance_on_reconcile"] = True
    if take_profit_pct is not None:
        preset["profit_taker_pct"] = take_profit_pct
    if trailing_stop_pct is not None:
        preset["trailing_stop_pct"] = trailing_stop_pct
    preset["account_type"] = account_type
    preset["pdt_rule"] = pdt_rule
    preset["swing_only"] = swing_only
    preset["submission_window"] = submission_window or preset.get("submission_window", "both")
    if trailing_activation_trigger is not None:
        preset["trailing_activation_trigger"] = trailing_activation_trigger
    if trailing_activation_r_multiple is not None:
        preset["trailing_activation_r_multiple"] = trailing_activation_r_multiple
    if trailing_activation_profit_pct is not None:
        preset["trailing_activation_profit_pct"] = trailing_activation_profit_pct
    if protection_transition_timeout_seconds is not None:
        preset["protection_transition_timeout_seconds"] = protection_transition_timeout_seconds
    if protection_transition_poll_interval_seconds is not None:
        preset["protection_transition_poll_interval_seconds"] = protection_transition_poll_interval_seconds
    if entry_order_type is not None:
        preset["entry_order_type"] = entry_order_type
    if limit_price_buffer_bps is not None:
        preset["limit_price_buffer_bps"] = limit_price_buffer_bps
    if max_order_retries is not None:
        preset["max_order_retries"] = max_order_retries
    if poll_interval_seconds is not None:
        preset["poll_interval_seconds"] = poll_interval_seconds
    if fill_timeout_seconds is not None:
        preset["fill_timeout_seconds"] = fill_timeout_seconds
    if cancel_timeout_seconds is not None:
        preset["cancel_timeout_seconds"] = cancel_timeout_seconds
    if max_slippage_bps is not None:
        preset["max_slippage_bps"] = max_slippage_bps
    if execution_batch_size is not None:
        preset["execution_batch_size"] = execution_batch_size
    if inter_order_delay_ms is not None:
        preset["inter_order_delay_ms"] = inter_order_delay_ms
    return preset

def _launch_post_watcher(
    *,
    summary: dict,
    preset: dict,
    account_id: str | None,
    broker_mode: str,
) -> int:
    """Démarre ``run_execution_protection_watch.py --mode once`` en arrière-plan.

    Sprint S2 / A-018. Ne bloque pas le shell : utilise ``subprocess.Popen``
    détaché. Retourne le PID du watcher.
    """
    script = PROJECT_ROOT / "run_execution_protection_watch.py"
    if not script.exists():
        raise FileNotFoundError(f"watcher introuvable : {script}")
    cmd: list[str] = [
        sys.executable,
        str(script),
        "--mode", "once",
        "--broker-mode", str(broker_mode or "paper"),
        "--profit-taker-pct", str(float(preset.get("profit_taker_pct", 0.08))),
        "--trailing-stop-pct", str(float(preset.get("trailing_stop_pct", 0.05))),
        "--trailing-activation-trigger", str(preset.get("trailing_activation_trigger", "multiple_r")),
        "--trailing-activation-r-multiple", str(float(preset.get("trailing_activation_r_multiple", 1.0))),
        "--trailing-activation-profit-pct", str(float(preset.get("trailing_activation_profit_pct", 0.03))),
    ]
    exec_run_id = str(summary.get("run_id") or "").strip()
    if exec_run_id:
        cmd += ["--exec-run-id", exec_run_id]
    if account_id:
        cmd += ["--account", str(account_id)]
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        creationflags=creationflags,
    )
    return int(proc.pid)


def run(
    mode: str,
    run_id: str | None,
    trade_date: str | None,
    debug: bool,
    allow_outside_rth: bool = False,
    auto_rebalance: bool = False,
    account_id: str | None = None,
    account_type: str = "cash",
    pdt_rule: str = "off",
    swing_only: bool = True,
    submission_window: str = "both",
    auto_watcher: bool = False,
    skip_preflight: bool = False,
    take_profit_pct: float | None = None,
    trailing_stop_pct: float | None = None,
    trailing_activation_trigger: str | None = None,
    trailing_activation_r_multiple: float | None = None,
    trailing_activation_profit_pct: float | None = None,
    protection_transition_timeout_seconds: int | None = None,
    protection_transition_poll_interval_seconds: float | None = None,
    entry_order_type: str | None = None,
    limit_price_buffer_bps: int | None = None,
    max_order_retries: int | None = None,
    poll_interval_seconds: float | None = None,
    fill_timeout_seconds: int | None = None,
    cancel_timeout_seconds: int | None = None,
    max_slippage_bps: int | None = None,
    execution_batch_size: int | None = None,
    inter_order_delay_ms: int | None = None,
    approval_token: str | None = None,
    run_plan_file: str | None = None,
) -> None:
    level = logging.DEBUG if debug else logging.INFO
    configure_root_logging(
        level=level,
        log_path="./log/alpha_trade.log",
        fmt="%(asctime)s  %(levelname)-8s  %(name)s -- %(message)s",
        datefmt="%H:%M:%S",
    )

    preset = _build_runtime_preset(
        mode,
        allow_outside_rth=allow_outside_rth,
        auto_rebalance=auto_rebalance,
        account_type=account_type,
        pdt_rule=pdt_rule,
        swing_only=swing_only,
        submission_window=submission_window,
        take_profit_pct=take_profit_pct,
        trailing_stop_pct=trailing_stop_pct,
        trailing_activation_trigger=trailing_activation_trigger,
        trailing_activation_r_multiple=trailing_activation_r_multiple,
        trailing_activation_profit_pct=trailing_activation_profit_pct,
        protection_transition_timeout_seconds=protection_transition_timeout_seconds,
        protection_transition_poll_interval_seconds=protection_transition_poll_interval_seconds,
        entry_order_type=entry_order_type,
        limit_price_buffer_bps=limit_price_buffer_bps,
        max_order_retries=max_order_retries,
        poll_interval_seconds=poll_interval_seconds,
        fill_timeout_seconds=fill_timeout_seconds,
        cancel_timeout_seconds=cancel_timeout_seconds,
        max_slippage_bps=max_slippage_bps,
        execution_batch_size=execution_batch_size,
        inter_order_delay_ms=inter_order_delay_ms,
    )

    live_run_plan_path: Path | None = None
    live_run_plan_fingerprint: str | None = None
    if mode == "live":
        try:
            _validate_live_secret_policy()
            validated_token = _validate_live_approval_token(approval_token)
            live_run_plan_path, live_run_plan_fingerprint = _ensure_immutable_run_plan(
                mode=mode,
                run_id=run_id,
                trade_date=trade_date,
                account_id=account_id,
                preset=preset,
                approval_token=validated_token,
                run_plan_file=run_plan_file,
            )
        except Exception as exc:
            print(
                f"{RED}{BOLD}[FATAL] garde-fous live refusent le lancement : {exc}{RESET}",
                file=sys.stderr,
            )
            sys.exit(2)

    mode_label = {
        "simulate": f"{CYAN}SIMULATION (dry-run){RESET}",
        "paper":    f"{YELLOW}PAPER TRADING{RESET}",
        "live":     f"{RED}{BOLD}LIVE TRADING [ARGENT REEL]{RESET}",
    }[mode]

    print(f"\n{BOLD}{SEP}{RESET}")
    print(f"{BOLD}  Recapitulatif{RESET}")
    print(f"{BOLD}{SEP}{RESET}")
    print(f"  Mode        : {mode_label}")
    print(f"  Run ID      : {run_id or '(dernier run disponible)'}")
    print(f"  Date        : {trade_date or '(auto)'}")
    print(f"  Bracket     : TP +{preset['profit_taker_pct']*100:.1f}%  /  TS -{preset['trailing_stop_pct']*100:.1f}%")
    print(f"  Profil      : {preset.get('execution_profile', 'custom')}  |  Fenetre={preset.get('submission_window', 'both')}")
    print(f"  Activation trailing : {preset['trailing_activation_trigger']}  |  timeout={preset['protection_transition_timeout_seconds']}s")
    print(f"  Max slippage: {preset['max_slippage_bps']} bps")
    print(f"  Compte      : {preset['account_type']}  |  PDT={preset['pdt_rule']}  |  swing_only={preset['swing_only']}")
    print(f"  Account ID  : {account_id or 'default'}")
    if mode == "live" and live_run_plan_path is not None and live_run_plan_fingerprint is not None:
        print(f"  Run plan    : {live_run_plan_path}")
        print(f"  Fingerprint : {live_run_plan_fingerprint}")
    if allow_outside_rth and not preset.get("dry_run"):
        print(f"  {YELLOW}[!] Execution hors horaires marche activee{RESET}")
    if auto_rebalance:
        print(f"  {YELLOW}[!] Reequilibrage automatique sur reconciliation ACTIVE{RESET}")
    print()

    try:
        from execution_engine.audit import build_execution_run_summary
        from execution_engine.broker_adapter import BrokerAdapter
        from execution_engine.config import ExecutionConfig, load_trailing_stop_config_from_yaml
        from execution_engine.db_io import ExecutionRepository
        from execution_engine.executor import ProductionExecutor
        from execution_engine.oco_manager import OcoManager
        from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
        from risk_management.config import RiskConfig
        from service.alpaca.trading_client import AlpacaTradingClient
    except ImportError as exc:
        print(f"{RED}Erreur d'import : {exc}{RESET}")
        print("-> Verifie que le projet est installe : pip install -e .")
        sys.exit(1)

    # Sprint S11 / S11.4 — preflight obligatoire en mode live.
    # Refus de boot si un check critique échoue, à moins que --skip-preflight
    # soit explicitement passé (réservé aux tests / dev local).
    if mode == "live" and not skip_preflight:
        try:
            from execution_engine.preflight import run_preflight
        except ImportError as exc:
            print(f"{RED}{BOLD}[FATAL] Impossible d'importer le module preflight : {exc}{RESET}", file=sys.stderr)
            sys.exit(1)
        try:
            preflight_report = run_preflight(
                account_id=account_id or "default",
                broker_mode="live",
            )
        except Exception as exc:  # pragma: no cover - filet
            print(
                f"{RED}{BOLD}[FATAL] preflight a levé une exception : {exc}{RESET}",
                file=sys.stderr,
            )
            sys.exit(1)
        # Persistance du rapport pour audit (best-effort).
        try:
            import json as _json
            reports_dir = PROJECT_ROOT / "artifacts" / "preflight_reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
            (reports_dir / f"preflight_{stamp}_{account_id or 'default'}.json").write_text(
                _json.dumps(preflight_report.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logging.getLogger(__name__).debug("Persistance preflight_reports indisponible.", exc_info=True)
        if not preflight_report.passed:
            print(f"\n{RED}{BOLD}[FATAL] Preflight live a échoué — boot refusé.{RESET}", file=sys.stderr)
            for check in preflight_report.checks:
                if check.status == "fail":
                    print(f"  {RED}[FAIL]{RESET} {check.name}: {check.message}", file=sys.stderr)
            print(
                f"\n{YELLOW}    -> corriger les checks ci-dessus puis relancer, "
                f"ou lancer manuellement : python -m execution_engine.preflight "
                f"--account {account_id or 'default'} --broker-mode live{RESET}",
                file=sys.stderr,
            )
            sys.exit(2)
        print(f"{GREEN}[OK] Preflight live: tous les checks critiques sont verts.{RESET}\n")
    elif mode == "simulate" and not skip_preflight:
        try:
            from execution_engine.preflight import run_preflight
        except ImportError as exc:
            print(
                f"{YELLOW}{BOLD}[WARN] Module preflight indisponible en simulate : {exc}{RESET}",
                file=sys.stderr,
            )
        else:
            try:
                preflight_report = run_preflight(
                    account_id=account_id or "default",
                    broker_mode="paper",
                )
            except Exception as exc:  # pragma: no cover - filet
                print(
                    f"{YELLOW}{BOLD}[WARN] preflight simulate a levé une exception : {exc}{RESET}",
                    file=sys.stderr,
                )
            else:
                if not preflight_report.passed:
                    print(
                        f"{YELLOW}{BOLD}[WARN] Preflight simulate en mode dégradé — boot maintenu malgré des checks KO.{RESET}",
                        file=sys.stderr,
                    )
                    for check in preflight_report.checks:
                        if check.status == "fail":
                            print(f"  {YELLOW}[WARN]{RESET} {check.name}: {check.message}", file=sys.stderr)
                else:
                    print(f"{GREEN}[OK] Preflight simulate: aucun check critique en échec.{RESET}\n")
    elif mode == "live" and skip_preflight:
        print(
            f"{YELLOW}{BOLD}[!!] --skip-preflight actif : les checks live sont contournés. "
            f"À utiliser exclusivement en dev/test.{RESET}\n",
            file=sys.stderr,
        )

    config   = ExecutionConfig(
        **preset,
        account_id=account_id,
        trailing_stop=load_trailing_stop_config_from_yaml(),
    )
    repo     = ExecutionRepository()
    client   = AlpacaTradingClient(broker_mode=config.broker_mode, account_id=account_id)
    broker   = BrokerAdapter(client, config)
    oco      = OcoManager(broker, repo)
    # Construction du circuit breaker.
    # Phase 1 sécurité : en mode paper / live, l'equity DOIT venir du broker.
    # Tout fallback à 100 000 $ silencieux est désormais fatal pour éviter
    # un sizing massivement faux (audit_global.md, audit_execution.md).
    equity = 100_000.0
    if not config.dry_run:
        try:
            equity = broker.get_account_equity()
        except Exception as exc:
            print(
                f"{RED}{BOLD}[FATAL] Impossible de récupérer l'equity broker "
                f"en mode {mode}: {exc}{RESET}\n"
                f"{RED}    -> abandon du run pour éviter un sizing fallback à 100k$.{RESET}",
                file=sys.stderr,
            )
            raise RuntimeError(
                f"broker.get_account_equity() a échoué en mode {mode}: {exc}"
            ) from exc
        if equity is None or equity <= 0:
            raise RuntimeError(
                f"Equity broker invalide en mode {mode}: {equity!r}. "
                "Abandon du run."
            )
    pnl = PnLSnapshot(portfolio_current_value=equity, portfolio_high_watermark=equity)
    cb = CircuitBreaker(RiskConfig(account_equity=max(equity, 1.0)), pnl)
    executor = ProductionExecutor(
        config,
        repo,
        broker,
        oco,
        circuit_breaker=cb,
        progress_callback=lambda summary: emit_run_summary(summary),
    )

    trade_date_val: date | None = None
    if trade_date:
        try:
            trade_date_val = date.fromisoformat(trade_date)
        except ValueError:
            print(f"{RED}Format de date invalide : {trade_date}. Utilise YYYY-MM-DD.{RESET}")
            sys.exit(1)

    # ----- Market-Aware regime pre-flight (Axe C plan/prompt/parttern/plan.md) ---------
    # Calcul UNE FOIS par cycle d'un ``MarketRegimeSnapshot`` puis :
    #  - rendu d'un résumé console + log ;
    #  - persistance JSON best-effort dans ``artifacts/market_regime/`` ;
    #  - propagation du mode dérivé (``close_only``/``cash_only``/...) dans
    #    ``ExecutionConfig.entry_mode`` afin que l'executor bloque les
    #    nouvelles entrées si le régime l'exige.
    # Tout échec reste non-bloquant (fallback neutre).
    try:
        from common.config_loader import load_config as _load_config_yaml
        from execution_engine.market_regime_preflight import (
            derive_entry_mode as _derive_entry_mode,
        )
        from execution_engine.market_regime_preflight import (
            emit_preflight as _emit_preflight,
        )
        from service.market import (
            DbSentimentScoreProvider as _DbSentimentScoreProvider,
        )
        from service.market import (
            build_default_macro_provider as _build_macro_provider,
        )
        from service.market import (
            build_snapshot as _build_regime_snapshot,
        )
        from service.market import (
            parse_market_regimes as _parse_market_regimes,
        )

        _yaml_cfg = _load_config_yaml()
        _mr_cfg = _parse_market_regimes(_yaml_cfg.get("market_regimes"))
        _macro_provider = _build_macro_provider(_yaml_cfg)
        _trade_date_for_regime = trade_date_val or date.today()
        _sentiment_provider = _DbSentimentScoreProvider(_trade_date_for_regime)
        _snapshot = _build_regime_snapshot(
            _trade_date_for_regime,
            config=_mr_cfg,
            equity=float(equity) if equity else None,
            execution_context="live",
            macro_provider=_macro_provider,
            sentiment_score_provider=_sentiment_provider,
        )
        _snap_dict = _snapshot.to_dict() if hasattr(_snapshot, "to_dict") else {
            "trade_date": str(_trade_date_for_regime),
            "mode": getattr(_snapshot, "mode", "normal"),
            "risk_multiplier": getattr(_snapshot, "risk_multiplier", 1.0),
            "effective_max_positions": getattr(_snapshot, "effective_max_positions", None),
            "enforced_min_notional": getattr(_snapshot, "enforced_min_notional", None),
            "allowed_slots": getattr(_snapshot, "allowed_slots", None),
            "allow_new_entries": getattr(_snapshot, "allow_new_entries", True),
            "active_patterns": getattr(_snapshot, "active_patterns", []),
            "blocked_sectors": getattr(_snapshot, "blocked_sectors", []),
            "earnings_shielded_symbols": getattr(_snapshot, "earnings_shielded_symbols", {}),
            "buyback_blackout_symbols": getattr(_snapshot, "buyback_blackout_symbols", {}),
            "macro": getattr(_snapshot, "macro", {}),
            "reasons": getattr(_snapshot, "reasons", []),
        }
        if _mr_cfg.enabled and _mr_cfg.sentinel.preflight_summary:
            print(_emit_preflight(_snap_dict))
        # Propagation du mode régime → ExecutionConfig.entry_mode
        # (ExecutionConfig est frozen → on reconstruit via dataclasses.replace)
        _new_mode = cast(
            Literal["normal", "close_only", "cash_only", "capital_preservation"],
            _derive_entry_mode(_snap_dict),
        )
        if _new_mode != config.entry_mode:
            from dataclasses import replace as _dc_replace
            _raw_reasons = _snap_dict.get("reasons")
            _reasons_list = list(_raw_reasons) if isinstance(_raw_reasons, Iterable) and not isinstance(_raw_reasons, (str, bytes)) else []
            _reasons_str = ", ".join(str(r) for r in _reasons_list) if _reasons_list else "régime"
            print(
                f"{YELLOW}[market_regime] entry_mode={config.entry_mode!r} → {_new_mode!r} "
                f"(motif: {_reasons_str}){RESET}"
            )
            config = _dc_replace(config, entry_mode=_new_mode)
            # Reconstruire executor avec la nouvelle config (frozen).
            broker = BrokerAdapter(client, config)
            oco = OcoManager(broker, repo)
            executor = ProductionExecutor(
                config,
                repo,
                broker,
                oco,
                circuit_breaker=cb,
                progress_callback=lambda summary: emit_run_summary(summary),
            )
        # Persistance best-effort
        try:
            import json as _json_regime
            _regime_dir = PROJECT_ROOT / "artifacts" / "market_regime"
            _regime_dir.mkdir(parents=True, exist_ok=True)
            _stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
            (_regime_dir / f"snapshot_{_stamp}_{config.resolved_account_id or 'default'}.json").write_text(
                _json_regime.dumps(_snap_dict, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception:
            logging.getLogger(__name__).debug("Persistance market_regime indisponible.", exc_info=True)
    except Exception:
        logging.getLogger(__name__).warning(
            "market_regime preflight indisponible — fallback neutre.", exc_info=True
        )

    print(f"{BOLD}Execution en cours...{RESET}\n")
    t0 = datetime.now()
    metrics = executor.execute_run(risk_run_id=run_id, trade_date=trade_date_val)
    finished_at = datetime.now()
    elapsed = (finished_at - t0).total_seconds()

    summary = build_execution_run_summary(
        metrics,
        started_at=t0,
        finished_at=finished_at,
        execution_mode=mode,
        broker_mode=config.broker_mode,
        account_id=config.resolved_account_id,
        account_type=config.account_type,
        effective_pdt_rule=config.effective_pdt_rule,
        swing_only=config.swing_only,
        dry_run=config.dry_run,
        allow_outside_rth=config.allow_outside_rth,
    )
    if mode == "live" and live_run_plan_path is not None and live_run_plan_fingerprint is not None:
        summary["approval"] = {
            "token_env": LIVE_APPROVAL_TOKEN_ENV,
            "run_plan_file": str(live_run_plan_path),
            "run_plan_fingerprint": live_run_plan_fingerprint,
        }
    try:
        persist_run_business_summary(
            summary=summary,
            step_key="execution",
            run_kind="step",
            status=str(summary.get("status", "") or "") or None,
            summary_run_id=str(summary.get("run_id", "") or "") or None,
            entity_run_id=str(summary.get("run_id", "") or "") or None,
            parent_summary_run_id=run_id,
            account_id=config.resolved_account_id,
            trade_date=summary.get("trade_date"),
            started_at=summary.get("started_at"),
            finished_at=summary.get("finished_at"),
        )
    except Exception:
        logging.getLogger(__name__).debug("Persistance run_business_summaries indisponible pour execution.", exc_info=True)
    emit_run_summary(summary)

    # Sprint S2 / A-018 — option ``--auto-watcher`` : lance le watcher de
    # protection en post-run (mode once) sans bloquer le shell.
    if auto_watcher:
        try:
            watcher_pid = _launch_post_watcher(
                summary=summary,
                preset=preset,
                account_id=config.resolved_account_id,
                broker_mode=config.broker_mode,
            )
            print(f"{GREEN}[OK] watcher post-run lance (pid={watcher_pid}).{RESET}")
        except Exception as exc:
            print(
                f"{YELLOW}[!] echec lancement watcher post-run : {exc}{RESET}",
                file=sys.stderr,
            )

    print(f"\n{BOLD}{SEP}{RESET}")
    print(f"{BOLD}  Resultats{RESET}")
    print(f"{BOLD}{SEP}{RESET}")
    print(f"  Duree       : {elapsed:.1f}s")
    print(f"  Cibles      : {metrics.get('targets', 0)}")
    print(f"  Soumis      : {GREEN}{metrics.get('submitted', 0)}{RESET}")
    print(f"  Remplis     : {GREEN}{metrics.get('filled', 0)}{RESET}")
    failed = metrics.get('failed', 0)
    print(f"  Echecs      : {(RED if failed else '')}{failed}{RESET}")
    print(f"  Ignores     : {metrics.get('skipped', 0)}")
    constraint_blocked = int(metrics.get("constraint_blocked", 0) or 0)
    if constraint_blocked:
        print(f"  Bloques     : {YELLOW}{constraint_blocked} contrainte(s) compte/capital{RESET}")
    rebal_sub = metrics.get("rebalance_submitted", 0)
    rebal_fail = metrics.get("rebalance_failed", 0)
    if rebal_sub or rebal_fail:
        print(f"  Rebalance   : {GREEN}{rebal_sub} soumis{RESET}  /  {(RED if rebal_fail else '')}{rebal_fail} echecs{RESET}")
    print()

    targets_n  = metrics.get("targets", 0)
    submitted_n = metrics.get("submitted", 0)

    if failed > 0:
        print(f"{YELLOW}[!] Certains ordres ont echoue. Consulte la table execution_events.{RESET}")
    elif targets_n == 0:
        print(f"{YELLOW}[!] Aucune cible trouvee. Verifie que portfolio_targets est alimente.{RESET}")
    elif targets_n > 0 and submitted_n == 0 and not PRESETS[mode]["dry_run"]:
        print(f"{YELLOW}[!] {targets_n} cible(s) chargee(s) mais AUCUN ordre soumis.{RESET}")
        if constraint_blocked > 0:
            print(
                f"{YELLOW}    Cause probable : contraintes de compte / capital insuffisant "
                f"({constraint_blocked} ordre(s) bloques).{RESET}"
            )
            print(
                f"{YELLOW}    Verifie l'equity utilisee a l'etape 11, le type de compte "
                f"(cash vs margin) et les events `INTENT_SKIPPED_ACCOUNT_CONSTRAINT`.{RESET}"
            )
        else:
            print(f"{YELLOW}    Cause probable : marche ferme (week-end ou hors RTH).{RESET}")
            print(f"{YELLOW}    Prochaine ouverture : lundi 09:30 ET.{RESET}")
            print(f"{YELLOW}    Pour forcer la soumission : coche 'Execution hors RTH' dans l'IHM ou ajoute --allow-outside-rth{RESET}")
    elif submitted_n > 0 and metrics.get("filled", 0) == 0 and not PRESETS[mode]["dry_run"]:
        print(f"{GREEN}[OK] {submitted_n} ordre(s) soumis chez Alpaca.{RESET}")
        print(f"{YELLOW}    Marche actuellement ferme -> les ordres seront remplis a l'ouverture.{RESET}")
        print(f"{YELLOW}    Les ordres 'day' expirent si non remplis en fin de prochaine seance.{RESET}")
    else:
        print(f"{GREEN}[OK] Run termine avec succes.{RESET}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Alpha Trade -- Production Executor (point d'entree simplifie)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python run_execution.py                           # menu interactif
  python run_execution.py simulate                  # simulation du dernier run dispo
  python run_execution.py simulate --debug          # simulation avec logs DEBUG
  python run_execution.py paper --date 2026-04-18   # paper trading par date
  python run_execution.py paper  --run-id abc123    # paper trading par risk_run_id
  python run_execution.py live   --run-id abc123    # live trading (argent reel !)
  python run_execution.py check                     # verifie les variables d'env
        """,
    )
    p.add_argument(
        "mode",
        nargs="?",
        choices=["simulate", "paper", "live", "check"],
        help="Mode d'execution (defaut : menu interactif)",
    )
    p.add_argument("--date",              dest="trade_date",      metavar="YYYY-MM-DD", help="Date du run (ex: 2026-04-18)")
    p.add_argument("--run-id",            dest="run_id",          metavar="RUN_ID",     help="risk_run_id precis")
    p.add_argument("--debug",             action="store_true",                          help="Active les logs DEBUG")
    p.add_argument("--allow-outside-rth",      dest="allow_outside_rth",  action="store_true", help="Execute meme si marche ferme (week-end / hors RTH)")
    p.add_argument("--auto-rebalance",          dest="auto_rebalance",     action="store_true", help="Vend/achete automatiquement les ecarts detectes en reconciliation")
    p.add_argument("--account",                 dest="account_id",         metavar="ACCOUNT_ID", help="ID du compte Alpaca multi-comptes (defaut: premier compte)")
    p.add_argument("--account-type",            dest="account_type",       choices=["margin", "cash"], default="cash", help="Type de compte simule ou utilise pour appliquer les contraintes de capital")
    p.add_argument("--pdt-rule",                dest="pdt_rule",           choices=["auto", "off"], default="off", help="Application de la regle PDT sur compte margin")
    p.add_argument("--swing-only",              dest="swing_only",         action=argparse.BooleanOptionalAction, default=True, help="Interdit les sorties le jour meme en execution")
    p.add_argument("--submission-window",       dest="submission_window",  choices=["post_close", "pre_open", "both"], default=None, help="Fenetre nominale de soumission hors seance")
    p.add_argument("--profit-taker-pct",        dest="profit_taker_pct", type=float, default=None, help="Take-profit cible (fraction: 0.08 = +8%%)")
    p.add_argument("--trailing-stop-pct",       dest="trailing_stop_pct", type=float, default=None, help="Trailing stop broker-side (fraction: 0.05 = 5%%)")
    p.add_argument("--trailing-activation-trigger", dest="trailing_activation_trigger", choices=["multiple_r", "profit_pct"], default=None, help="Trigger métier pour passer du stop initial au trailing dynamique")
    p.add_argument("--trailing-activation-r-multiple", dest="trailing_activation_r_multiple", type=float, default=None, help="Multiple de R pour activer le trailing dynamique")
    p.add_argument("--trailing-activation-profit-pct", dest="trailing_activation_profit_pct", type=float, default=None, help="Profit pct pour activer le trailing dynamique")
    p.add_argument("--protection-transition-timeout-seconds", dest="protection_transition_timeout_seconds", type=int, default=None, help="Fenêtre de surveillance du trigger de trailing dynamique")
    p.add_argument("--protection-transition-poll-interval-seconds", dest="protection_transition_poll_interval_seconds", type=float, default=None, help="Intervalle de polling du trigger de trailing dynamique")
    p.add_argument(
        "--auto-watcher",
        dest="auto_watcher",
        action="store_true",
        help="Lance run_execution_protection_watch.py --mode once en post-run (Sprint S2 / A-018).",
    )
    p.add_argument(
        "--skip-preflight",
        dest="skip_preflight",
        action="store_true",
        help="Sprint S11 / S11.4 — DANGER: contourne les checks preflight live. Réservé dev/test.",
    )
    p.add_argument(
        "--disable-sentiment",
        dest="disable_sentiment",
        action="store_true",
        help="Sprint S8 — désactive la fusion sentiment (positionne ALPHA_TRADE_DISABLE_SENTIMENT=1).",
    )
    p.add_argument(
        "--disable-ml",
        dest="disable_ml",
        action="store_true",
        help="Sprint S8 — désactive la consommation des prédictions ML (positionne ALPHA_TRADE_DISABLE_ML=1).",
    )
    p.add_argument(
        "--approval-token",
        dest="approval_token",
        default=None,
        help=(
            "S8 live only — token d'approbation opérateur. Obligatoire en mode live et comparé à "
            f"{LIVE_APPROVAL_TOKEN_ENV}."
        ),
    )
    p.add_argument(
        "--run-plan-file",
        dest="run_plan_file",
        default=None,
        help=(
            "S8 live only — chemin du run plan immuable. S'il existe déjà, son contenu doit "
            "correspondre exactement aux paramètres du run."
        ),
    )
    return p


def _apply_feature_flags(args) -> None:
    """Sprint S8 — propage --disable-sentiment / --disable-ml dans os.environ."""
    from core.feature_flags import FeatureFlags
    flags = FeatureFlags(
        disable_sentiment=bool(getattr(args, "disable_sentiment", False)),
        disable_ml=bool(getattr(args, "disable_ml", False)),
    )
    flags.export_env()
    if flags.disable_sentiment or flags.disable_ml:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "[feature_flags] disable_sentiment=%s disable_ml=%s (Sprint S8)",
            flags.disable_sentiment, flags.disable_ml,
        )


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    _apply_feature_flags(args)

    if args.mode == "check":
        print(BANNER)
        ok = print_env_status()
        sys.exit(0 if ok else 1)

    if args.mode is None:
        (
            mode,
            run_id,
            trade_date,
            debug,
            allow_outside_rth,
            auto_rebalance,
            account_id,
            account_type,
            pdt_rule,
            swing_only,
            submission_window,
            approval_token,
            run_plan_file,
        ) = interactive_menu()
        auto_watcher = False
        skip_preflight = False
        take_profit_pct = None
        trailing_stop_pct = None
        trailing_activation_trigger = None
        trailing_activation_r_multiple = None
        trailing_activation_profit_pct = None
        protection_transition_timeout_seconds = None
        protection_transition_poll_interval_seconds = None
    else:
        mode              = args.mode
        run_id            = args.run_id
        trade_date        = args.trade_date
        debug             = args.debug
        allow_outside_rth = args.allow_outside_rth
        auto_rebalance    = args.auto_rebalance
        account_id        = args.account_id
        account_type      = args.account_type
        pdt_rule          = args.pdt_rule
        swing_only        = args.swing_only
        submission_window = args.submission_window or PRESETS[mode].get("submission_window", "both")
        auto_watcher      = bool(getattr(args, "auto_watcher", False))
        skip_preflight    = bool(getattr(args, "skip_preflight", False))
        take_profit_pct   = args.profit_taker_pct
        trailing_stop_pct = args.trailing_stop_pct
        trailing_activation_trigger = args.trailing_activation_trigger
        trailing_activation_r_multiple = args.trailing_activation_r_multiple
        trailing_activation_profit_pct = args.trailing_activation_profit_pct
        protection_transition_timeout_seconds = args.protection_transition_timeout_seconds
        protection_transition_poll_interval_seconds = args.protection_transition_poll_interval_seconds
        approval_token = args.approval_token
        run_plan_file = args.run_plan_file

    abort_missing_env(account_id=account_id, mode=mode)
    run(
        mode,
        run_id,
        trade_date,
        debug,
        allow_outside_rth,
        auto_rebalance,
        account_id,
        account_type,
        pdt_rule,
        swing_only,
        submission_window,
        auto_watcher=auto_watcher,
        skip_preflight=skip_preflight,
        take_profit_pct=take_profit_pct,
        trailing_stop_pct=trailing_stop_pct,
        trailing_activation_trigger=trailing_activation_trigger,
        trailing_activation_r_multiple=trailing_activation_r_multiple,
        trailing_activation_profit_pct=trailing_activation_profit_pct,
        protection_transition_timeout_seconds=protection_transition_timeout_seconds,
        protection_transition_poll_interval_seconds=protection_transition_poll_interval_seconds,
        approval_token=approval_token,
        run_plan_file=run_plan_file,
    )


if __name__ == "__main__":
    main()



















