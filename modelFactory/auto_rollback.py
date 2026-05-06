"""Sprint S11 / S11.3 — Auto-rollback du champion ML.

Si la décision de gate ML (``MLPolicyDecision.gate``) est ``"disabled"`` pendant
``threshold_days`` jours consécutifs, on bascule automatiquement sur le dernier
challenger validé. Le swap est journalisé dans la table ``champion_history``
(création via Alembic prévue ; ce module est tolérant si la table n'existe pas
encore — il se contente de logger).

Mode par défaut : ``dry_run=True``. Le swap effectif requiert ``dry_run=False``.

Architecture (DI complète pour testabilité) :
    - ``decision_history_loader``: callable(symbol, *, engine) -> liste ordonnée
      chronologique décroissante de tuples ``(date, MLPolicyDecision)`` sur les
      ``threshold_days`` derniers jours.
    - ``challenger_resolver``: callable(symbol, *, engine, current_champion) ->
      str | None (nom du challenger validé à promouvoir).
    - ``champion_swapper``: callable(symbol, *, from_model, to_model, engine,
      reason, dry_run) -> dict (audit du swap).
    - ``notifier_factory``: callable() -> notifier (best-effort).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Optional

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AutoRollbackOutcome:
    symbol: str
    triggered: bool
    consecutive_disabled_days: int
    threshold_days: int
    previous_champion: Optional[str]
    promoted_challenger: Optional[str]
    reason: str
    dry_run: bool
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "triggered": self.triggered,
            "consecutive_disabled_days": self.consecutive_disabled_days,
            "threshold_days": self.threshold_days,
            "previous_champion": self.previous_champion,
            "promoted_challenger": self.promoted_challenger,
            "reason": self.reason,
            "dry_run": self.dry_run,
            "timestamp": self.timestamp,
        }


def count_consecutive_disabled_days(
    decisions: list[tuple[date, Any]],
) -> int:
    """Compte la séquence consécutive (à partir du plus récent) où ``gate == "disabled"``.

    ``decisions`` doit être ordonnée chronologiquement décroissante (jour le
    plus récent en tête). Le compteur s'arrête au premier jour où
    ``gate != "disabled"`` ou en l'absence de gate.
    """
    streak = 0
    for _day, decision in decisions:
        gate = getattr(decision, "gate", None) or (
            decision.get("gate") if isinstance(decision, dict) else None
        )
        if str(gate or "").lower() != "disabled":
            break
        streak += 1
    return streak


def auto_rollback_if_needed(
    symbol: str,
    *,
    engine: Any = None,
    threshold_days: int = 3,
    dry_run: bool = True,
    decision_history_loader: Callable[..., list[tuple[date, Any]]],
    challenger_resolver: Callable[..., Optional[str]],
    champion_swapper: Optional[Callable[..., dict[str, Any]]] = None,
    current_champion_loader: Optional[Callable[..., Optional[str]]] = None,
    notifier_factory: Optional[Callable[[], Any]] = None,
) -> AutoRollbackOutcome:
    """Évalue et exécute (ou non) le rollback du champion ML.

    Returns :class:`AutoRollbackOutcome` quel que soit le résultat (no-op,
    rollback dry-run, rollback effectif).
    """
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    decisions = decision_history_loader(symbol, engine=engine)
    streak = count_consecutive_disabled_days(decisions)

    if streak < threshold_days:
        LOGGER.info(
            "[auto_rollback] %s: streak=%d < threshold=%d → no-op.",
            symbol, streak, threshold_days,
        )
        return AutoRollbackOutcome(
            symbol=symbol,
            triggered=False,
            consecutive_disabled_days=streak,
            threshold_days=threshold_days,
            previous_champion=None,
            promoted_challenger=None,
            reason="below_threshold",
            dry_run=dry_run,
            timestamp=now_iso,
        )

    current_champion: Optional[str] = None
    if current_champion_loader is not None:
        try:
            current_champion = current_champion_loader(symbol, engine=engine)
        except Exception:
            LOGGER.exception("[auto_rollback] %s: lecture champion courant échouée.", symbol)

    challenger = challenger_resolver(symbol, engine=engine, current_champion=current_champion)
    if challenger is None:
        msg = f"[auto_rollback] {symbol}: streak={streak} ≥ {threshold_days} mais aucun challenger validé."
        LOGGER.warning(msg)
        if notifier_factory is not None:
            try:
                notifier = notifier_factory()
                fn = getattr(notifier, "notify_warning", None) or getattr(notifier, "notify", None)
                if callable(fn):
                    fn(msg)
            except Exception:
                LOGGER.exception("[auto_rollback] échec notif (best-effort).")
        return AutoRollbackOutcome(
            symbol=symbol,
            triggered=False,
            consecutive_disabled_days=streak,
            threshold_days=threshold_days,
            previous_champion=current_champion,
            promoted_challenger=None,
            reason="no_validated_challenger",
            dry_run=dry_run,
            timestamp=now_iso,
        )

    reason = f"ml_gate_disabled_{streak}_consecutive_days"
    swap_audit: dict[str, Any] = {"dry_run": True, "skipped": True}
    if not dry_run and champion_swapper is not None:
        try:
            swap_audit = champion_swapper(
                symbol,
                from_model=current_champion,
                to_model=challenger,
                engine=engine,
                reason=reason,
                dry_run=False,
            )
        except Exception as exc:
            LOGGER.exception("[auto_rollback] %s: swap échoué.", symbol)
            return AutoRollbackOutcome(
                symbol=symbol,
                triggered=False,
                consecutive_disabled_days=streak,
                threshold_days=threshold_days,
                previous_champion=current_champion,
                promoted_challenger=challenger,
                reason=f"swap_failed: {exc}",
                dry_run=dry_run,
                timestamp=now_iso,
            )

    LOGGER.warning(
        "[auto_rollback] %s: %s → %s (dry_run=%s, streak=%d).",
        symbol, current_champion, challenger, dry_run, streak,
    )
    if notifier_factory is not None:
        try:
            notifier = notifier_factory()
            fn = getattr(notifier, "notify_warning", None) or getattr(notifier, "notify", None)
            if callable(fn):
                action = "DRY-RUN" if dry_run else "APPLIED"
                fn(f"[auto_rollback {action}] {symbol}: {current_champion} → {challenger} ({reason})")
        except Exception:
            LOGGER.exception("[auto_rollback] échec notif (best-effort).")

    return AutoRollbackOutcome(
        symbol=symbol,
        triggered=True,
        consecutive_disabled_days=streak,
        threshold_days=threshold_days,
        previous_champion=current_champion,
        promoted_challenger=challenger,
        reason=reason,
        dry_run=dry_run,
        timestamp=now_iso,
    )


__all__ = [
    "AutoRollbackOutcome",
    "auto_rollback_if_needed",
    "count_consecutive_disabled_days",
]

