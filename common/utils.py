"""Façade rétrocompatible — Phase 2.1 du refactor.
Le contenu historique de ``common/utils.py`` a été décomposé en sous-modules
spécialisés afin d''éviter le « fourre-tout » :
- ``common.logging_setup`` : configuration logging.
- ``common.market_calendar`` : calendrier de marché US (NYSE).
- ``common.config_loader`` : chargement YAML de ``config.yaml``.
Ce module ré-exporte tous les symboles publics historiques pour que les
imports existants (``from common.utils import configure_root_logging``)
continuent de fonctionner. Les nouveaux modules consommateurs DOIVENT
importer depuis le sous-module adapté.
"""
from __future__ import annotations
from common.logging_setup import (
    DEFAULT_LOG_FORMAT,
    PROJECT_ROOT,
    _configure_utf8_stdio,
    _reset_root_logging_handlers,
    _resolve_log_path,
    configure_root_logging,
    setup_logging_with_file_handler,
)
from common.market_calendar import (
    _get_nyse_calendar,
    getLastDateMarche,
    is_trading_day,
    is_us_market_holiday,
)
from common.config_loader import load_config
from common.quantity_utils import (
    QUANTITY_DECIMALS,
    QUANTITY_EPSILON,
    format_share_quantity,
    is_effectively_integer_quantity,
    normalize_share_quantity,
)
__all__ = [
    "DEFAULT_LOG_FORMAT",
    "PROJECT_ROOT",
    "configure_root_logging",
    "setup_logging_with_file_handler",
    "getLastDateMarche",
    "is_trading_day",
    "is_us_market_holiday",
    "load_config",
    "QUANTITY_DECIMALS",
    "QUANTITY_EPSILON",
    "format_share_quantity",
    "is_effectively_integer_quantity",
    "normalize_share_quantity",
]
