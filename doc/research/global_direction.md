# Global Direction H20

Retour : [recherche](README.md)

## Objectif

Dans le pool Oracle top `pool_pct` par `proba_extreme`, Global Direction cherche le **sens** : distinguer D10 (bon long) de D1 (mauvais long). Il compare Oracle pur, reranking B25 et `direction_score` GD.

## Dataset

`global_direction/dataset.py` réutilise la matrice de features Oracle PIT mais interdit `proba_extreme` et `global_rank_20` comme features. La cible vaut 1 pour décile Oracle 10, 0 pour décile 1 ; D2–D9 sont exclus du train. `oracle_available_date` reste colonne de garde.

Les modes features sont minimal, directional, directional+xs, sector, complete et all. Le minimal privilégie momentum/trend/force relative. Les features secteur sont construites séparément ; les commentaires historiques « non disponible » ne suffisent pas, vérifier `build_sector_features` du code courant.

## Walk-forward et pipeline

`walk_forward.py` entraîne classification ou régression selon mode et écrit OOS. `pipeline.py` charge Oracle OOS, ranks B25 et régimes puis construit le pool quotidien. Il sélectionne top m24 et calcule D1/D10, ratio, mean/median H20, taux positif, couverture, folds, semestres et régimes.

Le critère principal déclaré est un gradient stable : quand `direction_score` augmente, D10 augmente et D1 diminue. Une AUC globale sans ce gradient/stabilité n'est pas suffisante.

## Statut

Cette branche est une expérience long-only dans un pool Oracle. Elle ne remplace ni Global Ranking production ni décision ternaire sans promotion explicite et intégration au predictor/risk.

