"""Profils de filtres swing cash — source de vérité unique.

Phase 2.1 → Phase 3.2.c du refactor (`prompt/refactor/plan.md`).

Avant Phase 3.2.c ce module n'était qu'une façade ré-exportant
``selector.strict_filter_profiles``. La dépendance a été inversée :

- la définition canonique de :class:`StrictFilterProfile` et de
  :data:`STRICT_SWING_CASH_FILTERS` vit désormais ici (``core/`` ne dépend
  d'aucun module métier amont) ;
- ``selector/strict_filter_profiles.py`` est devenu un alias
  rétro-compatible pour ne pas casser les imports historiques (IHM, scripts
  ``prompt/fix_swing/``…).

Phase 3.3.c/d ajoute deux extensions IEX :

- ``max_spread_bps_iex`` + ``min_quote_size`` : relâchement contrôlé du
  filtre ``spread_bps`` quand le carnet IEX est mince (``bid_size`` /
  ``ask_size`` faibles) — le rejet "spread trop large" est levé seulement si
  les tailles dépassent ``min_quote_size``.
- ``market_cap_max_age_days`` : TTL appliqué au filtre ``market_cap`` à
  partir de ``stock_metadata.market_cap_refreshed_at`` (alimenté en Phase
  3.1.e). ``None`` = TTL désactivé.

Phase 4 — ADV minimum adaptatif (LiquiditeDynamique.md P4) :
:func:`with_adaptive_adv` permet de dériver un profil dont le seuil
``min_avg_dollar_volume_20d`` est ajusté dynamiquement à la taille du compte.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd


@dataclass(frozen=True, slots=True)
class StrictFilterProfile:
    """Profil de seuils partagé entre scanner live, backfill PIT et reruns backtest."""

    name: str
    min_close: float
    min_avg_dollar_volume_20d: float
    max_volatility_ratio: float
    version: str = "v1"
    min_relative_strength_index: float | None = None
    min_high_52w_proximity: float | None = None
    min_weekly_trend_score: float | None = None
    min_atr_pct_20: float | None = None
    max_atr_pct_20: float | None = None
    min_market_cap: float | None = None
    min_beta_126: float | None = None
    max_spread_bps: float | None = None
    earnings_blackout_days: int | None = None
    require_above_ma200: bool = False
    # Phase 3.3.c — extensions IEX (cohabitent avec max_spread_bps).
    max_spread_bps_iex: float | None = None
    min_quote_size: float | None = None
    # Phase 3.3.d — TTL filtre market_cap (consommé par selector).
    market_cap_max_age_days: int | None = None

    def __post_init__(self) -> None:
        if self.min_close <= 0:
            raise ValueError("min_close doit être strictement positif.")
        if self.min_avg_dollar_volume_20d <= 0:
            raise ValueError("min_avg_dollar_volume_20d doit être strictement positif.")
        if self.max_volatility_ratio <= 0:
            raise ValueError("max_volatility_ratio doit être strictement positif.")
        if self.min_relative_strength_index is not None and self.min_relative_strength_index <= 0:
            raise ValueError("min_relative_strength_index doit être strictement positif lorsqu'il est renseigné.")
        if self.min_high_52w_proximity is not None and not 0 < self.min_high_52w_proximity <= 1:
            raise ValueError("min_high_52w_proximity doit être dans ]0, 1] lorsqu'il est renseigné.")
        if self.min_weekly_trend_score is not None and not 0 <= self.min_weekly_trend_score <= 1:
            raise ValueError("min_weekly_trend_score doit être dans [0, 1] lorsqu'il est renseigné.")
        if self.min_atr_pct_20 is not None and self.min_atr_pct_20 <= 0:
            raise ValueError("min_atr_pct_20 doit être strictement positif lorsqu'il est renseigné.")
        if self.max_atr_pct_20 is not None and self.max_atr_pct_20 <= 0:
            raise ValueError("max_atr_pct_20 doit être strictement positif lorsqu'il est renseigné.")
        if self.min_market_cap is not None and self.min_market_cap <= 0:
            raise ValueError("min_market_cap doit être strictement positif lorsqu'il est renseigné.")
        if self.min_beta_126 is not None and self.min_beta_126 <= 0:
            raise ValueError("min_beta_126 doit être strictement positif lorsqu'il est renseigné.")
        if self.max_spread_bps is not None and self.max_spread_bps <= 0:
            raise ValueError("max_spread_bps doit être strictement positif lorsqu'il est renseigné.")
        if self.max_spread_bps_iex is not None and self.max_spread_bps_iex <= 0:
            raise ValueError("max_spread_bps_iex doit être strictement positif lorsqu'il est renseigné.")
        if self.min_quote_size is not None and self.min_quote_size < 0:
            raise ValueError("min_quote_size doit être >= 0 lorsqu'il est renseigné.")
        if self.earnings_blackout_days is not None and self.earnings_blackout_days < 0:
            raise ValueError("earnings_blackout_days doit être positif ou nul lorsqu'il est renseigné.")
        if self.market_cap_max_age_days is not None and self.market_cap_max_age_days < 0:
            raise ValueError("market_cap_max_age_days doit être positif ou nul lorsqu'il est renseigné.")
        if (
            self.min_atr_pct_20 is not None
            and self.max_atr_pct_20 is not None
            and self.min_atr_pct_20 > self.max_atr_pct_20
        ):
            raise ValueError("min_atr_pct_20 ne peut pas être supérieur à max_atr_pct_20.")

    def to_backtest_filter_dict(self) -> dict[str, float]:
        payload: dict[str, float | bool] = {
            "min_close": self.min_close,
            "min_avg_dollar_volume_20d": self.min_avg_dollar_volume_20d,
            "max_volatility_ratio": self.max_volatility_ratio,
            "require_above_ma200": self.require_above_ma200,
        }
        optional_fields = {
            "min_relative_strength_index": self.min_relative_strength_index,
            "min_high_52w_proximity": self.min_high_52w_proximity,
            "min_weekly_trend_score": self.min_weekly_trend_score,
            "min_atr_pct_20": self.min_atr_pct_20,
            "max_atr_pct_20": self.max_atr_pct_20,
            "min_market_cap": self.min_market_cap,
            "min_beta_126": self.min_beta_126,
            "max_spread_bps": self.max_spread_bps,
            "earnings_blackout_days": self.earnings_blackout_days,
        }
        payload.update({key: value for key, value in optional_fields.items() if value is not None})
        return payload

    def to_scanner_config_kwargs(self) -> dict[str, float]:
        payload: dict[str, float | bool] = {
            "min_close": self.min_close,
            "liquidity_threshold": self.min_avg_dollar_volume_20d,
            "max_volatility_ratio": self.max_volatility_ratio,
            "require_above_ma200": self.require_above_ma200,
        }
        optional_fields = {
            "min_relative_strength_index": self.min_relative_strength_index,
            "min_high_52w_proximity": self.min_high_52w_proximity,
            "min_weekly_trend_score": self.min_weekly_trend_score,
            "min_atr_pct_20": self.min_atr_pct_20,
            "max_atr_pct_20": self.max_atr_pct_20,
            "min_market_cap": self.min_market_cap,
            "min_beta_126": self.min_beta_126,
            "max_spread_bps": self.max_spread_bps,
            "earnings_blackout_days": self.earnings_blackout_days,
        }
        payload.update({key: value for key, value in optional_fields.items() if value is not None})
        return payload

    def iex_extensions(self) -> dict[str, float | int | None]:
        """Phase 3.3.c/d — extensions IEX/TTL exposées séparément.

        Volontairement non incluses dans :meth:`to_scanner_config_kwargs` et
        :meth:`to_backtest_filter_dict` pour ne pas casser les consommateurs
        legacy qui ne connaissent pas encore ces clés. Le selector
        consommera ce payload directement (Phase 3.3.c/d).
        """
        return {
            "max_spread_bps_iex": self.max_spread_bps_iex,
            "min_quote_size": self.min_quote_size,
            "market_cap_max_age_days": self.market_cap_max_age_days,
        }

    def apply_to_frame(
        self,
        frame: pd.DataFrame,
        *,
        close_col: str = "latest_close",
        adv_col: str = "avg_dollar_volume_20d",
        volatility_ratio_col: str = "volatility_ratio",
        relative_strength_col: str = "relative_strength_index",
        atr_pct_col: str = "atr_pct_20",
        weekly_trend_col: str = "weekly_trend_score",
        ma200_col: str = "ma200",
        high_52w_col: str = "high_52w",
        market_cap_col: str = "market_cap",
        beta_col: str = "beta_126",
        spread_col: str = "spread_bps",
        earnings_blackout_col: str = "earnings_blackout",
    ) -> pd.DataFrame:
        if frame.empty:
            return frame.copy()

        required = {close_col, adv_col, volatility_ratio_col}
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise ValueError(f"Colonnes manquantes pour appliquer le profil {self.name}: {missing}")

        filtered = frame[
            (frame[close_col] >= self.min_close)
            & (frame[adv_col] >= self.min_avg_dollar_volume_20d)
            & frame[volatility_ratio_col].notna()
            & (frame[volatility_ratio_col] <= self.max_volatility_ratio)
        ]
        if self.min_relative_strength_index is not None:
            if relative_strength_col not in filtered.columns:
                raise ValueError(f"Colonne manquante pour appliquer {self.name}: {relative_strength_col}")
            filtered = filtered[
                filtered[relative_strength_col].notna()
                & (filtered[relative_strength_col] >= self.min_relative_strength_index)
            ]
        if self.require_above_ma200:
            required_ma_cols = {ma200_col, close_col}
            missing_ma_cols = sorted(required_ma_cols.difference(filtered.columns))
            if missing_ma_cols:
                raise ValueError(f"Colonnes manquantes pour appliquer {self.name}: {missing_ma_cols}")
            filtered = filtered[filtered[ma200_col].notna() & (filtered[close_col] > filtered[ma200_col])]
        if self.min_high_52w_proximity is not None:
            required_range_cols = {close_col, high_52w_col}
            missing_range_cols = sorted(required_range_cols.difference(filtered.columns))
            if missing_range_cols:
                raise ValueError(f"Colonnes manquantes pour appliquer {self.name}: {missing_range_cols}")
            filtered = filtered[
                filtered[high_52w_col].notna()
                & (filtered[high_52w_col] > 0)
                & ((filtered[close_col] / filtered[high_52w_col]) >= self.min_high_52w_proximity)
            ]
        if self.min_weekly_trend_score is not None:
            if weekly_trend_col not in filtered.columns:
                raise ValueError(f"Colonne manquante pour appliquer {self.name}: {weekly_trend_col}")
            filtered = filtered[
                filtered[weekly_trend_col].notna()
                & (filtered[weekly_trend_col] >= self.min_weekly_trend_score)
            ]
        if self.min_atr_pct_20 is not None or self.max_atr_pct_20 is not None:
            if atr_pct_col not in filtered.columns:
                raise ValueError(f"Colonne manquante pour appliquer {self.name}: {atr_pct_col}")
            atr_mask = filtered[atr_pct_col].notna()
            if self.min_atr_pct_20 is not None:
                atr_mask &= filtered[atr_pct_col] >= self.min_atr_pct_20
            if self.max_atr_pct_20 is not None:
                atr_mask &= filtered[atr_pct_col] <= self.max_atr_pct_20
            filtered = filtered[atr_mask]
        if self.min_market_cap is not None:
            if market_cap_col not in filtered.columns:
                raise ValueError(f"Colonne manquante pour appliquer {self.name}: {market_cap_col}")
            filtered = filtered[filtered[market_cap_col].notna() & (filtered[market_cap_col] >= self.min_market_cap)]
        if self.min_beta_126 is not None:
            if beta_col not in filtered.columns:
                raise ValueError(f"Colonne manquante pour appliquer {self.name}: {beta_col}")
            filtered = filtered[filtered[beta_col].notna() & (filtered[beta_col] >= self.min_beta_126)]
        if self.max_spread_bps is not None:
            if spread_col not in filtered.columns:
                raise ValueError(f"Colonne manquante pour appliquer {self.name}: {spread_col}")
            filtered = filtered[filtered[spread_col].notna() & (filtered[spread_col] <= self.max_spread_bps)]
        if self.earnings_blackout_days is not None:
            if earnings_blackout_col not in filtered.columns:
                raise ValueError(f"Colonne manquante pour appliquer {self.name}: {earnings_blackout_col}")
            filtered = filtered[(filtered[earnings_blackout_col].fillna(0).astype(int)) == 0]
        return filtered.copy()


def with_adaptive_adv(
    base: StrictFilterProfile,
    equity: float,
    max_position_weight: float = 0.10,
    target_pct_of_adv: float = 0.01,
) -> StrictFilterProfile:
    """Dérive un profil dont ``min_avg_dollar_volume_20d`` est adapté à l'equity.

    Le nouveau seuil = max(seuil adaptatif, seuil statique du profil de base).
    On ne descend **jamais** en dessous du seuil canonique.
    """
    from common.capital_presets import adaptive_min_adv

    adaptive = adaptive_min_adv(equity, max_position_weight, target_pct_of_adv)
    new_threshold = max(adaptive, base.min_avg_dollar_volume_20d)
    return replace(base, min_avg_dollar_volume_20d=new_threshold)


STRICT_SWING_CASH_FILTERS = StrictFilterProfile(
    name="strict_swing_cash",
    min_close=10.0,
    min_avg_dollar_volume_20d=30_000_000.0,
    max_volatility_ratio=0.9,
    min_relative_strength_index=100.0,
    min_high_52w_proximity=0.75,
    min_weekly_trend_score=1.0,
    min_atr_pct_20=0.015,
    max_atr_pct_20=0.06,
    min_market_cap=2_000_000_000.0,
    # Assouplissement prudent : accepte aussi des leaders un peu moins "high beta"
    # dans les régimes risk-off sans dégrader le filtre de tendance/prix.
    min_beta_126=0.8,
    # Les snapshots de quotes fin de séance peuvent être plus larges que le spread
    # réellement exécutable ; 40 bps reste strict tout en évitant un univers vide.
    max_spread_bps=40.0,
    earnings_blackout_days=3,
    require_above_ma200=True,
    # Phase 3.3.c — relâchement IEX documenté (cohabitation avec max_spread_bps).
    max_spread_bps_iex=65.0,
    min_quote_size=100.0,
    # Phase 3.3.d — TTL market cap par défaut (cohérent avec --refresh-stale-days=30).
    market_cap_max_age_days=45,
)


__all__ = ["STRICT_SWING_CASH_FILTERS", "StrictFilterProfile"]

