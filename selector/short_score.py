"""
selector/short_score.py
=======================
Option B — short_score dédié pour sélectionner les candidats short.

Calcule un score baissier composite (0-1, plus c'est élevé, plus le titre
est baissier) basé sur :
- trend_score faible (< 0.3)
- RSI bas (< 40)
- prix sous SMA50
- prix sous SMA200

Utilisé en remplacement du bottom-N final_score pour taguer les shorts.

Module canonique — tous les chemins (scanner, backtest, CLI live) doivent
passer par ``enrich_with_short_score()`` + ``tag_short_candidates()``.

Fournit aussi les helpers de pipeline Option C :
- ``ShortTrigger`` : dataclass de décision (short_by_regime, short_by_rotation, all_shorts)
- ``resolve_short_trigger()`` : détermine le déclencheur short live/backtest
- ``resolve_regime_adaptive_short_params()`` : boost des paramètres en capital_preservation
- ``inject_predicted_side()`` : injecte la colonne ``predicted_side`` depuis les prédictions ML
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from selector.regime_scoring import MomentumRotationState

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline Option C — helpers de décision (P1 2026-07-03)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ShortTrigger:
    """Résultat de la décision de déclenchement short (Option C).

    Attributes
    ----------
    short_by_regime : bool
        Régime capital_preservation avec allowed_short_entries=True.
    short_by_rotation : bool
        Rotation momentum (cumul < -3% sur 4 semaines).
    all_shorts : bool
        Les longs sont bloqués → tout candidat devient short.
    enabled : bool
        Short selling activé dans la config (short_selling_enabled).
    """
    short_by_regime: bool = False
    short_by_rotation: bool = False
    all_shorts: bool = False
    enabled: bool = False

    @property
    def active(self) -> bool:
        """True si un déclencheur short est actif."""
        return self.enabled and (self.short_by_regime or self.short_by_rotation)


def resolve_short_trigger(
    snap: object | None,
    rotation_state: "MomentumRotationState | None",
    short_selling_enabled: bool,
) -> ShortTrigger:
    """Détermine le déclencheur short (Option C) de manière unifiée.

    À utiliser dans le backtest ET le live pour éviter la duplication
    de la logique de détection.

    Parameters
    ----------
    snap : object or None
        Snapshot de régime (doit exposer allowed_short_entries, allowed_long_entries).
    rotation_state : MomentumRotationState or None
        État du tracker de rotation momentum.
    short_selling_enabled : bool
        ``risk_config.short_selling_enabled``.

    Returns
    -------
    ShortTrigger
        Décision complète avec tous les flags.
    """
    short_by_regime = (
        short_selling_enabled
        and snap is not None
        and bool(getattr(snap, "allowed_short_entries", False))
    )
    short_by_rotation = (
        short_selling_enabled
        and rotation_state is not None
        and rotation_state.is_ready()
        and rotation_state.should_rotate()
    )
    all_shorts = (
        snap is not None
        and not bool(getattr(snap, "allowed_long_entries", True))
    )
    return ShortTrigger(
        short_by_regime=short_by_regime,
        short_by_rotation=short_by_rotation,
        all_shorts=all_shorts,
        enabled=short_selling_enabled,
    )


def resolve_regime_adaptive_short_params(
    risk_config: object,
    short_by_regime: bool,
) -> tuple[int, float]:
    """Retourne (max_short_positions, min_score_for_short) adaptés au régime.

    En capital_preservation, les shorts sont boostés :
    - max positions : max(config, 4)
    - min score : min(config, 0.20)

    Parameters
    ----------
    risk_config : object
        Doit exposer short_max_positions (int) et short_min_score (float).
    short_by_regime : bool
        True si le régime est capital_preservation.

    Returns
    -------
    tuple[int, float]
        (max_short_positions, min_score_for_short)
    """
    eff_max = int(getattr(risk_config, "short_max_positions", 2))
    eff_min = float(getattr(risk_config, "short_min_score", 0.30))
    if short_by_regime:
        eff_max = max(eff_max, 4)
        eff_min = min(eff_min, 0.20)
    return eff_max, eff_min


def inject_predicted_side(
    day_df: pd.DataFrame,
    predictions_df: pd.DataFrame,
    trade_date: pd.Timestamp,
) -> pd.DataFrame:
    """Injecte la colonne ``predicted_side`` depuis les prédictions ML.

    Filtre sur ``trade_date``, mappe ``symbol → predicted_side``.

    Parameters
    ----------
    day_df : pd.DataFrame
        Candidats du jour (doit contenir ``symbol``).
    predictions_df : pd.DataFrame
        Prédictions ML (doit contenir ``trade_date``, ``symbol``, ``predicted_side``).
    trade_date : pd.Timestamp
        Date de trading à filtrer.

    Returns
    -------
    pd.DataFrame
        Copie de day_df avec colonne ``predicted_side`` ajoutée.
    """
    result = day_df.copy()
    if result.empty or predictions_df.empty:
        return result
    pred_day = predictions_df[predictions_df["trade_date"] == trade_date]
    if pred_day.empty or "predicted_side" not in pred_day.columns:
        return result
    side_map = dict(zip(pred_day["symbol"], pred_day["predicted_side"]))
    result["predicted_side"] = result["symbol"].map(side_map).fillna("")
    return result


def compute_short_score(
    day_df: pd.DataFrame,
    close_df: pd.DataFrame | None = None,
    trade_day: pd.Timestamp | None = None,
    *,
    sma_50_col: str = "sma_50",
    sma_200_col: str = "sma_200",
) -> pd.Series:
    """Calcule un score baissier composite (0-1).

    Parameters
    ----------
    day_df : pd.DataFrame
        Candidats du jour (doit contenir trend_score, relative_strength_index).
    close_df : pd.DataFrame or None
        OHLCV close (index=dates, columns=symbols). Si None, les facteurs SMA
        sont ignorés.
    trade_day : pd.Timestamp or None
        Date de trading pour chercher les prix dans close_df.
    sma_50_col, sma_200_col : str
        Noms des colonnes SMA si déjà présentes dans day_df.

    Returns
    -------
    pd.Series
        Score baissier entre 0.0 (pas baissier) et 1.0 (très baissier).
        Index aligné sur day_df.
    """
    n = len(day_df)
    if n == 0:
        return pd.Series(dtype=float)

    scores = pd.Series(0.0, index=day_df.index, dtype=float)

    # ── Facteur 1 : trend_score faible (< 0.3) → bearish ──────────
    if "trend_score" in day_df.columns:
        trend = day_df["trend_score"].astype(float).fillna(1.0)
        # trend_score ∈ [0, 1], on veut les valeurs faibles
        trend_bearish = (1.0 - trend.clip(0.0, 1.0)).clip(0.0, 1.0)
        scores += 0.30 * trend_bearish

    # ── Facteur 2 : RSI bas (< 40) → bearish ──────────────────────
    rsi_col = "relative_strength_index"
    if rsi_col in day_df.columns:
        rsi = day_df[rsi_col].astype(float).fillna(50.0)
        # RSI ∈ [0, 100], on veut RSI < 40 → bearish
        # Transforme : RSI=0 → 1.0, RSI=40 → 0.5, RSI=100 → 0.0
        rsi_bearish = (1.0 - rsi.clip(0.0, 100.0) / 100.0).clip(0.0, 1.0)
        scores += 0.25 * rsi_bearish

    # ── Facteur 3 : prix sous SMA50 ───────────────────────────────
    if sma_50_col in day_df.columns:
        sma50 = day_df[sma_50_col].astype(float)
        # Récupérer le prix (depuis close_df ou colonne last_close)
        price_col = None
        if "last_close" in day_df.columns:
            price_col = "last_close"
        elif close_df is not None and trade_day is not None:
            # On n'a pas de prix dans day_df, on laisse tomber ce facteur
            pass

        if price_col and price_col in day_df.columns:
            close_price = day_df[price_col].astype(float)
            below_sma50 = (close_price < sma50) & (sma50 > 0)
            scores += 0.25 * below_sma50.astype(float)

    # ── Facteur 4 : prix sous SMA200 ──────────────────────────────
    if sma_200_col in day_df.columns:
        sma200 = day_df[sma_200_col].astype(float)
        price_col = "last_close" if "last_close" in day_df.columns else None
        if price_col and price_col in day_df.columns:
            close_price = day_df[price_col].astype(float)
            below_sma200 = (close_price < sma200) & (sma200 > 0)
            scores += 0.20 * below_sma200.astype(float)

    return scores.clip(0.0, 1.0)


def enrich_with_short_score(
    day_df: pd.DataFrame,
    close_df: pd.DataFrame | None = None,
    trade_day: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Ajoute la colonne ``short_score``, les SMA, et un champ d'audit au DataFrame.

    Si ``close_df`` est fourni, les SMA50/200 sont calculés à la volée
    pour chaque symbole → ``short_score_quality = "full"``.
    Sinon → ``short_score_quality = "partial_missing_sma"`` (facteurs SMA ignorés).

    Returns
    -------
    pd.DataFrame
        DataFrame avec colonnes ajoutées : ``short_score``, ``short_score_quality``,
        et si ``close_df`` fourni : ``sma_50``, ``sma_200``, ``last_close``.
    """
    result = day_df.copy()

    has_sma = close_df is not None and trade_day is not None and "symbol" in result.columns

    # Calculer les SMA si close_df est fourni
    if has_sma:
        sma_50_vals = []
        sma_200_vals = []
        for _, row in result.iterrows():
            symbol = str(row["symbol"])
            sma_50_vals.append(compute_sma_column(close_df, symbol, trade_day, 50))
            sma_200_vals.append(compute_sma_column(close_df, symbol, trade_day, 200))
        result["sma_50"] = sma_50_vals
        result["sma_200"] = sma_200_vals
        result["last_close"] = [
            _get_close(close_df, str(row["symbol"]), trade_day)
            for _, row in result.iterrows()
        ]

    result["short_score"] = compute_short_score(result, close_df, trade_day)
    result["short_score_quality"] = "full" if has_sma else "partial_missing_sma"

    if not has_sma:
        LOGGER.info(
            "short_score_quality=partial_missing_sma (close_df absent, "
            "facteurs SMA50/SMA200 ignorés pour %d symboles)",
            len(result),
        )

    return result


def _get_close(
    close_df: pd.DataFrame,
    symbol: str,
    trade_day: pd.Timestamp,
) -> float | None:
    """Récupère le prix de clôture pour un symbole à une date donnée."""
    try:
        if symbol not in close_df.columns:
            return None
        val = close_df.at[trade_day, symbol]
        return float(val) if pd.notna(val) else None
    except (KeyError, IndexError):
        return None


def compute_sma_column(
    close_df: pd.DataFrame,
    symbol: str,
    trade_day: pd.Timestamp,
    window: int = 50,
) -> float | None:
    """Calcule la SMA(window) pour un symbole à une date donnée.

    Parameters
    ----------
    close_df : pd.DataFrame
        OHLCV close (index=dates, columns=symbols).
    symbol : str
        Symbole à analyser.
    trade_day : pd.Timestamp
        Date de référence.
    window : int
        Fenêtre de la SMA (50 ou 200).

    Returns
    -------
    float or None
        Valeur de la SMA, ou None si pas assez de données.
    """
    if close_df is None or symbol not in close_df.columns:
        return None
    try:
        # Trouver la position du trade_day dans l'index
        loc = close_df.index.get_loc(trade_day)
        if isinstance(loc, slice):
            return None
        # Prendre les window jours avant trade_day (inclus)
        start_loc = max(0, loc - window + 1)
        prices = close_df.iloc[start_loc:loc + 1][symbol].dropna()
        if len(prices) < min(window // 2, 20):
            return None
        return float(prices.mean())
    except (KeyError, IndexError):
        return None


# ---------------------------------------------------------------------------
# Tagging short — module canonique (P1 2026-07-03)
# ---------------------------------------------------------------------------


def tag_short_candidates(
    day_df: pd.DataFrame,
    *,
    max_short_positions: int = 2,
    min_score_for_short: float = 0.30,
    max_long_positions: int = 3,
    all_shorts: bool = False,
) -> pd.DataFrame:
    """Tag les candidats comme ``side="sell"`` (short).

    Deux modes :
    - ``all_shorts=False`` (rotation momentum) : seuls les bottom-N (score le
      plus bas, sous ``min_score_for_short``) sont tagués ``"sell"``.
    - ``all_shorts=True`` (régime capital_preservation) : TOUS les candidats
      sont tagués ``"sell"`` car les longs sont bloqués par le régime.

    La colonne de score est choisie automatiquement :
    ``short_score`` > ``score`` > ``final_score_sentiment`` > ``final_score``.

    Parameters
    ----------
    day_df : pd.DataFrame
        Candidats du jour. Doit contenir une colonne de score.
    max_short_positions : int
        Nombre maximum de shorts à taguer (mode rotation).
    min_score_for_short : float
        Score minimum/maximum pour être éligible short (selon la colonne).
    max_long_positions : int
        Nombre maximum de longs à conserver (mode rotation).
    all_shorts : bool
        Si True, tous les candidats deviennent ``side="sell"``.

    Returns
    -------
    pd.DataFrame
        DataFrame avec colonne ``side`` ajoutée/mise à jour.
    """
    if day_df.empty:
        return day_df

    result = day_df.copy()

    if all_shorts:
        result["side"] = "sell"
        return result

    # ── ML Sprint 6 — si le ML prédit le side, priorité absolue ──
    ml_side_col = None
    if "predicted_side" in result.columns:
        ml_side_col = "predicted_side"

    result["side"] = "buy"

    if ml_side_col:
        ml_shorts = result[ml_side_col] == "short"
        result.loc[ml_shorts, "side"] = "sell"
        n_ml = int(ml_shorts.sum())
        if n_ml > max_short_positions:
            ml_indices = result.index[ml_shorts][max_short_positions:]
            result.loc[ml_indices, "side"] = "buy"

    if not ml_side_col:
        if "short_score" in result.columns:
            score_col = "short_score"
            ascending = False
        elif "score" in result.columns:
            score_col = "score"
            ascending = True
        elif "final_score_sentiment" in result.columns:
            score_col = "final_score_sentiment"
            ascending = True
        elif "final_score" in result.columns:
            score_col = "final_score"
            ascending = True
        else:
            score_col = None
            ascending = True

        if score_col is None or score_col not in result.columns:
            return result

        sorted_idx = result[score_col].argsort().values
        if not ascending:
            sorted_idx = sorted_idx[::-1]

        short_count = 0
        for pos in sorted_idx:
            if short_count >= max_short_positions:
                break
            score_val = float(result.iloc[pos][score_col]) if pd.notna(result.iloc[pos][score_col]) else 0.0
            if min_score_for_short <= 0:
                result.iloc[pos, result.columns.get_loc("side")] = "sell"
                short_count += 1
            elif ascending and score_val <= min_score_for_short:
                result.iloc[pos, result.columns.get_loc("side")] = "sell"
                short_count += 1
            elif not ascending and score_val >= min_score_for_short:
                result.iloc[pos, result.columns.get_loc("side")] = "sell"
                short_count += 1

    # ── Audit : journaliser la qualité du short_score si dispo ──
    if "short_score_quality" in result.columns:
        partial_mask = (result["side"] == "sell") & (result["short_score_quality"] == "partial_missing_sma")
        n_partial = int(partial_mask.sum())
        if n_partial > 0:
            LOGGER.warning(
                "tag_short_candidates: %d shorts tagués avec short_score partiel "
                "(SMA50/SMA200 manquantes — score dégradé)",
                n_partial,
            )

    return result
