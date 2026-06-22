"""
backtesting/microstructure.py
==============================
Phase B (refactor/backtesting/audit_plan.md) — modélisation plus réaliste de
la micro-structure : slippage volume-aware, gap d'ouverture, stop-loss dur,
résolution intra-bar TP/TS.

Toutes les fonctions sont **pures** (pas d'I/O DB) pour rester testables et
réutilisables côté live (cohérence backtest/exécution).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# B.1 — Slippage volume-aware
# ---------------------------------------------------------------------------


SlippageModel = Literal["fixed", "linear", "sqrt"]

# ── P4 — Modèle d'exécution intraday ──

ExecutionModel = Literal["next_open", "arrival_price", "twap", "vwap"]


@dataclass(slots=True, frozen=True)
class ExecutionModelConfig:
    """Configuration du modèle d'exécution intraday.

    - ``model`` : modèle de prix d'exécution.
        * ``next_open`` (défaut historique) → exécution au prix d'ouverture de J+1.
        * ``arrival_price`` → open + slippage directionnel estimé (moitié du range).
        * ``twap`` → (open + close) / 2 — simule un échelonnement régulier.
        * ``vwap`` → (open + high + low + close) / 4 — pondéré par les volumes.
    - ``split_threshold_adv_pct`` : seuil en % de l'ADV au-delà duquel l'ordre
      est échelonné sur la journée. 0.0 = désactivé, 0.01 = 1% ADV.
    - ``split_slices`` : nombre de tranches pour l'échelonnement TWAP simulé.
    - ``arrival_slippage_factor`` : multiplicateur du slippage directionnel pour
      le modèle arrival_price (1.0 = demi-range, 2.0 = range complet).
    """

    model: ExecutionModel = "next_open"
    split_threshold_adv_pct: float = 0.0  # 0 = pas d'échelonnement
    split_slices: int = 5
    arrival_slippage_factor: float = 0.5  # 0.5 = demi-range journalière


# ── B.1 — Slippage volume-aware ──


@dataclass(slots=True, frozen=True)
class SlippageConfig:
    """Configuration du modèle de slippage **additionnel**.

    Les coûts ``commission_bps`` + ``slippage_bps`` de ``BacktestConfig``
    restent appliqués via ``fees_pct``. Ce slippage volume-aware vient
    **en plus** quand activé.

    - ``base_bps``    : composante fixe additionnelle (≈ moitié spread).
    - ``impact_coef`` : coefficient impact en bps appliqué au ratio
                        ``size_usd / adv_usd``.
    - ``model``       : forme fonctionnelle.
        * ``fixed`` (défaut, neutre) → renvoie ``base_bps`` (= 0 par défaut).
        * ``linear`` → base + impact * (size/ADV).
        * ``sqrt`` → base + impact * sqrt(size/ADV) (Almgren-Chriss).
    """

    base_bps: float = 0.0
    impact_coef: float = 0.0
    model: SlippageModel = "fixed"

    def compute_bps(self, size_usd: float, adv_usd: float | None) -> float:
        """Retourne le slippage en bps pour une trade donnée."""
        if self.model == "fixed" or not adv_usd or adv_usd <= 0:
            return float(self.base_bps)
        ratio = max(0.0, float(size_usd) / float(adv_usd))
        if self.model == "linear":
            return float(self.base_bps + self.impact_coef * ratio)
        # sqrt par défaut
        return float(self.base_bps + self.impact_coef * np.sqrt(ratio))


def compute_adv_usd(
    close: pd.DataFrame,
    volume: pd.DataFrame | None,
    *,
    window: int = 20,
) -> pd.DataFrame:
    """ADV (average daily volume) en USD, fenêtre glissante.

    Retourne un DataFrame de même shape que ``close``. Si ``volume`` est
    indisponible, retourne un DataFrame de NaN (le slippage retombera sur
    le mode ``fixed``).
    """
    if volume is None or volume.empty:
        return pd.DataFrame(np.nan, index=close.index, columns=close.columns)
    dollar_vol = close.fillna(0.0) * volume.fillna(0.0)
    return dollar_vol.rolling(window=window, min_periods=1).mean()


# ---------------------------------------------------------------------------
# B.2 — Stop-loss initial dur
# B.3 — Gap d'ouverture
# B.4 — Résolution intra-bar TP/TS
# ---------------------------------------------------------------------------


IntraBarPriority = Literal["conservative", "tp_first", "ts_first", "random"]


@dataclass(slots=True)
class MicrostructureConfig:
    """Bundle des options micro-structure activables sur le simulateur.

    - ``slippage``           : configuration du modèle de slippage.
    - ``initial_stop_pct``   : stop-loss dur (initial). 0.0 = désactivé.
    - ``max_entry_gap_pct``  : skip d'entrée si le gap entre close[J] et
                               open[J+1] dépasse ce seuil. 0.0 = désactivé.
    - ``intrabar_priority``  : politique de résolution si TP et TS touchés
                               dans la même bar.
        * ``conservative`` (défaut historique) → TS prioritaire.
        * ``tp_first``     → TP prioritaire (optimiste).
        * ``ts_first``     → équivalent à ``conservative`` (alias clarté).
        * ``random``       → tirage uniforme reproductible (seed externe).
    - ``execution_model``    : P4 — modèle de prix d'exécution intraday.
    """

    slippage: SlippageConfig = field(default_factory=SlippageConfig)
    initial_stop_pct: float = 0.0
    max_entry_gap_pct: float = 0.0
    intrabar_priority: IntraBarPriority = "conservative"
    execution_model: ExecutionModelConfig = field(default_factory=ExecutionModelConfig)

    def is_default(self) -> bool:
        """Compat : retourne True si le bundle reproduit le comportement legacy."""
        return (
            self.slippage.model == "fixed"
            and self.initial_stop_pct == 0.0
            and self.max_entry_gap_pct == 0.0
            and self.intrabar_priority in ("conservative", "ts_first")
            and self.execution_model.model == "next_open"
        )


def should_skip_entry_for_gap(
    previous_close: float | None,
    next_open: float,
    *,
    max_gap_pct: float,
) -> bool:
    """B.3 — décide si l'on annule l'entrée à cause d'un gap d'ouverture.

    Renvoie True si ``|next_open - previous_close| / previous_close > max_gap_pct``.
    Si ``max_gap_pct <= 0`` ou previous_close indispo → False.
    """
    if max_gap_pct <= 0 or previous_close is None or previous_close <= 0:
        return False
    if not np.isfinite(next_open) or not np.isfinite(previous_close):
        return False
    gap = abs(float(next_open) - float(previous_close)) / float(previous_close)
    return gap > float(max_gap_pct)


@dataclass(slots=True)
class IntraBarResolution:
    """Résultat de la résolution intra-bar des sorties bracket."""

    triggered: bool
    exit_price: float
    exit_reason: str  # 'take_profit' | 'trailing_stop' | 'initial_stop'


def resolve_intrabar_exit(
    *,
    day_high: float,
    day_low: float,
    take_profit_price: float,
    trailing_stop_price: float,
    initial_stop_price: float | None,
    priority: IntraBarPriority,
    rng: np.random.Generator | None = None,
) -> IntraBarResolution:
    """B.2/B.4 — résout la sortie quand plusieurs niveaux sont touchés.

    Ordre d'évaluation :
    1. ``initial_stop_price`` (si fourni) : strict, si touché on sort.
    2. TP / TS : selon ``priority``.
    """
    hit_initial_stop = initial_stop_price is not None and day_low <= initial_stop_price
    hit_tp = day_high >= take_profit_price
    hit_ts = day_low <= trailing_stop_price

    # Initial stop dur prioritaire sur tout le reste — protège un trade bull.
    if hit_initial_stop and (hit_ts or initial_stop_price >= trailing_stop_price):
        # Si ts et initial_stop sont tous deux touchés, prend le plus haut (perte
        # plus faible mais quand même une protection contre l'aléa intraday).
        chosen = max(trailing_stop_price, float(initial_stop_price))
        return IntraBarResolution(True, chosen, "initial_stop")

    if not hit_tp and not hit_ts:
        return IntraBarResolution(False, 0.0, "none")

    if hit_tp and not hit_ts:
        return IntraBarResolution(True, take_profit_price, "take_profit")
    if hit_ts and not hit_tp:
        return IntraBarResolution(True, trailing_stop_price, "trailing_stop")

    # Conflit : TP ET TS touchés sur la même bar.
    if priority == "tp_first":
        return IntraBarResolution(True, take_profit_price, "take_profit")
    if priority == "random":
        if rng is None:
            rng = np.random.default_rng(0)
        if rng.random() < 0.5:
            return IntraBarResolution(True, take_profit_price, "take_profit")
        return IntraBarResolution(True, trailing_stop_price, "trailing_stop")
    # conservative / ts_first → trailing stop gagne (comportement historique).
    return IntraBarResolution(True, trailing_stop_price, "trailing_stop")


# ── P4 — Fonction pure de calcul du prix d'exécution ──


def compute_execution_price(
    *,
    model: ExecutionModelConfig,
    side: str,
    open_price: float,
    high_price: float | None = None,
    low_price: float | None = None,
    close_price: float | None = None,
    adv_usd: float | None = None,
    notional: float | None = None,
) -> float:
    """Calcule le prix d'exécution estimé selon le modèle intraday.

    - ``next_open`` : open (comportement historique).
    - ``arrival_price`` : open + slippage directionnel estimé.
        Long  → open + factor * (high - low)  → exécution plus chère (achat).
        Short → open - factor * (high - low)  → exécution moins chère (vente).
    - ``twap`` : (open + close) / 2.
    - ``vwap`` : (open + high + low + close) / 4.

    Retourne toujours un float fini > 0.
    """
    if model.model == "next_open":
        return float(open_price)

    is_short = side.strip().lower() == "sell"

    if model.model == "arrival_price":
        if high_price is not None and low_price is not None and np.isfinite(high_price) and np.isfinite(low_price):
            half_range = (float(high_price) - float(low_price)) * float(model.arrival_slippage_factor)
            if is_short:
                return float(open_price) - half_range  # short: on vend, slippage défavorable = prix plus bas
            else:
                return float(open_price) + half_range  # long: on achète, slippage défavorable = prix plus haut
        return float(open_price)

    if model.model == "twap":
        if close_price is not None and np.isfinite(close_price):
            return (float(open_price) + float(close_price)) / 2.0
        return float(open_price)

    if model.model == "vwap":
        h = float(high_price) if high_price is not None and np.isfinite(high_price) else float(open_price)
        l = float(low_price) if low_price is not None and np.isfinite(low_price) else float(open_price)
        c = float(close_price) if close_price is not None and np.isfinite(close_price) else float(open_price)
        return (float(open_price) + h + l + c) / 4.0

    return float(open_price)


def should_split_order(
    *,
    model: ExecutionModelConfig,
    notional_usd: float,
    adv_usd: float | None,
) -> bool:
    """Décide si l'ordre doit être échelonné (taille > seuil ADV)."""
    if model.split_threshold_adv_pct <= 0:
        return False
    if adv_usd is None or adv_usd <= 0:
        return False
    if notional_usd <= 0:
        return False
    return (notional_usd / adv_usd) > float(model.split_threshold_adv_pct)


__all__ = [
    "ExecutionModel",
    "ExecutionModelConfig",
    "IntraBarPriority",
    "IntraBarResolution",
    "MicrostructureConfig",
    "SlippageConfig",
    "SlippageModel",
    "compute_adv_usd",
    "compute_execution_price",
    "resolve_intrabar_exit",
    "should_skip_entry_for_gap",
    "should_split_order",
]


