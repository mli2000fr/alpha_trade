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
import json
import math
import os
import sys
from pathlib import Path

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

def _load_metrics(path: str) -> dict[str, dict[str, float]]:
    """Load computed side metrics and reject placeholder-like input."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("--metrics-json doit contenir un objet JSON")
    metrics: dict[str, dict[str, float]] = {}
    for side in ("long", "short", "flat"):
        values = payload.get(side)
        if not isinstance(values, dict) or not values:
            raise ValueError(f"--metrics-json doit contenir un objet non vide pour {side}")
        parsed: dict[str, float] = {}
        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"métrique invalide {side}.{name}: valeur numérique finie requise")
            parsed[str(name)] = float(value)
        metrics[side] = parsed
    return metrics


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
    parser.add_argument(
        "--metrics-json",
        required=True,
        help="JSON des métriques réelles par side: long, short et flat.",
    )
    parser.add_argument(
        "--data-fingerprint",
        required=True,
        help="Fingerprint du dataset effectivement évalué; 'unknown' est refusé.",
    )
    args = parser.parse_args()

    universe = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    data_fingerprint = args.data_fingerprint.strip()
    if not data_fingerprint or data_fingerprint.lower() == "unknown":
        parser.error("--data-fingerprint doit identifier le dataset réellement évalué")
    try:
        metrics_by_side = _load_metrics(args.metrics_json)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    artifact: BaselineArtifact = produce_baseline_artifact(
        period_start=args.start,
        period_end=args.end,
        universe=universe,
        metrics_by_side=metrics_by_side,
        seed=args.seed,
        data_fingerprint=data_fingerprint,
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
