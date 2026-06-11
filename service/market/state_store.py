"""Persistance simple de l'état de régime pour le mode live.

Le stockage par défaut est un JSON local sous ``artifacts/market_regime/state/``.
Cette première version R9.0 reste volontairement minimale et portable.
"""
from __future__ import annotations

import json
from pathlib import Path

from service.market.models import MarketRegimeState

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_STATE_PATH = PROJECT_ROOT / "artifacts" / "market_regime" / "state" / "latest.json"


def load_regime_state(path: Path | None = None) -> MarketRegimeState | None:
    state_path = Path(path) if path is not None else DEFAULT_STATE_PATH
    if not state_path.is_file():
        return None
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return MarketRegimeState.from_dict(payload)


def save_regime_state(state: MarketRegimeState | None, path: Path | None = None) -> Path:
    state_path = Path(path) if path is not None else DEFAULT_STATE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = state.to_dict() if state is not None else {}
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return state_path


__all__ = ["DEFAULT_STATE_PATH", "load_regime_state", "save_regime_state"]

