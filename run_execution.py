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
import sys
from datetime import date, datetime

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

def check_env() -> list[str]:
    required = ["LOGIN_DB", "PASSWORD_DB", "ALPACA_API_KEY", "ALPACA_SECRET_KEY"]
    return [v for v in required if not os.getenv(v)]


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


def abort_missing_env() -> None:
    missing = check_env()
    if missing:
        print(f"\n{RED}{BOLD}Erreur : variables manquantes : {', '.join(missing)}{RESET}")
        print("\nDefinis-les dans PowerShell avec :")
        for v in missing:
            print(f'  $env:{v} = "ta_valeur"')
        sys.exit(1)


# ---------------------------------------------------------------------------
# Menu interactif
# ---------------------------------------------------------------------------

def interactive_menu() -> tuple[str, str | None, str | None, bool, bool]:
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
        confirm = input(
            f"\n{RED}{BOLD}[ATTENTION] Confirmes-tu le lancement en LIVE (argent reel) ? [oui/non] : {RESET}"
        ).strip().lower()
        if confirm != "oui":
            print("Annule.")
            sys.exit(0)

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

    return mode, run_id, trade_date, debug, outside_rth


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
        "max_slippage_bps": 30,
        "max_order_retries": 3,
        "poll_interval_seconds": 2.0,
        "fill_timeout_seconds": 120,
        "allow_outside_rth": True,   # dry-run : ignore les horaires
        "inter_order_delay_ms": 0,   # dry-run : pas de throttle
    },
    "paper": {
        "broker_mode": "paper",
        "dry_run": False,
        "entry_order_type": "market",
        "profit_taker_pct": 0.08,
        "trailing_stop_pct": 0.05,
        "max_slippage_bps": 30,
        "max_order_retries": 3,
        "poll_interval_seconds": 2.0,
        "fill_timeout_seconds": 120,
        "allow_outside_rth": False,
        "inter_order_delay_ms": 350,
    },
    "live": {
        "broker_mode": "live",
        "dry_run": False,
        "entry_order_type": "market",
        "profit_taker_pct": 0.08,
        "trailing_stop_pct": 0.05,
        "max_slippage_bps": 20,      # plus strict en live
        "max_order_retries": 3,
        "poll_interval_seconds": 1.5,
        "fill_timeout_seconds": 180,
        "allow_outside_rth": False,
        "inter_order_delay_ms": 350,
    },
}


# ---------------------------------------------------------------------------
# Lancement
# ---------------------------------------------------------------------------

def run(mode: str, run_id: str | None, trade_date: str | None, debug: bool, allow_outside_rth: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s -- %(message)s",
        datefmt="%H:%M:%S",
    )

    # Overrider allow_outside_rth si demande explicitement
    preset = dict(PRESETS[mode])  # copie mutable
    if allow_outside_rth:
        preset["allow_outside_rth"] = True

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
    print(f"  Max slippage: {preset['max_slippage_bps']} bps")
    if allow_outside_rth and not preset.get("dry_run"):
        print(f"  {YELLOW}[!] Execution hors horaires marche activee{RESET}")
    print()

    try:
        from execution_engine.broker_adapter import BrokerAdapter
        from execution_engine.config import ExecutionConfig
        from execution_engine.db_io import ExecutionRepository
        from execution_engine.executor import ProductionExecutor
        from execution_engine.oco_manager import OcoManager
        from service.alpaca.trading_client import AlpacaTradingClient
    except ImportError as exc:
        print(f"{RED}Erreur d'import : {exc}{RESET}")
        print("-> Verifie que le projet est installe : pip install -e .")
        sys.exit(1)

    config   = ExecutionConfig(**preset)
    repo     = ExecutionRepository()
    client   = AlpacaTradingClient(broker_mode=config.broker_mode)
    broker   = BrokerAdapter(client, config)
    oco      = OcoManager(broker, repo)
    executor = ProductionExecutor(config, repo, broker, oco)

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
    elapsed = (datetime.now() - t0).total_seconds()

    print(f"\n{BOLD}{SEP}{RESET}")
    print(f"{BOLD}  Resultats{RESET}")
    print(f"{BOLD}{SEP}{RESET}")
    print(f"  Duree       : {elapsed:.1f}s")
    print(f"  Cibles      : {metrics.get('targets', 0)}")
    print(f"  Soumis      : {GREEN}{metrics.get('submitted', 0)}{RESET}")
    print(f"  Remplis     : {GREEN}{metrics.get('filled', 0)}{RESET}")
    failed = metrics.get('failed', 0)
    print(f"  Echecs      : {(RED if failed else '')}{failed}{RESET}")
    print(f"  Doublons    : {metrics.get('skipped', 0)}")
    print()

    targets_n  = metrics.get("targets", 0)
    submitted_n = metrics.get("submitted", 0)

    if failed > 0:
        print(f"{YELLOW}[!] Certains ordres ont echoue. Consulte la table execution_events.{RESET}")
    elif targets_n == 0:
        print(f"{YELLOW}[!] Aucune cible trouvee. Verifie que portfolio_targets est alimente.{RESET}")
    elif targets_n > 0 and submitted_n == 0 and not PRESETS[mode]["dry_run"]:
        print(f"{YELLOW}[!] {targets_n} cible(s) chargee(s) mais AUCUN ordre soumis.{RESET}")
        print(f"{YELLOW}    Cause probable : marche ferme (week-end ou hors RTH).{RESET}")
        print(f"{YELLOW}    Prochaine ouverture : lundi 09:30 ET.{RESET}")
        print(f"{YELLOW}    Pour tester hors horaires : utilise 'simulate' ou ajoute --allow-outside-rth{RESET}")
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
    p.add_argument("--allow-outside-rth", dest="allow_outside_rth", action="store_true", help="Execute meme si marche ferme (week-end / hors RTH)")
    return p


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    if args.mode == "check":
        print(BANNER)
        ok = print_env_status()
        sys.exit(0 if ok else 1)

    if args.mode is None:
        mode, run_id, trade_date, debug, allow_outside_rth = interactive_menu()
    else:
        mode             = args.mode
        run_id           = args.run_id
        trade_date       = args.trade_date
        debug            = args.debug
        allow_outside_rth = args.allow_outside_rth

    abort_missing_env()
    run(mode, run_id, trade_date, debug, allow_outside_rth)


if __name__ == "__main__":
    main()









