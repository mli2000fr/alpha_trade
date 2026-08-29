# 5 — Configuration, diagnostics et runbook per-symbol

## Paramètres clés

`sequence_length`, horizons, historique minimal, feature set/whitelist, modes et
seuils de target, calibration, walk-forward, hyperparamètres LSTM/tabulaires,
champion selection, seed, limites d’univers et flags de features.

`per_symbol_max_symbols` peut plafonner la campagne ; la sélection peut être
stratifiée. `exclude_per_symbol_per_sector=True` saute cette famille tout en
conservant Global Ranking/Oracle, contrairement à certains anciens modes globaux.

## Diagnostic

Contrôler par symbole : statut et motif de skip, dates/effectifs, features et
fingerprint, métriques par split, calibration/ECE, action rate, collapse,
challengers, champion, route, signatures et source des prédictions récentes.

## Incidents

- historique trop court : compléter les données, ne pas réduire arbitrairement
  le minimum ;
- séquences insuffisantes : vérifier NaN/features/splits ;
- champion différent du served : auditer route, promotion et signatures ;
- prédiction absente : vérifier cutoff PIT, config, artefacts et fallback secteur ;
- forte hétérogénéité : analyser couverture et préférer le modèle sectoriel/global
  seulement après validation comparable.

## Promotion

Comparer sur partitions autorisées, garder le holdout final intact, vérifier
artefacts signés, effectuer une prédiction de contrôle, persister gouvernance et
préparer rollback. Une bonne métrique d’un symbole peu observé ne suffit pas.

