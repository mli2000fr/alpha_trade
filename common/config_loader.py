"""Chargement de configuration YAML — extrait de ``common/utils.py`` (Phase 2.1)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml


def load_config(path: Optional[str] = None) -> dict:
    """Charge la configuration centralisée YAML (par défaut ``config.yaml`` du projet)."""
    config_path = Path(path) if path else Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


__all__ = ["load_config"]

