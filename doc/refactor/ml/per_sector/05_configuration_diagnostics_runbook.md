# 5 — Configuration, diagnostics et runbook per-sector

## Paramètres clés

`training_mode=per_sector`, `sector_use_symbol_feature`, flags de features,
cross-sectionnel, stacking, targets T2/T3, quantile ternaire, horizons,
walk-forward et hyperparamètres `BaselineConfig`.

`exclude_per_symbol_per_sector` désactive toute la famille. Un batch Oracle/global
peut donc être valide tout en ne contenant aucun artefact sectoriel.

## Avant entraînement

- mapping secteur suffisamment complet et stable ;
- effectif/historique par secteur ;
- données contextuelles chargées sur la même fenêtre ;
- cache cross-sectionnel non vide ;
- choix explicite de la feature `symbol` et du contrat T2/T3 ;
- splits par dates et minimums compatibles avec les petits secteurs.

## Après entraînement

Contrôler secteurs completed/skipped/failed, effectifs, features vivantes,
distribution ternaire, métriques par horizon/split, champion, artefacts,
signatures, routes et capacité de prédire plusieurs tickers du secteur.

## Incidents

- `empty_train` : vérifier mapping, historique et NaN après préparation ;
- secteur trop petit : ne pas fusionner arbitrairement des secteurs sans
  validation ;
- modèle LSTM absent : état attendu du code actuel ;
- champion sans WF : choix par `selection_score`, à considérer moins robuste ;
- fallback secteur inattendu : rechercher absence/inéligibilité du per-symbol ;
- divergence entre tickers : vérifier feature catégorielle et contexte propre.

## Validation

Comparer per-sector au per-symbol et au global sur les mêmes lignes, dates et
targets. Mesurer valeur marginale, couverture et stabilité par secteur. Une
moyenne globale peut cacher un secteur nettement négatif.

