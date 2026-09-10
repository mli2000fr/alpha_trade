# P0h — Serving shadow de l'Oracle à univers PIT dynamique

## Statut

P0h est implémenté en `SHADOW_ONLY`. Il permet de produire des scores avec un
batch Oracle `pit_dynamic_bars`, mais interdit leur consommation par le
backtest, le risque ou l'exécution.

Le batch de référence est :

```text
model-factory-20260909051302-323684
```

P0h ne transforme pas ce batch en modèle de trading. P0f a validé l'amplitude,
alors que P0g a rejeté la direction D1/D10.

## Flux fonctionnel

```text
Fichier univers large
        │
        ▼
Barres connues à la date J
        │
        ▼
Admission PIT P0b
  504 séances réelles
  prix >= 10 $
  volume moyen 20j >= 100 000
  dollar-volume moyen 20j >= 10 M$
  ratio de barres remplies 252j <= 2 %
        │
        ▼
Features et rangs cross-sectionnels
calculés uniquement sur les admis de J
        │
        ▼
Champion Oracle applicable à J
        │
        ▼
proba_extreme + percentile quotidien + TOP20
        │
        ▼
Artefacts shadow isolés
        │
        ├── aucune écriture oracle_extreme_predictions
        ├── aucune écriture model_predictions
        ├── aucune synthèse oracle_synth
        └── aucun signal transmis au backtest/trading
```

## Garanties de sécurité

Un batch dynamique lancé sans `--oracle-shadow` reste refusé avec
`dynamic_oracle_universe_not_serving_ready`.

Le mode shadow :

- exige un profil `oracle_universe_mode=pit_dynamic_bars` ;
- exige un batch Oracle-only possédant des champions ;
- reconstruit l'univers indépendamment pour chaque date ;
- filtre avant le calcul des rangs cross-sectionnels ;
- écrit uniquement des fichiers Parquet et un rapport JSON ;
- renomme `fold_start` en `champion_t_start` pour ne jamais présenter
  une prédiction shadow comme une prédiction OOF ;
- marque chaque ligne `prediction_mode=shadow` ;
- produit `trading_eligible=false` et `serving_ready=false` dans le rapport.

## Artefacts

Chaque lancement crée :

```text
artifacts/models/oracle/shadow/
└── <batch_id>/
    └── oracle-shadow-<timestamp>-<suffixe_batch>/
        ├── report.json
        └── parts/
            ├── part-00000.parquet
            ├── part-00001.parquet
            └── ...
```

Chaque ligne contient notamment :

- `date` et `symbol` ;
- `proba_extreme` ;
- `extreme_pct`, percentile quotidien dans l'univers admis ;
- `extreme_gate_top20` ;
- `champion_t_start` ;
- `prediction_mode=shadow` ;
- les cibles réalisées lorsqu'elles sont déjà disponibles, sinon `NULL`.

Le rapport indique la période, le nombre de dates, de symboles et de lignes,
les seuils d'admission, la couverture quotidienne et la liste des fragments.

## Utilisation depuis l'IHM

Dans **Pipeline → 10. ML Predict** :

1. sélectionner `model-factory-20260909051302-323684` ;
2. vérifier que l'univers repris est `univers_filtred.txt` ;
3. la case **Oracle dynamique — prédiction shadow uniquement** s'active
   automatiquement ;
4. activer la plage historique ;
5. utiliser comme première fenêtre `2025-07-14 → 2026-06-30` ;
6. lancer **Prédire l'univers sélectionné**.

Si la case shadow est décochée, le batch dynamique est refusé. Les workers de
dates affichés par l'IHM ne parallélisent pas actuellement le chemin Oracle :
la persistance reste néanmoins découpée en lots.

## Commande équivalente

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory --mode predict --oracle-shadow --batch-id model-factory-20260909051302-323684 --symbol-source universe-file:univers_filtred.txt --artifacts-dir artifacts/models/model-factory-20260909051302-323684 --training-start-date 2025-07-14 --training-end-date 2026-06-30 --forecast-horizon 20 --max-workers 4 --log-level INFO
```

## Ancienneté du champion

Le dernier champion disponible porte `t_start=2025-01-08`. Il a été construit
dans le dernier fold Walk-Forward et est appliqué aux dates postérieures. P0h
enregistre cette valeur sur chaque score afin de mesurer explicitement le
vieillissement. Il ne faut pas interpréter le nom du batch ou sa date de fin
comme la preuve d'un refit final au 31 décembre 2025.

## Évaluation ultérieure

Lorsque H20 est réalisé, un audit prospectif doit joindre les scores shadow aux
prix futurs sans réentraîner ni choisir un seuil. Les mesures minimales sont :

1. AUC extrême et précision/rappel TOP10/TOP20 ;
2. lift et rétention d'amplitude ;
3. résultats par mois et semestre ;
4. dérive de la distribution de `proba_extreme` ;
5. taille et composition de l'univers quotidien ;
6. âge du champion ;
7. proportion D1/D10, uniquement comme diagnostic et non comme gate.

La promotion vers les tables de serving exige une décision séparée. Aucun
artefact P0h n'est automatiquement promouvable.

L'évaluation complète du premier holdout est documentée dans
[P0i — évaluation du shadow dynamique](oracle_universe_p0i_shadow_evaluation.md).

## Validation technique du 9 septembre 2026

Le smoke de non-régression sur `univers_test_rapide.txt`, à la date du
30 juin 2026, a terminé avec un code retour nul :

- 47 symboles demandés, 45 admis par les règles PIT ;
- 45 scores shadow et 10 candidats dans le quantile TOP20 quotidien ;
- un fragment Parquet et un `report.json` complets ;
- zéro ligne pour ce batch et cette date dans
  `oracle_extreme_predictions` ;
- zéro ligne pour ce batch et cette date dans `model_predictions`.

Un calcul de contrôle sur `univers_filtred.txt` a également produit 2 095
scores admis sur 2 696 symboles sources. Son calcul était valide ; une erreur
d'affichage CLI survenue après l'écriture du rapport a été corrigée puis
revalidée par le smoke réduit.
