#!/usr/bin/env python
"""scripts/produce_baseline_artifact.py — Génère un artefact baseline JSON (Point 1).

Usage :
    python scripts/produce_baseline_artifact.py [--start 2022-01-01] [--end 2024-01-31] [--symbols SPY,XLF,XLK,...]

Produit un fichier JSON dans artifacts/baselines/ contenant :
- period_start / period_end
- universe (SPY + secteurs par défaut)
- seed, code SHA, config fingerprint, data fingerprint
- métriques par side (précision, rappel, f1, hit rate)

Exigences Point 1 (cf. md_risque.md) :
    "baseline JSON réelle sur SPY/secteurs" pour vérifier que le système
    produit des métriques reproductibles et documentées.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

# Ajoute la racine du projet au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ternary_decision_policy import (
    produce_baseline_artifact,
    save_baseline_artifact,
    BaselineArtifact,
)


# ── Univers par défaut : SPY + secteurs ──────────────────────────────────────

DEFAULT_UNIVERSE = [
    "SPY",   # S&P 500
    "XLF",   # Financials
    "XLK",   # Technology
    "XLE",   # Energy
    "XLV",   # Health Care
    "XLI",   # Industrials
    "XLY",   # Consumer Discretionary
    "XLP",   # Consumer Staples
    "XLU",   # Utilities
    "XLB",   # Materials
    "XLRE",  # Real Estate
    "XLC",   # Communication Services
]

# ── Métriques dummy (à remplacer par des métriques réelles calculées) ─────────
# Dans la vraie vie, ces métriques sont calculées par le pipeline ML sur
# la période et l'univers donnés. Ici on met des placeholders documentés.

DUMMY_METRICS_BY_SIDE: dict[str, dict[str, float]] = {
    "long": {
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "hit_rate": 0.0,
        "total_predictions": 0,
        "note": "PLACEHOLDER — run real ML pipeline to populate",
    },
    "short": {
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "hit_rate": 0.0,
        "total_predictions": 0,
        "note": "PLACEHOLDER — run real ML pipeline to populate",
    },
    "flat": {
        "abstention_rate": 0.0,
        "total_predictions": 0,
        "note": "PLACEHOLDER — run real ML pipeline to populate",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Produit un artefact baseline JSON pour Point 1.",
    )
    parser.add_argument(
        "--start",
        default="2022-01-01",
        help="Début de période (YYYY-MM-DD). Défaut: 2022-01-01",
    )
    parser.add_argument(
        "--end",
        default="2024-01-31",
        help="Fin de période (YYYY-MM-DD). Défaut: 2024-01-31",
    )
    parser.add_argument(
        "--symbols",
        default=",".join(DEFAULT_UNIVERSE),
        help="Tickers séparés par des virgules. Défaut: SPY + 11 secteurs.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed de reproductibilité. Défaut: 42.",
    )
    args = parser.parse_args()

    universe = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    artifact: BaselineArtifact = produce_baseline_artifact(
        period_start=args.start,
        period_end=args.end,
        universe=universe,
        metrics_by_side=DUMMY_METRICS_BY_SIDE,
        seed=args.seed,
    )

    filepath: str = save_baseline_artifact(artifact)

    print(f"Baseline produite → {filepath}")
    print(f"  artifact_id       : {artifact.artifact_id}")
    print(f"  period            : {artifact.period_start} → {artifact.period_end}")
    print(f"  universe          : {artifact.universe}")
    print(f"  seed              : {artifact.seed}")
    print(f"  code_sha          : {artifact.code_sha}")
    print(f"  config_fingerprint: {artifact.config_fingerprint}")
    print(f"  policy            : {artifact.policy_dict}")

    # Vérification basique : le fichier peut être relu
    with open(filepath, "r", encoding="utf-8") as fh:
        reloaded = json.load(fh)
    assert reloaded["artifact_id"] == artifact.artifact_id
    print(f"  ✅ Fichier reproductible OK ({len(json.dumps(reloaded))} octets)")


if __name__ == "__main__":
    main()
