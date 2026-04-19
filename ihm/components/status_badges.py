"""ihm/components/status_badges.py — Badges colorés pour les statuts."""
from __future__ import annotations


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

