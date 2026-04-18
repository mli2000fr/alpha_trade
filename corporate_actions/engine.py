"""
Moteur d'orchestration du module corporate_actions.

Coordonne : ingestion provider → persist DB → application sur positions → audit.
"""
from __future__ import annotations

import logging
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

    Stratégie données de marché :
        Les barres OHLCV sont ingérées avec Alpaca adjustment="all".
        Les prix historiques sont DÉJÀ ajustés pour splits et dividendes.
        Ce module NE TOUCHE PAS aux tables stock_bars / stock_bars_daily.
        Il gère uniquement la comptabilité portefeuille (qty, cost basis, cash).
    """

    def __init__(
        self,
        provider: CorporateActionProvider,
        repo: CorporateActionRepository | None = None,
    ) -> None:
        self.provider = provider
        self.repo = repo or CorporateActionRepository()

    # ------------------------------------------------------------------
    # Phase 1 : Synchronisation (ingestion)
    # ------------------------------------------------------------------

    def sync(
        self,
        symbols: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, int]:
        """
        Ingère les corporate actions depuis le provider et les persiste en DB.

        Retourne un résumé : {"fetched": N, "inserted": M, "duplicates": D, "invalid": I}
        """
        LOGGER.info("Corporate actions sync started | symbols=%s start=%s end=%s", symbols, start_date, end_date)

        events = self.provider.fetch_events(
            symbols=symbols or [],
            start_date=start_date,
            end_date=end_date,
        )

        stats = {"fetched": len(events), "inserted": 0, "duplicates": 0, "invalid": 0}

        for event in events:
            errors = event.validate()
            if errors:
                LOGGER.warning("Événement corporate action invalide ignoré | symbol=%s errors=%s", event.symbol, errors)
                stats["invalid"] += 1
                continue

            row_id = self.repo.insert_event(event)
            if row_id == -1:
                stats["duplicates"] += 1
            else:
                stats["inserted"] += 1

        LOGGER.info("Corporate actions sync completed | stats=%s", stats)
        return stats

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
            LOGGER.info("Aucun événement corporate action pending à traiter.")
            return {"applied": 0, "skipped": 0, "failed": 0}

        # Charger les positions
        if positions is None:
            raw_positions = self.repo.load_latest_positions()
        else:
            raw_positions = positions

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
        # Vérification idempotence
        if self.repo.is_event_applied(event.idempotency_key):
            LOGGER.debug("Événement déjà appliqué (idempotence) | key=%s", event.idempotency_key)
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
            self.repo.insert_application(application)
            self.repo.insert_cash_ledger(ledger)

        elif event.ca_type in (CaType.SPLIT, CaType.REVERSE_SPLIT):
            application, ledger = process_split(event, pos)
            self.repo.insert_application(application)
            if ledger is not None:
                self.repo.insert_cash_ledger(ledger)
            # Mettre à jour la position en mémoire pour les événements suivants
            pos.qty = application.position_qty_after
            if application.cost_basis_after is not None:
                pos.avg_entry_price = application.cost_basis_after

        else:
            LOGGER.warning("Type de corporate action non supporté : %s", event.ca_type)
            if event.id is not None:
                self.repo.mark_skipped(event.id, f"Unsupported ca_type: {event.ca_type}")
            stats["skipped"] += 1
            return

        # Marquer comme appliqué
        if event.id is not None:
            self.repo.mark_applied(event.id)
        stats["applied"] += 1


