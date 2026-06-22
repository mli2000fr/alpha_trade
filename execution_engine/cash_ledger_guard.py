"""Sprint S9 — Cash Ledger Guard : vérification de cohérence quotidienne.

Vérifie l'alignement entre le cash settled, le cash unsettled (J+1 settlement),
la valeur de marché des positions et l'equity rapportée par le broker.

Un désalignement (> 1% par défaut) déclenche une alerte système critique.
"""
from __future__ import annotations

import logging
from typing import Optional

LOGGER = logging.getLogger(__name__)

# Seuil de tolérance par défaut : 1% d'écart entre equity calculée et equity rapportée.
DEFAULT_TOLERANCE_PCT = 0.01  # 1%


def check_cash_ledger_consistency(
    settled_cash: float,
    unsettled_cash: float = 0.0,
    market_value: float = 0.0,
    reported_equity: float = 0.0,
    *,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
    account_id: str | None = None,
) -> bool:
    """Vérifie la cohérence du cash ledger et alerte en cas de désalignement.

    Parameters
    ----------
    settled_cash:
        Cash réglé (settled) disponible.
    unsettled_cash:
        Cash en attente de settlement J+1.
    market_value:
        Valeur de marché totale des positions ouvertes.
    reported_equity:
        Equity rapportée par le broker (``portfolio_value`` ou ``equity``).
    tolerance_pct:
        Écart relatif maximal toléré avant alerte (défaut 1%).
    account_id:
        Identifiant du compte pour le contexte d'alerte.

    Returns
    -------
    bool
        ``True`` si cohérent, ``False`` si désalignement détecté.
    """
    computed_equity = settled_cash + unsettled_cash + market_value

    if reported_equity <= 0:
        LOGGER.warning(
            "cash_ledger_guard | reported_equity=%.2f <= 0 — vérification impossible.",
            reported_equity,
        )
        return True  # pas d'alerte si pas de référence fiable

    if computed_equity <= 0:
        LOGGER.warning(
            "cash_ledger_guard | computed_equity=%.2f <= 0 — vérification ignorée.",
            computed_equity,
        )
        return True

    delta = computed_equity - reported_equity
    delta_pct = abs(delta) / reported_equity

    if delta_pct <= tolerance_pct:
        LOGGER.debug(
            "cash_ledger_guard OK | computed=%.2f reported=%.2f delta=%.2f (%.4f%%)",
            computed_equity,
            reported_equity,
            delta,
            delta_pct * 100,
        )
        # Métrique Prometheus
        try:
            from service.prometheus_metrics import set_cash_ledger_aligned
            set_cash_ledger_aligned(True)
        except Exception:
            pass
        return True

    # Désalignement détecté → alerte système
    LOGGER.error(
        "cash_ledger_guard MISALIGNMENT | computed=%.2f reported=%.2f delta=%.2f (%.2f%%) "
        "settled=%.2f unsettled=%.2f market_value=%.2f",
        computed_equity,
        reported_equity,
        delta,
        delta_pct * 100,
        settled_cash,
        unsettled_cash,
        market_value,
    )

    # Métrique Prometheus
    try:
        from service.prometheus_metrics import set_cash_ledger_aligned
        set_cash_ledger_aligned(False)
    except Exception:
        pass

    try:
        from service.alerting import send_system_alert

        send_system_alert(
            event="CASH_LEDGER_MISALIGNMENT",
            payload={
                "settled_cash": round(settled_cash, 2),
                "unsettled_cash": round(unsettled_cash, 2),
                "market_value": round(market_value, 2),
                "computed_equity": round(computed_equity, 2),
                "reported_equity": round(reported_equity, 2),
                "delta": round(delta, 2),
                "delta_pct": round(delta_pct * 100, 4),
                "tolerance_pct": round(tolerance_pct * 100, 2),
                "account_id": account_id or "unknown",
            },
            severity="critical",
        )
    except Exception:
        LOGGER.debug("Alerte cash ledger indisponible.", exc_info=True)

    return False


def check_cash_ledger_from_broker_snapshot(
    snapshot: dict,
    *,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
) -> bool:
    """Version utilitaire qui extrait les champs d'un snapshot broker (Alpaca).

    Le snapshot doit contenir les clés :
    - ``cash`` ou ``settled_cash``
    - ``accrued_fees``, ``pending_transfer_out``, etc. (agrégés en unsettled)
    - ``portfolio_value`` ou ``equity``
    - ``long_market_value`` + ``short_market_value`` ou ``market_value``
    """
    def _f(key: str, default: float = 0.0) -> float:
        val = snapshot.get(key)
        if val is None:
            return default
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    settled = _f("settled_cash") or _f("cash")
    # Unsettled approximatif : ce qui est dû mais pas encore réglé
    unsettled = (
        _f("accrued_fees")
        + _f("pending_transfer_out", 0.0)
        - _f("pending_transfer_in", 0.0)
    )
    market_value = _f("long_market_value") + _f("short_market_value") or _f("market_value") or _f("portfolio_value")
    reported_equity = _f("portfolio_value") or _f("equity")

    account_id = str(snapshot.get("account_id") or snapshot.get("account_number") or "")

    return check_cash_ledger_consistency(
        settled_cash=settled,
        unsettled_cash=unsettled,
        market_value=market_value,
        reported_equity=reported_equity,
        tolerance_pct=tolerance_pct,
        account_id=account_id or None,
    )


__all__ = [
    "check_cash_ledger_consistency",
    "check_cash_ledger_from_broker_snapshot",
    "DEFAULT_TOLERANCE_PCT",
]
