#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
import logging
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

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

def interactive_menu() -> tuple[str, str | None, str | None, bool, bool, bool, str | None, str, str, bool, str]:
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

    return mode, run_id, trade_date, debug, outside_rth, rebalance, account_id, account_type, pdt_rule, swing_only, submission_window


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
    account_type: str = "margin",
    pdt_rule: str = "auto",
    swing_only: bool = False,
    submission_window: str = "both",
    auto_watcher: bool = False,
) -> None:
    level = logging.DEBUG if debug else logging.INFO
    configure_root_logging(
        level=level,
        log_path="./log/alpha_trade.log",
        fmt="%(asctime)s  %(levelname)-8s  %(name)s -- %(message)s",
        datefmt="%H:%M:%S",
    )

    # Overrider allow_outside_rth si demande explicitement
    preset = dict(PRESETS[mode])  # copie mutable
    if allow_outside_rth:
        preset["allow_outside_rth"] = True
    if auto_rebalance:
        preset["auto_rebalance_on_reconcile"] = True
    preset["account_type"] = account_type
    preset["pdt_rule"] = pdt_rule
    preset["swing_only"] = swing_only
    preset["submission_window"] = submission_window

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
    print(f"  Bracket     : TP +{preset['profit_taker_pct']*100:.0f}%  /  TS -{preset['trailing_stop_pct']*100:.0f}%")
    print(f"  Profil      : {preset.get('execution_profile', 'custom')}  |  Fenetre={preset.get('submission_window', 'both')}")
    print(f"  Activation trailing : {preset['trailing_activation_trigger']}  |  timeout={preset['protection_transition_timeout_seconds']}s")
    print(f"  Max slippage: {preset['max_slippage_bps']} bps")
    print(f"  Compte      : {preset['account_type']}  |  PDT={preset['pdt_rule']}  |  swing_only={preset['swing_only']}")
    print(f"  Account ID  : {account_id or 'default'}")
    if allow_outside_rth and not preset.get("dry_run"):
        print(f"  {YELLOW}[!] Execution hors horaires marche activee{RESET}")
    if auto_rebalance:
        print(f"  {YELLOW}[!] Reequilibrage automatique sur reconciliation ACTIVE{RESET}")
    print()

    try:
        from execution_engine.audit import build_execution_run_summary
        from execution_engine.broker_adapter import BrokerAdapter
        from execution_engine.config import ExecutionConfig
        from execution_engine.db_io import ExecutionRepository
        from execution_engine.executor import ProductionExecutor
        from execution_engine.oco_manager import OcoManager
        from service.alpaca.trading_client import AlpacaTradingClient
        # Ajout pour circuit breaker
        from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
        from risk_management.config import RiskConfig
    except ImportError as exc:
        print(f"{RED}Erreur d'import : {exc}{RESET}")
        print("-> Verifie que le projet est installe : pip install -e .")
        sys.exit(1)

    config   = ExecutionConfig(**preset, account_id=account_id)
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
    return p


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    if args.mode == "check":
        print(BANNER)
        ok = print_env_status()
        sys.exit(0 if ok else 1)

    if args.mode is None:
        mode, run_id, trade_date, debug, allow_outside_rth, auto_rebalance, account_id, account_type, pdt_rule, swing_only, submission_window = interactive_menu()
        auto_watcher = False
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
        if args.trailing_activation_trigger is not None:
            PRESETS[mode]["trailing_activation_trigger"] = args.trailing_activation_trigger
        if args.trailing_activation_r_multiple is not None:
            PRESETS[mode]["trailing_activation_r_multiple"] = args.trailing_activation_r_multiple
        if args.trailing_activation_profit_pct is not None:
            PRESETS[mode]["trailing_activation_profit_pct"] = args.trailing_activation_profit_pct
        if args.protection_transition_timeout_seconds is not None:
            PRESETS[mode]["protection_transition_timeout_seconds"] = args.protection_transition_timeout_seconds
        if args.protection_transition_poll_interval_seconds is not None:
            PRESETS[mode]["protection_transition_poll_interval_seconds"] = args.protection_transition_poll_interval_seconds

    abort_missing_env(account_id=account_id, mode=mode)
    run(mode, run_id, trade_date, debug, allow_outside_rth, auto_rebalance, account_id, account_type, pdt_rule, swing_only, submission_window, auto_watcher=auto_watcher)


if __name__ == "__main__":
    main()



















