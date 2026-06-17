"""
Regime-aware scoring — ajuste la composition du ``final_score`` selon le
régime de marché (``MarketRegimeSnapshot``).

Fonctions pures (sans I/O, sans état) consommables depuis le selector,
le backtest et le pipeline live.

.. code-block:: python

    from selector.regime_scoring import apply_regime_weights

    adjusted = apply_regime_weights(merged_df, snapshot, config)
    # adjusted["final_score"] reflète les poids directionnels du régime
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from selector.factors import winsorize_and_normalize

if TYPE_CHECKING:
    from selector.alpha_scanner import AlphaScannerConfig
    from service.market import MarketRegimeSnapshot

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Poids par régime
# ---------------------------------------------------------------------------

# Régime normal : comportement actuel (momentum / croissance)
NORMAL_WEIGHTS: dict[str, float] = {
    "trend_vcp": 0.50,
    "total_score": 0.30,
    "rsi": 0.20,
    "defensive_beta": 0.00,
    "defensive_size": 0.00,
    "defensive_low_vol": 0.00,
}

# Régime capital_preservation : rotation modérée vers qualité / low-beta
# Calibration (2026-06-17) basée sur l'analyse du run 20260617_170031_69b838e7 :
# - En CP, les trades momentum ont un avg_pnl positif (+$1.22 vs -$0.40 en normal)
# - Le momentum n'est donc PAS le problème en CP ; c'est la volatilité excessive
#   qui déclenche le drawdown breaker et bloque l'allocation
# - Poids cible : conserver ~50% momentum (qui fonctionne) + 50% défensif
#   (low-beta, low-vol, large-cap) pour réduire la volatilité du portefeuille
#   et éviter que le breaker ne se déclenche
CAPITAL_PRESERVATION_WEIGHTS: dict[str, float] = {
    "trend_vcp": 0.25,
    "total_score": 0.15,
    "rsi": 0.10,
    "defensive_beta": 0.22,
    "defensive_size": 0.13,
    "defensive_low_vol": 0.15,
}

# Seuils de filtres renforcés en régime défensif
DEFENSIVE_FILTER_OVERLAYS: dict[str, float | None] = {
    "min_market_cap": 2_000_000_000.0,   # 2B$ minimum (qualité)
    "max_spread_bps": 15.0,               # spread plus strict
    "max_beta_126": 1.2,                  # cap beta haut
    "min_atr_pct_20": None,               # pas de minimum ATR (tolère faible vol)
    "max_atr_pct_20": 0.06,               # rejette très forte volatilité
}

# ---------------------------------------------------------------------------
# Rotation factor : tracker de performance momentum
# ---------------------------------------------------------------------------

# Fenêtre d'évaluation glissante (en semaines de trading ≈ 5 jours ouvrés)
DEFAULT_ROTATION_LOOKBACK_WEEKS: int = 4
# Seuil de déclenchement : retour cumulé < ce seuil → rotation défensive
DEFAULT_ROTATION_THRESHOLD: float = -0.03  # -3% sur la fenêtre


class MomentumRotationState:
    """Tracker de performance pour le rotation factor.

    Accumule les returns quotidiens du portefeuille (ou d'un proxy momentum)
    et détermine si le momentum sous-performe suffisamment pour justifier
    une rotation automatique vers les poids défensifs, même en régime
    ``normal``.

    Parameters
    ----------
    lookback_weeks : int
        Nombre de semaines de recul (défaut 4).
    threshold : float
        Seuil de retour cumulé en dessous duquel on rotate (défaut -0.03).
    """

    def __init__(
        self,
        lookback_weeks: int = DEFAULT_ROTATION_LOOKBACK_WEEKS,
        threshold: float = DEFAULT_ROTATION_THRESHOLD,
    ) -> None:
        self._lookback = max(1, lookback_weeks)
        self._threshold = float(threshold)
        self._daily_returns: list[float] = []
        self._window_size = self._lookback * 5  # ~5 jours ouvrés par semaine

    @property
    def lookback_weeks(self) -> int:
        return self._lookback

    @property
    def threshold(self) -> float:
        return self._threshold

    def record(self, daily_return: float) -> None:
        """Enregistre un retour quotidien.

        Parameters
        ----------
        daily_return : float
            Retour du jour (ex: 0.01 = +1%).
        """
        self._daily_returns.append(float(daily_return))
        if len(self._daily_returns) > self._window_size:
            self._daily_returns = self._daily_returns[-self._window_size:]

    def cumulative_return(self) -> float | None:
        """Retourne le retour cumulé sur la fenêtre glissante.

        Returns
        -------
        float or None
            None si pas assez de données.
        """
        if len(self._daily_returns) < 5:  # au moins 1 semaine
            return None
        # Retour composé sur la fenêtre
        cum = 1.0
        for r in self._daily_returns[-self._window_size:]:
            cum *= 1.0 + r
        return float(cum - 1.0)

    def should_rotate(self) -> bool:
        """Retourne True si le momentum sous-performe et qu'il faut basculer.

        Conditions :
        - Au moins 1 semaine de données
        - Retour cumulé < seuil
        """
        cum = self.cumulative_return()
        if cum is None:
            return False
        return cum < self._threshold

    def is_ready(self) -> bool:
        """Le tracker a-t-il assez de données pour être fiable ?"""
        return len(self._daily_returns) >= 5

    def reset(self) -> None:
        """Réinitialise l'historique (utile après une rotation effectuée)."""
        self._daily_returns.clear()


def evaluate_momentum_rotation(
    rotation_state: MomentumRotationState | None,
    snapshot: MarketRegimeSnapshot | None = None,
) -> bool:
    """Détermine si le scoring doit basculer en mode défensif.

    Combine le régime de marché ET le rotation factor :
    - Si le snapshot est déjà défensif → True
    - Si le rotation tracker signale une sous-performance → True
    - Sinon → False (reste en normal)

    Parameters
    ----------
    rotation_state : MomentumRotationState or None
        État du tracker de rotation. Si None, seule la snapshot est considérée.
    snapshot : MarketRegimeSnapshot or None
        Contexte de régime.

    Returns
    -------
    bool
        True si les poids défensifs doivent être utilisés.
    """
    if snapshot is not None:
        mode = str(getattr(snapshot, "mode", "normal") or "normal").strip().lower()
        if mode in ("capital_preservation", "close_only", "cash_only"):
            return True

    if rotation_state is not None and rotation_state.is_ready():
        return rotation_state.should_rotate()

    return False


# ---------------------------------------------------------------------------
# Helpers de calcul
# ---------------------------------------------------------------------------

def _safe_float_series(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)
    result = pd.to_numeric(series, errors="coerce")
    if isinstance(result, pd.Series):
        return result.fillna(0.0)
    # scalaire (colonne absente) → série vide
    return pd.Series(dtype=float)


def _invert_and_normalize(series: pd.Series) -> pd.Series:
    """Inverse la série (1 - normalized) pour transformer « plus bas = mieux »."""
    norm = winsorize_and_normalize(series)
    return 1.0 - norm


def _compute_defensive_beta_score(df: pd.DataFrame) -> pd.Series:
    """Score défensif basé sur le bêta : plus le bêta est bas, mieux c'est."""
    beta = _safe_float_series(df.get("beta_126"))
    # Inverser : beta=0.5 → meilleur score que beta=2.0
    return _invert_and_normalize(beta)


def _compute_defensive_size_score(df: pd.DataFrame) -> pd.Series:
    """Score défensif basé sur la capitalisation : plus c'est gros, mieux c'est."""
    mcap = _safe_float_series(df.get("market_cap"))
    # Log pour éviter l'écrasement par les mega-caps
    log_mcap = np.log1p(mcap.clip(lower=1.0))
    return winsorize_and_normalize(log_mcap)


def _compute_defensive_low_vol_score(df: pd.DataFrame) -> pd.Series:
    """Score défensif basé sur la volatilité : plus c'est bas, mieux c'est."""
    vol = _safe_float_series(df.get("volatility_ratio"))
    return _invert_and_normalize(vol)


# ---------------------------------------------------------------------------
# Filtres additionnels par régime
# ---------------------------------------------------------------------------

def apply_regime_filters(
    df: pd.DataFrame,
    snapshot: MarketRegimeSnapshot | None,
) -> pd.DataFrame:
    """Applique les filtres renforcés en régime défensif.

    Retourne un DataFrame filtré (peut être vide si tous les candidats
    sont rejetés).
    """
    if df.empty or snapshot is None:
        return df

    mode = str(getattr(snapshot, "mode", "normal") or "normal").strip().lower()
    if mode == "normal":
        return df

    result = df.copy()
    removed_count = 0

    # --- beta cap ---
    max_beta = DEFENSIVE_FILTER_OVERLAYS.get("max_beta_126")
    if max_beta is not None and "beta_126" in result.columns:
        beta_mask = result["beta_126"] > max_beta
        if beta_mask.any():
            removed_count += int(beta_mask.sum())
            result = result.loc[~beta_mask]

    # --- spread plus strict ---
    max_spread = DEFENSIVE_FILTER_OVERLAYS.get("max_spread_bps")
    if max_spread is not None and "spread_bps" in result.columns:
        spread_mask = result["spread_bps"] > max_spread
        if spread_mask.any():
            removed_count += int(spread_mask.sum())
            result = result.loc[~spread_mask]

    # --- market cap minimum ---
    min_mcap = DEFENSIVE_FILTER_OVERLAYS.get("min_market_cap")
    if min_mcap is not None and "market_cap" in result.columns:
        mcap_mask = result["market_cap"] < min_mcap
        if mcap_mask.any():
            removed_count += int(mcap_mask.sum())
            result = result.loc[~mcap_mask]

    # --- volatilité max ---
    max_atr = DEFENSIVE_FILTER_OVERLAYS.get("max_atr_pct_20")
    if max_atr is not None and "atr_pct_20" in result.columns:
        atr_mask = result["atr_pct_20"] > max_atr
        if atr_mask.any():
            removed_count += int(atr_mask.sum())
            result = result.loc[~atr_mask]

    if removed_count > 0:
        LOGGER.info(
            "Regime defensive filters removed %d candidates (mode=%s)",
            removed_count,
            mode,
        )

    return result


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def get_regime_weights(
    snapshot: MarketRegimeSnapshot | None,
    rotation_state: MomentumRotationState | None = None,
) -> dict[str, float]:
    """Retourne les poids factoriels adaptés au régime courant.

    Parameters
    ----------
    snapshot : MarketRegimeSnapshot or None
        Contexte de régime de marché.
    rotation_state : MomentumRotationState or None
        État du rotation factor. Si le momentum sous-performe, les poids
        défensifs sont utilisés même en régime ``normal``.

    Returns
    -------
    dict[str, float]
        Poids factoriels à appliquer.
    """
    if evaluate_momentum_rotation(rotation_state, snapshot):
        return dict(CAPITAL_PRESERVATION_WEIGHTS)
    return dict(NORMAL_WEIGHTS)


def apply_regime_weights(
    df: pd.DataFrame,
    snapshot: MarketRegimeSnapshot | None,
    config: AlphaScannerConfig | None = None,
    rotation_state: MomentumRotationState | None = None,
) -> pd.DataFrame:
    """Recalcule ``final_score`` avec les poids directionnels du régime.

    En régime ``normal`` (sans rotation forcée), la fonction est une non-op
    (retourne le DataFrame tel quel).  En régime défensif (``capital_preservation``,
    … ou rotation forcée par le tracker de momentum), le score final est
    recomposé en intégrant des facteurs qualité / low-beta / large-cap, et
    le DataFrame est filtré avec des seuils plus stricts.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame post-merge (doit contenir les colonnes de facteurs :
        ``trend_score``, ``vcp_score``, ``total_score``,
        ``relative_strength_index``, ``beta_126``, ``market_cap``,
        ``volatility_ratio``, etc.).
    snapshot : MarketRegimeSnapshot or None
        Contexte de régime pour la séance.
    config : AlphaScannerConfig or None
        Configuration du scanner (utilisée pour winsorisation).
    rotation_state : MomentumRotationState or None
        État du rotation factor pour forcer une rotation si le momentum
        sous-performe.

    Returns
    -------
    pd.DataFrame
        DataFrame avec ``final_score`` recalibré et colonnes défensives
        ajoutées.
    """
    if df.empty:
        return df

    # 1. Appliquer les filtres stricts du régime défensif
    filtered = apply_regime_filters(df, snapshot)

    if filtered.empty:
        return filtered

    # 2. Récupérer les poids du régime (avec rotation factor)
    weights = get_regime_weights(snapshot, rotation_state=rotation_state)
    mode = str(getattr(snapshot, "mode", "normal") or "normal").strip().lower()
    rotated = (
        rotation_state is not None
        and rotation_state.is_ready()
        and rotation_state.should_rotate()
    )

    # 3. En régime normal sans rotation, rien ne change
    if not rotated and mode == "normal":
        return filtered

    # 4. Calculer les scores défensifs
    result = filtered.copy()

    defensive_beta = _compute_defensive_beta_score(result)
    defensive_size = _compute_defensive_size_score(result)
    defensive_low_vol = _compute_defensive_low_vol_score(result)

    # 5. Récupérer les composantes existantes (ou les recalculer)
    trend_vcp_raw = 0.5 * (
        _safe_float_series(result.get("trend_score"))
        + _safe_float_series(result.get("vcp_score"))
    )
    total_score_norm = _safe_float_series(result.get("normalized_total_score"))
    rsi_norm = _safe_float_series(result.get("normalized_rsi"))

    # Si les colonnes normalisées n'existent pas encore, les calculer
    if total_score_norm.abs().sum() < 1e-12 and "total_score" in result.columns:
        total_score_norm = winsorize_and_normalize(
            _safe_float_series(result["total_score"])
        )
    if rsi_norm.abs().sum() < 1e-12 and "relative_strength_index" in result.columns:
        rsi_norm = winsorize_and_normalize(
            _safe_float_series(result["relative_strength_index"])
        )

    # 6. Composer le final_score avec les nouveaux poids
    result["trend_vcp_component"] = weights["trend_vcp"] * trend_vcp_raw
    result["total_score_component"] = weights["total_score"] * total_score_norm
    result["rsi_component"] = weights["rsi"] * rsi_norm
    result["defensive_beta_component"] = weights["defensive_beta"] * defensive_beta
    result["defensive_size_component"] = weights["defensive_size"] * defensive_size
    result["defensive_low_vol_component"] = weights["defensive_low_vol"] * defensive_low_vol

    result["raw_final_score"] = (
        result["trend_vcp_component"]
        + result["total_score_component"]
        + result["rsi_component"]
        + result["defensive_beta_component"]
        + result["defensive_size_component"]
        + result["defensive_low_vol_component"]
    )
    result["final_score"] = result["raw_final_score"]

    # 7. Mettre à jour l'explication
    if "selection_explanation" in result.columns:
        result["selector_signal_mode"] = result.get("selector_signal_mode", "factor_only")
        mask = result["final_score"] != trend_vcp_raw  # a été modifié
        result.loc[mask, "selector_signal_mode"] = f"regime_{mode}"

    LOGGER.info(
        "Regime scoring applied | mode=%s weights=%s candidates=%d",
        mode,
        {k: v for k, v in weights.items() if v > 0},
        len(result),
    )

    return result


__all__ = [
    "CAPITAL_PRESERVATION_WEIGHTS",
    "DEFENSIVE_FILTER_OVERLAYS",
    "NORMAL_WEIGHTS",
    "MomentumRotationState",
    "apply_regime_filters",
    "apply_regime_weights",
    "evaluate_momentum_rotation",
    "get_regime_weights",
]
