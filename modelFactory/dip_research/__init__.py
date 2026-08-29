"""modelFactory/dip_research — Recherche DIP (Persistent Rank DIP filter).

Filtres de recherche basés sur ``global_rank_history`` (B25) + persistance + dip,
initialement rangés dans ``global_direction/`` par convenance de batch_id.

Modules :
- ``persistent_top10_dip.py``        : validation du signal DIP (persist N=4 + ret_4).
- ``persistent_top10_dip_portfolio.py`` : backtest portefeuille P0/P1/P1b/P2 (BacktestEngine).
- ``persistent_top10_dip_parity.py`` : audit de parité PROD (P0_PROD / P2_PROD).
- ``persistent_top10_dip_reclaim.py``: reclaim research-only (R50/R100).
- ``persistent_tail_price.py``       : confirmation tail price.

NB : dépend de ``global_direction.config.resolve_global_direction_batch_id``
(helper partagé de résolution de batch_id), pas du modèle GlobalDirection.
"""
