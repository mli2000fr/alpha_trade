"""Module ``service.eodhd`` — client EOD Historical Data.

Phase 2 du plan ``prompt/iex/plan_eodhd.md``.

Source primaire des barres OHLCV daily (``stock_bars`` + ``stock_bars_daily``)
pour Alpha Trade, en remplacement progressif d'Alpaca/IEX (volume biaisé).

Composants :
- :mod:`service.eodhd.clientEodhd` : appels HTTP ``/eod-bulk-last-day``,
  ``/eod/{ticker}``, ``/splits/``, ``/div/``.
- :mod:`service.eodhd.symbols`    : mapping ``AAPL`` <-> ``AAPL.US``,
  ``BRK.B`` <-> ``BRK-B.US``.
- :mod:`service.eodhd.adapters`   : reconstruction split-only + mappage vers
  les schémas ``stock_bars`` / ``stock_bars_daily``.
- :mod:`service.eodhd.cache`      : cache disque (``artifacts/eodhd_cache/``).
- :mod:`service.eodhd.quota`      : compteur journalier + circuit-breaker.
- :mod:`service.eodhd.accounts`   : registre du token API.

L'activation runtime est pilotée par :
- ``config.yaml`` clé ``market_data.bars_provider`` (``alpaca`` / ``eodhd``).
- variable d'environnement ``EODHD_API_TOKEN``.

Note : il n'existe **aucun** flag ``eodhd.enabled`` (audit S1 / anomalie
A-002). La bascule de provider se fait exclusivement via
``market_data.bars_provider``.
"""
from __future__ import annotations

__all__: list[str] = []

