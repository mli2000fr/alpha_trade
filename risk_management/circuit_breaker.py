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

    # Alerting multi-canaux (Slack / SMTP / log) via service.alerting
    if event == "circuit_breaker_fired":
        try:
            from service.alerting import send_system_alert

            send_system_alert(event="CIRCUIT_BREAKER_FIRED", payload=payload, severity="critical")
        except Exception:  # noqa: BLE001 — alerting best-effort
            LOGGER.debug("Notification externe circuit_breaker indisponible.", exc_info=True)


class CircuitBreaker:
    """Évalue si le trading doit être suspendu.

    Phase C.5 (parité backtest) : supporte un mode dégradé avec allocation
    réduite (``degraded_entry_allocation_pct`` dans ``RiskConfig``) et un
    pic roulant optionnel (``rolling_peak_window_days``).
    Si ``degraded_entry_allocation_pct > 0``, ``is_active()`` retourne toujours
    ``False`` (le circuit breaker ne bloque plus totalement) mais ``allocation_scale()``
    retourne la fraction d'allocation autorisée.

    Sprint short — ramp-up régimed : si ``regime_ramp_up_enabled``, l'allocation
    dégradée est progressivement augmentée quand le régime est ``normal`` ET que
    l'equity établit un nouveau pic sur la fenêtre glissante des N derniers jours
    (``regime_ramp_up_peak_window_days``). Le streak est gelé si l'equity ne fait
    pas de nouveau pic, et remis à zéro si le régime quitte ``normal``.
    """

    def __init__(self, config: RiskConfig, pnl: PnLSnapshot | None = None) -> None:
        self._cfg = config
        self._pnl = pnl or PnLSnapshot()
        self._last_notified_signature: str | None = None
        self._peak_window: list[float] = []
        self._tripped: bool = False
        self._normal_streak: int = 0
        self._equity_prev: float = 0.0
        self._equity_peak_window: list[float] = []

    # ------------------------------------------------------------------
    # Pic de référence roulant (optionnel)
    # ------------------------------------------------------------------
    def _reference_hwm(self) -> float | None:
        """Retourne le high-watermark de référence (roulant ou absolu)."""
        hwm = self._pnl.portfolio_high_watermark
        window = int(self._cfg.rolling_peak_window_days)
        if window <= 0:
            # Comportement original : pic absolu fourni par l'appelant
            return hwm
        cur = self._pnl.portfolio_current_value
        if cur is not None and cur > 0:
            self._peak_window.append(float(cur))
            if len(self._peak_window) > window:
                self._peak_window = self._peak_window[-window:]
        if not self._peak_window:
            return hwm
        return float(max(self._peak_window))

    def allocation_scale(self, entry_mode: str | None = None) -> float:
        """Fraction d'allocation autorisée : 1.0 si normal, dégradé si trippé.

        Si le ramp-up régimed est actif, l'allocation dégradée de base est
        augmentée de ``regime_ramp_up_pct_per_day`` par jour où le régime
        est ``normal`` ET l'equity progresse, plafonnée à ``regime_ramp_up_max_pct``.
        """
        if not self._tripped:
            return 1.0
        base = float(max(0.0, min(1.0, float(self._cfg.degraded_entry_allocation_pct))))
        if not self._cfg.regime_ramp_up_enabled or not entry_mode:
            return base
        if str(entry_mode).strip().lower() == "normal" and self._normal_streak > 0:
            ramp_bonus = float(self._normal_streak) * float(self._cfg.regime_ramp_up_pct_per_day)
            return float(max(0.0, min(1.0, base + ramp_bonus, float(self._cfg.regime_ramp_up_max_pct))))
        return base

    def update_regime_streak(self, entry_mode: str | None, current_equity: float = 0.0) -> None:
        """Met à jour le compteur de jours de recovery.

        Le streak n'est incrémenté que si :
        - le breaker est trippé,
        - le régime est ``normal``,
        - l'equity du jour établit un nouveau pic sur la fenêtre glissante
          des N derniers jours (``regime_ramp_up_peak_window_days``).

        Cela rend le ramp-up résilient aux jours de stagnation : le streak
        progresse dès que l'equity dépasse le meilleur niveau récent, sans
        exiger une hausse quotidienne stricte.

        Si le régime est normal mais que l'equity ne fait pas de nouveau pic,
        le streak reste inchangé (gelé, pas de reset).
        Tout régime non-normal remet le compteur à zéro.
        """
        if not self._cfg.regime_ramp_up_enabled or not self._tripped:
            self._normal_streak = 0
            self._equity_peak_window.clear()
            return
        if entry_mode and str(entry_mode).strip().lower() == "normal":
            # Alimente la fenêtre glissante des N derniers jours
            if current_equity > 0:
                self._equity_peak_window.append(float(current_equity))
                peak_window = int(self._cfg.regime_ramp_up_peak_window_days)
                if peak_window > 0 and len(self._equity_peak_window) > peak_window:
                    self._equity_peak_window = self._equity_peak_window[-peak_window:]
            # Incrémente le streak si l'equity du jour bat le pic des jours précédents
            if len(self._equity_peak_window) >= 2:
                previous_peak = max(self._equity_peak_window[:-1])
                if current_equity > previous_peak:
                    self._normal_streak += 1
            # else: streak gelé (normal mais equity ne fait pas de nouveau pic)
        else:
            self._normal_streak = 0
            self._equity_peak_window.clear()

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
        """Retourne True si un circuit breaker est déclenché ET qu'il n'y a pas de mode dégradé.

        En mode dégradé (``degraded_entry_allocation_pct > 0``), le breaker
        ne bloque jamais l'executor, mais bascule ``_tripped = True`` pour
        activer l'allocation réduite. Une fois trippé, il ne revient à
        ``False`` que si l'equity remonte au-dessus de
        ``recovery_pct * high_watermark`` (hystérésis de réarmement).
        """
        status = self.status()
        degraded = float(self._cfg.degraded_entry_allocation_pct) > 0.0
        if status.active and degraded:
            # Mode dégradé : on signale mais on ne bloque pas l'executor
            self._tripped = True
            return False
        if self._tripped and degraded and not status.active:
            # Vérifie si l'equity a suffisamment récupéré pour désactiver le mode dégradé
            hwm = self._reference_hwm()
            cur = self._pnl.portfolio_current_value
            if hwm is not None and cur is not None and hwm > 0:
                if cur >= hwm * float(self._cfg.recovery_pct):
                    self._tripped = False
                    self._normal_streak = 0
                    self._equity_peak_window.clear()
            # Si pas encore récupéré, on reste en mode dégradé
            return False
        # Mode non-dégradé (blocage total) : _tripped suit status.active sans hystérésis
        self._tripped = status.active
        return status.active

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
        hwm = self._reference_hwm()
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
