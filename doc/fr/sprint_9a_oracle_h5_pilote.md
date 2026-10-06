# Sprint 9-A — Oracle H5 prix-only : protocole du pilote

Protocole figé avant les premiers fits/test de ce lot, le 3 octobre 2026. Les données et critères de couverture ont déjà été examinés aux Sprints 7/8 ; ce protocole n'est pas une validation indépendante de ces choix d'amont.

## Périmètre autorisé

Recherche seulement sur H5 et les folds 4, 5 et 6 validés en couverture au [Sprint 8-B](sprint_8b_revue_chemins_et_support_folds.md). Aucun benchmark, secteur ou feature fondamentale ajouté ; les 14 features du profil prix figé sont les seules entrées prédictives. Les cibles restent les labels d'amplitude terminale brute 8-A ; ni cash-flow dividende, coût, fill, sens D1/D10 ni stratégie de portefeuille ne sont modélisés.

2026 est réservé et n'est ni utilisé pour les fits, ni évalué dans ce lot. Aucun changement des features, hyperparamètres, folds ou gates ne sera fait après consultation des résultats de test. Une expérience modifiée devrait avoir un autre nom et être explicitement exploratoire.

## Comparateurs et modèles

- Baseline mécanique `atr20_pct` décroissante.
- Baseline mécanique `realized_vol20` décroissante.
- Classement pseudo-aléatoire reproductible date/UID/seed, indépendant des cibles.
- Régression logistique C=1, max_iter=500, sans pondération artificielle des classes.
- HistGradientBoosting : 100 itérations, learning_rate=0,05, profondeur ≤3, 7 feuilles, min_samples_leaf=100, L2=1, early stopping désactivé, seed=17.

`traded_value_mean20_eur` est transformée par log1p pour limiter son échelle ; les autres colonnes sont conservées. Le scaler de la régression logistique est ajusté sur le train seul. Les paramètres appris ne sont jamais estimés sur validation/test. Pas de calibration dans ce pilote : les scores probabilistes bruts ne sont pas promus en probabilités d'exécution.

Le champion de chaque fold est choisi entre les deux modèles selon l'average precision **validation uniquement**. En cas d'égalité, la régression logistique est prioritaire. Pas de recherche d'hyperparamètres ni de choix de seuil de proba. TOP20 signifie sélectionner ceil(20 % × effectif) chaque jour ; une clé déterministe date/UID/seed départage uniquement les scores égaux, jamais les vérités terrain.

## Supports et mesures

Mêmes candidates matures, features finies et cross-sections ≥20 pour tous les comparateurs du fold. Train et validation respectent les dates de disponibilité de labels 8-A ; test n'emploie aucune cible publiée après fin 2025. Les effectifs doivent correspondre exactement au rapport de support 8-B, sinon le run échoue.

Rapporter AUC, average precision (AP), prévalence, precision et recall TOP20, lift de precision vs prévalence de la même journée, ainsi que precision quotidienne moyenne, distribution des scores, répartition par semestre et couverture. Les scores ATR/volatilité ne sont pas des probabilités : aucun Brier score n'est annoncé pour ces comparateurs. Les AP et AUC globales sont pondérées implicitement par le nombre de lignes ; les métriques quotidiennes sont moyennées à poids égal par séance.

Les sorties OOF/test sont persistées avec fold, date, UID, symbole, label, score et modèle. Les modèles des deux variantes restent des artefacts de recherche non servables. Le choix champion est conservé séparément afin de ne pas choisir le meilleur modèle sur test a posteriori.

## Gate descriptif pré-fixé

Le pilote indique `PILOT_SIGNAL_REQUIRES_CONFIRMATION` seulement si le champion choisi sur validation satisfait simultanément :

- gain moyen de precision quotidienne TOP20 ≥2 points contre **chacune** des deux baselines mécaniques ;
- gain AP moyen des trois folds ≥0,01 contre chacune de ces baselines ;
- lift quotidien moyen ≥1,10 ;
- gain de precision strictement positif contre les deux baselines dans au moins deux des trois folds.

Sinon `NO_GO_INCREMENTAL_PILOT`. Ce gate n'est pas un test de significativité ni un GO production : les folds sont chronologiques mais leurs trains expanding se recouvrent, les rendements H5 se chevauchent et seulement trois folds sont étudiés. Les résultats de couverture limitée, cinq radiés faiblement représentés et les 58 grands mouvements à compléter documentairement restent des réserves. Ne pas exclure des titres ou événements après test pour améliorer le verdict.

## Exécution

Configuration : `config/research_fr/oracle_h5_pilot_v1.yaml`. Module : `modelFactory.fr_oracle_h5_pilot`.

```powershell
python -u -m modelFactory.fr_oracle_h5_pilot
```

Le run travaille sur les archives existantes et ne touche ni la base, ni l'IHM, ni les batchs actifs, ni le serving. Les résultats seront ajoutés ci-dessous après l'exécution ; ils ne modifieront pas ce protocole.

## Résultats du premier run

Run exécuté le 3 octobre 2026 : `artifacts/fr/research/oracle_h5_pilot/fr-oracle-h5-d0f5fe0e2b07/`. Les modèles arbres ont été sélectionnés sur validation dans chacun des trois folds. Ils n'ont pas été réajustés sur train+validation avant test : chaque modèle test est celui ajusté sur train seul. Aucun changement de paramètres n'a suivi la lecture des tests.

### Précision moyenne quotidienne du TOP20

| Fold / période de test | Aléatoire | ATR | Volatilité | Logistique | Arbres, champion VAL |
|---|---:|---:|---:|---:|---:|
| 4 : 2023-08-02–2024-01-29 | 20,90 % | 44,39 % | 39,94 % | 43,70 % | 45,08 % |
| 5 : 2024-01-30–2024-07-26 | 19,79 % | 39,59 % | 36,74 % | 37,72 % | 40,31 % |
| 6 : 2024-07-29–2025-01-23 | 18,54 % | 42,45 % | 38,58 % | 39,11 % | 41,61 % |

La prévalence Oracle sur les lignes de test est proche de 20 % dans chaque fold. La precision d'environ 42 % du champion signifie qu'environ 42 % de ses titres classés TOP20 sont réellement labellisés Extreme selon la cible 8-A **sur le sous-univers complet et mature retenu**. Elle ne signifie pas 42 % de trades gagnants, ni 42 % de probabilité LONG, ni une capture de tous les mouvements intrahorizon.

### AUC et AP du champion versus ATR

| Fold | AUC arbres | AUC ATR | AP arbres | AP ATR | Lift quotidien arbres |
|---|---:|---:|---:|---:|---:|
| 4 | 0,7197 | 0,7111 | 0,4270 | 0,3983 | 2,149 |
| 5 | 0,6904 | 0,6847 | 0,3727 | 0,3694 | 2,023 |
| 6 | 0,7073 | 0,7147 | 0,4088 | 0,4050 | 2,036 |

AP signifie average precision : résumé precision/recall calculé sur toutes les lignes du fold, distinct de la precision TOP20. AUC mesure la qualité d'ordre entre labels positifs/négatifs ; elle ne mesure pas le sens des rendements.

### Gate incrémental

- Delta moyen de precision quotidienne vs ATR : **+0,1884 point**, inférieur aux +2 points requis.
- Delta moyen AP vs ATR : **+0,01192**, supérieur au +0,01 requis.
- Delta moyen de precision vs volatilité : **+3,9128 points** ; delta AP **+0,04249**.
- Deux folds sur trois améliorent la precision contre les deux baselines ; le troisième est inférieur à l'ATR.
- Lift quotidien moyen du champion : **2,0692**.

Les deltas sont des moyennes à poids égal entre folds ; les precisions utilisées sont elles-mêmes des moyennes à poids égal entre séances. Ne pas les confondre avec une precision poolée par titre. **Verdict : `NO_GO_INCREMENTAL_PILOT`**, car toutes les conditions devaient être satisfaites et le gain TOP20 contre ATR est insuffisant.

## Interprétation et suite

La détection de l'amplitude n'est pas aléatoire sur ce périmètre FR H5, mais une grande partie du signal est déjà capturée par l'ATR. Ce résultat ne démontre pas de gain ML matériel sur la sélection TOP20. Il n'invalide pas toutes les formulations Oracle France ; il invalide la promotion incrémentale de **ce pilote précis**, sous les gates fixés. Les résultats ne prouvent toujours aucune capacité à distinguer D1/D10.

Ne pas déployer ce modèle, rechercher un meilleur hyperparamètre sur les mêmes tests ou utiliser 2026 pour contourner ce NO-GO. Conserver ATR comme référence mécanique. Avant une nouvelle campagne supervisée, clarifier la couverture et le caractère incrémental recherché ; H10/H20 et benchmark restent bloqués par leurs gates de données, et le simple ajout de features ne répare pas ces trous.

## Artefacts et vérifications

- `protocol.json` : configuration/features/fingerprint, écrit avant le premier fit ;
- `fold4_metrics.json`, `fold5_metrics.json`, `fold6_metrics.json` : choix champion et métriques validation/test ;
- `fold{n}_logistic.joblib`, `fold{n}_trees.joblib` : poids de recherche, non servables ;
- `predictions.parquet` : scores des cinq comparateurs, vérité Oracle, clés et disponibilité du label sur validation/test ;
- `daily_metrics.parquet` : données par séance/fold/phase/modèle, utilisables pour les diagnostics par semestre ;
- `report.json` : résultats, deltas, verdict et limitations.

Les poids seuls ne constituent pas un artefact de serving autonome : respecter l'ordre des 14 features et appliquer `feature_matrix` (notamment log1p de la valeur échangée) avant usage. Aucune inscription dans les tables modèles/prédictions, aucun fit sur 2026, aucun backtest économique.

SHA-256 des prédictions : `36afd83718aafced51aec5ec3b0b4f7361c87d23af04660957f3e62fa59f8f91`. Le run existant n'est pas écrasé par une relance ; il est conservé et la commande refuse le même répertoire/version. Les versions sklearn/numpy/pandas participent au fingerprint, ainsi que les règles et sources. Les poids ne sont pas prétendus bit-identiques sur un autre environnement.

**192 tests ciblés passent**, dont sept nouveaux vérifiant la liste de features sans cible, la transformation déterministe, le TOP20 quotidien, les scores égaux indépendants de l'ordre des lignes, la sélection champion et sa priorité en cas d'égalité, la maturité/minimum cross-section, les scores invalides et le gate contre les deux baselines. Ruff passe. La suite ciblée n'est pas l'ensemble des tests de l'application.
