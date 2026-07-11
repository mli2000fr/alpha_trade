"""
Filtres de concentration et anti-repetition — limite le nombre de trades
par symbole sur une fenêtre glissante et blackliste temporairement les
symboles après N pertes consécutives.

Utilisable à la fois par le backtest (``backtesting/simulator.py``) et
le pipeline live (``risk_management/portfolio_builder.py``).

.. code-block:: python

    from risk_management.concentration import SymbolTradeTracker, ConsecutiveLossTracker

    tracker = SymbolTradeTracker(max_trades=5, window_days=126)
    if tracker.allow_entry("AAPL", trade_date):
        ...  # soumettre l'ordre
        tracker.record("AAPL", trade_date)

    loss_tracker = ConsecutiveLossTracker(max_consecutive_losses=3)
    loss_tracker.record("TSLA", pnl=-50.0)
    if loss_tracker.is_blacklisted("TSLA"):
        ...  # bloquer l'entrée
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paramètres par défaut
# ---------------------------------------------------------------------------

DEFAULT_MAX_TRADES_PER_SYMBOL: int = 5
DEFAULT_CONCENTRATION_WINDOW_CALENDAR_DAYS: int = 180  # ~6 mois
DEFAULT_MAX_CONSECUTIVE_LOSSES: int = 3


# ---------------------------------------------------------------------------
# SymbolTradeTracker
# ---------------------------------------------------------------------------

class SymbolTradeTracker:
    """Limite le nombre d'entrées par symbole sur une fenêtre glissante.

    Parameters
    ----------
    max_trades : int
        Nombre maximum d'entrées autorisées par symbole dans la fenêtre.
    window_days : int
        Taille de la fenêtre glissante en jours **calendaires**.
    """

    def __init__(
        self,
        max_trades: int = DEFAULT_MAX_TRADES_PER_SYMBOL,
        window_days: int = DEFAULT_CONCENTRATION_WINDOW_CALENDAR_DAYS,
    ) -> None:
        self._max_trades = max(1, int(max_trades))
        self._window_days = max(1, int(window_days))
        # {symbol: [date, date, ...]} — dates d'entrée triées
        self._history: dict[str, list[date]] = {}

    # ------------------------------------------------------------------
    @property
    def max_trades(self) -> int:
        return self._max_trades

    @property
    def window_days(self) -> int:
        return self._window_days

    # ------------------------------------------------------------------
    def _prune(self, symbol: str, as_of: date) -> None:
        """Supprime les entrées hors fenêtre pour un symbole."""
        entries = self._history.get(symbol)
        if not entries:
            return
        cutoff = as_of - timedelta(days=self._window_days)
        self._history[symbol] = [d for d in entries if d >= cutoff]

    def _count(self, symbol: str, as_of: date) -> int:
        """Nombre d'entrées dans la fenêtre glissante pour un symbole."""
        self._prune(symbol, as_of)
        return len(self._history.get(symbol, []))

    # ------------------------------------------------------------------
    def allow_entry(self, symbol: str, as_of: date, side: str | None = None) -> bool:
        """Retourne True si le symbole peut encore être tradé.

        Parameters
        ----------
        symbol : str
            Symbole à vérifier.
        as_of : date
            Date de référence (jour de trading).
        side : str or None
            ``"buy"``, ``"sell"`` ou None (rétrocompatible, pas de distinction).
        """
        key = self._make_key(symbol, side)
        if not key:
            return False
        return self._count(key, as_of) < self._max_trades

    def record(self, symbol: str, trade_date: date, side: str | None = None) -> None:
        """Enregistre une entrée pour un symbole.

        Parameters
        ----------
        symbol : str
            Symbole tradé.
        trade_date : date
            Date de l'entrée.
        side : str or None
            ``"buy"``, ``"sell"`` ou None (rétrocompatible).
        """
        key = self._make_key(symbol, side)
        if not key:
            return
        if key not in self._history:
            self._history[key] = []
        self._history[key].append(trade_date)
        self._prune(key, trade_date)

    @staticmethod
    def _make_key(symbol: str, side: str | None) -> str:
        """Construit la clé interne, avec préfixe side si renseigné."""
        base = str(symbol).strip().upper()
        if not base:
            return ""
        if side and str(side).strip().lower() == "sell":
            return f"short:{base}"
        return f"long:{base}" if side else base

    def reset(self) -> None:
        """Vide tout l'historique."""
        self._history.clear()

    def to_summary(self) -> dict[str, object]:
        """Résumé sérialisable pour diagnostics."""
        return {
            "max_trades": self._max_trades,
            "window_days": self._window_days,
            "tracked_symbols": len(self._history),
            "total_entries": sum(len(v) for v in self._history.values()),
        }

    def to_dict(self) -> dict[str, object]:
        """Sérialise l'état complet pour persistence cross-run (P2 2026-06-25)."""
        return {
            "max_trades": self._max_trades,
            "window_days": self._window_days,
            "history": {
                key: [d.isoformat() for d in dates]
                for key, dates in self._history.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> SymbolTradeTracker:
        """Reconstruit un tracker depuis un dictionnaire (P2 2026-06-25)."""
        tracker = cls(
            max_trades=int(data.get("max_trades", DEFAULT_MAX_TRADES_PER_SYMBOL)),
            window_days=int(data.get("window_days", DEFAULT_CONCENTRATION_WINDOW_CALENDAR_DAYS)),
        )
        history_data = data.get("history")
        if isinstance(history_data, dict):
            tracker._history = {
                str(key): [
                    date.fromisoformat(d) for d in dates
                    if isinstance(d, str)
                ]
                for key, dates in history_data.items()
                if isinstance(dates, list)
            }
        return tracker


# ---------------------------------------------------------------------------
# ConsecutiveLossTracker
# ---------------------------------------------------------------------------

class ConsecutiveLossTracker:
    """Blacklist temporaire après N pertes consécutives sur un même symbole.

    Une fois blacklisté, le symbole est bloqué pendant une durée configurable
    (``blacklist_duration_days``).  Tout nouveau trade gagnant réinitialise
    le compteur de pertes.

    Parameters
    ----------
    max_consecutive_losses : int
        Nombre de pertes consécutives avant blacklist.
    blacklist_duration_days : int
        Durée de la blacklist en jours calendaires (défaut 90).
    """

    def __init__(
        self,
        max_consecutive_losses: int = DEFAULT_MAX_CONSECUTIVE_LOSSES,
        blacklist_duration_days: int = 90,
    ) -> None:
        self._max_losses = max(1, int(max_consecutive_losses))
        self._blacklist_duration = max(1, int(blacklist_duration_days))
        # {symbol: consecutive_loss_count}
        self._streak: dict[str, int] = {}
        # {symbol: date_until_blacklisted}
        self._blacklist: dict[str, date] = {}

    # ------------------------------------------------------------------
    @property
    def max_consecutive_losses(self) -> int:
        return self._max_losses

    # ------------------------------------------------------------------
    def is_blacklisted(self, symbol: str, as_of: date | None = None, side: str | None = None) -> bool:
        """Retourne True si le symbole est blacklisté.

        Parameters
        ----------
        symbol : str
            Symbole à vérifier.
        as_of : date or None
            Date de référence. Si None, utilise la date du jour.
        side : str or None
            ``"buy"``, ``"sell"`` ou None (rétrocompatible).
        """
        key = self._make_key(symbol, side)
        if key not in self._blacklist:
            return False
        if as_of is None:
            as_of = date.today()
        return self._blacklist[key] >= as_of

    def record(self, symbol: str, pnl: float, trade_date: date | None = None, side: str | None = None) -> bool:
        """Enregistre le résultat d'un trade pour un symbole.

        Parameters
        ----------
        symbol : str
            Symbole tradé.
        pnl : float
            PnL du trade (négatif = perte).
        trade_date : date or None
            Date du trade. Utilisé pour fixer la durée de blacklist.
        side : str or None
            ``"buy"``, ``"sell"`` ou None (rétrocompatible).

        Returns
        -------
        bool
            True si le symbole vient d'être blacklisté.
        """
        key = self._make_key(symbol, side)
        if not key:
            return False

        if pnl > 0:
            # Trade gagnant → reset du streak
            self._streak[key] = 0
            return False

        # Trade perdant
        current = self._streak.get(key, 0) + 1
        self._streak[key] = current

        if current >= self._max_losses:
            ref_date = trade_date or date.today()
            self._blacklist[key] = ref_date + timedelta(days=self._blacklist_duration)
            self._streak[key] = 0  # reset après blacklist
            LOGGER.info(
                "Blacklist activee pour %s (apres %d pertes consecutives, jusqu'au %s)",
                key,
                current,
                self._blacklist[key].isoformat(),
            )
            return True

        return False

    def reset(self) -> None:
        """Réinitialise tous les compteurs et blacklists."""
        self._streak.clear()
        self._blacklist.clear()

    @staticmethod
    def _make_key(symbol: str, side: str | None) -> str:
        """Construit la clé interne, avec préfixe side si renseigné."""
        base = str(symbol).strip().upper()
        if not base:
            return ""
        if side and str(side).strip().lower() == "sell":
            return f"short:{base}"
        return f"long:{base}" if side else base

    def to_summary(self) -> dict[str, object]:
        """Résumé sérialisable pour diagnostics."""
        today = date.today()
        active_blacklists = {
            sym: d.isoformat()
            for sym, d in self._blacklist.items()
            if d >= today
        }
        return {
            "max_consecutive_losses": self._max_losses,
            "blacklist_duration_days": self._blacklist_duration,
            "active_blacklists": active_blacklists,
            "tracked_symbols": len(self._streak),
        }

    def to_dict(self) -> dict[str, object]:
        """Sérialise l'état complet pour persistence cross-run (P2 2026-06-25)."""
        return {
            "max_consecutive_losses": self._max_losses,
            "blacklist_duration_days": self._blacklist_duration,
            "streak": dict(self._streak),
            "blacklist": {
                key: d.isoformat()
                for key, d in self._blacklist.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ConsecutiveLossTracker:
        """Reconstruit un tracker depuis un dictionnaire (P2 2026-06-25)."""
        tracker = cls(
            max_consecutive_losses=int(data.get("max_consecutive_losses", DEFAULT_MAX_CONSECUTIVE_LOSSES)),
            blacklist_duration_days=int(data.get("blacklist_duration_days", 90)),
        )
        streak_data = data.get("streak")
        if isinstance(streak_data, dict):
            tracker._streak = {str(k): int(v) for k, v in streak_data.items()}
        blacklist_data = data.get("blacklist")
        if isinstance(blacklist_data, dict):
            tracker._blacklist = {
                str(key): date.fromisoformat(d)
                for key, d in blacklist_data.items()
                if isinstance(d, str)
            }
        return tracker


# ---------------------------------------------------------------------------
# BreakoutConfirmationTracker — filtre anti-faux-départs (Quick Win 1)
# ---------------------------------------------------------------------------

DEFAULT_MIN_BREAKOUT_DAYS: int = 1


class BreakoutConfirmationTracker:
    """Exige qu'un candidat apparaisse N jours consécutifs avant d'être tradable.

    Élimine les « faux départs » : un symbole qui entre dans le top-N pour
    la première fois n'est éligible qu'après ``min_breakout_days`` jours
    consécutifs de présence dans la liste des candidats.

    Parameters
    ----------
    min_breakout_days : int
        Nombre minimum de jours consécutifs de présence (défaut 3).
    """

    def __init__(self, min_breakout_days: int = DEFAULT_MIN_BREAKOUT_DAYS) -> None:
        self._min_days = max(1, int(min_breakout_days))
        # {symbol: consecutive_days_count}
        self._streak: dict[str, int] = {}
        # Date du dernier enregistrement (pour détecter les trous)
        self._last_date: date | None = None

    # ------------------------------------------------------------------
    @property
    def min_breakout_days(self) -> int:
        return self._min_days

    # ------------------------------------------------------------------
    def record_selections(self, symbols: list[str], trade_date: date) -> None:
        """Enregistre les symboles présents dans la liste des candidats du jour.

        Les symboles absents voient leur streak réinitialisé à 0.
        Les symboles présents voient leur streak incrémenté de 1
        (ou initialisé à 1 si nouveau).

        Parameters
        ----------
        symbols : list[str]
            Liste des symboles candidats du jour.
        trade_date : date
            Date de trading.
        """
        # Détection de gap : si on saute un jour, reset tous les streaks
        if self._last_date is not None:
            gap = (trade_date - self._last_date).days
            if gap > 1:
                self._streak.clear()

        self._last_date = trade_date
        present = {str(s).strip().upper() for s in symbols}
        present.discard("")

        # Incrémenter les symboles présents
        for sym in present:
            self._streak[sym] = self._streak.get(sym, 0) + 1

        # Réinitialiser les symboles absents
        absent = [s for s in self._streak if s not in present]
        for sym in absent:
            self._streak[sym] = 0

    def is_confirmed(self, symbol: str) -> bool:
        """Retourne True si le breakout du symbole est confirmé.

        Parameters
        ----------
        symbol : str
            Symbole à vérifier.
        """
        key = str(symbol).strip().upper()
        return self._streak.get(key, 0) >= self._min_days

    def allow_entry(self, symbol: str) -> bool:
        """Alias sémantique de :meth:`is_confirmed`."""
        return self.is_confirmed(symbol)

    def reset(self) -> None:
        """Réinitialise tous les streaks."""
        self._streak.clear()
        self._last_date = None

    def to_summary(self) -> dict[str, object]:
        """Résumé sérialisable pour diagnostics."""
        return {
            "min_breakout_days": self._min_days,
            "tracked_symbols": len(self._streak),
            "confirmed_symbols": sum(
                1 for v in self._streak.values() if v >= self._min_days
            ),
            "pending_symbols": sum(
                1 for v in self._streak.values() if 0 < v < self._min_days
            ),
        }

    def to_dict(self) -> dict[str, object]:
        """Sérialise l'état complet pour persistence cross-run (live)."""
        return {
            "min_breakout_days": self._min_days,
            "last_date": self._last_date.isoformat() if self._last_date else None,
            "streak": dict(self._streak),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> BreakoutConfirmationTracker:
        """Reconstruit un tracker depuis un état persisté."""
        tracker = cls(min_breakout_days=int(data.get("min_breakout_days", DEFAULT_MIN_BREAKOUT_DAYS)))
        last_date_str = data.get("last_date")
        if last_date_str and isinstance(last_date_str, str):
            tracker._last_date = date.fromisoformat(last_date_str)
        streak_data = data.get("streak")
        if isinstance(streak_data, dict):
            tracker._streak = {str(k): int(v) for k, v in streak_data.items()}
        return tracker


# ---------------------------------------------------------------------------
# Helpers pratiques (intégration backtest / live)
# ---------------------------------------------------------------------------

def build_entry_concentration_filter(
    *,
    max_trades_per_symbol: int = DEFAULT_MAX_TRADES_PER_SYMBOL,
    window_calendar_days: int = DEFAULT_CONCENTRATION_WINDOW_CALENDAR_DAYS,
    max_consecutive_losses: int = DEFAULT_MAX_CONSECUTIVE_LOSSES,
    blacklist_duration_days: int = 90,
) -> tuple[SymbolTradeTracker, ConsecutiveLossTracker]:
    """Construit les deux trackers de concentration avec des paramètres homogènes.

    Returns
    -------
    tuple[SymbolTradeTracker, ConsecutiveLossTracker]
    """
    trade_tracker = SymbolTradeTracker(
        max_trades=max_trades_per_symbol,
        window_days=window_calendar_days,
    )
    loss_tracker = ConsecutiveLossTracker(
        max_consecutive_losses=max_consecutive_losses,
        blacklist_duration_days=blacklist_duration_days,
    )
    return trade_tracker, loss_tracker


__all__ = [
    "BreakoutConfirmationTracker",
    "ConsecutiveLossTracker",
    "SymbolTradeTracker",
    "build_entry_concentration_filter",
    "DEFAULT_CONCENTRATION_WINDOW_CALENDAR_DAYS",
    "DEFAULT_MAX_CONSECUTIVE_LOSSES",
    "DEFAULT_MAX_TRADES_PER_SYMBOL",
    "DEFAULT_MIN_BREAKOUT_DAYS",
]
