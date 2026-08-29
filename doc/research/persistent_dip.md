# Persistent Top10 DIP et filtre live/backtest

Retour : [recherche](README.md)

## Hypothèse

Le signal historique teste un `global_rank_20 >= 0.90` persistant N séances, combiné à un retour N séances <= -X pour DIP, puis entrée à J+1. Les configurations pré-enregistrées de la validation sont N 3/4/5 et X 2/3 %. Des variantes momentum servent de contrôle.

## Scripts de recherche

`persistent_top10_dip.py` mesure H20, MFE, MAE, recovery, déciles et breakdown. `persistent_top10_dip_portfolio.py` compare P0/P1/P1b/P2. `persistent_top10_dip_parity.py` audite le contrat PROD. `persistent_top10_dip_reclaim.py` teste une confirmation de rebond research-only. `persistent_tail_price.py` compare queues Oracle/rank et direction du prix.

## Filtre applicatif

`selector/dip_filter.py` charge `persistent_dip_filter_long` avec clés `prod_*` ou `backtest_*`. Champs : enabled, rank horizon, threshold, persist days, dip pct, reclaim ratio et max wait. `dip_pct >= 0` signifie baisse ; négatif inverse en momentum/breakout.

Le filtre charge l'historique du batch strict. En mode Oracle, il transforme `proba_extreme` en percentile intra-date. Le lookback est PIT jusqu'à trade date. Le reclaim, s'il est activé, attend un close remonté à un ratio du prix pré-DIP tout en maintenant le rank.

## Intégration

`modelFactory.predictor.cascade_select` applique le filtre selon mode et config. La synthèse live charge les clés prod ; le backtest les clés backtest ou overrides. Un filtre vide peut être fail-open dans certains blocs avec warning : ce comportement doit être surveillé et testé selon le contrat souhaité.

## Pièges

Persistance en jours calendaires vs séances, batch incorrect, rang recalculé sur mauvais univers, entrée close J+1 dans recherche vs next open PROD, reclaim activé seulement d'un côté, et lifecycle différent. La parité P0/P2 doit précéder toute conclusion.

