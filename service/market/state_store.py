"""Persistance simple de l'état de régime pour le mode live.

Le stockage par défaut est un JSON local sous ``artifacts/market_regime/state/``.
Cette première version R9.0 reste volontairement minimale et portable.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from service.market.models import MarketRegimeState

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_STATE_PATH = PROJECT_ROOT / "artifacts" / "market_regime" / "state" / "latest.json"
LOGGER = logging.getLogger(__name__)


def load_regime_state(path: Path | None = None) -> MarketRegimeState | None:
    state_path = Path(path) if path is not None else DEFAULT_STATE_PATH
    if not state_path.is_file():
        return None
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    # save_regime_state(None) intentionally writes this empty-state sentinel.
    # It is absence of previous hysteresis state, NOT a qualified normal regime.
    if payload == {}:
        LOGGER.info("État de régime persistant vide : aucun état précédent ; snapshot du jour à recalculer.")
        return None
    if not isinstance(payload, dict):
        raise ValueError("État de régime invalide : objet JSON attendu")
    if "trade_date" not in payload:
        raise ValueError("État de régime incomplet : trade_date absent")
    return MarketRegimeState.from_dict(payload)


def save_regime_state(state: MarketRegimeState | None, path: Path | None = None) -> Path:
    state_path = Path(path) if path is not None else DEFAULT_STATE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = state.to_dict() if state is not None else {}
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return state_path


__all__ = ["DEFAULT_STATE_PATH", "load_regime_state", "save_regime_state"]

