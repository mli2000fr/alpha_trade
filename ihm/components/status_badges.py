"""ihm/components/status_badges.py — Badges colorés pour les statuts."""
from __future__ import annotations

from datetime import datetime


def badge(label: str, status: str = "ok") -> str:
    """Retourne un emoji + label selon le statut."""
    icons = {"ok": "🟢", "warn": "🟡", "error": "🔴", "info": "🔵"}
    return f"{icons.get(status, '⚪')} {label}"


def env_badge(var_name: str, value: str | None) -> str:
    if value:
        masked = value[:4] + "****" if len(value) > 4 else "****"
        return f"🟢 `{var_name}` = `{masked}`"
    return f"🔴 `{var_name}` — **MANQUANT**"


def run_status_badge(status: str | None) -> str:
    if status is None:
        return "⚪ Inconnu"
    s = str(status).upper()
    if s in ("COMPLETED", "SUCCESS"):
        return f"🟢 {s}"
    if s == "RUNNING":
        return f"🟡 {s}"
    return f"🔴 {s}"


def decision_badge(decision: str) -> str:
    d = str(decision).upper()
    if d == "ACCEPTED":
        return "🟢 ACCEPTED"
    if d == "REDUCED":
        return "🟡 REDUCED"
    return "🔴 REJECTED"


def classify_heartbeat_freshness(
    last_heartbeat_at: str | None,
    heartbeat_interval_seconds: float | int | None,
    *,
    service_status: str | None = None,
    now: datetime | None = None,
) -> tuple[str, str, int | None]:
    """Retourne (niveau, libellé, âge secondes) pour la fraîcheur heartbeat.

    Niveaux:
    - ok    : heartbeat frais
    - warn  : heartbeat à surveiller / inconnu
    - error : stale ou service arrêté/en échec
    """
    status_text = str(service_status or "").upper()
    if status_text in {"FAILED", "ERROR"}:
        return "error", "KO", None
    if status_text == "STOPPED":
        return "error", "ARRÊTÉ", None

    interval_value = float(heartbeat_interval_seconds or 0.0)
    if not last_heartbeat_at or interval_value <= 0:
        return "warn", "INCONNU", None

    try:
        heartbeat_dt = datetime.fromisoformat(str(last_heartbeat_at))
    except ValueError:
        return "warn", "INCONNU", None

    reference_dt = now or datetime.now()
    age_seconds = max(int((reference_dt - heartbeat_dt).total_seconds()), 0)
    if age_seconds <= int(interval_value * 1.25):
        return "ok", "FRAIS", age_seconds
    if age_seconds <= int(interval_value * 2.5):
        return "warn", "À SURVEILLER", age_seconds
    return "error", "STALE", age_seconds


def heartbeat_badge(
    last_heartbeat_at: str | None,
    heartbeat_interval_seconds: float | int | None,
    *,
    service_status: str | None = None,
    now: datetime | None = None,
) -> str:
    level, label, age_seconds = classify_heartbeat_freshness(
        last_heartbeat_at,
        heartbeat_interval_seconds,
        service_status=service_status,
        now=now,
    )
    suffix = f" ({age_seconds}s)" if age_seconds is not None else ""
    return badge(f"Heartbeat {label}{suffix}", level)


