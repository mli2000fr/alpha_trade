# Oracle Extreme O0 — référence technique

Contrats détaillés : [dossier Oracle Extreme complet](oracle/README.md).

Retour : [références ML](README.md) · [présentation](../08_ml_oracle_extreme.md)

## Sémantique

Oracle détecte l'appartenance à une queue de mouvement futur. `proba_extreme` mesure l'extrême, sans direction. L'usage long du top pool est une observation de recherche qui doit être revalidée ; le modèle ne produit pas `P(LONG)`.

## Dataset et anti-fuite

`build_labels.py` construit MFE/MAE/retours futurs et labels sur l'horizon. `dataset.py` joint uniquement les features disponibles. `leakage.py` interdit noms futurs/oracle et vérifie `available_at <= prediction cutoff`, cutoff train et absence de lecture future.

O0 exclut `global_rank_20`. Toute variante qui l'ajoute est une autre expérience et doit porter un autre contrat.

`build_labels.py` peut construire son univers depuis ranks, predictions ou bars et vérifie l’égalité attendue. Il charge la matrice de closes, calcule les mesures futures et écrit par batches. Le dry-run doit permettre de contrôler dates, volumes et distribution avant persistance.

`dataset.py` expose feature sets expert/lean, matrice, targets, split et ablations. Les ablations `O0|O1|O2` sont des contrats expérimentaux distincts ; ne pas comparer leurs métriques sans publier la liste exacte de colonnes.

## Walk-forward et modèles

`walk_forward.py` construit des folds temporels fixes ou adaptatifs. `train.py` expose classifier/regressor LightGBM et CatBoost, puis AUC, precision/recall top pct et monotonie déciles. `persist_oos` conserve les prédictions hors échantillon.

Le mode adaptatif paramètre taille minimale train, validation, test, pas et nombre maximum de splits. Les fenêtres doivent être exprimées en séances et leurs bornes conservées dans le rapport. Une ligne OOS ne peut provenir que d’un modèle n’ayant pas vu sa cible.

Les métriques de queue complètent l’AUC : precision/recall au top pourcentage, rendement/label par décile, monotonie, concentration par date/symbole/secteur et stabilité des folds. Un AUC acceptable ne garantit pas un top pool exploitable.

## Combinaison/calibration

`combine.py` combine scores, recherche les poids sur folds et calibre `p_extreme` par isotonic regression. La calibration doit être apprise sans le fold évalué. `predictions_store.py` écrit batch/date/symbole/probabilité dans la table spécialisée.

La recherche sépare selection folds et final folds. Réutiliser les final folds pour modifier les poids invalide leur rôle. L’isotonic peut créer des plateaux : le percentile quotidien peut alors nécessiter une règle d’égalité déterministe pour stabiliser la taille du pool.

## Gate quotidien

`compute_extreme_gate` fait `groupby(date).rank(pct=True)` et garde `pct >= 1-pool_pct`. Avec 20 %, le seuil est 0,8. Si DataFrame vide/colonne absente, gate faux. Le percentile dépend de la population du jour ; changer le scope change les membres.

`build_oracle_rank_map` fournit la représentation consommable. Le run doit enregistrer batch Oracle, date, pool_pct, population initiale, nombre retenu et gestion des valeurs manquantes/égalités. Le gate sélectionne une intensité extrême, pas un côté ; la direction doit venir d’un autre contrat explicitement validé.

## Diagnostics spécialisés

`hard_negatives.py` étudie les faux positifs difficiles ; `catastrophic_detector.py` le rejet des cas sévères ; `error_severity.py` quantifie le coût ; `confound_validation.py` teste les variables confondantes ; diagnostics features/fondamentaux mesurent séparabilité. Ces scripts sont recherche, pas gates live automatiques.

## Promotion

Reproduire OOS multi-fold/seeds, vérifier calibration/monotonie, top pool, concentration et coûts. Puis rejouer avec lifecycle PROD exact. Un résultat issu de labels stop 3.5 ATR/time-stop ON ne valide pas un lifecycle stop 2.5 ATR/time-stop neutralisé.

## Persistance et audit

`oracle_extreme_predictions` est la table dédiée. Les écritures et lectures portent batch/date/symbole. Ne pas mélanger des prédictions de batches différents dans un percentile quotidien. L’audit peut rattacher labels Oracle aux trades, calculer capture, histogrammes, rendements par décile, monotonie et comparaison golden.

## Modes d’échec

| Symptôme | Cause possible |
|---|---|
| pool trop grand/petit | égalités, population ou `pool_pct` |
| forte AUC, mauvais top | ranking de queue ou calibration |
| résultat change après backfill | dataset/fingerprint non figé |
| direction incohérente | `proba_extreme` interprétée comme long |
| OOS trop beau | fuite de cutoff, feature future, sélection sur final folds |
| production vide | batch/date absents ou colonnes incompatibles |
