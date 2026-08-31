# 2 — Dataset, features et targets per-symbol

## Entrées

Barres du symbole, benchmark, sentiment, univers, selector/screener, features
cross-sectionnelles et fondamentales peuvent alimenter le DataModule selon les
flags. Le minimum historique vaut par défaut 504 jours et doit dépasser
`sequence_length + forecast_horizon`.

## Features LSTM

Par défaut, `force_v1_lstm=True` force le feature set `v1` afin de limiter la
dimension. Une whitelist active ou `force_v1_lstm=False` respecte le feature set
demandé. La whitelist filtre les features X, jamais les colonnes structurelles.
Le scaler appris sur train est sauvegardé avec le checkpoint.

## Modes de target

- `binary` ;
- `swing_cash` ;
- `ternary` ;
- `regression`.

Les labels peuvent être `fixed_horizon` ou `triple_barrier`; ce dernier exige le
mode ternaire. La configuration porte seuils up/down, multiples stop/TP ATR et
nombre maximal de séances. Des cibles multi-horizons produisent `target_hN` et
`future_return_hN`.

## Optimisation de target et seuil

L’optimisation optionnelle choisit horizon/seuils ou paramètres triple-barrier
avant le fit effectif. L’optimisation du seuil de décision compare une grille
avec bornes d’action rate et précision long minimale. Les choix sont enregistrés
dans la configuration effective et le rapport ; la configuration initiale seule
ne décrit pas le modèle final.

## PIT

Les découpages sont temporels. Toute feature benchmark, sentiment, fondamentale
ou screener doit respecter sa disponibilité. Le DataModule aligne les séquences ;
les lignes insuffisantes après split provoquent un `skipped`, pas un entraînement
sur une fenêtre raccourcie silencieuse.

