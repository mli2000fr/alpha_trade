"""Sprint S24.2 — Service de chargement du rollup sandbox health.

Service pur : ne dépend pas de Streamlit, donc testable en isolation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_SANDBOX_DIR = Path("artifacts/sandbox_runs/")


def load_rollup(sandbox_dir: Path | str | None = None) -> dict[str, Any]:
    """Retourne le rollup JSON ou un dict vide si absent."""
    base = Path(sandbox_dir) if sandbox_dir else DEFAULT_SANDBOX_DIR
    target = base / "_rollup.json"
    if not target.exists():
        return {}
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_day(date_iso: str, sandbox_dir: Path | str | None = None) -> dict[str, Any]:
    base = Path(sandbox_dir) if sandbox_dir else DEFAULT_SANDBOX_DIR
    target = base / date_iso / "health.json"
    if not target.exists():
        return {}
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}

