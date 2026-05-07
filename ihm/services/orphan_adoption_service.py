"""Helpers IHM pour adoption d'ordres orphelins (achat / vente manuelle).

Permet d'écrire l'audit trail canonique (``execution_*``) immédiatement après
une action manuelle déclenchée depuis l'IHM (bouton "Vendre tout" de la page
Compte Alpaca, par exemple), sans attendre le prochain cycle de
réconciliation broker.
"""
from __future__ import annotations

import logging
from typing import Any

from execution_engine.db_io import ExecutionRepository
from execution_engine.orphan_adoption import adopt_orphan_sell
from service.alpaca.accounts import AccountRegistry

LOGGER = logging.getLogger(__name__)


def adopt_after_close(
    *,
    account_id: str,
    symbol: str,
    close_payload: dict[str, Any] | None,
) -> bool:
    """Adopte la vente manuelle qui vient d'être déclenchée par l'IHM.

    ``close_payload`` est le dict retourné par ``close_position_all`` (= le
    payload broker de l'ordre de clôture créé par Alpaca). Si Alpaca ne
    renvoie pas un dict exploitable, l'adoption est silencieusement ignorée :
    la prochaine sync broker (cycle d'exécution / tick du watcher) la rattrapera.
    """
    if not isinstance(close_payload, dict) or not close_payload.get("id"):
        LOGGER.debug(
            "adopt_after_close: payload broker indisponible pour %s, "
            "adoption laissée à la prochaine réconciliation.",
            symbol,
        )
        return False
    try:
        account = AccountRegistry.get().resolve(account_id)
        broker_mode = account.mode
    except Exception:
        broker_mode = "paper"

    try:
        repo = ExecutionRepository()
    except Exception:
        LOGGER.warning("adopt_after_close: ExecutionRepository indisponible", exc_info=True)
        return False

    # Aligne le payload sur le format consommé par adopt_orphan_sell.
    raw_order = dict(close_payload)
    raw_order.setdefault("symbol", symbol)
    raw_order.setdefault("side", "sell")

    try:
        result = adopt_orphan_sell(
            repo,
            broker_mode=broker_mode,
            account_id=account_id,
            raw_order=raw_order,
        )
    except Exception:
        LOGGER.warning("adopt_after_close: adoption échouée pour %s", symbol, exc_info=True)
        return False
    return result is not None

