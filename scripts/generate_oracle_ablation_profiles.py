"""Génère la campagne d'ablation des features Oracle Extreme.

La source unique est config/features/oracle/oracle.json. Chaque profil produit
est un sous-ensemble strict et ordonné du contrat canonique, afin qu'un batch
ne diffère de la baseline que par ses colonnes d'entrée.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "config" / "features" / "oracle"
BASELINE_PATH = PROFILE_DIR / "oracle.json"


def _is_xs(feature: str) -> bool:
    return feature.endswith("_xs_rank")


def _is_zscore(feature: str) -> bool:
    return feature.endswith("_zscore")


def _is_engineered_transform(feature: str) -> bool:
    tokens = ("_x_", "_div_", "_minus_", "_times_")
    exact = {
        "accel_3_5", "decay_5_10", "rsi_slope", "vol_expansion",
        "meanrev_signal", "gap_fade", "log_return_div_intraday_range",
    }
    return feature in exact or any(token in feature for token in tokens)


def _is_momentum_return(feature: str) -> bool:
    prefixes = ("momentum_", "rolling_mean_return_", "return_")
    exact = {"daily_return", "log_return", "accel_3_5", "decay_5_10"}
    return feature in exact or feature.startswith(prefixes)


def _is_trend_position(feature: str) -> bool:
    prefixes = (
        "sma", "ema", "distance_high_", "distance_low_", "range_position_",
        "dist_to_sma_", "zscore_close_vs_ma", "adx_",
    )
    exact = {"close_location_value"}
    return feature in exact or feature.startswith(prefixes)


def _is_volatility_range(feature: str) -> bool:
    prefixes = ("rolling_volatility_", "atr_", "atr20_", "vol_ratio_")
    exact = {"intraday_range", "body_range", "vol_expansion"}
    return feature in exact or feature.startswith(prefixes) or "volatility" in feature


def _is_volume_flow(feature: str) -> bool:
    prefixes = ("volume_", "dollar_volume_", "amihud_", "obv_", "up_volume_", "cmf_")
    return (
        feature.startswith(prefixes)
        or "vwap" in feature
        or "volume_ratio" in feature
        or "times_volume" in feature
    )


def _is_rsi_mean_reversion(feature: str) -> bool:
    return (
        feature.startswith("rsi_")
        or feature in {"meanrev_signal", "gap_fade", "overnight_gap"}
    )


def _is_market_relative_regime(feature: str) -> bool:
    return (
        feature.startswith(("market_", "relative_strength_", "regime_", "SPY_", "VIX_"))
        or feature.endswith("_x_bull")
        or feature.endswith("_x_risk_off")
        or "market_trend" in feature
        or "market_volatility" in feature
    )


def _raw_simple(feature: str) -> bool:
    return not _is_xs(feature) and not _is_zscore(feature) and not _is_engineered_transform(feature)


CAMPAIGNS: list[tuple[str, str, Callable[[str], bool], str]] = [
    (
        "ablation_01_no_xs_ranks.json",
        "O0 sans les rangs percentiles cross-sectionnels.",
        lambda feature: not _is_xs(feature),
        "Mesure la valeur ajoutée globale des 44 rangs cross-sectionnels.",
    ),
    (
        "ablation_02_xs_ranks_only.json",
        "Oracle limité aux rangs percentiles cross-sectionnels.",
        _is_xs,
        "Teste si l'information utile est presque entièrement relative au marché du jour.",
    ),
    (
        "ablation_03_raw_simple.json",
        "Socle brut sans rangs XS, z-scores temporels ni transformations complexes.",
        _raw_simple,
        "Teste un Oracle plus parcimonieux et moins exposé au surapprentissage.",
    ),
    (
        "ablation_04_no_momentum_returns.json",
        "O0 sans la famille rendements et momentum, y compris ses dérivés nommés.",
        lambda feature: not _is_momentum_return(feature),
        "Mesure si la détection d'amplitude dépend principalement du momentum multi-horizon.",
    ),
    (
        "ablation_05_no_trend_position.json",
        "O0 sans distances aux moyennes, pentes et positions dans les ranges.",
        lambda feature: not _is_trend_position(feature),
        "Mesure l'apport de la structure de tendance et de position du prix.",
    ),
    (
        "ablation_06_no_volatility_range.json",
        "O0 sans volatilité, ATR, ratios de volatilité et amplitude intraday.",
        lambda feature: not _is_volatility_range(feature),
        "Mesure l'apport de la volatilité à une cible elle-même fondée sur l'amplitude future.",
    ),
    (
        "ablation_07_no_volume_flow.json",
        "O0 sans volume, flux, CMF et relations prix-volume/VWAP.",
        lambda feature: not _is_volume_flow(feature),
        "Mesure l'apport de la participation et de la liquidité au mouvement extrême futur.",
    ),
    (
        "ablation_08_no_rsi_mean_reversion.json",
        "O0 sans RSI, mean-reversion, gap fade et overnight gap.",
        lambda feature: not _is_rsi_mean_reversion(feature),
        "Mesure l'apport des oscillateurs et configurations de retour à la moyenne.",
    ),
    (
        "ablation_09_no_market_relative_regime.json",
        "O0 sans marché, force relative, régimes et interactions bull/risk-off.",
        lambda feature: not _is_market_relative_regime(feature),
        "Mesure l'apport du contexte marché et du comportement relatif du symbole.",
    ),
    (
        "ablation_10_no_engineered_transforms.json",
        "O0 sans ratios, différences, produits et dynamiques construites.",
        lambda feature: not _is_engineered_transform(feature),
        "Teste si les transformations complexes améliorent réellement le signal OOS.",
    ),
    (
        "ablation_11_no_temporal_zscores.json",
        "O0 sans z-scores temporels glissants.",
        lambda feature: not _is_zscore(feature),
        "Mesure l'apport de la normalisation temporelle longue.",
    ),
    (
        "combined_12_no_market_regime_no_engineered.json",
        "O0 sans marché/régime ni transformations complexes.",
        lambda feature: not (
            _is_market_relative_regime(feature) or _is_engineered_transform(feature)
        ),
        "Combine les deux retraits les plus favorables de la vague 1 (A09 + A10).",
    ),
    (
        "combined_13_no_market_regime_no_momentum.json",
        "O0 sans marché/régime ni rendements/momentum.",
        lambda feature: not (
            _is_market_relative_regime(feature) or _is_momentum_return(feature)
        ),
        "Teste le retrait A04 après nettoyage du contexte marché A09.",
    ),
    (
        "combined_14_no_market_regime_no_engineered_no_momentum.json",
        "O0 compact sans marché/régime, transformations complexes ni momentum.",
        lambda feature: not (
            _is_market_relative_regime(feature)
            or _is_engineered_transform(feature)
            or _is_momentum_return(feature)
        ),
        "Test de parcimonie agressif réunissant A09, A10 et A04.",
    ),
]


def main() -> None:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    columns = list(baseline["feature_columns"])
    if len(columns) != len(set(columns)):
        raise ValueError("Le profil Oracle canonique contient des doublons.")

    for index, (filename, description, keep, hypothesis) in enumerate(CAMPAIGNS, start=1):
        selected = [feature for feature in columns if keep(feature)]
        if not selected or selected == columns:
            raise ValueError(f"Ablation sans effet ou vide: {filename}")
        options = dict(baseline.get("generator_options") or {})
        if filename == "ablation_01_no_xs_ranks.json" or filename == "ablation_03_raw_simple.json":
            options["enable_cross_sectional_ranks"] = False
        payload = {
            "schema_version": 1,
            "profile_id": f"oracle-o0-ablation-{index:02d}-20260904",
            "direction": "oracle",
            "description": description,
            "feature_set": baseline.get("feature_set", "expert"),
            "generator_options": options,
            "feature_columns": selected,
            "provenance": {
                "campaign": "oracle_feature_ablation_20260904",
                "baseline_profile": "oracle.json",
                "baseline_feature_count": len(columns),
                "feature_count": len(selected),
                "removed_feature_count": len(columns) - len(selected),
                "hypothesis": hypothesis,
            },
        }
        (PROFILE_DIR / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
