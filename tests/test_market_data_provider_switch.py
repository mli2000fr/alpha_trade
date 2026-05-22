"""Sprint S0 / A-001 — provider switch explicite, sans faux fallback."""
from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config.yaml"


def test_fallback_on_failure_is_effective_or_rejected() -> None:
    """Le dépôt a choisi la stratégie *rejet/suppression* du faux fallback.

    Tant qu'aucun router runtime explicite n'existe, `config.yaml` ne doit plus
    exposer `market_data.fallback_on_failure`, afin d'éviter toute ambiguïté
    opérateur sur un basculement EODHD -> Alpaca qui n'existe pas.
    """
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    market_data = (cfg or {}).get("market_data") or {}
    assert market_data.get("bars_provider") in {"eodhd", "alpaca"}
    assert "fallback_on_failure" not in market_data

