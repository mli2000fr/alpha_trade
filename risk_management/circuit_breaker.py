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

    # Alerting multi-canaux (Slack / SMTP / Telegram / Discord / SMS / log) via service.alerting
    if event in ("circuit_breaker_fired", "early_warning_drawdown"):
        try:
            from service.alerting import send_system_alert

            severity = "critical" if event == "circuit_breaker_fired" else "warning"
            send_system_alert(
                event="CIRCUIT_BREAKER_FIRED" if event == "circuit_breaker_fired" else "DRAWDOWN_APPROACHING",
                payload=payload,
                severity=severity,
            )
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
        self._was_tripped: bool = False
        self._normal_streak: int = 0
        self._equity_prev: float = 0.0
        self._equity_peak_window: list[float] = []
        # E23 — machine d'état adaptative (b1/b2/b3/b4/b4a), OFF par défaut (b0).
        self._episode: object | None = None
        self._regime_today: str | None = None
        self._alloc_today: float = 1.0

    # ------------------------------------------------------------------
    # E23 — politiques adaptatives (miroir EXACT du backtest, logique partagée)
    # ------------------------------------------------------------------
    @property
    def is_adaptive(self) -> bool:
        """True si une politique adaptative (b1-b4) est active (≠ b0)."""
        return str(getattr(self._cfg, "policy", "b0") or "b0").strip().lower() != "b0"

    def _ensure_episode(self) -> object:
        if self._episode is None:
            from backtesting.adaptive_breaker import BreakerEpisode
            self._episode = BreakerEpisode()
        return self._episode

    def set_spy_regime(self, trade_date) -> None:
        """Enregistre le régime SPY du jour (réévalué chaque jour)."""
        self._regime_today = None
        regime_map = getattr(self._cfg, "spy_regime_map", None)
        if regime_map:
            try:
                import pandas as pd
                self._regime_today = regime_map.get(pd.Timestamp(trade_date).date())
            except Exception:  # noqa: BLE001 — best-effort
                self._regime_today = None

    def update_adaptive(self, equity: float, peak_equity: float) -> bool:
        """Pilote la machine d'état adaptative — miroir du simulateur backtest.

        À appeler CHAQUE jour (AVANT ``is_active()``/``allocation_scale()``)
        avec l'equity courante et le peak roulant (high-watermark). Utilise la
        MÊME logique pure que le backtest (``backtesting.adaptive_breaker``) :
        mêmes seuils, mêmes règles PIT, même régime SPY. B0 n'est PAS concerné.
        """
        from backtesting.adaptive_breaker import allocate, trip_or_recover
        policy = str(getattr(self._cfg, "policy", "b0") or "b0").strip().lower()
        episode = self._ensure_episode()
        self._was_tripped = self._tripped
        trip_or_recover(
            episode, float(equity), float(peak_equity),
            policy=policy,
            max_dd_pct=abs(float(self._cfg.max_portfolio_drawdown_pct)),
            recovery_pct=float(self._cfg.recovery_pct),
        )
        self._tripped = bool(episode.tripped)
        degraded = float(max(0.0, min(1.0, float(self._cfg.degraded_entry_allocation_pct))))
        episode.allocation = allocate(
            policy, episode, float(equity),
            regime=self._regime_today,
            recovery_pct=float(self._cfg.recovery_pct),
            degraded=degraded,
            ramp_max=float(self._cfg.regime_ramp_up_max_pct),
        )
        self._alloc_today = float(episode.allocation)
        return not self._tripped

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

    def allocation_scale(self, entry_mode: str | None = None, side: str | None = None) -> float:
        """Fraction d'allocation autorisée : 1.0 si normal, dégradé si trippé.

        Si le ramp-up régimed est actif, l'allocation dégradée de base est
        augmentée de ``regime_ramp_up_pct_per_day`` par jour où le régime
        est ``normal`` ET l'equity progresse, plafonnée à ``regime_ramp_up_max_pct``.
        """
        _ = side  # réservé pour un scaling différencié long/short
        if self.is_adaptive:
            # Machine d'état pilotée par update_adaptive() ; alloc min > 0 -> scale.
            return 1.0 if not self._tripped else float(self._alloc_today)
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

        E23 (b1-b4) : hystérésis du régime SPY journalier (3 séances favorables
        pour augmenter, reset immédiat si défavorable) — miroir du backtest.
        """
        if self.is_adaptive:
            from backtesting.adaptive_breaker import is_favorable, update_streak
            episode = self._ensure_episode()
            if self._tripped:
                update_streak(episode, is_favorable(self._regime_today))
            return
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

        E23 (b1-b4) : ne bloque JAMAIS (allocation minimale > 0, comme le
        backtest) — l'état est piloté par ``update_adaptive()`` et le sizing
        passe par ``allocation_scale()``.
        """
        if self.is_adaptive:
            return False
        status = self.status()
        degraded = float(self._cfg.degraded_entry_allocation_pct) > 0.0
        if status.active and degraded:
            # Mode dégradé : on signale mais on ne bloque pas l'executor
            self._tripped = True
            _set_cb_prometheus(True)
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
                    _set_cb_prometheus(False)
            # Si pas encore récupéré, on reste en mode dégradé
            return False
        # Mode non-dégradé (blocage total) : _tripped suit status.active sans hystérésis
        self._was_tripped = self._tripped
        self._tripped = status.active
        return status.active

    def just_tripped(self) -> bool:
        """Retourne True si le breaker vient de se déclencher (transition)."""
        if self.is_adaptive:
            # miroir backtest : lecture seule, _was_tripped maintenu par update_adaptive()
            return self._tripped and not self._was_tripped
        result = self._tripped and not self._was_tripped
        self._was_tripped = self._tripped
        return result

    def notify_if_active(self) -> bool:
        """Envoie au plus une alerte par statut déclenché.

        Inclut également une alerte précoce (early warning) quand le drawdown
        ou la perte quotidienne approche du seuil (≥ 80% du seuil), sans
        déclencher le circuit breaker.
        """
        status = self.status()
        # --- Early warning : drawdown approche le seuil ---
        if not status.active:
            early_warning = self._evaluate_early_warning()
            if early_warning is not None:
                signature = f"early_warning:{early_warning}"
                if signature != self._last_notified_signature:
                    self._last_notified_signature = signature
                    _try_send_alert(event="early_warning_drawdown", payload=early_warning)
                return False

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

    def _evaluate_early_warning(self) -> dict[str, Any] | None:
        """Évalue si le drawdown ou la perte quotidienne approche du seuil
        (≥ 80% du seuil) et retourne un payload d'alerte précoce, ou None."""
        hwm = self._reference_hwm()
        cur = self._pnl.portfolio_current_value
        early_warning_ratio = 0.80  # alerte à 80% du seuil

        if hwm is not None and cur is not None and hwm > 0:
            dd = (hwm - cur) / hwm
            dd_threshold = self._cfg.max_portfolio_drawdown_pct
            if dd >= dd_threshold * early_warning_ratio and dd < dd_threshold:
                return {
                    "trigger": "drawdown_approaching",
                    "drawdown_pct": round(dd * 100, 2),
                    "threshold_pct": round(dd_threshold * 100, 2),
                    "early_warning_at_pct": round(dd_threshold * early_warning_ratio * 100, 2),
                    "portfolio_high_watermark": hwm,
                    "portfolio_current_value": cur,
                }

        daily = self._pnl.daily_pnl
        equity = self._cfg.account_equity
        if daily is not None and equity > 0:
            loss_pct = abs(min(daily, 0.0)) / equity
            loss_threshold = self._cfg.max_daily_loss_pct
            if loss_pct >= loss_threshold * early_warning_ratio and loss_pct < loss_threshold:
                return {
                    "trigger": "daily_loss_approaching",
                    "daily_loss_pct": round(loss_pct * 100, 2),
                    "threshold_pct": round(loss_threshold * 100, 2),
                    "early_warning_at_pct": round(loss_threshold * early_warning_ratio * 100, 2),
                    "daily_pnl": daily,
                    "account_equity": equity,
                }

        return None

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


# ---------------------------------------------------------------------------
# Prometheus metrics helper (best-effort, ne bloque jamais)
# ---------------------------------------------------------------------------

def _set_cb_prometheus(active: bool) -> None:
    try:
        from service.prometheus_metrics import set_circuit_breaker_active
        set_circuit_breaker_active(active)
    except Exception:
        pass
