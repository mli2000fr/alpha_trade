"""Sprint S12.3 — Récupération paginée des Alpaca account activities.

Endpoint : ``GET /v2/account/activities`` (filtrable par
``activity_types``, ``date``, ``page_token``, ``page_size``).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Iterable

from service.alpaca.trading_client import AlpacaTradingClient

LOGGER = logging.getLogger(__name__)

#: Activités pertinentes pour la réconciliation des fills.
FILL_ACTIVITY_TYPES: tuple[str, ...] = ("FILL", "PFILL")


def fetch_account_activities(
    client: AlpacaTradingClient,
    *,
    since: date | datetime | None = None,
    until: date | datetime | None = None,
    activity_types: Iterable[str] = FILL_ACTIVITY_TYPES,
    page_size: int = 100,
    max_pages: int = 200,
) -> list[dict[str, Any]]:
    """Récupère toutes les activities (paginé) sur la fenêtre demandée.

    Le paramètre ``page_token`` Alpaca correspond à l'``id`` de la dernière
    activity de la page précédente.
    """
    params: dict[str, str] = {
        "page_size": str(page_size),
        "activity_types": ",".join(activity_types),
        "direction": "asc",
    }
    if since is not None:
        params["after"] = _iso(since)
    if until is not None:
        params["until"] = _iso(until)

    out: list[dict[str, Any]] = []
    page_token: str | None = None
    for _ in range(max_pages):
        if page_token:
            params["page_token"] = page_token
        try:
            resp = client._request("GET", "/v2/account/activities", params=dict(params))  # noqa: SLF001
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("fetch_account_activities: %s", exc)
            break
        if not isinstance(resp, list) or not resp:
            break
        out.extend(resp)
        if len(resp) < page_size:
            break
        page_token = str(resp[-1].get("id") or "")
        if not page_token:
            break
    return out


def _iso(d: date | datetime) -> str:
    if isinstance(d, datetime):
        return d.isoformat()
    return d.isoformat()


__all__ = ["fetch_account_activities", "FILL_ACTIVITY_TYPES"]

