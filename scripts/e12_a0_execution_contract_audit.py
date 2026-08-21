"""E12-A0 — Execution Contract Audit : verrouillage du lifecycle.

CONTEXTE (spec user 2026-08-20) : avant toute campagne E12 exits, verifier que le
lifecycle reellement execute par E6->E11 est identique (ou nomme distinct) au
lifecycle canonique production (B25_POST_TP_FIX_P14_M8). Deux incoherences
signalees par l'utilisateur :
  1. E11 a 229 exits time_stop, alors que la production P14 n'en execute aucun
     (time_stop neutralise quand un ordre TP/trailing travaille).
  2. E11/E6 utilisent un stop initial 3.5xATR (et TP min(4xATR,13%), trailing 7%),
     alors que la baseline canonique post-fix utilise 2.5xATR / min(3xATR,7%).

METHODE (aucun sweep) :
  - Instancier le config recherche (BacktestConfig de e11) et imprimer le contrat
    RESOLU (stop/TP/trailing/time_stop/intrabar/entry/couts).
  - Charger le contrat canonique production (params rebench post-fix + config.yaml).
  - Comparer bit-for-bit, lister les divergences, nommer explicitement le lifecycle.
  - Compter les exits time_stop dans le run E11 vs les runs production-parity.
  - Verdict : le lifecycle E6->E11 est un lifecycle de RECHERCHE, distinct du
    canonique ; les conclusions E6->E11 en sont conditionnelles.

Sortie : print (ASCII only).
"""
from __future__ import annotations

import sys
sys.path.insert(0, "f:/projets")

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.e11_extreme_long_payoff_diag import make_engine, SEED_REP

# Runs production-parity canoniques (post-fix TP) + p23_m8
CANON_RUNS = [
    Path("artifacts/backtesting/cmp_b25_h20_2026_postfix_tp_m8"),
    Path("artifacts/backtesting/cmp_b25_h20_2026_prodparity_p23_m8"),
    Path("artifacts/backtesting/cmp_b25_h20_2025_prodparity_p23_m8"),
]
E11_LOG = Path("log/e11_extreme_long_payoff_diag.log")


def _canonical_contract() -> dict:
    """Contrat canonique B25_POST_TP_FIX_P14_M8 (rebench post-fix, verifie memoire + runs)."""
    return {
        "initial_stop_atr_multiple": 2.5,          # --atr-risk-stop-multiple 2.5
        "tp_formula": "min(3xATR, 7%)",            # --tp-atr-multiple 3.0 --tp-max-pct 0.07
        "trailing_activation": "J+1 (0R) via watcher",
        "trailing_long_pct": "risk-based 2.5xATR (derive du stop initial)",
        "time_stop_enabled": False,                # 0 fills en exit_lifecycle_replay
        "time_stop_max_business_days": 20,         # config presente mais jamais executee
        "min_tp_progress_ratio": 0.5,
        "near_zero_return_pct": 0.005,
        "intrabar_priority": "conservative",
        "max_entry_gap_pct": 0.03,                 # gap filter ON (skip gap > 3%)
        "entry_timing": "next_open (marché, entry_price_source=next_session_open)",
        "max_positions": 8,
        "costs": "canonical 16bps RT (use_canonical_costs)",
    }


def _research_contract() -> dict:
    """Contrat recherche E6->E11 RESOLU depuis le BacktestConfig reelement execute."""
    cfg = make_engine().config
    m = cfg.microstructure
    return {
        "initial_stop_atr_multiple": cfg.atr_risk_stop_multiple,
        "tp_formula": f"min({cfg.tp_atr_multiple}xATR, {100*cfg.tp_max_pct:.0f}%)",
        "trailing_activation": "immediat (des J1, previous peak; pas de watcher J+1)",
        "trailing_long_pct": (f"max(derive {cfg.atr_risk_stop_multiple}xATR, "
                              f"{100*cfg.trailing_stop_long_pct:.0f}%)"),
        "time_stop_enabled": cfg.time_stop_enabled,
        "time_stop_max_business_days": cfg.time_stop_max_business_days,
        "min_tp_progress_ratio": cfg.time_stop_min_tp_progress_ratio,
        "near_zero_return_pct": cfg.time_stop_near_zero_return_pct,
        "intrabar_priority": m.intrabar_priority,
        "max_entry_gap_pct": m.max_entry_gap_pct,
        "entry_timing": f"{cfg.execution_timing} (entry_limit_offset_pct={cfg.entry_limit_offset_pct})",
        "max_positions": cfg.max_positions,
        "costs": "canonical 16bps RT" if cfg.use_canonical_costs else f"legacy fees_pct={cfg.fees_pct}",
    }


def _count_time_stop_prod() -> None:
    print("\n" + "=" * 110)
    print("E12-A0.2  COUNT time_stop DANS LES RUNS PRODUCTION-PARITY")
    print("=" * 110)
    for r in CANON_RUNS:
        csv = r / "trade_audit_log.csv"
        if not csv.exists():
            print(f"  {r.name:<45} (pas de trade_audit_log)")
            continue
        df = pd.read_csv(csv)
        col = "replay_exit_reason" if "replay_exit_reason" in df.columns else "exit_reason"
        ts = int((df[col] == "time_stop").sum())
        tr = int((df[col] == "trailing_stop").sum())
        tp = int((df[col] == "take_profit").sum())
        st = int((df[col] == "initial_stop").sum())
        print(f"  {r.name:<45} time_stop={ts:>4} | trailing={tr:>4} | TP={tp:>4} | init_stop={st:>4} | n={len(df)}")


def _count_time_stop_research() -> None:
    print("\n" + "=" * 110)
    print("E12-A0.3  COUNT time_stop DANS LE RUN E11 (recherche)")
    print("=" * 110)
    if not E11_LOG.exists():
        print("  (log E11 absent)")
        return
    txt = E11_LOG.read_text(encoding="utf-16-le", errors="replace")
    # Cibler la table D2 (section "D2. Metriques par reason"), pas la table A4 (winners coupes)
    import re
    m = re.search(r"D2\. Metriques par reason.*?time_stop\s+(\d+)\s+(-?\d+)", txt, flags=re.S)
    if m:
        print(f"  E11 seed {SEED_REP} : time_stop n={m.group(1)} PnL={m.group(2)}$ (table D2)")
    else:
        print("  (table D2 time_stop non trouvee dans le log E11)")


def main() -> None:
    r = _research_contract()
    c = _canonical_contract()

    print("=" * 110)
    print("E12-A0 — EXECUTION CONTRACT AUDIT : RESEARCH (E6-E11) vs CANONIQUE (B25 POST-FIX P14)")
    print("=" * 110)

    keys = [
        ("initial_stop_atr_multiple", "initial stop (ATR multiple)"),
        ("tp_formula", "TP formula"),
        ("trailing_activation", "trailing activation"),
        ("trailing_long_pct", "trailing long %"),
        ("time_stop_enabled", "time_stop enabled/effective"),
        ("time_stop_max_business_days", "time_stop max business days"),
        ("min_tp_progress_ratio", "min_tp_progress_ratio"),
        ("near_zero_return_pct", "near_zero_return_pct"),
        ("intrabar_priority", "intrabar resolution"),
        ("max_entry_gap_pct", "max entry gap (gap filter)"),
        ("entry_timing", "entry timing"),
        ("max_positions", "max positions"),
        ("costs", "costs"),
    ]
    print(f"\n  {'champ':<32} {'RESEARCH (E6-E11)':<34} {'CANONIQUE (prod)':<30} {'=' if '=' else ''}")
    print("-" * 110)
    div = []
    for k, label in keys:
        rv, cv = str(r[k]), str(c[k])
        same = "SAME" if rv == cv else "DIFF"
        if same == "DIFF":
            div.append(label)
        print(f"  {label:<32} {rv:<34} {cv:<30} {same}")

    print("\n  DIVERGENCES :")
    for d in div:
        print(f"    - {d}")

    _count_time_stop_prod()
    _count_time_stop_research()

    print("\n" + "=" * 110)
    print("VERDICT E12-A0")
    print("=" * 110)
    print("""  Le lifecycle E6->E11 est un lifecycle de RECHERCHE, nomme explicitement :
    E-LIFECYCLE = stop 3.5xATR / TP min(4xATR,13%) / trailing max(3.5xATR,7%) arme J1 /
                  time_stop ON 15j (0.5/0.005) / gap filter OFF / intrabar conservative /
                  entry next_open marché / costs 16bps RT / m8.
  Il est DIFFERENT du lifecycle canonique production (B25_POST_TP_FIX_P14_M8) :
    PROD = stop 2.5xATR / TP min(3xATR,7%) / trailing 2.5xATR arme J+1 (watcher) /
           time_stop NEUTRALISE (0 fills) / gap filter 3% / intrabar conservative /
           entry next_open / costs 16bps RT / m8.

  Les 229 time_stop d'E11 sont un ARTEFACT du moteur recherche :
    - le config recherche laisse time_stop ENABLED (defaut 15 jours ouvrés, progress 0.5) ;
    - le moteur recherche declenche time_stop A LA CLOTURE sans verifier si un trailing
      travaille deja (simulator.py:2096-2130) ;
    - la production n'execute JAMAIS time_stop (exit_lifecycle_replay: 0 fills) : le
      watcher annule le stop initial et arme le trailing a J+1 ; si TP/trailing travaille,
      le time_stop saute (audit P14).

  IMPLICATION : E6->E11 (univers Extreme LONG + diagnostic payoff) sont conditionnels
  au E-LIFECYCLE, PAS au contrat production. Les 229 time_stop (-85k) et le stop large
  3.5xATR font partie du contrat recherche ; ils n'existent pas tels quels en prod.

  DECISION REQUISE avant E12 exits : E12-A/B/C/D doivent etre executes sous
    - (1) le E-LIFECYCLE (continuite E6-E11, nomme explicitement) puis valider le
          gagnant sous PROD, OU
    - (2) directement sous PROD (reverifier d'abord le diagnostic E11 sous PROD).
  AUCUN sweep avant cette decision.""")
    print("\n  Contrat research instancie depuis make_engine() ; canonique depuis rebench post-fix.")
    print("  (bit-for-bit : les champs ATR de la baseline canonique viennent de la commande")
    print("  rebench --atr-risk-stop-multiple 2.5 --tp-atr-multiple 3.0 --tp-max-pct 0.07.)")


if __name__ == "__main__":
    main()
