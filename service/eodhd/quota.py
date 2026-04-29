"""Compteur de quota journalier EODHD + circuit-breaker.

Plan §5.5. Persistance JSON dans ``artifacts/eodhd_cache/quota_YYYYMMDD.json``.

Coûts EODHD officiels :
- ``/eod-bulk-last-day/`` : **100 calls** par appel.
- ``/eod/{ticker}``       : **1 call**.
- ``/splits/`` , ``/div/``: **1 call**.

Le quota par défaut du plan est de **100 000 calls/jour** (configurable).
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger(__name__)

#: Coût standard par endpoint (cf. plan §5.5).
ENDPOINT_COSTS: dict[str, int] = {
    "bulk": 100,
    "eod": 1,
    "splits": 1,
    "dividends": 1,
}

DEFAULT_DAILY_QUOTA = 100_000
DEFAULT_SOFT_QUOTA_WARN = 80_000
DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_COOLDOWN_SECONDS = 30 * 60


class EodhdQuotaExceeded(RuntimeError):
    """Quota journalier EODHD atteint."""


class EodhdCircuitOpen(RuntimeError):
    """Circuit-breaker EODHD actuellement ouvert."""


@dataclass
class QuotaState:
    date_utc: str = ""
    calls_used: int = 0
    calls_failed: int = 0
    consecutive_failures: int = 0
    circuit_open_until_epoch: float = 0.0


@dataclass
class EodhdQuotaTracker:
    """Tracker thread-safe avec persistance disque optionnelle."""

    daily_quota: int = DEFAULT_DAILY_QUOTA
    soft_warn: int = DEFAULT_SOFT_QUOTA_WARN
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    cooldown_seconds: float = float(DEFAULT_COOLDOWN_SECONDS)
    cache_dir: Optional[Path] = None
    state: QuotaState = field(default_factory=QuotaState)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _warned_soft: bool = False

    def __post_init__(self) -> None:
        self._reset_if_new_day()
        self._load()

    # ------------------------------------------------------------------
    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d")

    def _reset_if_new_day(self) -> None:
        today = self._today()
        if self.state.date_utc != today:
            self.state = QuotaState(date_utc=today)
            self._warned_soft = False

    def _path(self) -> Optional[Path]:
        if self.cache_dir is None:
            return None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir / f"quota_{self.state.date_utc}.json"

    def _load(self) -> None:
        path = self._path()
        if path is None or not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        for key in ("calls_used", "calls_failed", "consecutive_failures"):
            if key in payload:
                setattr(self.state, key, int(payload[key]))
        self.state.circuit_open_until_epoch = float(payload.get("circuit_open_until_epoch", 0.0))

    def _save(self) -> None:
        path = self._path()
        if path is None:
            return
        try:
            path.write_text(
                json.dumps(
                    {
                        "date_utc": self.state.date_utc,
                        "calls_used": self.state.calls_used,
                        "calls_failed": self.state.calls_failed,
                        "consecutive_failures": self.state.consecutive_failures,
                        "circuit_open_until_epoch": self.state.circuit_open_until_epoch,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            LOGGER.warning("[eodhd] quota persistence failed: %s", exc)

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def cost_for(self, endpoint: str) -> int:
        return ENDPOINT_COSTS.get(endpoint, 1)

    @staticmethod
    def _format_remaining_duration(seconds: float) -> str:
        total_seconds = max(0, int(round(seconds)))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        parts: list[str] = []
        if hours:
            parts.append(f"{hours}h")
        if minutes or hours:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        return " ".join(parts)

    @classmethod
    def _format_circuit_open_until(cls, epoch: float, *, now_epoch: float | None = None) -> str:
        if epoch <= 0:
            return "échéance inconnue"
        now_ts = time.time() if now_epoch is None else now_epoch
        remaining = max(0.0, epoch - now_ts)
        open_until_utc = datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return f"{open_until_utc} (reste ~{cls._format_remaining_duration(remaining)})"

    def reserve(self, endpoint: str) -> int:
        """Vérifie qu'il reste assez de quota et que le circuit est fermé.

        Lève :
        - :class:`EodhdQuotaExceeded` si quota dur dépassé.
        - :class:`EodhdCircuitOpen` si circuit-breaker ouvert.
        Retourne le coût qui sera décompté.
        """
        with self._lock:
            self._reset_if_new_day()
            if self.is_circuit_open():
                raise EodhdCircuitOpen(
                    f"[eodhd] circuit-breaker ouvert jusqu'à "
                    f"{self._format_circuit_open_until(self.state.circuit_open_until_epoch)}"
                )
            cost = self.cost_for(endpoint)
            if self.state.calls_used + cost > self.daily_quota:
                raise EodhdQuotaExceeded(
                    f"Quota EODHD dépassé : {self.state.calls_used}+{cost} "
                    f"> {self.daily_quota}"
                )
            return cost

    def record_success(self, endpoint: str) -> None:
        with self._lock:
            self._reset_if_new_day()
            self.state.calls_used += self.cost_for(endpoint)
            self.state.consecutive_failures = 0
            self.state.circuit_open_until_epoch = 0.0
            if (
                not self._warned_soft
                and self.state.calls_used >= self.soft_warn
            ):
                LOGGER.warning(
                    "[eodhd] soft-quota atteint : %d/%d calls (seuil=%d)",
                    self.state.calls_used,
                    self.daily_quota,
                    self.soft_warn,
                )
                self._warned_soft = True
            self._save()

    def record_failure(
        self,
        endpoint: str,
        *,
        count_call: bool = True,
        count_towards_circuit: bool = True,
    ) -> None:
        """Enregistre un échec.

        Par défaut, l'échec compte aussi dans ``calls_used`` (EODHD facture
        souvent les 4xx). Mettre ``count_call=False`` pour les erreurs
        purement réseau (timeout local). ``count_towards_circuit=False`` permet
        d'exclure certains cas attendus (ex. 404 symbole introuvable) du seuil
        d'ouverture du circuit-breaker.
        """
        with self._lock:
            self._reset_if_new_day()
            if count_call:
                self.state.calls_used += self.cost_for(endpoint)
            self.state.calls_failed += 1
            if count_towards_circuit:
                self.state.consecutive_failures += 1
            else:
                self.state.consecutive_failures = 0
            if self.state.consecutive_failures >= self.failure_threshold:
                self.state.circuit_open_until_epoch = time.time() + self.cooldown_seconds
                LOGGER.warning(
                    "[eodhd] circuit-breaker OPEN après %d échecs consécutifs (cooldown=%.0fs, reprise après %s)",
                    self.state.consecutive_failures,
                    self.cooldown_seconds,
                    self._format_circuit_open_until(self.state.circuit_open_until_epoch),
                )
            self._save()

    def is_circuit_open(self) -> bool:
        return (
            self.state.circuit_open_until_epoch > 0.0
            and time.time() < self.state.circuit_open_until_epoch
        )

    def snapshot(self) -> dict[str, int | bool]:
        """Snapshot pour ``run_summary`` (cf. plan §8.1)."""
        with self._lock:
            self._reset_if_new_day()
            return {
                "calls_used": int(self.state.calls_used),
                "calls_failed": int(self.state.calls_failed),
                "circuit_open": bool(self.is_circuit_open()),
                "soft_quota_reached": bool(
                    self.state.calls_used >= self.soft_warn
                ),
                "daily_quota": int(self.daily_quota),
            }


# Singleton process-wide (option). Les tests doivent appeler ``reset_default_tracker()``.
_DEFAULT_TRACKER: Optional[EodhdQuotaTracker] = None
_DEFAULT_LOCK = threading.Lock()


def get_default_tracker(cache_dir: Optional[Path] = None) -> EodhdQuotaTracker:
    global _DEFAULT_TRACKER
    with _DEFAULT_LOCK:
        if _DEFAULT_TRACKER is None:
            _DEFAULT_TRACKER = EodhdQuotaTracker(cache_dir=cache_dir)
        return _DEFAULT_TRACKER


def reset_default_tracker() -> None:
    """Réinitialise le singleton (tests)."""
    global _DEFAULT_TRACKER
    with _DEFAULT_LOCK:
        _DEFAULT_TRACKER = None


__all__ = [
    "DEFAULT_COOLDOWN_SECONDS",
    "DEFAULT_DAILY_QUOTA",
    "DEFAULT_FAILURE_THRESHOLD",
    "DEFAULT_SOFT_QUOTA_WARN",
    "ENDPOINT_COSTS",
    "EodhdCircuitOpen",
    "EodhdQuotaExceeded",
    "EodhdQuotaTracker",
    "QuotaState",
    "get_default_tracker",
    "reset_default_tracker",
]

