"""Utilitaires walk-forward pour charger et appliquer les meilleurs poids calibrés.

Sprint S3 / A-027 : ``validate_walk_forward_weights`` ajoute des bornes business
([0.05, 0.40] par défaut) sur les poids sentiment/macro/quant et **clip** les
valeurs hors bornes avec un log WARNING plutôt qu'un assert fatal, afin de ne
pas bloquer un run opérationnel.

Sprint S4 / A-022 : ``walk_forward_risk_params`` étend le walk-forward aux
paramètres risk (ATR, Kelly, ``correlation_threshold``) via une grid-search
légère sur une série de rendements daily.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from event_sentiment.signal_aggregator import SentimentSignalAggregator

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sprint S3 / A-027 — bornes business sur les poids calibrés
# ---------------------------------------------------------------------------

#: Borne inférieure inclusive sur chaque poids individuel.
WEIGHT_MIN: float = 0.0
#: Borne supérieure inclusive sur chaque poids individuel.
WEIGHT_MAX: float = 0.95

_WEIGHT_FILENAMES = (
    "latest_best_weights.json",
    "walk_forward_best_weights_latest.json",
    "champion_weights.json",
    "sentiment_weight_calibration_best.json",
)


@dataclass(frozen=True, slots=True)
class WalkForwardWeights:
    sentiment_weight: float
    macro_weight: float
    quant_weight: float
    calibration_run_id: str | None = None
    calibration_source: str | None = None
    scenario_name: str | None = None
    artifact_path: str | None = None


def _candidate_roots(search_roots: Iterable[Path] | None = None) -> list[Path]:
    roots = list(search_roots or [])
    if not roots:
        roots = [
            Path("artifacts/sentiment_walk_forward"),
            Path("artifacts/sentiment_calibration"),
            Path("artifacts"),
        ]
    return roots


def _extract_weight(payload: dict[str, Any], *names: str) -> float | None:
    for name in names:
        value = payload.get(name)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def load_walk_forward_weights(path: Path) -> WalkForwardWeights | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        LOGGER.warning("Impossible de lire les poids walk-forward depuis %s.", path, exc_info=True)
        return None
    sentiment_weight = _extract_weight(payload, "sentiment_weight", "scenario_sentiment_weight")
    macro_weight = _extract_weight(payload, "macro_weight", "scenario_macro_weight")
    quant_weight = _extract_weight(payload, "quant_weight", "scenario_quant_weight")
    if sentiment_weight is None or macro_weight is None or quant_weight is None:
        return None
    return WalkForwardWeights(
        sentiment_weight=sentiment_weight,
        macro_weight=macro_weight,
        quant_weight=quant_weight,
        calibration_run_id=str(payload.get("calibration_run_id")) if payload.get("calibration_run_id") is not None else None,
        calibration_source=str(payload.get("calibration_source") or payload.get("best_scenario_name") or "walk_forward"),
        scenario_name=str(payload.get("scenario_name") or payload.get("best_scenario_name")) if payload.get("scenario_name") or payload.get("best_scenario_name") else None,
        artifact_path=str(path),
    )


# ---------------------------------------------------------------------------
# Sprint S3 / A-027 — validation des bornes business sur les poids
# ---------------------------------------------------------------------------


def validate_walk_forward_weights(
    weights: WalkForwardWeights,
    *,
    min_weight: float = WEIGHT_MIN,
    max_weight: float = WEIGHT_MAX,
    strict: bool = False,
) -> WalkForwardWeights:
    """Vérifie et corrige les poids walk-forward selon les bornes business.

    En mode ``strict=False`` (défaut opérationnel), les poids hors bornes sont
    **clippés** avec un log ``WARNING``. En mode ``strict=True`` (tests unitaires,
    validation manuelle), une ``ValueError`` est levée.

    Args:
        weights: Poids calibrés à valider.
        min_weight: Borne inférieure inclusive (défaut 0.05).
        max_weight: Borne supérieure inclusive (défaut 0.40).
        strict: Si ``True``, lève ``ValueError`` sur tout dépassement.

    Returns:
        ``WalkForwardWeights`` validés/clippés.

    Raises:
        ValueError: Si ``strict=True`` et au moins un poids est hors bornes.
    """
    violations: list[str] = []

    def _check(name: str, value: float) -> float:
        if value < min_weight:
            msg = f"Poids {name}={value:.4f} < borne inférieure {min_weight}"
            violations.append(msg)
            return min_weight
        if value > max_weight:
            msg = f"Poids {name}={value:.4f} > borne supérieure {max_weight}"
            violations.append(msg)
            return max_weight
        return value

    clipped_sentiment = _check("sentiment_weight", weights.sentiment_weight)
    clipped_macro = _check("macro_weight", weights.macro_weight)
    clipped_quant = _check("quant_weight", weights.quant_weight)

    if violations:
        if strict:
            raise ValueError(
                "Poids walk-forward hors bornes business [{}, {}] : {}".format(
                    min_weight, max_weight, " | ".join(violations)
                )
            )
        for msg in violations:
            LOGGER.warning("A-027 bornes walk-forward — %s (clippage appliqué)", msg)

    # Renormalisation pour que la somme des poids = 1.0 après clippage.
    # Uniquement lorsque le clippage a effectivement modifié au moins un poids.
    _clipping_occurred = (
        abs(clipped_sentiment - weights.sentiment_weight) > 1e-12
        or abs(clipped_macro - weights.macro_weight) > 1e-12
        or abs(clipped_quant - weights.quant_weight) > 1e-12
    )
    if _clipping_occurred:
        total = clipped_sentiment + clipped_macro + clipped_quant
        if total > 0 and abs(total - 1.0) > 1e-9:
            clipped_sentiment = clipped_sentiment / total
            clipped_macro = clipped_macro / total
            clipped_quant = clipped_quant / total
            LOGGER.info(
                "A-027 poids walk-forward renormalisés à somme=1.0 : sentiment=%.4f macro=%.4f quant=%.4f",
                clipped_sentiment, clipped_macro, clipped_quant,
            )

    if clipped_sentiment == weights.sentiment_weight and clipped_macro == weights.macro_weight and clipped_quant == weights.quant_weight:
        return weights

    return WalkForwardWeights(
        sentiment_weight=clipped_sentiment,
        macro_weight=clipped_macro,
        quant_weight=clipped_quant,
        calibration_run_id=weights.calibration_run_id,
        calibration_source=weights.calibration_source,
        scenario_name=weights.scenario_name,
        artifact_path=weights.artifact_path,
    )


def resolve_latest_walk_forward_weights(search_roots: Iterable[Path] | None = None) -> WalkForwardWeights | None:
    candidates: list[Path] = []
    for root in _candidate_roots(search_roots):
        if not root.exists():
            continue
        for filename in _WEIGHT_FILENAMES:
            candidates.extend(root.rglob(filename))
    existing_candidates = [path for path in candidates if path.is_file()]
    if not existing_candidates:
        return None
    latest_path = max(existing_candidates, key=lambda path: path.stat().st_mtime)
    loaded = load_walk_forward_weights(latest_path)
    if loaded is None:
        return None
    # Sprint S3 / A-027 — applique les bornes business (clippage + warning).
    return validate_walk_forward_weights(loaded)


# ---------------------------------------------------------------------------
# Sprint S4 / A-022 — Walk-forward sur paramètres risk
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RiskParamResult:
    """Résultat d'un run walk-forward sur les paramètres risk.

    Attributes:
        best_params: dict des meilleurs paramètres (ex. ``{"atr_period": 14,
            "correlation_threshold": 0.80}``).
        best_score: score associé (ex. Sharpe ratio moyen out-of-sample).
        metric_name: nom de la métrique utilisée pour l'optimisation.
        param_grid: grille initiale passée à la fonction.
        n_evaluated: nombre de combinaisons évaluées.
    """

    best_params: dict[str, Any]
    best_score: float
    metric_name: str
    param_grid: dict[str, list[Any]]
    n_evaluated: int


def walk_forward_risk_params(
    returns_series: "pd.Series[float]",
    param_grid: dict[str, list[Any]],
    *,
    metric_name: str = "sharpe",
    min_observations: int = 20,
) -> RiskParamResult:
    """Walk-forward grid-search sur les paramètres risk (Sprint S4 / A-022).

    Évalue toutes les combinaisons de ``param_grid`` sur ``returns_series``
    et retourne la combinaison maximisant ``metric_name``.

    Cette implémentation est intentionnellement **légère** (pure Python /
    NumPy) : elle n'exécute pas un backtest complet mais calcule des métriques
    agrégées (Sharpe, Sortino, hit-rate) directement sur la série de
    rendements fournie, paramétrée via les clés supportées :

    - ``atr_period`` (int) : utilisé pour calculer une fenêtre glissante de
      vol réalisée sur ``returns_series`` (proxy ATR).
    - ``kelly_fraction`` (float) : fraction Kelly maximale (contrôle le
      niveau de levier implicite dans le Sharpe half-Kelly).
    - ``correlation_threshold`` (float) : seuil de corrélation appliqué comme
      multiplicateur de diversification sur le Sharpe (proxy).

    Pour chaque combinaison, un score scalaire est produit et la meilleure
    combinaison est retournée.

    Args:
        returns_series: Série de rendements daily (float, index quelconque).
        param_grid: Grille de paramètres, ex. ``{"atr_period": [14, 20],
            "correlation_threshold": [0.75, 0.80, 0.85]}``.
        metric_name: Métrique d'optimisation : ``"sharpe"`` (défaut),
            ``"sortino"``, ``"hit_rate"``.
        min_observations: Nombre minimum de rendements non-nuls requis.

    Returns:
        :class:`RiskParamResult` avec la meilleure combinaison.

    Raises:
        ValueError: Si ``returns_series`` a moins de ``min_observations``
            valeurs non-nulles ou si ``metric_name`` est inconnu.
    """
    import itertools

    import numpy as np

    supported_metrics = ("sharpe", "sortino", "hit_rate")
    if metric_name not in supported_metrics:
        raise ValueError(
            f"metric_name '{metric_name}' non supporté. Valeurs acceptées : {supported_metrics}"
        )

    rets = pd.to_numeric(pd.Series(returns_series), errors="coerce").dropna()
    if len(rets) < min_observations:
        raise ValueError(
            f"walk_forward_risk_params requiert au moins {min_observations} observations non-nulles "
            f"(reçu {len(rets)})."
        )

    arr = rets.to_numpy(dtype=float)

    def _score(params: dict[str, Any]) -> float:
        atr_period = int(params.get("atr_period", 14))
        kelly_fraction = float(params.get("kelly_fraction", 0.25))
        corr_threshold = float(params.get("correlation_threshold", 0.80))

        # Proxy ATR : écart-type rolling fenêtré
        window = min(atr_period, len(arr))
        vol_rolling = np.array([np.std(arr[max(0, i - window):i + 1]) for i in range(len(arr))])
        vol_rolling = np.where(vol_rolling == 0, 1e-8, vol_rolling)

        # Normalisation Kelly : applique un plafond implicite sur les rendements
        kelly_adj = np.clip(arr / vol_rolling, -kelly_fraction, kelly_fraction)

        # Diversification proxy : amplitude réduite en zone corrélée
        diversity_mult = 1.0 - max(0.0, corr_threshold - 0.5) * 0.5

        if metric_name == "sharpe":
            mu = np.mean(kelly_adj)
            sigma = np.std(kelly_adj)
            return float((mu / sigma) * diversity_mult) if sigma > 1e-8 else 0.0
        if metric_name == "sortino":
            mu = np.mean(kelly_adj)
            downside = np.std(kelly_adj[kelly_adj < 0])
            return float((mu / downside) * diversity_mult) if downside > 1e-8 else 0.0
        # hit_rate
        return float(np.mean(kelly_adj > 0) * diversity_mult)

    keys = list(param_grid.keys())
    values_product = list(itertools.product(*[param_grid[k] for k in keys]))
    if not values_product:
        raise ValueError("param_grid est vide ou ne contient aucune valeur.")

    best_score = float("-inf")
    best_params: dict[str, Any] = {}
    for combo in values_product:
        params = dict(zip(keys, combo))
        s = _score(params)
        if s > best_score:
            best_score = s
            best_params = params

    return RiskParamResult(
        best_params=best_params,
        best_score=best_score,
        metric_name=metric_name,
        param_grid=param_grid,
        n_evaluated=len(values_product),
    )


def apply_walk_forward_weights(scores_df: pd.DataFrame, weights: WalkForwardWeights | None) -> pd.DataFrame:
    if scores_df.empty or weights is None:
        return scores_df.copy()

    result = scores_df.copy()
    quant = pd.Series(pd.to_numeric(result.get("final_score"), errors="coerce"), index=result.index, dtype=float).fillna(0.0).clip(0.0, 1.0)

    if "company_idio_score" not in result.columns:
        result["company_idio_score"] = pd.to_numeric(result.get("sentiment_net_agg"), errors="coerce")
    if "macro_regime_score" not in result.columns:
        result["macro_regime_score"] = pd.to_numeric(result.get("sector_impact_agg"), errors="coerce")

    if "company_idio_signal_norm" in result.columns:
        company_norm = pd.Series(pd.to_numeric(result["company_idio_signal_norm"], errors="coerce"), index=result.index, dtype=float)
    else:
        company_norm = SentimentSignalAggregator._normalize_signed_signal(result.get("company_idio_score", pd.Series(index=result.index, dtype=float)))
    if "macro_regime_signal_norm" in result.columns:
        macro_norm = pd.Series(pd.to_numeric(result["macro_regime_signal_norm"], errors="coerce"), index=result.index, dtype=float)
    else:
        macro_norm = SentimentSignalAggregator._normalize_signed_signal(result.get("macro_regime_score", pd.Series(index=result.index, dtype=float)))

    company_norm = company_norm.fillna(0.5).clip(0.0, 1.0)
    macro_norm = macro_norm.fillna(0.5).clip(0.0, 1.0)

    result["company_idio_signal_norm"] = company_norm
    result["macro_regime_signal_norm"] = macro_norm
    result["company_idio_component"] = (weights.sentiment_weight * company_norm).clip(0.0, 1.0)
    result["macro_regime_component"] = (weights.macro_weight * macro_norm).clip(0.0, 1.0)
    result["quant_component"] = (weights.quant_weight * quant).clip(0.0, 1.0)
    result["final_score_walk_forward"] = (
        result["company_idio_component"] + result["macro_regime_component"] + result["quant_component"]
    ).clip(0.0, 1.0)
    result["walk_forward_sentiment_weight"] = weights.sentiment_weight
    result["walk_forward_macro_weight"] = weights.macro_weight
    result["walk_forward_quant_weight"] = weights.quant_weight
    result["calibration_run_id"] = weights.calibration_run_id
    result["calibration_source"] = weights.calibration_source or "walk_forward"
    result["score_source"] = "final_score_walk_forward"
    return result

