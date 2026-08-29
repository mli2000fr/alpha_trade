# Oracle Extreme O0 — référence technique

Retour : [références ML](README.md) · [présentation](../08_ml_oracle_extreme.md)

## Sémantique

Oracle détecte l'appartenance à une queue de mouvement futur. `proba_extreme` mesure l'extrême, sans direction. L'usage long du top pool est une observation de recherche qui doit être revalidée ; le modèle ne produit pas `P(LONG)`.

## Dataset et anti-fuite

`build_labels.py` construit MFE/MAE/retours futurs et labels sur l'horizon. `dataset.py` joint uniquement les features disponibles. `leakage.py` interdit noms futurs/oracle et vérifie `available_at <= prediction cutoff`, cutoff train et absence de lecture future.

O0 exclut `global_rank_20`. Toute variante qui l'ajoute est une autre expérience et doit porter un autre contrat.

## Walk-forward et modèles

`walk_forward.py` construit des folds temporels fixes ou adaptatifs. `train.py` expose classifier/regressor LightGBM et CatBoost, puis AUC, precision/recall top pct et monotonie déciles. `persist_oos` conserve les prédictions hors échantillon.

## Combinaison/calibration

`combine.py` combine scores, recherche les poids sur folds et calibre `p_extreme` par isotonic regression. La calibration doit être apprise sans le fold évalué. `predictions_store.py` écrit batch/date/symbole/probabilité dans la table spécialisée.

## Gate quotidien

`compute_extreme_gate` fait `groupby(date).rank(pct=True)` et garde `pct >= 1-pool_pct`. Avec 20 %, le seuil est 0,8. Si DataFrame vide/colonne absente, gate faux. Le percentile dépend de la population du jour ; changer le scope change les membres.

## Diagnostics spécialisés

`hard_negatives.py` étudie les faux positifs difficiles ; `catastrophic_detector.py` le rejet des cas sévères ; `error_severity.py` quantifie le coût ; `confound_validation.py` teste les variables confondantes ; diagnostics features/fondamentaux mesurent séparabilité. Ces scripts sont recherche, pas gates live automatiques.

## Promotion

Reproduire OOS multi-fold/seeds, vérifier calibration/monotonie, top pool, concentration et coûts. Puis rejouer avec lifecycle PROD exact. Un résultat issu de labels stop 3.5 ATR/time-stop ON ne valide pas un lifecycle stop 2.5 ATR/time-stop neutralisé.

