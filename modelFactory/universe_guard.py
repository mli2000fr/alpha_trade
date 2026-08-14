"""Garde-fou « breadth » — largeur minimale de l'univers pour les prédictions ML live.

Le ranking cross-sectionnel est très sensible à la largeur de l'univers :
backtest B25 → IC sector-neutral 0.0238 à 350+ symboles/jour vs 0.0060 à
250-350 (même modèle, même période). Générer des rangs globaux sur un univers
dégradé (ex. < 100 symboles) produit un signal sans sens et pollue
``global_rank_history`` / ``model_predictions``.

Le seuil est configurable via ``config.yaml → batch_diagnostics.ml_min_universe_symbols``
(défaut 300, calibré sur la borne basse du backtest validé : 311).
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

LOGGER = logging.getLogger(__name__)

DEFAULT_MIN_UNIVERSE_PCT = 75.0  # % du référentiel (400) → 300 symboles
DEFAULT_REFERENCE_UNIVERSE_SIZE = 400
_CONFIG_PATH = Path("config.yaml")
_TICKET_PATH = Path("config/ticket_recherche.txt")


def compute_min_breadth(reference_size: int, pct: float) -> int:
    """Seuil minimal = ceil(référentiel × pct/100)."""
    import math

    return max(1, int(math.ceil(reference_size * pct / 100.0)))


def load_min_universe_pct() -> float:
    """Lit le pourcentage minimal depuis config.yaml (défaut 75)."""
    try:
        import yaml

        with open(_CONFIG_PATH, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        value = float(
            (raw.get("batch_diagnostics") or {}).get("ml_min_universe_pct")
            or DEFAULT_MIN_UNIVERSE_PCT
        )
        return value if value > 0 else DEFAULT_MIN_UNIVERSE_PCT
    except Exception:
        LOGGER.warning("load_min_universe_pct: config illisible → défaut %.0f%%", DEFAULT_MIN_UNIVERSE_PCT)
        return DEFAULT_MIN_UNIVERSE_PCT


def load_reference_universe_size() -> int:
    """Taille du référentiel = nombre de symboles dans config/ticket_recherche.txt."""
    try:
        raw = _TICKET_PATH.read_text(encoding="utf-8").strip()
        symbols: set[str] = set()
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            symbols.update(s.strip().upper() for s in line.split(",") if s.strip())
        if symbols:
            return len(symbols)
    except Exception:
        LOGGER.warning("load_reference_universe_size: ticket_recherche.txt illisible → défaut %d", DEFAULT_REFERENCE_UNIVERSE_SIZE)
    return DEFAULT_REFERENCE_UNIVERSE_SIZE


def load_min_universe_breadth() -> int:
    """Seuil minimal de symboles = référentiel (400) × pct config (75%)."""
    return compute_min_breadth(load_reference_universe_size(), load_min_universe_pct())


def current_universe_size(engine, trade_date: date) -> int:
    """Taille de l'univers tradable PIT le plus récent ≤ trade_date."""
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT tradable_rows FROM tradable_universe_runs "
                    "WHERE is_canonical = 1 AND snapshot_date <= :d "
                    "ORDER BY snapshot_date DESC LIMIT 1"
                ),
                {"d": trade_date},
            ).fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        LOGGER.warning("current_universe_size: lecture impossible → 0 (blocage conservateur)", exc_info=True)
        return 0


def enforce_min_universe_breadth(
    symbol_count: int,
    *,
    trade_date: date | None = None,
    batch_id: str | None = None,
    minimum: int | None = None,
    block: bool = True,
) -> bool:
    """Valide la largeur d'univers.

    Returns
    -------
    bool
        True si le compte est suffisant. Sinon lève ``RuntimeError`` quand
        ``block=True`` (comportement live), ou log un warning et retourne False
        quand ``block=False`` (backfill).
    """
    threshold = minimum if minimum is not None else load_min_universe_breadth()
    if symbol_count >= threshold:
        return True
    message = (
        f"Garde-fou breadth : univers de {symbol_count} symboles < seuil {threshold} "
        f"(date={trade_date or '?'}, batch={batch_id or '?'}). Prédictions ML live BLOQUÉES "
        f"pour éviter de générer des rangs sur un univers dégradé. "
        f"Vérifier l'ingestion (barres eodhd, stock_quote_snapshots) et l'étape 6 "
        f"(publish_tradable_universe)."
    )
    if block:
        raise RuntimeError(message)
    LOGGER.warning(message)
    return False
