"""Sprint S1 / Anomalie A-001 — Convention `data_adjustment = 'split'`.

Verrouille la convention canonique projet à plusieurs niveaux :

- constante `DATA_ADJUSTMENT` côté Alpaca (`import_alpaca_bar`,
  `data_sanitizer_daily`),
- constante `DATA_ADJUSTMENT_SPLIT` côté EODHD (`service.eodhd.adapters`),
- docstring de `corporate_actions.engine.CorporateActionEngine` (qui doit
  désormais refléter la convention `'split'` + ledger dividendes, et **ne
  doit plus** mentionner ``adjustment="all"`` ni la fausse stratégie
  d'ajustement total).

Ce test bloque toute régression vers l'ancienne convention `'all'` ou un
désalignement Alpaca/EODHD.
"""
from __future__ import annotations

import inspect


def test_alpaca_data_adjustment_constant_is_split() -> None:
    from dataIntegrityEngine import import_alpaca_bar

    assert import_alpaca_bar.DATA_ADJUSTMENT == "split"


def test_alpaca_sanitizer_data_adjustment_constant_is_split() -> None:
    from dataIntegrityEngine import data_sanitizer_daily

    assert data_sanitizer_daily.DATA_ADJUSTMENT == "split"


def test_eodhd_data_adjustment_constant_is_split() -> None:
    from service.eodhd import adapters

    assert adapters.DATA_ADJUSTMENT_SPLIT == "split"


def test_corporate_action_engine_docstring_reflects_split_convention() -> None:
    from corporate_actions.engine import CorporateActionEngine

    doc = inspect.getdoc(CorporateActionEngine) or ""

    # Mention positive de la convention canonique.
    assert "data_adjustment" in doc
    assert "'split'" in doc or '"split"' in doc
    assert "portfolio_cash_ledger" in doc

    # Régression : l'ancienne convention 'all' (ajustement total) ne doit
    # plus apparaître dans la docstring.
    assert 'adjustment="all"' not in doc
    assert "adjustment='all'" not in doc
    assert "data_adjustment='all'" not in doc
    assert 'data_adjustment="all"' not in doc

