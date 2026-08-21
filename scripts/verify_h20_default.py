"""Vérifie que le best_horizon par défaut du RiskConfig vient de config.yaml (H20)
après le correctif, et que les maps stop/TP utilisent H20."""
from __future__ import annotations

import sys

sys.path.insert(0, r"F:\projets")

from risk_management.config import load_risk_config


def main() -> None:
    # Chargement PAR DÉFAUT (aucun override) → doit lire config.yaml backtest_horizon/live_horizon
    cfg = load_risk_config(preset_key="capital_2001_5000", equity=4000.0)
    print(f"best_horizon par défaut : {cfg.best_horizon}  (attendu 20 = config.yaml)")

    stop = cfg.atr_stop_multiple_for()
    tp_atr, tp_max = cfg.tp_params_for()
    print(f"  stop  = {stop}x ATR  (attendu 3.5 pour H20)")
    print(f"  TP    = min({tp_atr}x ATR, {tp_max:.0%})  (attendu 4x / 13%)")

    # Avec override explicite (comme l'ancien comportement H10)
    cfg10 = load_risk_config(
        preset_key="capital_2001_5000", equity=4000.0,
        cli_overrides={"best_horizon": 10},
    )
    print(f"\nOverride explicite best_horizon=10 -> {cfg10.best_horizon} "
          f"(stop {cfg10.atr_stop_multiple_for()}x, TP min({cfg10.tp_params_for()[0]}x, {cfg10.tp_params_for()[1]:.0%}))")


if __name__ == "__main__":
    main()
