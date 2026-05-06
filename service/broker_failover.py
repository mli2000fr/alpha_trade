"""Sprint S13.5 — Failover ``BrokerClient`` (Alpaca → IBKR read-only).

Pattern circuit-breaker simple :

- Toutes les opérations sont d'abord déléguées au ``primary``.
- Une opération **lecture** qui lève → incrémente le compteur d'erreurs.
- Au-delà de ``circuit_breaker_threshold`` erreurs consécutives, on bascule
  les **lectures** sur ``secondary`` et on **suspend les écritures** (raise
  :class:`WriteSuspendedError`) jusqu'à ce que la sentinelle
  ``artifacts/failover/RESUME`` soit créée par un opérateur.
- Une réussite secondaire ne réinitialise PAS le primaire — la décision de
  reprise est explicitement humaine.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from core.broker_models import (
    AccountSnapshot,
    BrokerOrderSnapshot,
    BrokerPosition,
    OrderRequest,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_RESUME_FLAG = Path("artifacts") / "failover" / "RESUME"


class WriteSuspendedError(RuntimeError):
    """Écritures suspendues : le circuit breaker primaire est ouvert."""


class FailoverBrokerClient:
    """Wrapper qui bascule en lecture seule sur ``secondary`` après N erreurs."""

    name = "failover"

    def __init__(
        self,
        primary: Any,
        secondary: Any,
        *,
        circuit_breaker_threshold: int = 3,
        resume_flag_path: Path = DEFAULT_RESUME_FLAG,
        notifier: Any | None = None,
    ) -> None:
        self.primary = primary
        self.secondary = secondary
        self.threshold = circuit_breaker_threshold
        self.resume_flag_path = resume_flag_path
        self.notifier = notifier
        self._error_count = 0
        self._tripped = False
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def tripped(self) -> bool:
        with self._lock:
            self._maybe_resume()
            return self._tripped

    def _maybe_resume(self) -> None:
        if self._tripped and self.resume_flag_path.exists():
            LOGGER.warning("Failover: sentinelle %s détectée → reset breaker.",
                           self.resume_flag_path)
            try:
                self.resume_flag_path.unlink()
            except OSError:
                pass
            self._tripped = False
            self._error_count = 0

    def _trip(self) -> None:
        if self._tripped:
            return
        self._tripped = True
        LOGGER.critical("Failover: bascule lecture sur '%s' — écritures suspendues.",
                        getattr(self.secondary, "name", "secondary"))
        if self.notifier is not None:
            try:
                self.notifier.send(
                    subject="[failover] Broker primary tripped",
                    body=(f"Primary={getattr(self.primary, 'name', 'primary')} "
                          f"errors={self._error_count} threshold={self.threshold}. "
                          f"Création de {self.resume_flag_path} requise pour reprise."),
                    severity="critical",
                )
            except Exception:  # noqa: BLE001
                LOGGER.debug("notifier indisponible.", exc_info=True)

    def _read(self, op: Callable[[Any], Any]) -> Any:
        with self._lock:
            self._maybe_resume()
            if self._tripped:
                return op(self.secondary)
            try:
                result = op(self.primary)
                self._error_count = 0
                return result
            except Exception as exc:  # noqa: BLE001
                self._error_count += 1
                LOGGER.warning("Failover: primary error %d/%d : %s",
                               self._error_count, self.threshold, exc)
                if self._error_count >= self.threshold:
                    self._trip()
                    return op(self.secondary)
                raise

    def _write_guard(self) -> None:
        with self._lock:
            self._maybe_resume()
            if self._tripped:
                raise WriteSuspendedError(
                    "Failover actif : écritures suspendues jusqu'à création de "
                    f"{self.resume_flag_path}."
                )

    # ------------------------------------------------------------------
    # BrokerClient API
    # ------------------------------------------------------------------

    def get_account(self) -> AccountSnapshot:
        return self._read(lambda b: b.get_account())

    def get_positions(self) -> list[BrokerPosition]:
        return self._read(lambda b: b.get_positions())

    def get_orders(self, status: str = "all", since: datetime | None = None) -> list[BrokerOrderSnapshot]:
        return self._read(lambda b: b.get_orders(status=status, since=since))

    def submit_order(self, request: OrderRequest) -> BrokerOrderSnapshot:
        self._write_guard()
        return self.primary.submit_order(request)

    def cancel_order(self, order_id: str) -> bool:
        self._write_guard()
        return self.primary.cancel_order(order_id)

    def stream_trades(self, callback: Callable[[BrokerOrderSnapshot], None]) -> Any:
        # Stream = lecture, mais on reste sur primary tant qu'il n'a pas tripped.
        target = self.secondary if self.tripped else self.primary
        return target.stream_trades(callback)


__all__ = ["FailoverBrokerClient", "WriteSuspendedError", "DEFAULT_RESUME_FLAG"]

