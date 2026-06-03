"""
Moteur d'orchestration du module corporate_actions.

Coordonne : ingestion provider → persist DB → application sur positions → audit.
"""
from __future__ import annotations

import logging
import math
from datetime import date
from typing import Any

from corporate_actions.db_io import CorporateActionRepository
from corporate_actions.models import (
    CaType,
    CorporateActionEvent,
    PositionSnapshot,
)
from corporate_actions.processors import process_dividend, process_split
from corporate_actions.provider import CorporateActionProvider

LOGGER = logging.getLogger(__name__)


class CorporateActionEngine:
    """
    Orchestrateur principal du module corporate actions.

    Responsabilités :
    1. sync()  — Ingérer les événements du provider et les persister en DB.
    2. apply() — Appliquer les événements pending sur les positions, de manière
                 idempotente et transactionnelle, avec audit trail complet.

    Stratégie données de marché (convention canonique projet) :
        Les barres OHLCV (`stock_bars`, `stock_bars_daily`) sont ingérées
        avec ``data_adjustment = 'split'`` quel que soit le provider primaire
        (Alpaca ``adjustment="split"`` ou EODHD reconstruction split-only —
        cf. ``dataIntegrityEngine/import_alpaca_bar.py:DATA_ADJUSTMENT`` et
        ``service/eodhd/adapters.py:DATA_ADJUSTMENT_SPLIT``). Cette convention
        est matérialisée par les contraintes SQL ``chk_bars_adj`` /
        ``chk_daily_adj`` (cf. ``doc/database.md`` §9).

        Conséquence : les **splits** sont déjà neutralisés dans les prix.
        Les **dividendes** ne sont PAS injectés dans les prix ; ils sont
        comptabilisés séparément par ce module via le ledger
        ``portfolio_cash_ledger``. La performance totale d'un portefeuille
        s'obtient donc par :

            MTM(positions, stock_bars_daily.close)
              + cumulative(portfolio_cash_ledger)

        Ce module NE TOUCHE PAS aux tables ``stock_bars`` /
        ``stock_bars_daily`` (les splits sont déjà appliqués upstream). Il
        gère uniquement la comptabilité portefeuille : qty (splits), cost
        basis (splits), cash (dividendes).
    """

    def __init__(
        self,
        provider: CorporateActionProvider,
        repo: CorporateActionRepository | None = None,
        account_id: str | None = None,
    ) -> None:
        self.provider = provider
        self.repo = repo or CorporateActionRepository()
        self.account_id = account_id

    # ------------------------------------------------------------------
    # Phase 1 : Synchronisation (ingestion)
    # ------------------------------------------------------------------

    def sync(
        self,
        symbols: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        batch_size: int = 25,
        skip_existing: bool = False,
    ) -> dict[str, int]:
        """
        Ingère les corporate actions depuis le provider et les persiste en DB.

        Retourne un résumé : {"fetched": N, "inserted": M, "duplicates": D, "invalid": I}
        """
        LOGGER.info(
            "Corporate actions sync started | symbols=%s start=%s end=%s batch_size=%s skip_existing=%s",
            symbols, start_date, end_date, batch_size, skip_existing,
        )

        if symbols == []:
            LOGGER.info("Corporate actions sync skipped | aucun symbole resolu pour la synchronisation.")
            return {"fetched": 0, "inserted": 0, "duplicates": 0, "invalid": 0}

        if batch_size < 1:
            raise ValueError("batch_size doit être supérieur ou égal à 1.")

        if skip_existing and symbols is not None:
            existing_symbols = set(self.repo.load_existing_event_symbols(symbols))
            if existing_symbols:
                filtered_symbols = [symbol for symbol in symbols if symbol.upper() not in existing_symbols]
                LOGGER.info(
                    "Corporate actions sync skip_existing actif | requested=%d existing=%d filtered=%d",
                    len(symbols),
                    len(existing_symbols),
                    len(filtered_symbols),
                )
                symbols = filtered_symbols

        if skip_existing and symbols is None:
            LOGGER.warning(
                "skip_existing ignore car le perimetre sync est global (symbols=None). "
                "Utiliser un perimetre de symboles resolu pour exclure les symboles deja presents."
            )

        if symbols == []:
            LOGGER.info("Corporate actions sync skipped | tous les symboles resolus existent deja en base.")
            return {"fetched": 0, "inserted": 0, "duplicates": 0, "invalid": 0}

        stats = {"fetched": 0, "inserted": 0, "duplicates": 0, "invalid": 0}

        if symbols is None:
            events = self.provider.fetch_events(
                symbols=None,
                start_date=start_date,
                end_date=end_date,
            )
            self._ingest_events(events, stats)
        else:
            total_symbols = len(symbols)
            total_batches = math.ceil(total_symbols / batch_size)
            for batch_index, batch_symbols in enumerate(self._chunk_symbols(symbols, batch_size), start=1):
                first_symbol_index = ((batch_index - 1) * batch_size) + 1
                last_symbol_index = first_symbol_index + len(batch_symbols) - 1
                LOGGER.info(
                    "Corporate actions sync batch %d/%d | symbols %d-%d/%d | batch_size=%d | first=%s | last=%s",
                    batch_index,
                    total_batches,
                    first_symbol_index,
                    last_symbol_index,
                    total_symbols,
                    len(batch_symbols),
                    batch_symbols[0],
                    batch_symbols[-1],
                )
                events = self.provider.fetch_events(
                    symbols=batch_symbols,
                    start_date=start_date,
                    end_date=end_date,
                )
                self._ingest_events(events, stats)

        LOGGER.info("Corporate actions sync completed | stats=%s", stats)
        return stats

    def _ingest_events(self, events: list[CorporateActionEvent], stats: dict[str, int]) -> None:
        """Valide et persiste les événements immédiatement après chaque appel provider."""
        stats["fetched"] += len(events)
        for event in events:
            errors = event.validate()
            if errors:
                LOGGER.warning("Evenement corporate action invalide ignore | symbol=%s errors=%s", event.symbol, errors)
                stats["invalid"] += 1
                continue

            row_id = self.repo.insert_event(event)
            if row_id == -1:
                stats["duplicates"] += 1
            else:
                stats["inserted"] += 1

    @staticmethod
    def _chunk_symbols(symbols: list[str], batch_size: int) -> list[list[str]]:
        """Découpe une liste de symboles en lots ordonnés de taille maximale batch_size."""
        return [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]


    # ------------------------------------------------------------------
    # Phase 2 : Application sur positions
    # ------------------------------------------------------------------

    def apply(
        self,
        as_of: date | None = None,
        positions: list[dict[str, Any]] | None = None,
    ) -> dict[str, int]:
        """
        Applique les événements pending sur les positions actuelles.

        Paramètres :
            as_of      — Ne traiter que les événements dont ex_date <= as_of.
            positions  — Positions override (pour tests). Si None, charge depuis le dernier snapshot broker.

        Retourne un résumé : {"applied": N, "skipped": M, "failed": F}
        """
        LOGGER.info("Corporate actions apply started | as_of=%s", as_of)

        pending = self.repo.load_pending_events(as_of=as_of)
        if not pending:
            LOGGER.info("Aucun evenement corporate action pending a traiter.")
            return {"applied": 0, "skipped": 0, "failed": 0}

        # Charger les positions
        if positions is None:
            raw_positions = self.repo.load_latest_positions(account_id=self.account_id)
        else:
            raw_positions = positions

        if not raw_positions:
            LOGGER.warning(
                "Aucune position broker trouvee dans broker_positions_snapshots. "
                "L'apply ne peut crediter de dividendes ni ajuster de splits sans positions. "
                "Verifier que execution_engine a deja tourne au moins une fois."
            )

        position_map: dict[str, PositionSnapshot] = {
            str(p.get("symbol", "")).upper(): PositionSnapshot(
                symbol=str(p.get("symbol", "")).upper(),
                qty=float(p.get("qty", 0)),
                avg_entry_price=float(p.get("avg_entry_price", 0)),
                market_value=float(p.get("market_value", 0)),
            )
            for p in raw_positions
        }

        stats = {"applied": 0, "skipped": 0, "failed": 0}

        for event in pending:
            try:
                self._apply_single(event, position_map, stats)
            except Exception as exc:
                LOGGER.exception(
                    "Erreur lors de l'application du corporate action | id=%s symbol=%s type=%s",
                    event.id, event.symbol, event.ca_type,
                )
                if event.id is not None:
                    self.repo.mark_failed(event.id, str(exc)[:500])
                stats["failed"] += 1

        LOGGER.info("Corporate actions apply completed | stats=%s", stats)
        return stats

    def _apply_single(
        self,
        event: CorporateActionEvent,
        position_map: dict[str, PositionSnapshot],
        stats: dict[str, int],
    ) -> None:
        """Applique un seul événement corporate action."""
        validation_errors = event.validate()
        if validation_errors:
            message = "; ".join(validation_errors)
            LOGGER.warning(
                "Evenement corporate action invalide au moment de l'apply | id=%s symbol=%s errors=%s",
                event.id,
                event.symbol,
                validation_errors,
            )
            if event.id is not None:
                self.repo.mark_failed(event.id, message[:500])
            stats["failed"] += 1
            return

        # Phase 5.3.a — Vérification idempotence scopée par account_id.
        # ``is_event_applied`` essaie d'abord la clé scopée (account_id) puis
        # tombe sur la clé legacy pour les events ingérés avant la migration.
        scoped_key = event.compute_idempotency_key(self.account_id)
        legacy_key = event.idempotency_key
        if self.repo.is_event_applied(scoped_key, legacy_key=legacy_key):
            LOGGER.debug(
                "Evenement deja applique (idempotence) | scoped_key=%s legacy_key=%s",
                scoped_key, legacy_key,
            )
            stats["skipped"] += 1
            return

        # Vérifier que nous avons une position
        pos = position_map.get(event.symbol)
        if pos is None or pos.qty <= 0:
            LOGGER.info(
                "Pas de position pour %s, skip corporate action id=%s",
                event.symbol, event.id,
            )
            if event.id is not None:
                self.repo.mark_skipped(event.id, f"No position held for {event.symbol}")
            stats["skipped"] += 1
            return

        # Dispatch par type
        if event.ca_type in (CaType.CASH_DIVIDEND, CaType.SPECIAL_DIVIDEND):
            application, ledger = process_dividend(event, pos)
            self.repo.insert_application(application, account_id=self.account_id)
            self.repo.insert_cash_ledger(ledger, account_id=self.account_id)

        elif event.ca_type in (CaType.SPLIT, CaType.REVERSE_SPLIT):
            application, ledger = process_split(event, pos)
            self.repo.insert_application(application, account_id=self.account_id)
            if ledger is not None:
                self.repo.insert_cash_ledger(ledger, account_id=self.account_id)
            # Mettre à jour la position en mémoire pour les événements suivants
            pos.qty = application.position_qty_after
            if application.cost_basis_after is not None:
                pos.avg_entry_price = application.cost_basis_after

        else:
            LOGGER.warning("Type de corporate action non supporte : %s", event.ca_type)
            if event.id is not None:
                self.repo.mark_skipped(event.id, f"Unsupported ca_type: {event.ca_type}")
            stats["skipped"] += 1
            return

        # Marquer comme appliqué
        if event.id is not None:
            self.repo.mark_applied(event.id)
        stats["applied"] += 1


