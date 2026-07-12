"""common/price_convention.py — Contrat de séparation prix ajustés / prix exécutables.

Sprint Maître 2 / Section 17 Point 2.3 :
- Les **features** et l'entraînement ML utilisent des prix ajustés (split-only).
- Les **fills** et l'exécution utilisent des prix exécutables (split-only également).
- La différence est une intention de contrat, pas un écart mathématique aujourd'hui :
  les deux conventions portent sur les mêmes prix split-only, mais la séparation
  permet d'activer un ajustement dividendes côté features sans contaminer les fills.

Convention actuelle (2026-07-12) :
- ``stock_bars_daily`` stocke des prix **split-only** (``close == adj_close``).
- Les dividendes ne sont PAS dans les prix ; ils sont tracés dans
  ``portfolio_cash_ledger`` et ``corporate_actions/``.
- Le pipeline EODHD rejette volontairement l'``adjusted_close`` split+dividendes
  fourni par l'API ; ``to_stock_bars_daily_row()`` force ``adj_close = close``.
- ``_build_adjusted_price_frame()`` applique le ratio ``adj_close / close``
  (actuellement 1.0) pour future-proof les features si un jour on injecte
  l'ajustement dividende dans ``adj_close``.
- Le simulateur backtest utilise ``open``/``high``/``low``/``close`` bruts
  (split-only, jamais ajustés pour les dividendes).

Usage ::

    from common.price_convention import PriceConvention, PRICE_CONVENTION_LABEL

    # Dans un loader de features :
    df.attrs["price_convention"] = PriceConvention.ADJUSTED.value

    # Dans un loader de prix pour fills :
    df.attrs["price_convention"] = PriceConvention.EXECUTABLE.value
"""

from __future__ import annotations

from enum import Enum


class PriceConvention(str, Enum):
    """Convention de prix pour un DataFrame ou une colonne.

    Attributes
    ----------
    ADJUSTED : str
        Prix ajustés pour les splits (split-only). Dans l'état actuel du projet,
        **n'inclut pas** l'ajustement dividende (les dividendes sont dans
        ``portfolio_cash_ledger``). Utilisés UNIQUEMENT pour les features,
        l'entraînement ML et les calculs de rendement théorique.
        **Jamais** pour les fills.
    EXECUTABLE : str
        Prix de marché réels split-only — utilisés UNIQUEMENT pour les fills,
        le sizing, les stops et le P&L réalisé. **Jamais** pour les features ML.
        Aujourd'hui identiques aux prix ADJUSTED (les deux sont split-only),
        mais la séparation est maintenue pour future-proof l'ajout de
        l'ajustement dividende côté features.
    UNSPECIFIED : str
        Convention non déclarée (legacy). Doit être migré vers ADJUSTED
        ou EXECUTABLE avant paper/live.
    """

    ADJUSTED = "adjusted"
    EXECUTABLE = "executable"
    UNSPECIFIED = "unspecified"


# ── Label documenté pour les DataFrames ─────────────────────────────────────

PRICE_CONVENTION_LABEL = "price_convention"
"""Clé utilisée dans ``df.attrs`` pour déclarer la convention de prix."""


def declare_price_convention(
    df: "pd.DataFrame",
    convention: PriceConvention,
    *,
    source: str | None = None,
) -> "pd.DataFrame":
    """Attache une convention de prix explicite à un DataFrame.

    À appeler dans TOUS les loaders qui retournent des prix.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame à annoter.
    convention : PriceConvention
        Convention applicable.
    source : str | None
        Source des données (optionnel, pour traçabilité).

    Returns
    -------
    pd.DataFrame
        Le même DataFrame (modifié sur place, aussi retourné).
    """
    df.attrs[PRICE_CONVENTION_LABEL] = convention.value
    if source:
        df.attrs["price_convention_source"] = source
    return df


def get_price_convention(df: "pd.DataFrame") -> PriceConvention:
    """Lit la convention de prix déclarée sur un DataFrame.

    Parameters
    ----------
    df : pd.DataFrame

    Returns
    -------
    PriceConvention
        La convention déclarée, ou ``UNSPECIFIED`` si absente.
    """
    raw = df.attrs.get(PRICE_CONVENTION_LABEL)
    if raw is None:
        return PriceConvention.UNSPECIFIED
    try:
        return PriceConvention(str(raw))
    except ValueError:
        return PriceConvention.UNSPECIFIED


def validate_no_mixed_convention(
    features_df: "pd.DataFrame",
    execution_df: "pd.DataFrame",
    *,
    strict: bool = False,
) -> list[str]:
    """Vérifie que deux DataFrames n'utilisent pas la même convention.

    Un DataFrame de features DOIT être ``ADJUSTED``.
    Un DataFrame d'exécution DOIT être ``EXECUTABLE``.
    L'inverse est une violation du contrat.

    Parameters
    ----------
    features_df : pd.DataFrame
        DataFrame utilisé pour les features ML.
    execution_df : pd.DataFrame
        DataFrame utilisé pour les fills/exécution.
    strict : bool
        Si True, lève ``ValueError`` au lieu de retourner des violations.

    Returns
    -------
    list[str]
        Liste des violations (vide = OK).
    """
    violations: list[str] = []
    feat_conv = get_price_convention(features_df)
    exec_conv = get_price_convention(execution_df)

    if feat_conv == PriceConvention.EXECUTABLE:
        msg = "Features utilisent des prix EXECUTABLE (doit être ADJUSTED)"
        violations.append(msg)
    if exec_conv == PriceConvention.ADJUSTED:
        msg = "Fills utilisent des prix ADJUSTED (doit être EXECUTABLE)"
        violations.append(msg)
    if feat_conv == PriceConvention.UNSPECIFIED:
        violations.append("Features : convention de prix non déclarée")
    if exec_conv == PriceConvention.UNSPECIFIED:
        violations.append("Exécution : convention de prix non déclarée")

    if strict and violations:
        raise ValueError(
            "Violation du contrat prix ajustés/exécutables : " + "; ".join(violations)
        )
    return violations
