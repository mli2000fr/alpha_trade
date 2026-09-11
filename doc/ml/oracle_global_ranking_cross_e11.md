# E11 — Croisement Oracle H20 × Global Ranking H20

## Statut

`READY_NEEDS_CLEAN_GLOBAL_RANK_OOF`

L''évaluateur est implémenté et testé, mais l''expérience ne doit pas être lancée
avec `global_rank_history`. Il faut d''abord produire un nouvel artefact
`global_rank_cache.parquet` strictement Walk-Forward OOF.

E11 est une expérience de recherche. Elle ne modifie ni le serving, ni le
backtest, ni le live.

## Hypothèse

L''Oracle H20 sait détecter une forte amplitude future, sans en connaître le
sens. Le Global Ranking H20 sait ordonner les rendements relatifs de la coupe
transversale. L''hypothèse E11 est donc :

> parmi les seuls événements Oracle TOP20, le Global Ranking H20 place les
> futurs gagnants en haut et les futurs perdants en bas suffisamment bien pour
> séparer LONG, SHORT et abstention.

Ce croisement ne suppose pas que le bas du classement baisse en valeur absolue.
C''est précisément l''une des conditions à vérifier : un titre classé en bas peut
simplement monter moins que les autres.

## Politique gelée avant lecture des résultats

```text
univers quotidien PIT de l''Oracle P0f
        │
        ▼
Oracle H20 OOF : TOP20 amplitude
        │
        ▼
intersection date × symbole avec Global Ranking H20 OOF
        │
        ▼
reclassement du Global Ranking à l''intérieur du pool Oracle
        ├── 20 % supérieurs : LONG
        ├── 60 % centraux   : ABSTENTION
        └── 20 % inférieurs : SHORT
```

- Horizon unique : H20.
- Oracle : TOP20 exact de l''artefact `_oracle_oof_gate.parquet`.
- Rang : `global_rank_20`, recalculé en percentile dans le pool Oracle du jour.
- Entrée économique : open ajusté J+1.
- Sortie de diagnostic : open ajusté J+21.
- Coûts aller-retour : 1 bp de commission + 2 bp de slippage par côté, soit
  6 bp par position.
- Aucun seuil n''est optimisé sur les résultats E11.

La sortie H20 fixe sert à mesurer la qualité directionnelle pure. Les stops, TP,
contraintes de portefeuille et règles de protection ne sont pas rejoués à ce
stade.

## Pourquoi la table `global_rank_history` est interdite

Les anciens entraînements ont bien produit des rangs OOF Walk-Forward. Mais les
fichiers `global_rank_cache.parquet` correspondants ne sont plus présents.
Ensuite, le préremplissage Oracle a calculé des rangs sur toute la période
d''entraînement et les a enregistrés par upsert dans `global_rank_history`.

La table actuelle ne contient ni identifiant de fold, ni indicateur OOF, ni type
de provenance. Une ligne OOF et une ligne de préremplissage in-sample ne peuvent
donc plus être distinguées. Même une restriction aux anciennes dates OOS ne
garantit pas que la valeur OOF n''a pas été remplacée.

E11 impose par conséquent les deux fichiers suivants :

```text
artifacts/models/model-factory-20260909051302-323684/_oracle_oof_gate.parquet
artifacts/models/<NOUVEAU_BATCH_RANK>/global_rank_cache.parquet
```

Le programme refuse volontairement un export de table ou un fichier renommé.
Il exige également `_global_ranking_features.json`, qui doit attester H20.

## Étape 1 — produire un Global Ranking H20 OOF propre

Commande PowerShell en une ligne :

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory --mode train --global-model-only --target-mode regression --num-classes 1 --forecast-horizon 20 --feature-set expert --benchmark-symbol SPY --training-start-date 2016-01-01 --training-end-date 2026-06-30 --symbol-source universe-file:univers_filtred.txt --artifacts-dir artifacts/models --max-workers 4 --enable-global-model --global-model-name catboost --global-champion --catboost-loss-function YetiRank --include-short-score --include-factors --include-volume-features --no-include-score-components --target-excess-vs-spy --enable-cross-sectional --global-ranking-max-symbols 0 --select-champion --walkforward --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 14 --log-level INFO --comment "E11 Global Ranking H20 OOF univers P0f"
```

Points importants :

- `--global-model-only` évite les modèles Per-Symbol et Per-Sector ;
- `--forecast-horizon 20` évite quatre horizons inutiles ;
- `--global-ranking-max-symbols 0` interdit un cap implicite à 300 symboles ;
- le même `univers_filtred.txt` que P0f maximise le recouvrement ;
- `step=126`, `max_splits=14` reproduisent la profondeur temporelle P0f ;
- CatBoost, LightGBM et XGBoost sont comparés par le mode champion actuel ;
- le fichier OOF doit être conservé avant toute purge d''artefacts.

Contrôles à faire à la fin :

```powershell
Test-Path artifacts/models/<NOUVEAU_BATCH_RANK>/global_rank_cache.parquet
Test-Path artifacts/models/<NOUVEAU_BATCH_RANK>/_global_ranking_features.json
```

## Étape 2 — lancer le croisement E11

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.oracle_global_rank_cross --oracle-gate artifacts/models/model-factory-20260909051302-323684/_oracle_oof_gate.parquet --global-rank-cache artifacts/models/<NOUVEAU_BATCH_RANK>/global_rank_cache.parquet --bootstrap-samples 2000 --log-level INFO
```

Les résultats sont écrits dans :

```text
artifacts/research/oracle_global_rank_cross/oracle-global-rank-cross-<timestamp>/
```

| Fichier | Contenu |
|---|---|
| `report.json` | contrat, provenance, couverture, métriques, gates et verdicts |
| `events.parquet` | événements Oracle joints, rang, côté et rendement H20 |
| `daily.csv` | IC, LONG, SHORT, spread et lifts quotidiens |
| `by_fold.csv` | stabilité selon les folds OOF Oracle |
| `by_semester.csv` | stabilité par semestre |

## Métriques et gates

E11 mesure l''IC de Spearman quotidien dans le pool Oracle, le spread brut, le
portefeuille LONG/SHORT dollar-neutral net, le rendement LONG, le rendement
SHORT, leurs lifts appariés contre l''Oracle entier, leurs IC95 par bootstrap en
blocs de 21 séances, puis leur stabilité par fold et semestre.

Le signe absolu est indispensable : un bon classement relatif ne valide pas la
branche SHORT si les titres du bas continuent à monter.

Gates communs : couverture de jointure ≥ 70 % et au moins 500 événements par
côté.

Le ranking passe seulement si : IC quotidien ≥ 0,02, IC positif dans au moins
75 % des folds et 60 % des semestres, portefeuille LONG/SHORT net positif et
borne basse de son IC95 supérieure à zéro.

La branche LONG ou SHORT passe seulement si : rendement net positif, lift
quotidien ≥ 25 bp contre l''Oracle, borne basse de l''IC95 du lift supérieure à
zéro, lift positif dans au moins 75 % des folds et 60 % des semestres.

Les verdicts `ranking`, `long` et `short` sont indépendants. Même un
`GO_RESEARCH` n''autorise pas la production : il ouvre une confirmation OOS
indépendante, puis seulement un replay du lifecycle canonique.

## Limites

- Le fichier `univers_filtred.txt` est une liste courante : le biais de
  survivance doit être rappelé dans l''interprétation.
- Les folds Oracle et Global Ranking sont tous deux OOF, mais leurs fenêtres
  d''apprentissage ne sont pas nécessairement identiques.
- Les rendements d''un même jour sont corrélés ; les statistiques sont d''abord
  agrégées par jour et le bootstrap utilise des blocs.
- E11 ne teste ni sizing, ni portefeuille, ni exits.

## Implémentation et tests

- Code : `modelFactory/oracle_global_rank_cross.py`
- Tests : `tests/test_oracle_global_rank_cross.py`
- Contrôle ciblé : 9 tests unitaires passants, Ruff et compilation Python
  propres au 11 septembre 2026.

