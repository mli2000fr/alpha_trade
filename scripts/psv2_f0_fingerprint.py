"""F0 — Fingerprint de référence pour la campagne Per-Symbol Directional v2.

F0 = le per-symbol LEGACY EXACT (whitelist OFF), gelé avant toute campagne.
Référence : run S7 bl (model-factory-20260818161922-d7d984), 39 symboles communs.

Produit : un manifeste F0 (features + target + preprocessing + modèles + selection)
qui sert de contrat de référence : chaque famille F1/F2/F3a/F3b doit être comparée à F0.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BL_BATCH = ROOT / "artifacts" / "models_s7_bl" / "model-factory-20260818161922-d7d984"
SYM_REF = "ACI"

cfg = json.load(open(BL_BATCH / SYM_REF / "config.json", encoding="utf-8"))
data = cfg.get("data", {})
features = cfg.get("feature_columns", [])
contract = cfg.get("feature_contract", {})

# Manifeste F0 : features + target + preprocessing + modèles + selection
manifest = {
    "campaign": "per_symbol_directional_v2",
    "f0_label": "F0 legacy exact (whitelist OFF)",
    "reference_run": "model-factory-20260818161922-d7d984 (S7 bl)",
    "symbols": 39,  # 40 prod - CRBG
    "feature_set": data.get("feature_set"),
    "feature_count": len(features),
    "feature_columns": features,
    "feature_fingerprint": cfg.get("feature_fingerprint"),
    "feature_whitelist": {"enabled": data.get("feature_whitelist_enabled", False),
                          "features": data.get("feature_whitelist", [])},
    "target": {
        "mode": data.get("target_mode"),
        "horizon": data.get("forecast_horizon"),
        "horizons": data.get("forecast_horizons"),
        "up_threshold": data.get("target_up_threshold"),
        "down_threshold": data.get("target_down_threshold"),
        "excess_vs_spy": data.get("target_excess_vs_spy"),
    },
    "preprocessing": {
        "sequence_length": data.get("sequence_length"),
        "min_history_days": data.get("min_history_days"),
        "calibration": cfg.get("calibration", {}).get("method"),
        "decision_threshold": cfg.get("selected_decision_threshold"),
        "walk_forward": cfg.get("walk_forward"),
    },
    "models": {
        "architectures": ["lstm_attention", "lightgbm", "catboost"],
        "default_champion": "lstm_attention",
        "selection_metric": "selection_score",
        "select_champion": True,
    },
    "training_window": {
        "start": data.get("training_start_date"),
        "end": data.get("training_end_date"),  # <= 2024-12-31 → 2025+2026 OOS
    },
    "benchmark_b": "B25 (global ranking) — gelé, non modifié",
}

# Fingerprint F0 canonique (toutes les clés hors path)
payload = {
    "feature_set": manifest["feature_set"],
    "feature_count": manifest["feature_count"],
    "feature_columns": manifest["feature_columns"],
    "feature_whitelist_enabled": False,
    "target": manifest["target"],
    "preprocessing": manifest["preprocessing"],
    "models": manifest["models"],
    "training_window": manifest["training_window"],
}
f0_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]
manifest["f0_fingerprint"] = f0_hash

out = ROOT / "artifacts" / "per_symbol_v2"
out.mkdir(parents=True, exist_ok=True)
(out / "f0_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
print("F0 manifeste ->", out / "f0_manifest.json")
print("F0 feature_fingerprint:", manifest["feature_fingerprint"])
print("F0 f0_fingerprint:", f0_hash)
print("F0 features (%d):" % len(features))
print(" ", features)
