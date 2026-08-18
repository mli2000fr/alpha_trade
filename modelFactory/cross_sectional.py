"""modelFactory/cross_sectional.py — Features cross-sectionnelles et sectorielles PIT-safe.

Refactored to load bars symbol-by-symbol instead of all at once,
avoiding massive MySQL queries that exceed max_allowed_packet.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import Table, MetaData, select

from modelFactory.features import _build_adjusted_price_frame, _range_position, _rsi

LOGGER = logging.getLogger(__name__)

CROSS_SECTIONAL_FEATURE_COLUMNS: list[str] = [
    "ret_20_rank",
    "ret_60_rank",
    "relative_strength_20_rank",
    "relative_strength_60_rank",
    "volatility_20_rank",
    "dollar_volume_20_rank",
    "volume_ratio_20_rank_xs",
    "range_position_20_rank",
]

SECTOR_FEATURE_COLUMNS: list[str] = [
    "sector_ret_5",
    "sector_ret_20",
    "sector_ret_60",
    "sector_vol_20",
    "sector_relative_strength_20",
    "sector_dollar_volume_20",
    "sector_symbol_count",
    "stock_vs_sector_ret_5",
    "stock_vs_sector_ret_20",
    "stock_vs_sector_ret_60",
]

# ── Approche 2 — Stacking : rang global comme feature ──
# Le Global Ranking Model prédit le rendement futur → rang percentil dans l'univers.
# Injecté comme feature, le per-symbol peut ajuster sa conviction selon la position
# relative du titre (top 10% = renforcer long, bottom 10% = renforcer short).
GLOBAL_PRED_FEATURE_COLUMNS: list[str] = [
    "global_rank_3",
    "global_rank_5",
    "global_rank_10",
    "global_rank_15",
    "global_rank_20",
    "global_rank",  # backward compat
]

# ── Sprint 2026-07-25 : Sector-neutralisation ──
# Chaque feature est ajustée par soustraction de la médiane sectorielle.
# Isole l'alpha spécifique au titre, indépendamment de la tendance du secteur.

SECTOR_NEUTRAL_SOURCE_FEATURES: list[str] = [
    # Techniques (Sprint 2026-07-25)
    "momentum_20", "momentum_60",
    "relative_strength_20", "relative_strength_60",
    "rolling_volatility_20", "rolling_volatility_60",
    "rsi_14",
    "sma20_distance", "sma50_distance",
    "volume_ratio_20",
    # Fondamentales (Sprint 2026-08-01) — neutralisation sectorielle indispensable.
    # Un PE de 15 est "cher" dans l'Énergie mais "donné" dans la Tech.
    # Sans neutralisation, le modèle fait un pari sectoriel, pas du stock-picking.
    "fund_pe_ratio", "fund_pb_ratio", "fund_ev_to_ebitda",
    "fund_roa", "fund_roe",
]

def _sector_neutral_column_name(source_col: str) -> str:
    return f"{source_col}_sector_neutral"

SECTOR_NEUTRAL_FEATURE_COLUMNS: list[str] = [
    _sector_neutral_column_name(c) for c in SECTOR_NEUTRAL_SOURCE_FEATURES
]

# ── Sprint 2026-08-02 : Z-score sectoriel pour fondamentales ──
# Normalisation (valeur − médiane secteur) / MAD secteur → échelle comparable
# entre secteurs. Un PE de 25 dans la Tech (Z≈−1) vs Utilities (Z≈+3).
SECTOR_ZSCORE_SOURCE_FEATURES: list[str] = [
    "fund_pe_ratio", "fund_pb_ratio", "fund_ev_to_ebitda",
    "fund_roa", "fund_roe",
    "fund_debt_to_equity", "fund_eps_to_price",
    "fund_net_margin", "fund_operating_margin", "fund_gross_margin",
    "fund_revenue_growth_yoy", "fund_eps_growth_yoy",
    "fund_current_ratio",
]

def _sector_zscore_column_name(source_col: str) -> str:
    return f"{source_col}_sector_zscore"

SECTOR_ZSCORE_FEATURE_COLUMNS: list[str] = [
    _sector_zscore_column_name(c) for c in SECTOR_ZSCORE_SOURCE_FEATURES
]

# ── Approche 2 (Sprint 2026-07-21) — Features cross-symbol exclusives ──
# Ces features n'ont de sens qu'au niveau cross-symbol (agrégation intra-secteur).
# Elles sont injectées UNIQUEMENT dans le Global Model (pas dans les per-symbol).
# Le per-symbol ne peut pas les calculer seul — il lui faut la vision transverse.
GLOBAL_EXCLUSIVE_FEATURE_COLUMNS: list[str] = [
    "sector_breadth_20",              # % de titres du secteur avec ret_20 > 0
    "sector_dispersion_20",           # écart-type des ret_20 intra-secteur
    "sector_concentration_20",        # concentration du dollar volume (top-3 / total)
    "symbol_rank_in_sector_20",       # rang percentil du ret_20 du titre dans son secteur
    "stock_vs_sector_vol_ratio",      # volatilité du titre / volatilité moyenne du secteur
    "sector_momentum_spread_20",      # spread momentum (top décile - bottom décile) intra-secteur
]

RAW_CROSS_SECTIONAL_COLUMNS_MAP: dict[str, str] = {
    "ret_20": "ret_20_rank",
    "ret_60": "ret_60_rank",
    "relative_strength_20_value": "relative_strength_20_rank",
    "relative_strength_60_value": "relative_strength_60_rank",
    "volatility_20": "volatility_20_rank",
    "dollar_volume_20": "dollar_volume_20_rank",
    "volume_ratio_20": "volume_ratio_20_rank_xs",
    "range_position_20": "range_position_20_rank",
}

RAW_CROSS_SECTIONAL_COLS = list(RAW_CROSS_SECTIONAL_COLUMNS_MAP.keys())


def _compute_symbol_raw_values(
    sym_df: pd.DataFrame,
    benchmark_returns: pd.DataFrame | None,
) -> pd.DataFrame:
    """Compute raw cross-sectional values for a single symbol (all dates)."""
    sym_sorted = sym_df.sort_values("date").reset_index(drop=True)
    prices = _build_adjusted_price_frame(sym_sorted)
    close = prices["close"]
    volume = pd.to_numeric(sym_sorted["volume"], errors="coerce").astype(float)
    daily_return = close.pct_change(fill_method=None)
    dollar_volume = close * volume

    part = pd.DataFrame(
        {
            "symbol": sym_sorted["symbol"].iloc[0] if "symbol" in sym_sorted.columns else "?",
            "date": pd.to_datetime(sym_sorted["date"]),
            "ret_5": close / close.shift(5) - 1.0,
            "ret_20": close / close.shift(20) - 1.0,
            "ret_60": close / close.shift(60) - 1.0,
            "volatility_20": daily_return.rolling(20).std(),
            "dollar_volume_20": dollar_volume.rolling(20).mean(),
            "volume_ratio_20": volume / volume.rolling(20).mean().clip(lower=1.0),
            "range_position_20": _range_position(close, 20),
            # ── Sector-neutral source features (Sprint 2026-07-25) ──
            "momentum_20": close / close.shift(20) - 1.0,
            "momentum_60": close / close.shift(60) - 1.0,
            "rolling_volatility_60": daily_return.rolling(60).std(),
            "rsi_14": _rsi(close, 14),
        }
    )
    # SMA distances
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    part["sma20_distance"] = (close - sma20) / sma20.clip(lower=1e-8)
    part["sma50_distance"] = (close - sma50) / sma50.clip(lower=1e-8)
    # Relative strength (raw, before ranking)
    if benchmark_returns is not None and not benchmark_returns.empty:
        part = part.merge(benchmark_returns, on="date", how="left")
        _br20 = part.get("benchmark_return_20", pd.Series(0.0, index=part.index))
        _br60 = part.get("benchmark_return_60", pd.Series(0.0, index=part.index))
        part["relative_strength_20_value"] = part["ret_20"] - _br20
        part["relative_strength_60_value"] = part["ret_60"] - _br60
        part["relative_strength_20"] = part["relative_strength_20_value"]
        part["relative_strength_60"] = part["relative_strength_60_value"]
    else:
        part["relative_strength_20_value"] = part["ret_20"]
        part["relative_strength_60_value"] = part["ret_60"]
        part["relative_strength_20"] = part["ret_20"]
        part["relative_strength_60"] = part["ret_60"]
    return part


def _build_benchmark_returns(
    benchmark_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """Build benchmark return columns for relative strength computation."""
    if benchmark_df is None or benchmark_df.empty:
        return pd.DataFrame()
    bench = benchmark_df.copy()
    bench["date"] = pd.to_datetime(bench["date"])
    bench = bench.sort_values("date").reset_index(drop=True)
    prices = _build_adjusted_price_frame(bench)
    close = prices["close"]
    out = pd.DataFrame({"date": bench["date"]})
    out["benchmark_return_20"] = close / close.shift(20) - 1.0
    out["benchmark_return_60"] = close / close.shift(60) - 1.0
    return out


def _load_sector_mapping(engine) -> dict[str, str]:
    """Charge le mapping symbole -> secteur depuis ``stock_metadata``.

    Returns
    -------
    dict[str, str]
        ``{symbol: sector_name}``, symboles uppercase, secteurs stripped.
    """
    try:
        meta = MetaData()
        stock_metadata = Table("stock_metadata", meta, autoload_with=engine)
        sector_col = None
        for candidate in ("provider_sector", "sector"):
            if candidate in stock_metadata.c:
                sector_col = stock_metadata.c[candidate]
                break
        if sector_col is None:
            LOGGER.warning("_load_sector_mapping: no sector column found in stock_metadata")
            return {}

        stmt = select(stock_metadata.c.symbol, sector_col).where(
            sector_col.isnot(None),
            sector_col != "",
        )
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()

        mapping: dict[str, str] = {}
        for sym, sec in rows:
            sym_str = str(sym).strip().upper()
            sec_str = str(sec).strip()
            if sym_str and sec_str:
                mapping[sym_str] = sec_str
        LOGGER.info("_load_sector_mapping: loaded %d symbols in %d sectors",
                     len(mapping), len(set(mapping.values())))
        return mapping
    except Exception:
        LOGGER.warning("_load_sector_mapping: failed to load sector mapping", exc_info=True)
        return {}


# ── GICS Sector grouping (Sprint 2026-08-03) ──
# Maps DB sub-industry names → 11 GICS sectors for per-sector training.
_GICS_SECTOR_MAP: dict[str, str] = {
    # Energy
    "energy": "Energy",
    # Materials
    "chemicals": "Materials",
    "metals & mining": "Materials",
    "paper & forest": "Materials",
    # Industrials
    "machinery": "Industrials",
    "electrical equipment": "Industrials",
    "building": "Industrials",
    "commercial services & supplies": "Industrials",
    "construction": "Industrials",
    "aerospace & defense": "Industrials",
    "trading companies & distributors": "Industrials",
    "professional services": "Industrials",
    "road & rail": "Industrials",
    "airlines": "Industrials",
    "marine": "Industrials",
    "logistics & transportation": "Industrials",
    "distributors": "Industrials",
    "packaging": "Industrials",
    # Consumer Discretionary
    "retail": "Consumer Discretionary",
    "hotels, restaurants & leisure": "Consumer Discretionary",
    "auto components": "Consumer Discretionary",
    "textiles, apparel & luxury goods": "Consumer Discretionary",
    "leisure products": "Consumer Discretionary",
    "automobiles": "Consumer Discretionary",
    "diversified consumer services": "Consumer Discretionary",
    # Consumer Staples
    "consumer products": "Consumer Staples",
    "food products": "Consumer Staples",
    "beverages": "Consumer Staples",
    "tobacco": "Consumer Staples",
    # Health Care
    "health care": "Health Care",
    "biotechnology": "Health Care",
    "pharmaceuticals": "Health Care",
    "life sciences tools & services": "Health Care",
    # Financials
    "banking": "Financials",
    "financial services": "Financials",
    "insurance": "Financials",
    # Real Estate
    "real estate": "Real Estate",
    # Information Technology
    "technology": "Information Technology",
    "semiconductors": "Information Technology",
    # Communication Services
    "media": "Communication Services",
    "communications": "Communication Services",
    "telecommunication": "Communication Services",
    # Utilities
    "utilities": "Utilities",
}


def _map_to_gics_sector(db_sector: str) -> str:
    """Map a DB sub-industry name to its GICS sector.

    Returns the GICS sector name, or "Other" if unmatched.
    """
    key = db_sector.strip().lower()
    return _GICS_SECTOR_MAP.get(key, "Other")


def load_sector_groups(engine) -> dict[str, list[str]]:
    """Load symbol→sector from DB and group symbols by GICS sector.

    Returns
    -------
    dict[str, list[str]]
        ``{gics_sector: [symbols]}}, symbols sorted alphabetically.
    """
    raw_mapping = _load_sector_mapping(engine)
    groups: dict[str, list[str]] = {}
    for sym, db_sec in raw_mapping.items():
        gics = _map_to_gics_sector(db_sec)
        groups.setdefault(gics, []).append(sym)
    # Sort symbols within each group
    for gics in groups:
        groups[gics] = sorted(groups[gics])
    LOGGER.info("load_sector_groups: %d symbols → %d GICS sectors", len(raw_mapping), len(groups))
    return groups


def _compute_sector_features(
    raw_panel: pd.DataFrame,
    sector_map: dict[str, str],
    *,
    min_symbols_per_sector: int = 3,
) -> pd.DataFrame:
    """Calcule les features sectorielles depuis le raw_panel cross-sectional.

    Pour chaque (date, secteur) agrège les valeurs brutes de tous les titres
    du secteur, puis réinjecte dans chaque ligne (symbol, date).

    Parameters
    ----------
    raw_panel : pd.DataFrame
        Doit contenir ``symbol``, ``date`` et les colonnes de RAW_CROSS_SECTIONAL_COLS.
    sector_map : dict[str, str]
        Mapping ``{symbol: sector_name}``.
    min_symbols_per_sector : int
        Nombre minimum de symboles dans un secteur pour que l'agrégat soit valide
        (sinon → NaN, puis forward-fillé).

    Returns
    -------
    pd.DataFrame
        DataFrame avec colonnes ``[symbol, date, *SECTOR_FEATURE_COLUMNS]``.
    """
    if not sector_map or raw_panel.empty:
        return pd.DataFrame(columns=["symbol", "date", *SECTOR_FEATURE_COLUMNS])

    panel = raw_panel.copy()
    panel["sector"] = panel["symbol"].astype(str).str.upper().map(sector_map)
    panel = panel.dropna(subset=["sector"])
    if panel.empty:
        return pd.DataFrame(columns=["symbol", "date", *SECTOR_FEATURE_COLUMNS])

    # Compte le nombre de symboles distincts par (date, secteur)
    sector_counts = panel.groupby(["date", "sector"])["symbol"].transform("nunique")
    valid_mask = sector_counts >= min_symbols_per_sector

    # Agrégats sectoriels par (date, secteur)
    agg_map: dict[str, str | callable] = {
        "ret_5": "mean",
        "ret_20": "mean",
        "ret_60": "mean",
        "volatility_20": "mean",
        "dollar_volume_20": "sum",
    }
    available_aggs = {k: v for k, v in agg_map.items() if k in panel.columns}
    sector_agg = panel.groupby(["date", "sector"], sort=False).agg(available_aggs).reset_index()
    sector_agg.rename(
        columns={
            "ret_5": "sector_ret_5",
            "ret_20": "sector_ret_20",
            "ret_60": "sector_ret_60",
            "volatility_20": "sector_vol_20",
            "dollar_volume_20": "sector_dollar_volume_20",
        },
        inplace=True,
    )

    # Secteur relative strength vs benchmark
    if "benchmark_return_20" in panel.columns:
        bench_by_date = panel.groupby("date")["benchmark_return_20"].first().reset_index()
        sector_agg = sector_agg.merge(bench_by_date, on="date", how="left")
        sector_agg["sector_relative_strength_20"] = (
            sector_agg["sector_ret_20"] - sector_agg["benchmark_return_20"]
        )
    else:
        sector_agg["sector_relative_strength_20"] = sector_agg["sector_ret_20"]

    # Nombre de symboles par secteur
    symbol_counts = panel.groupby(["date", "sector"])["symbol"].nunique().reset_index(name="sector_symbol_count")
    sector_agg = sector_agg.merge(symbol_counts, on=["date", "sector"], how="left")

    # Merge back to per-symbol level
    result = panel[["symbol", "date", "sector"] + [c for c in ("ret_5", "ret_20", "ret_60") if c in panel.columns]].merge(
        sector_agg, on=["date", "sector"], how="left"
    )

    # Stock vs secteur (alpha individuel)
    if "ret_5" in result.columns and "sector_ret_5" in result.columns:
        result["stock_vs_sector_ret_5"] = result["ret_5"] - result["sector_ret_5"]
    else:
        result["stock_vs_sector_ret_5"] = 0.0
    result["stock_vs_sector_ret_20"] = result["ret_20"] - result["sector_ret_20"]
    result["stock_vs_sector_ret_60"] = result["ret_60"] - result["sector_ret_60"]

    # Invalider les agrégats quand le secteur a trop peu de symboles
    _invalid = ~valid_mask.reindex(result.index, fill_value=False)
    for col in SECTOR_FEATURE_COLUMNS:
        if col in result.columns:
            result.loc[_invalid, col] = np.nan

    # Forward-fill les NaN au sein de chaque (symbol, secteur) pour les dates sans agrégat
    result = result.sort_values(["symbol", "date"]).reset_index(drop=True)
    fill_cols = [c for c in SECTOR_FEATURE_COLUMNS if c in result.columns]
    result[fill_cols] = result.groupby("symbol", sort=False)[fill_cols].ffill()

    # Remplir les NaN restants par 0 (début de série sans historique sectoriel),
    # et créer les colonnes sectorielles absentes (ex: ret_5 non fourni).
    for col in SECTOR_FEATURE_COLUMNS:
        if col not in result.columns:
            result[col] = 0.0
        else:
            result[col] = result[col].fillna(0.0)

    return result[["symbol", "date", *SECTOR_FEATURE_COLUMNS]].copy()


def _compute_cross_symbol_features(
    raw_panel: pd.DataFrame,
    sector_map: dict[str, str],
    *,
    min_symbols_per_sector: int = 5,
) -> pd.DataFrame:
    """Calcule les features cross-symbol exclusives pour le Global Model.

    Ces features capturent des patterns émergents qu'un modèle per-symbol
    ne peut pas voir : breadth sectoriel, dispersion, concentration,
    rang intra-secteur. Elles sont calculées sur le raw_panel existant
    (coût marginal nul).

    Parameters
    ----------
    raw_panel : pd.DataFrame
        Doit contenir ``symbol``, ``date``, ``ret_20``, ``ret_60``,
        ``volatility_20``, ``dollar_volume_20``.
    sector_map : dict[str, str]
        Mapping ``{symbol: sector_name}``.
    min_symbols_per_sector : int
        Seuil minimum de symboles par secteur pour des features valides.

    Returns
    -------
    pd.DataFrame
        ``[symbol, date, *GLOBAL_EXCLUSIVE_FEATURE_COLUMNS]``.
    """
    if not sector_map or raw_panel.empty:
        return pd.DataFrame(columns=["symbol", "date", *GLOBAL_EXCLUSIVE_FEATURE_COLUMNS])

    panel = raw_panel.copy()
    panel["sector"] = panel["symbol"].astype(str).str.upper().map(sector_map)
    panel = panel.dropna(subset=["sector"])
    if panel.empty:
        return pd.DataFrame(columns=["symbol", "date", *GLOBAL_EXCLUSIVE_FEATURE_COLUMNS])

    required = {"ret_20", "dollar_volume_20"}
    available = required.intersection(panel.columns)
    if "ret_20" not in available:
        return pd.DataFrame(columns=["symbol", "date", *GLOBAL_EXCLUSIVE_FEATURE_COLUMNS])

    # ── Agrégats par (date, secteur) ──
    agg_parts: list[pd.DataFrame] = []

    for (dt, sec), grp in panel.groupby(["date", "sector"], sort=False):
        n_sym = grp["symbol"].nunique()
        if n_sym < min_symbols_per_sector:
            continue

        row: dict[str, Any] = {"date": dt, "sector": sec}

        # 1. Breadth : % de titres avec ret_20 > 0
        if "ret_20" in grp.columns:
            row["sector_breadth_20"] = float((grp["ret_20"] > 0).mean())

        # 2. Dispersion : écart-type des ret_20
        if "ret_20" in grp.columns:
            row["sector_dispersion_20"] = float(grp["ret_20"].std())

        # 3. Concentration : top-3 dollar volume / total
        if "dollar_volume_20" in grp.columns:
            dv = grp["dollar_volume_20"].dropna().sort_values(ascending=False)
            total_dv = float(dv.sum())
            top_n = min(3, len(dv))
            top3_dv = float(dv.head(top_n).sum()) if top_n > 0 else 0.0
            row["sector_concentration_20"] = float(top3_dv / total_dv) if total_dv > 0 else 0.0

        # 6. Momentum spread : top décile - bottom décile ret_20
        if "ret_20" in grp.columns and len(grp) >= 10:
            rets = grp["ret_20"].dropna().sort_values()
            if len(rets) >= 10:
                top_idx = max(0, min(len(rets) - 1, int(len(rets) * 0.9)))
                bot_idx = max(0, min(len(rets) - 1, int(len(rets) * 0.1)))
                top_decile = rets.iloc[top_idx]
                bot_decile = rets.iloc[bot_idx]
                row["sector_momentum_spread_20"] = float(top_decile - bot_decile)

        agg_parts.append(pd.DataFrame([row]))

    if not agg_parts:
        out = panel[["symbol", "date", "sector"]].copy()
        for col in GLOBAL_EXCLUSIVE_FEATURE_COLUMNS:
            out[col] = 0.0
        return out[["symbol", "date", *GLOBAL_EXCLUSIVE_FEATURE_COLUMNS]]

    sector_agg = pd.concat(agg_parts, ignore_index=True)

    # ── Merge sur chaque symbole ──
    result = panel[["symbol", "date", "sector", "ret_20", "ret_60", "volatility_20"]].merge(
        sector_agg, on=["date", "sector"], how="left",
    )

    # 4. Rang intra-secteur du ret_20
    result["symbol_rank_in_sector_20"] = result.groupby(
        ["date", "sector"], sort=False
    )["ret_20"].rank(pct=True).where(
        result.groupby(["date", "sector"], sort=False)["symbol"].transform("nunique") >= min_symbols_per_sector,
        0.5,
    )

    # 5. Ratio volatilité titre / secteur
    result["stock_vs_sector_vol_ratio"] = np.where(
        result["sector_dispersion_20"] > 0,
        result["volatility_20"] / result["sector_dispersion_20"].clip(lower=0.001),
        1.0,
    )

    # ── Nettoyage ──
    result = result.sort_values(["symbol", "date"]).reset_index(drop=True)
    for col in GLOBAL_EXCLUSIVE_FEATURE_COLUMNS:
        if col in result.columns:
            result[col] = result.groupby("symbol", sort=False)[col].ffill().fillna(0.0).astype(float)
        else:
            result[col] = 0.0

    return result[["symbol", "date", *GLOBAL_EXCLUSIVE_FEATURE_COLUMNS]].copy()


def _compute_sector_neutral_features(
    raw_panel: pd.DataFrame,
    sector_map: dict[str, str],
    *,
    min_symbols_per_sector: int = 3,
) -> pd.DataFrame:
    """Calcule les versions sector-neutralisées des features techniques.

    Pour chaque (date, secteur), calcule la médiane de chaque feature source
    et soustrait cette médiane de la valeur brute du titre. Isole l'alpha
    spécifique au titre, indépendamment de la tendance sectorielle.

    Parameters
    ----------
    raw_panel : pd.DataFrame
        Doit contenir ``symbol``, ``date`` et les colonnes de
        ``SECTOR_NEUTRAL_SOURCE_FEATURES``.
    sector_map : dict[str, str]
        Mapping ``{symbol: sector_name}``.
    min_symbols_per_sector : int
        Minimum de symboles dans un secteur pour que la médiane soit valide.

    Returns
    -------
    pd.DataFrame [symbol, date, *SECTOR_NEUTRAL_FEATURE_COLUMNS]
    """
    if not sector_map or raw_panel.empty:
        return pd.DataFrame(columns=["symbol", "date", *SECTOR_NEUTRAL_FEATURE_COLUMNS])

    panel = raw_panel.copy()
    panel["sector"] = panel["symbol"].astype(str).str.upper().map(sector_map)
    panel = panel.dropna(subset=["sector"])
    if panel.empty:
        return pd.DataFrame(columns=["symbol", "date", *SECTOR_NEUTRAL_FEATURE_COLUMNS])

    # Compter les symboles par (date, secteur) pour filtrer les petits secteurs
    sector_counts = panel.groupby(["date", "sector"])["symbol"].transform("nunique")
    valid_mask = sector_counts >= min_symbols_per_sector

    result = panel[["symbol", "date"]].copy()

    for src_col in SECTOR_NEUTRAL_SOURCE_FEATURES:
        target_col = _sector_neutral_column_name(src_col)
        if src_col not in panel.columns:
            result[target_col] = 0.0
            continue
        # Médiane sectorielle par date
        sector_median = panel.groupby(["date", "sector"])[src_col].transform("median")
        neutral = panel[src_col] - sector_median
        # Mettre à 0 quand le secteur est trop petit (médiane non fiable)
        neutral = neutral.where(valid_mask, 0.0)
        result[target_col] = neutral.fillna(0.0).astype(float)

    return result[["symbol", "date", *SECTOR_NEUTRAL_FEATURE_COLUMNS]]


def build_cross_sectional_features_from_db(
    engine,
    symbols: list[str],
    *,
    benchmark_df: pd.DataFrame | None = None,
    min_universe_size: int = 20,
    start_date=None,
    end_date=None,
    sector_map: dict[str, str] | None = None,
    min_symbols_per_sector: int = 3,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build cross-sectional (+ optional sector) features by loading bars symbol-by-symbol.

    Avoids loading all symbols at once -- queries one symbol's bars at a time,
    accumulates raw values, then computes percentile ranks per date.

    If ``sector_map`` is provided, also computes sector-level aggregate features
    and appends them to the returned DataFrame.

    This replaces the old approach of loading all universe bars in a single
    massive MySQL query that exceeded max_allowed_packet.
    """
    from modelFactory.data_loader import load_symbol_bars

    all_feature_cols = list(CROSS_SECTIONAL_FEATURE_COLUMNS)
    if sector_map:
        all_feature_cols.extend(SECTOR_FEATURE_COLUMNS)
        all_feature_cols.extend(GLOBAL_EXCLUSIVE_FEATURE_COLUMNS)

    if not symbols:
        return pd.DataFrame(columns=["symbol", "date", *all_feature_cols]), {
            "enabled": False,
            "reason": "empty_symbols_list",
            "feature_columns": all_feature_cols,
        }

    benchmark_returns = _build_benchmark_returns(benchmark_df)

    all_raw_parts: list[pd.DataFrame] = []
    loaded_count = 0
    skipped_count = 0

    for symbol in symbols:
        try:
            sym_df = load_symbol_bars(engine, symbol, end_date=end_date, start_date=start_date)
        except Exception:
            skipped_count += 1
            continue
        if sym_df.empty or len(sym_df) < 60:
            skipped_count += 1
            continue
        raw_part = _compute_symbol_raw_values(sym_df, benchmark_returns)
        raw_part["symbol"] = symbol
        if not raw_part.empty:
            all_raw_parts.append(raw_part)
        loaded_count += 1

    if not all_raw_parts:
        return pd.DataFrame(columns=["symbol", "date", *all_feature_cols]), {
            "enabled": True,
            "reason": "no_valid_symbols",
            "feature_columns": all_feature_cols,
            "loaded_count": loaded_count,
            "skipped_count": skipped_count,
        }

    raw_panel = pd.concat(all_raw_parts, ignore_index=True)
    raw_panel["universe_symbol_count"] = raw_panel.groupby("date")["symbol"].transform("nunique")

    for raw_col, rank_col in RAW_CROSS_SECTIONAL_COLUMNS_MAP.items():
        if raw_col not in raw_panel.columns:
            raw_panel[rank_col] = 0.5
            continue
        rank_series = raw_panel.groupby("date")[raw_col].rank(method="average", pct=True)
        rank_series = rank_series.where(raw_panel["universe_symbol_count"] >= min_universe_size, 0.5)
        raw_panel[rank_col] = rank_series.astype(float)

    feature_frame = raw_panel[["symbol", "date", *CROSS_SECTIONAL_FEATURE_COLUMNS]].copy()

    diagnostics: dict[str, Any] = {
        "enabled": True,
        "feature_columns": list(CROSS_SECTIONAL_FEATURE_COLUMNS),
        "output_rows": int(len(feature_frame)),
        "unique_symbols": int(raw_panel["symbol"].nunique()),
        "unique_dates": int(raw_panel["date"].nunique()),
        "min_universe_size": int(min_universe_size),
        "dates_below_min_universe": int((raw_panel.groupby("date")["universe_symbol_count"].first() < min_universe_size).sum()),
        "loaded_count": loaded_count,
        "skipped_count": skipped_count,
    }

    # ── Sector features (optional) ──
    if sector_map:
        sector_frame = _compute_sector_features(
            raw_panel, sector_map, min_symbols_per_sector=min_symbols_per_sector,
        )
        if not sector_frame.empty:
            feature_frame = feature_frame.merge(sector_frame, on=["symbol", "date"], how="left")
            for col in SECTOR_FEATURE_COLUMNS:
                if col not in feature_frame.columns:
                    feature_frame[col] = 0.0
        else:
            for col in SECTOR_FEATURE_COLUMNS:
                feature_frame[col] = 0.0
        diagnostics["feature_columns"] = all_feature_cols
        diagnostics["sector_features_enabled"] = True
        diagnostics["sector_count"] = len(set(sector_map.values()))
        diagnostics["sector_symbol_mapped"] = len(sector_map)

        # ── Cross-symbol exclusive features (Global Model uniquement) ──
        cross_symbol_frame = _compute_cross_symbol_features(
            raw_panel, sector_map, min_symbols_per_sector=min_symbols_per_sector,
        )
        if not cross_symbol_frame.empty:
            feature_frame = feature_frame.merge(cross_symbol_frame, on=["symbol", "date"], how="left")
        for col in GLOBAL_EXCLUSIVE_FEATURE_COLUMNS:
            if col not in feature_frame.columns:
                feature_frame[col] = 0.0
        diagnostics["cross_symbol_features_enabled"] = True
        diagnostics["cross_symbol_feature_count"] = len(GLOBAL_EXCLUSIVE_FEATURE_COLUMNS)

    # ── Sector-neutral features (Sprint 2026-07-25) ──
    # Calcule les versions sector-neutralisées des features techniques.
    # Chaque feature est ajustée par soustraction de la médiane de son secteur à chaque date.
    if sector_map:
        _sn_frame = _compute_sector_neutral_features(
            raw_panel, sector_map, min_symbols_per_sector=min_symbols_per_sector,
        )
        if not _sn_frame.empty:
            feature_frame = feature_frame.merge(_sn_frame, on=["symbol", "date"], how="left")
        for col in SECTOR_NEUTRAL_FEATURE_COLUMNS:
            if col not in feature_frame.columns:
                feature_frame[col] = 0.0
        diagnostics["sector_neutral_features_enabled"] = True
        diagnostics["sector_neutral_feature_count"] = len(SECTOR_NEUTRAL_FEATURE_COLUMNS)
        diagnostics["feature_columns"] = list(feature_frame.columns)

    return feature_frame, diagnostics


# ---------------------------------------------------------------------------
# Legacy wrapper -- accepts a pre-loaded DataFrame (backward compat)
# ---------------------------------------------------------------------------

def build_cross_sectional_features(
    universe_df: pd.DataFrame | None,
    *,
    benchmark_df: pd.DataFrame | None = None,
    min_universe_size: int = 20,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build cross-sectional features from a pre-loaded DataFrame.

    Prefer ``build_cross_sectional_features_from_db`` which loads bars
    symbol-by-symbol and avoids massive MySQL queries.
    """
    if universe_df is None or universe_df.empty:
        return pd.DataFrame(columns=["symbol", "date", *CROSS_SECTIONAL_FEATURE_COLUMNS]), {
            "enabled": False,
            "reason": "empty_universe",
            "feature_columns": list(CROSS_SECTIONAL_FEATURE_COLUMNS),
        }

    required_cols = {"symbol", "date", "close", "adj_close", "volume"}
    missing = required_cols.difference(universe_df.columns)
    if missing:
        raise ValueError(f"build_cross_sectional_features missing required columns: {sorted(missing)}")

    panel = universe_df.copy()
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["symbol", "date"]).reset_index(drop=True)

    benchmark_returns = _build_benchmark_returns(benchmark_df)
    parts: list[pd.DataFrame] = []
    for symbol, sym_df in panel.groupby("symbol", sort=False):
        raw_part = _compute_symbol_raw_values(sym_df, benchmark_returns)
        if not raw_part.empty:
            parts.append(raw_part)

    raw_panel = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["symbol", "date", *RAW_CROSS_SECTIONAL_COLS])
    raw_panel["universe_symbol_count"] = raw_panel.groupby("date")["symbol"].transform("nunique")

    for raw_col, rank_col in RAW_CROSS_SECTIONAL_COLUMNS_MAP.items():
        if raw_col not in raw_panel.columns:
            raw_panel[rank_col] = 0.5
            continue
        rank_series = raw_panel.groupby("date")[raw_col].rank(method="average", pct=True)
        rank_series = rank_series.where(raw_panel["universe_symbol_count"] >= min_universe_size, 0.5)
        raw_panel[rank_col] = rank_series.astype(float)

    feature_frame = raw_panel[["symbol", "date", *CROSS_SECTIONAL_FEATURE_COLUMNS]].copy()
    diagnostics = {
        "enabled": True,
        "feature_columns": list(CROSS_SECTIONAL_FEATURE_COLUMNS),
        "input_rows": int(len(universe_df)),
        "output_rows": int(len(feature_frame)),
        "unique_symbols": int(panel["symbol"].nunique()),
        "unique_dates": int(panel["date"].nunique()),
        "min_universe_size": int(min_universe_size),
        "dates_below_min_universe": int((raw_panel.groupby("date")["universe_symbol_count"].first() < min_universe_size).sum()),
    }
    return feature_frame, diagnostics


def merge_cross_sectional_features(
    symbol_df: pd.DataFrame,
    cross_sectional_df: pd.DataFrame | None,
) -> pd.DataFrame:
    """Merge cross-sectional (+ optional sector + optional global_pred + optional cross-symbol) features on (symbol, date) PIT-safe.

    Gère quatre familles de features :
    - Rangs percentiles (``CROSS_SECTIONAL_FEATURE_COLUMNS``) → fillna(0.5)
    - Sectorielles (``SECTOR_FEATURE_COLUMNS``) → fillna(0.0)
    - Global stacking (``GLOBAL_PRED_FEATURE_COLUMNS``) → fillna(0.5) si présent dans le cache
    - Cross-symbol exclusives (``GLOBAL_EXCLUSIVE_FEATURE_COLUMNS``) → fillna(0.0) si présent
    """
    all_cols = (
        list(CROSS_SECTIONAL_FEATURE_COLUMNS)
        + list(SECTOR_FEATURE_COLUMNS)
        + list(GLOBAL_PRED_FEATURE_COLUMNS)
        + list(GLOBAL_EXCLUSIVE_FEATURE_COLUMNS)
        + list(SECTOR_NEUTRAL_FEATURE_COLUMNS)
        + list(SECTOR_ZSCORE_FEATURE_COLUMNS)
    )
    if cross_sectional_df is None or cross_sectional_df.empty:
        merged = symbol_df.copy()
        for col in all_cols:
            if col not in merged.columns:
                if col in CROSS_SECTIONAL_FEATURE_COLUMNS or col in GLOBAL_PRED_FEATURE_COLUMNS:
                    merged[col] = 0.5
                else:
                    merged[col] = 0.0
        return merged

    # Ne merger que les colonnes effectivement présentes dans le cache
    available_cols = [c for c in all_cols if c in cross_sectional_df.columns]
    if not available_cols:
        merged = symbol_df.copy()
        for col in all_cols:
            if col not in merged.columns:
                if col in CROSS_SECTIONAL_FEATURE_COLUMNS or col in GLOBAL_PRED_FEATURE_COLUMNS:
                    merged[col] = 0.5
                else:
                    merged[col] = 0.0
        return merged

    # Supprimer les colonnes déjà présentes dans symbol_df pour éviter les
    # suffixes _x/_y lors du merge (qui feraient perdre les valeurs réelles).
    # Cas typique : prepare_symbol_frame a déjà appelé merge_cross_sectional_features
    # avec un cache vide → colonnes à 0.5. Puis _prepare_sector_data rappelle
    # avec le vrai cache → si on ne drop pas, les 0.5 écrasent les vraies valeurs.
    _symbol_df_clean = symbol_df.drop(columns=[c for c in all_cols if c in symbol_df.columns], errors="ignore")

    merge_df = cross_sectional_df[["symbol", "date", *available_cols]]
    merged = _symbol_df_clean.merge(merge_df, on=["symbol", "date"], how="left")
    for col in all_cols:
        if col not in merged.columns:
            if col in CROSS_SECTIONAL_FEATURE_COLUMNS or col in GLOBAL_PRED_FEATURE_COLUMNS:
                merged[col] = 0.5
            else:
                merged[col] = 0.0
        else:
            # Colonne présente (issue du merge) mais peut contenir NaN
            # (symbole absent du cache → left join → NaN)
            default_val = 0.5 if (col in CROSS_SECTIONAL_FEATURE_COLUMNS or col in GLOBAL_PRED_FEATURE_COLUMNS) else 0.0
            merged[col] = merged[col].fillna(default_val).astype(float)
    return merged
