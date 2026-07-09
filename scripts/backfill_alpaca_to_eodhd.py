"""
Script de backfill EODHD pour les données actuellement servies uniquement par alpaca_iex.

--------------------------------------------------------------------------------
OBJECTIF
--------------------------------------------------------------------------------

La table ``stock_bars_daily`` est alimentée par plusieurs sources de données
(alpaca_iex, eodhd_eod, etc.). Lorsqu'une date pour un symbole donné n'existe
QUE chez alpaca_iex (et pas chez eodhd_eod ni ailleurs), il est souhaitable de
la réalimenter depuis EODHD pour :

  1. Disposer d'une source alternative (redondance / fiabilité).
  2. Bénéficier des données EODHD qui incluent l'``adjusted_close`` (split +
     dividendes), permettant une reconstruction split-only plus précise.

Ce script automatise cette opération en deux phases.

--------------------------------------------------------------------------------
REQUÊTE SQL AYANT PRODUIT bars.txt
--------------------------------------------------------------------------------

La requête ci-dessous liste les couples (symbol, date) présents dans
``stock_bars_daily`` UNIQUEMENT via la source ``alpaca_iex`` (c.-à-d. aucune
autre source ne couvre ce jour pour ce symbole) :

.. code-block:: sql

    SELECT a.symbol, a.date
    FROM stock_bars_daily a
    WHERE a.data_source = 'alpaca_iex'
      AND NOT EXISTS (
        SELECT 1
        FROM stock_bars_daily b
        WHERE b.symbol = a.symbol
          AND b.date = a.date
          AND b.data_source <> 'alpaca_iex'
      )
    ORDER BY a.date, a.symbol;

Le résultat a été exporté dans ``bars.txt`` au format :

    SYMBOL<TAB>DATE

Exemple :

    STXX    2015-02-24
    STXX    2015-02-25
    AAPL    2020-06-15

--------------------------------------------------------------------------------
FONCTIONNEMENT
--------------------------------------------------------------------------------

Parcourt le fichier bars.txt (symbol + date par ligne, séparés par tabulation),
fetch les barres EODHD manquantes, les insère dans ``stock_bars``, puis exécute
``DataSanitizer.run_pipeline()`` pour chaque symbole afin de repeupler
``stock_bars_daily``.

Le script fonctionne en **deux phases** :

Phase 1 — Fetch EODHD + upsert stock_bars ET stock_bars_daily (optimisée)
    - Regroupe toutes les dates par symbole (1 seule lecture du fichier).
    - Pour chaque symbole : **1 appel** ``fetch_eod`` (plage min→max) + **1 appel**
      ``fetch_splits``.
    - Reconstruit les barres split-only via ``eodhd_to_split_only``.
    - Filtre localement pour ne garder que les dates listées dans ``bars.txt``.
    - Upsert dans ``stock_bars`` ET ``stock_bars_daily`` (``ON DUPLICATE KEY UPDATE``,
      source = ``eodhd_eod``, data_source **explicitement positionné** — contrairement
      au sanitizer qui ne touche pas cette colonne).
    - Commit périodique tous les N symboles (``--commit-every``).

Phase 2 — data_sanitizer_daily
    - Pour chaque symbole traité avec succès en Phase 1, exécute
      ``DataSanitizer().run_pipeline(symbols=[symbol])``.
    - Cela forward-fill les jours manquants, calcule le ``daily_return``,
      détecte les anomalies, et upsert dans ``stock_bars_daily``.

--------------------------------------------------------------------------------
USAGE
--------------------------------------------------------------------------------

.. code-block:: bash

    # 1) Dry-run : simule sans écrire en base (recommandé avant la 1ʳᵉ exécution)
    python scripts/backfill_alpaca_to_eodhd.py --dry-run

    # 2) Exécution réelle complète (Phase 1 + Phase 2)
    python scripts/backfill_alpaca_to_eodhd.py

    # 3) Phase 1 uniquement (fetch EODHD + upsert stock_bars, sans sanitizer)
    python scripts/backfill_alpaca_to_eodhd.py --skip-phase2

    # 4) Phase 2 uniquement (si la Phase 1 a déjà été exécutée)
    python scripts/backfill_alpaca_to_eodhd.py --only-phase2

    # 5) Phase 2 pour des symboles spécifiques
    python scripts/backfill_alpaca_to_eodhd.py --only-phase2 --symbols AAPL MSFT TSLA

    # 6) Avec limite d'appels API (pour étaler sur plusieurs jours)
    python scripts/backfill_alpaca_to_eodhd.py --max-api-calls 500

    # 7) Commit DB tous les 100 symboles au lieu de 50
    python scripts/backfill_alpaca_to_eodhd.py --commit-every 100

    # 8) Fichier d'entrée alternatif
    python scripts/backfill_alpaca_to_eodhd.py --input /chemin/vers/mon_fichier.txt

--------------------------------------------------------------------------------
OPTIONS
--------------------------------------------------------------------------------

--input, -i           Chemin vers le fichier d'entrée (défaut : bars.txt).
--dry-run             Simule l'ensemble du pipeline sans écrire en base.
--skip-phase1         Saute la Phase 1 (pratique pour relancer uniquement le sanitizer).
--skip-phase2         Saute la Phase 2 (pratique pour ne faire que le fetch).
--only-phase2         Exécute UNIQUEMENT la Phase 2. Utiliser avec ``--symbols``
                      ou laisser le script relire bars.txt pour extraire les symboles.
--symbols SYM1 SYM2   Liste de symboles pour ``--only-phase2``.
--commit-every N      Commit DB tous les N symboles (défaut : 50).
--max-api-calls N     Nombre maximum d'appels API EODHD (0 = illimité).
                      Utile pour étaler le backfill sur plusieurs jours sans
                      dépasser le quota EODHD.

--------------------------------------------------------------------------------
PRÉREQUIS
--------------------------------------------------------------------------------

- Variables d'environnement : ``LOGIN_DB``, ``PASSWORD_DB``, ``EODHD_API_TOKEN``.
- Le fichier ``bars.txt`` doit être présent à la racine du projet (ou via ``--input``).
- L'environnement Python doit avoir les dépendances du projet installées
  (``requirements.txt``).
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path

# Ajouter la racine du projet au PYTHONPATH pour les imports (common, database, ...)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import MetaData, Table
from sqlalchemy.dialects.mysql import insert as mysql_insert

from common.logging_setup import configure_root_logging
from database.connection import SessionLocal, get_sqlalchemy_engine
from dataIntegrityEngine.data_sanitizer_daily import DataSanitizer
from service.eodhd.adapters import (
    eodhd_to_split_only,
    to_stock_bars_daily_row,
    to_stock_bars_row,
)
from service.eodhd.clientEodhd import (
    EodhdBarsFetchError,
    EodhdSymbolNotFound,
    fetch_eod,
    fetch_splits,
)
from service.eodhd.quota import EodhdQuotaExceeded

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

DEFAULT_COMMIT_EVERY_SYMBOLS = 50
MAX_API_CALLS_DEFAULT = 0  # 0 = pas de limite


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_input_path(raw: str | None) -> Path:
    """Résout le chemin du fichier d'entrée (relatif ou absolu)."""
    if raw is None:
        raw = "bars.txt"
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    script_dir = Path(__file__).resolve().parent
    for base in (script_dir.parent, Path.cwd()):
        resolved = base / candidate
        if resolved.exists():
            return resolved
    return Path(raw)


def _parse_line(line: str, line_no: int) -> tuple[str, date] | None:
    """Parse une ligne 'SYMBOL  DATE' (tab ou espaces multiples).

    Retourne (symbol, date) ou None si ligne vide / commentaire.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    parts = stripped.split()
    if len(parts) < 2:
        LOGGER.warning("Ligne %d ignorée (format invalide) : %r", line_no, stripped)
        return None
    symbol = parts[0].strip().upper()
    date_str = parts[1].strip()
    try:
        bar_date = date.fromisoformat(date_str)
    except ValueError:
        LOGGER.warning("Ligne %d ignorée (date invalide %r)", line_no, date_str)
        return None
    return symbol, bar_date


def _load_symbol_dates(input_path: Path) -> dict[str, set[date]]:
    """Lit le fichier et regroupe les dates par symbole.

    Retourne un dict ``{symbol: set(date, ...)}``.
    """
    symbol_dates: dict[str, set[date]] = {}
    total = 0

    LOGGER.info("Lecture de %s ...", input_path)
    with open(input_path, "r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            parsed = _parse_line(line, line_no)
            if parsed is None:
                continue
            symbol, bar_date = parsed
            symbol_dates.setdefault(symbol, set()).add(bar_date)
            total += 1

    LOGGER.info(
        "Fichier chargé : %d lignes valides, %d symboles uniques",
        total,
        len(symbol_dates),
    )
    return symbol_dates


@lru_cache(maxsize=1)
def _get_stock_bars_daily_table() -> Table:
    """Reflect ``stock_bars_daily`` (mise en cache)."""
    metadata = MetaData()
    engine = get_sqlalchemy_engine()
    return Table("stock_bars_daily", metadata, autoload_with=engine)


@lru_cache(maxsize=1)
def _get_stock_bars_table() -> Table:
    """Reflect ``stock_bars`` (mise en cache)."""
    metadata = MetaData()
    engine = get_sqlalchemy_engine()
    return Table("stock_bars", metadata, autoload_with=engine)


def _upsert_stock_bars_daily_rows(session, rows: list[dict]) -> int:
    """UPSERT dans ``stock_bars_daily`` (MySQL ON DUPLICATE KEY UPDATE).

    Contrairement au sanitizer (``_build_stock_bars_daily_records``), cette
    fonction inclut **explicitement** ``data_source`` dans les colonnes mises
    à jour, ce qui permet de corriger les lignes héritées d'Alpaca avec le
    défaut ``'alpaca_iex'``.
    """
    if not rows:
        return 0
    stock_bars_daily = _get_stock_bars_daily_table()
    stmt = mysql_insert(stock_bars_daily).values(rows)
    update_cols = {
        col: stmt.inserted[col]
        for col in (
            "open", "high", "low", "close", "volume", "adj_close",
            "vwap", "daily_return", "is_filled",
            "data_adjustment", "data_source",
        )
        if col in stock_bars_daily.c
    }
    session.execute(stmt.on_duplicate_key_update(**update_cols))
    return len(rows)


def _upsert_stock_bars_rows(session, rows: list[dict]) -> int:
    """UPSERT dans ``stock_bars`` (MySQL ON DUPLICATE KEY UPDATE)."""
    if not rows:
        return 0
    stock_bars = _get_stock_bars_table()
    stmt = mysql_insert(stock_bars).values(rows)
    update_cols = {
        col: stmt.inserted[col]
        for col in (
            "open_price", "high_price", "low_price", "close_price",
            "volume", "trade_count", "vwa_price",
            "data_adjustment", "data_source",
        )
        if col in stock_bars.c
    }
    session.execute(stmt.on_duplicate_key_update(**update_cols))
    return len(rows)


# ---------------------------------------------------------------------------
# Phase 1 : fetch EODHD + upsert stock_bars (stratégie groupée par symbole)
# ---------------------------------------------------------------------------


def _process_one_symbol(
    session,
    symbol: str,
    needed_dates: set[date],
    dry_run: bool,
    stats: dict,
) -> bool:
    """Traite un symbole : fetch EODHD pour la plage complète, filtre, upsert.

    Retourne True si au moins une barre a été insérée.
    """
    if not needed_dates:
        return False

    min_date = min(needed_dates)
    max_date = max(needed_dates)
    date_str_start = min_date.isoformat()
    date_str_end = max_date.isoformat()

    # 1) Fetch splits
    try:
        splits = fetch_splits(symbol)
    except Exception as exc:
        LOGGER.warning("[%s] échec fetch splits : %s", symbol, exc)
        splits = []

    # 2) Fetch historique EODHD pour la plage complète
    try:
        raw_bars = fetch_eod(symbol, start=date_str_start, end=date_str_end)
    except EodhdSymbolNotFound:
        LOGGER.warning("[%s] symbole inconnu chez EODHD", symbol)
        stats["symbol_not_found"] += 1
        return False
    except EodhdQuotaExceeded:
        LOGGER.error("[%s] quota EODHD dépassé", symbol)
        stats["quota_exceeded"] = True
        raise
    except EodhdBarsFetchError as exc:
        LOGGER.error("[%s] erreur fetch [%s -> %s] : %s", symbol, date_str_start, date_str_end, exc)
        stats["fetch_errors"] += 1
        return False

    if not raw_bars:
        LOGGER.info("[%s] aucune barre EODHD retournée [%s -> %s]", symbol, date_str_start, date_str_end)
        stats["no_data"] += 1
        return False

    # 3) Appliquer splits -> split-only
    split_only_bars = eodhd_to_split_only(raw_bars, splits)

    # 4) Filtrer exactement les dates demandées
    needed_str = {d.isoformat() for d in needed_dates}
    matching = [b for b in split_only_bars if str(b.get("date", "")) in needed_str]

    if not matching:
        LOGGER.info(
            "[%s] %d barres reçues mais aucune ne correspond aux %d dates demandées [%s -> %s]",
            symbol,
            len(split_only_bars),
            len(needed_dates),
            date_str_start,
            date_str_end,
        )
        stats["date_mismatch"] += 1
        return False

    # 5) Convertir en lignes stock_bars + stock_bars_daily
    stock_bars_rows = [to_stock_bars_row(b, symbol) for b in matching]
    stock_bars_daily_rows = [to_stock_bars_daily_row(b, symbol) for b in matching]
    found_count = len(stock_bars_rows)
    missing_count = len(needed_dates) - found_count

    if missing_count > 0:
        LOGGER.info(
            "[%s] %d/%d dates trouvées dans EODHD, %d manquantes",
            symbol,
            found_count,
            len(needed_dates),
            missing_count,
        )
        stats["dates_missing_in_eodhd"] += missing_count

    # 6) Upsert stock_bars + stock_bars_daily
    if dry_run:
        LOGGER.info(
            "[DRY-RUN] [%s] upsert : %d ligne(s) stock_bars + %d ligne(s) stock_bars_daily pour %d dates [%s -> %s]",
            symbol,
            found_count,
            len(stock_bars_daily_rows),
            len(needed_dates),
            date_str_start,
            date_str_end,
        )
    else:
        written_bars = _upsert_stock_bars_rows(session, stock_bars_rows)
        written_daily = _upsert_stock_bars_daily_rows(session, stock_bars_daily_rows)
        LOGGER.info(
            "[%s] upsert : %d stock_bars + %d stock_bars_daily [%s -> %s]",
            symbol,
            written_bars,
            written_daily,
            date_str_start,
            date_str_end,
        )
        stats["rows_written_stock_bars"] += written_bars
        stats["rows_written_stock_bars_daily"] += written_daily

    stats["bars_inserted"] += found_count
    stats["api_calls_used"] += 1  # fetch_eod
    if splits:
        stats["api_calls_used"] += 1  # fetch_splits
    return True


def _should_stop(stats: dict, max_api_calls: int) -> bool:
    if stats.get("quota_exceeded"):
        return True
    if max_api_calls > 0 and stats.get("api_calls_used", 0) >= max_api_calls:
        LOGGER.warning(
            "Limite d'appels API atteinte (%d) — arrêt anticipé",
            max_api_calls,
        )
        return True
    return False


def phase1_fetch_and_insert(
    symbol_dates: dict[str, set[date]],
    session,
    dry_run: bool,
    commit_every_symbols: int,
    max_api_calls: int,
) -> tuple[set[str], dict]:
    """Phase 1 : pour chaque symbole, fetch EODHD, upsert stock_bars.

    Commit périodique tous les ``commit_every_symbols`` symboles.
    """
    stats: dict = {
        "total_symbols": len(symbol_dates),
        "total_dates": sum(len(d) for d in symbol_dates.values()),
        "symbols_processed": 0,
        "bars_inserted": 0,
        "rows_written_stock_bars": 0,
        "rows_written_stock_bars_daily": 0,
        "symbol_not_found": 0,
        "fetch_errors": 0,
        "no_data": 0,
        "date_mismatch": 0,
        "dates_missing_in_eodhd": 0,
        "quota_exceeded": False,
        "api_calls_used": 0,
        "batch_commits": 0,
    }
    successful_symbols: set[str] = set()

    sorted_symbols = sorted(symbol_dates.keys())
    LOGGER.info(
        "=== Phase 1 : %d symboles, %d dates, commit tous les %d symboles ===",
        len(sorted_symbols),
        stats["total_dates"],
        commit_every_symbols,
    )

    for idx, symbol in enumerate(sorted_symbols, 1):
        needed_dates = symbol_dates[symbol]

        try:
            ok = _process_one_symbol(
                session=session,
                symbol=symbol,
                needed_dates=needed_dates,
                dry_run=dry_run,
                stats=stats,
            )
            if ok:
                successful_symbols.add(symbol)
            stats["symbols_processed"] += 1
        except EodhdQuotaExceeded:
            LOGGER.error("Arrêt anticipé : quota EODHD épuisé (symbole %d/%d).", idx, len(sorted_symbols))
            stats["quota_exceeded"] = True
            break
        except Exception:
            LOGGER.exception("[%s] erreur inattendue — symbole %d/%d", symbol, idx, len(sorted_symbols))
            stats["fetch_errors"] += 1

        # Commit périodique
        if not dry_run and idx % commit_every_symbols == 0 and (stats["rows_written_stock_bars"] > 0 or stats["rows_written_stock_bars_daily"] > 0):
            session.commit()
            stats["batch_commits"] += 1
            LOGGER.info(
                "Commit #%d | %d/%d symboles | %d lignes stock_bars + %d stock_bars_daily | %d appels API",
                stats["batch_commits"],
                idx,
                len(sorted_symbols),
                stats["rows_written_stock_bars"],
                stats["rows_written_stock_bars_daily"],
                stats["api_calls_used"],
            )

        if _should_stop(stats, max_api_calls):
            break

    # Commit final
    if not dry_run and (stats["rows_written_stock_bars"] > 0 or stats["rows_written_stock_bars_daily"] > 0):
        session.commit()
        stats["batch_commits"] += 1
        LOGGER.info(
            "Commit final : %d lignes stock_bars + %d stock_bars_daily, %d appels API",
            stats["rows_written_stock_bars"],
            stats["rows_written_stock_bars_daily"],
            stats["api_calls_used"],
        )

    return successful_symbols, stats


# ---------------------------------------------------------------------------
# Phase 2 : data_sanitizer_daily
# ---------------------------------------------------------------------------


def phase2_sanitize_daily(
    symbols: set[str],
    dry_run: bool,
) -> dict:
    """Phase 2 : exécute le pipeline data_sanitizer_daily pour chaque symbole."""
    stats: dict = {
        "symbols_processed": 0,
        "symbols_success": 0,
        "symbols_failed": 0,
        "rows_upserted_daily": 0,
    }

    if not symbols:
        LOGGER.info("Aucun symbole à traiter en Phase 2.")
        return stats

    sorted_symbols = sorted(symbols)
    LOGGER.info("=== Phase 2 : data_sanitizer_daily pour %d symbole(s) ===", len(sorted_symbols))

    if dry_run:
        LOGGER.info("[DRY-RUN] Phase 2 simulée pour %d symboles.", len(sorted_symbols))
        stats["symbols_processed"] = len(sorted_symbols)
        stats["symbols_success"] = len(sorted_symbols)
        return stats

    sanitizer = DataSanitizer()

    for idx, symbol in enumerate(sorted_symbols, 1):
        LOGGER.info("[%s] data_sanitizer_daily (%d/%d) ...", symbol, idx, len(sorted_symbols))
        try:
            summary = sanitizer.run_pipeline(symbols=[symbol])
            stats["symbols_processed"] += 1
            stats["symbols_success"] += int(summary.get("successful_symbols", 0))
            stats["symbols_failed"] += int(summary.get("failed_symbols", 0))
            stats["rows_upserted_daily"] += int(summary.get("upserted_rows", 0))
            LOGGER.info(
                "[%s] OK : success=%s failed=%s rows_daily=%s",
                symbol,
                summary.get("successful_symbols"),
                summary.get("failed_symbols"),
                summary.get("upserted_rows"),
            )
        except Exception:
            LOGGER.exception("[%s] échec data_sanitizer_daily", symbol)
            stats["symbols_failed"] += 1

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill EODHD pour les données alpaca_iex uniquement",
    )
    parser.add_argument(
        "--input", "-i",
        default="bars.txt",
        help="Chemin vers le fichier bars.txt (défaut: bars.txt)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule sans écrire en base",
    )
    parser.add_argument(
        "--skip-phase1",
        action="store_true",
        help="Saute la Phase 1 (fetch+insert stock_bars)",
    )
    parser.add_argument(
        "--skip-phase2",
        action="store_true",
        help="Saute la Phase 2 (data_sanitizer_daily)",
    )
    parser.add_argument(
        "--only-phase2",
        action="store_true",
        help="Exécute uniquement la Phase 2. Utilise --symbols ou relit bars.txt.",
    )
    parser.add_argument(
        "--symbols",
        nargs="*",
        help="Liste de symboles pour --only-phase2 (si omis, relit bars.txt)",
    )
    parser.add_argument(
        "--commit-every",
        type=int,
        default=DEFAULT_COMMIT_EVERY_SYMBOLS,
        help=f"Commit DB tous les N symboles (défaut: {DEFAULT_COMMIT_EVERY_SYMBOLS})",
    )
    parser.add_argument(
        "--max-api-calls",
        type=int,
        default=MAX_API_CALLS_DEFAULT,
        help="Nombre max d'appels API EODHD (0 = illimité). Utile pour étaler sur plusieurs jours.",
    )
    args = parser.parse_args()

    configure_root_logging(
        level=logging.INFO,
        log_path="./log/backfill_alpaca_to_eodhd.log",
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    input_path = _resolve_input_path(args.input)
    LOGGER.info("Fichier d'entrée : %s (dry_run=%s)", input_path, args.dry_run)

    session = SessionLocal()

    try:
        successful_symbols: set[str] = set()

        # ---- Phase 1 : fetch EODHD + upsert stock_bars ----
        if args.only_phase2:
            LOGGER.info("--only-phase2 : Phase 1 ignorée.")
            if args.symbols:
                successful_symbols = {s.strip().upper() for s in args.symbols if s.strip()}
            else:
                # Relire le fichier pour extraire les symboles
                if not input_path.exists():
                    LOGGER.error("Fichier introuvable : %s", input_path)
                    sys.exit(1)
                symbol_dates = _load_symbol_dates(input_path)
                successful_symbols = set(symbol_dates.keys())
        elif not args.skip_phase1:
            if not input_path.exists():
                LOGGER.error("Fichier introuvable : %s", input_path)
                sys.exit(1)

            symbol_dates = _load_symbol_dates(input_path)

            if not symbol_dates:
                LOGGER.warning("Aucune donnée valide dans %s — arrêt.", input_path)
                return

            successful_symbols, phase1_stats = phase1_fetch_and_insert(
                symbol_dates=symbol_dates,
                session=session,
                dry_run=args.dry_run,
                commit_every_symbols=args.commit_every,
                max_api_calls=args.max_api_calls,
            )

            LOGGER.info("=== Résumé Phase 1 ===")
            for k, v in phase1_stats.items():
                LOGGER.info("  %s: %s", k, v)

        # ---- Phase 2 : data_sanitizer_daily ----
        if not args.skip_phase2:
            if not successful_symbols and not args.only_phase2:
                LOGGER.warning("Aucun symbole traité avec succès en Phase 1 — Phase 2 ignorée.")
            else:
                phase2_stats = phase2_sanitize_daily(
                    symbols=successful_symbols,
                    dry_run=args.dry_run,
                )
                LOGGER.info("=== Résumé Phase 2 ===")
                for k, v in phase2_stats.items():
                    LOGGER.info("  %s: %s", k, v)
    finally:
        session.close()

    LOGGER.info("Terminé.")


if __name__ == "__main__":
    main()
