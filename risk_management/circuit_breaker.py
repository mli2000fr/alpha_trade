"""Circuit breaker — coupe les allocations si drawdown/perte excessive.

Sprint S3 / A-013 : l'évaluation est désormais explicitement scindée en deux :

- ``status()`` / ``is_active()`` restent purs et sans effet de bord ;
- ``notify_if_active()`` envoie au plus une notification best-effort par
  statut déclenché.

La dépendance vers ``ihm.services.email_notifier`` est importée à la volée pour
éviter de polluer les imports du moteur risk.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from risk_management.config import RiskConfig

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class PnLSnapshot:
    """Snapshot PnL injecté de l'extérieur (ou valeurs par défaut)."""
    portfolio_high_watermark: float | None = None
    portfolio_current_value: float | None = None
    daily_pnl: float | None = None


@dataclass(frozen=True, slots=True)
class CircuitBreakerStatus:
    """Statut évalué du circuit breaker, sans effet de bord."""

    active: bool
    trigger: str | None = None
    payload: dict[str, Any] | None = None


def _try_send_alert(event: str, payload: dict) -> None:
    """Tente d'envoyer des notifications — silencieux si désactivé.

    Envoie les alertes par tous les canaux disponibles:
    - Email (IHM) — historique
    - Slack webhook (nouveau S5.2) — pour alerting opérateur temps réel
    """
    # Email (historique)
    try:
        from ihm.services.email_notifier import send_notification
        send_notification(event=event, payload=payload)
    except Exception:  # noqa: BLE001 — alerting best-effort, ne bloque jamais le trading
        LOGGER.debug("Notification email circuit_breaker indisponible.", exc_info=True)

    # Slack webhook (nouveau S5.2) — utilise le notifier existant de service.alerting
    if event == "circuit_breaker_fired":
        try:
            from service.alerting import build_notifier_from_env, SlackNotifier

            trigger = payload.get("trigger", "unknown")
            reason = f"{trigger.upper()}: {payload}"  # Formattage simplifié

            # Créer le notifier depuis l'env si Slack est configuré
            notifier = build_notifier_from_env()  # Retourne SlackNotifier ou LogNotifier

            notifier.send(
                subject=f"Circuit Breaker: {trigger}",
                body=reason,
                severity="critical"
            )
        except Exception:  # noqa: BLE001 — alerting best-effort
            LOGGER.debug("Notification Slack circuit_breaker indisponible.", exc_info=True)


class CircuitBreaker:
    """Évalue si le trading doit être suspendu."""

    def __init__(self, config: RiskConfig, pnl: PnLSnapshot | None = None) -> None:
        self._cfg = config
        self._pnl = pnl or PnLSnapshot()
        self._last_notified_signature: str | None = None

    def status(self) -> CircuitBreakerStatus:
        """Évalue le statut courant sans journalisation ni notification."""
        drawdown_status = self._evaluate_drawdown()
        if drawdown_status.active:
            return drawdown_status
        daily_loss_status = self._evaluate_daily_loss()
        if daily_loss_status.active:
            return daily_loss_status
        return CircuitBreakerStatus(active=False)

    def is_active(self) -> bool:
        """Retourne True si un circuit breaker est déclenché."""
        return self.status().active

    def notify_if_active(self) -> bool:
        """Envoie au plus une alerte par statut déclenché."""
        status = self.status()
        if not status.active or not status.trigger or not status.payload:
            return False
        signature = f"{status.trigger}:{status.payload}"
        if signature == self._last_notified_signature:
            return False
        self._last_notified_signature = signature
        if status.trigger == "drawdown":
            LOGGER.warning(
                "Circuit breaker drawdown: %.2f%% >= seuil %.2f%%",
                float(status.payload["drawdown_pct"]),
                float(status.payload["threshold_pct"]),
            )
        elif status.trigger == "daily_loss":
            LOGGER.warning(
                "Circuit breaker daily loss: %.2f%% >= seuil %.2f%%",
                float(status.payload["daily_loss_pct"]),
                float(status.payload["threshold_pct"]),
            )
        _try_send_alert(event="circuit_breaker_fired", payload=status.payload)
        return True

    # ------------------------------------------------------------------
    def _evaluate_drawdown(self) -> CircuitBreakerStatus:
        hwm = self._pnl.portfolio_high_watermark
        cur = self._pnl.portfolio_current_value
        if hwm is None or cur is None or hwm <= 0:
            return CircuitBreakerStatus(active=False)
        dd = (hwm - cur) / hwm
        if dd >= self._cfg.max_portfolio_drawdown_pct:
            return CircuitBreakerStatus(
                active=True,
                trigger="drawdown",
                payload={
                    "trigger": "drawdown",
                    "drawdown_pct": round(dd * 100, 2),
                    "threshold_pct": round(self._cfg.max_portfolio_drawdown_pct * 100, 2),
                    "portfolio_high_watermark": hwm,
                    "portfolio_current_value": cur,
                },
            )
        return CircuitBreakerStatus(active=False)

    def _evaluate_daily_loss(self) -> CircuitBreakerStatus:
        daily = self._pnl.daily_pnl
        if daily is None:
            return CircuitBreakerStatus(active=False)
        equity = self._cfg.account_equity
        if equity <= 0:
            return CircuitBreakerStatus(active=False)
        loss_pct = abs(min(daily, 0.0)) / equity
        if loss_pct >= self._cfg.max_daily_loss_pct:
            return CircuitBreakerStatus(
                active=True,
                trigger="daily_loss",
                payload={
                    "trigger": "daily_loss",
                    "daily_loss_pct": round(loss_pct * 100, 2),
                    "threshold_pct": round(self._cfg.max_daily_loss_pct * 100, 2),
                    "daily_pnl": daily,
                    "account_equity": equity,
                },
            )
        return CircuitBreakerStatus(active=False)
