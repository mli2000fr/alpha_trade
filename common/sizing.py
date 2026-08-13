"""common/sizing.py — SizingConfig partagé (backtest + live).

P2-1 inc.2/3 : ``rank_weighted`` + multiplicateurs sectoriels.
Extrait de ``backtesting/risk_overlay.py`` pour être consommé par
``risk_management`` sans import circulaire. ``backtesting/risk_overlay``
ré-exporte ces symboles (rétrocompatibilité).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd


SizingMode = Literal["equal_weight", "conviction_weighted", "rank_weighted"]


@dataclass(slots=True, frozen=True)
class SizingConfig:
    """Sizing config (equal_weight | conviction_weighted | rank_weighted).

    ``rank_weighted`` (P2-1 inc.2) : pondère chaque candidat du jour par
    ``N + 1 - selection_rank`` (N = rang max du jour) → le top du classement
    reçoit ~N fois le poids du dernier. Fallback equal si le rang est absent.
    """

    mode: SizingMode = "equal_weight"
    min_weight_pct: float = 0.005
    max_weight_pct: float = 0.20
    # P2-1 inc.3 : multiplicateurs par secteur (nom GICS/sub-industry → facteur).
    # Appliqués après le calcul du poids de base (equal/conviction/rank), avant clip+normalisation.
    sector_multipliers: dict[str, float] | None = field(default=None, compare=False)
    # Mapping symbole → secteur (fallback quand la colonne `sector` des candidats est absente/Unknown).
    sector_map: dict[str, str] | None = field(default=None, compare=False)

    def compute_weights(self, candidates: pd.DataFrame, max_positions: int) -> pd.Series:
        if candidates.empty:
            return pd.Series(dtype=float)
        base_weight = 1.0 / max(max_positions, 1)
        if self.mode == "rank_weighted":
            rank_col = "selection_rank" if "selection_rank" in candidates.columns else "rank" if "rank" in candidates.columns else None
            if rank_col is None:
                return pd.Series(base_weight, index=candidates.index, dtype=float)
            ranks = pd.to_numeric(candidates[rank_col], errors="coerce")
            if ranks.notna().sum() == 0:
                return pd.Series(base_weight, index=candidates.index, dtype=float)
            n_max = float(max(ranks.max(), 1.0))
            scores = (n_max + 1.0 - ranks.fillna(n_max)).clip(lower=0.0)
            total = float(scores.sum())
            if total <= 0:
                return pd.Series(base_weight, index=candidates.index, dtype=float)
            weights = scores / total
        elif self.mode == "conviction_weighted" and "conviction" in candidates.columns:
            conv = candidates["conviction"].fillna(0.0).clip(lower=0.0)
            total = float(conv.sum())
            if total <= 0:
                return pd.Series(base_weight, index=candidates.index, dtype=float)
            weights = conv / total
        else:
            weights = pd.Series(base_weight, index=candidates.index, dtype=float)
        if self.sector_multipliers:
            # ── P2-1 inc.3 : multiplicateurs sectoriels (scale puis clip+normalisation) ──
            weights = self._apply_sector_multipliers(candidates, weights)
            weights = weights.clip(lower=self.min_weight_pct, upper=self.max_weight_pct)
            weights = weights / max(weights.sum(), 1e-9)
        elif self.mode != "equal_weight":
            weights = weights.clip(lower=self.min_weight_pct, upper=self.max_weight_pct)
            weights = weights / max(weights.sum(), 1e-9)
        return weights

    def _apply_sector_multipliers(self, candidates: pd.DataFrame, weights: pd.Series) -> pd.Series:
        if not self.sector_multipliers:
            return weights
        sectors: pd.Series | None = None
        if "sector" in candidates.columns:
            sectors = candidates["sector"].astype(str).where(
                candidates["sector"].notna() & (candidates["sector"].astype(str) != "Unknown")
            )
        if self.sector_map and "symbol" in candidates.columns:
            mapped = (
                candidates["symbol"].astype(str).str.upper()
                .map({str(s).strip().upper(): v for s, v in self.sector_map.items()})
            )
            sectors = sectors.combine_first(mapped) if sectors is not None else mapped
        if sectors is None:
            return weights
        factors = sectors.map(self.sector_multipliers).fillna(1.0)
        return weights * factors
