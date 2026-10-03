# Sprint 7-A2 — Profil prix figé et qualification par période

Gel réalisé le 3 octobre 2026, avant toute feature benchmark et avant tout entraînement France. Ce document complète le [panel 7-A](sprint_7a_panel_features_price_only.md), sans modifier ni supprimer son profil complet.

## Décision et portée

Le profil de comparaison devient **`fr_price_short_v1`**, identique pour tous les semestres. Les 18 features du panel initial restent archivées pour diagnostic ; leur masque complet n'est pas utilisé implicitement pour ce nouveau profil.

Le choix est fondé sur la disponibilité des données : le profil complet fournit seulement 35 080 lignes prêtes, avec zéro ligne prête en 2019–2021. Une observation manquante ou mise en quarantaine invalide toutes les longues fenêtres qui la traversent. On ne remplit pas ces trous et on ne raccourcit pas une fenêtre selon l'année.

Les seuils ci-dessous sont une **nouvelle règle de qualification décidée après inspection de la couverture**, puis figée avant lecture de toute performance ML. Ce n'est pas une pré-inscription antérieure à l'audit de disponibilité. Aucun label, rendement futur, F1, AUC ou résultat de backtest n'a guidé ce choix. Un GO signifie « données suffisamment couvertes selon cette règle », jamais « modèle rentable ».

## Features conservées

Liste ordonnée servant de contrat pour les consommateurs futurs :

```text
return_1,return_3,return_5,return_10,return_20,
sma20_distance,atr20_pct,realized_vol20,range20_position,
volume_ratio20,traded_value_mean20_eur,overnight_gap,
intraday_return,intraday_range
```

Les formules sont exactement celles du dictionnaire 7-A, reprises dans le manifeste figé. Les fenêtres demandent au maximum 21 séances consécutives valides. `return_60`, `sma50_distance`, `sma200_distance` et `position_52w` sont exclus **sur toutes les périodes**, sans prétendre qu'ils seraient inutiles économiquement.

Les prix restent bruts, les historiques splits non validés restent exclus, les dividendes ne sont pas réinvestis. `C × V` est un proxy de valeur échangée fournisseur. Identifiant, symbole, MIC, disponibilité et états de qualification ne sont pas des features prédictives. Aucune feature benchmark, secteur, fondamentale ou sentiment n'est ajoutée.

## Deux niveaux de qualification à ne pas confondre

### Ligne de décision : masque calculable séance par séance

`profile_complete` exige 14 valeurs finies ; NaN et infinis sont rejetés. `profile_complete_count` compte uniquement les titres complets de la **même séance de décision**. `profile_row_ready` exige une ligne complète et au moins 20 titres complets ce jour-là.

Une ligne reste exclue même si le semestre passe. Aucune imputation, aucun pont au-dessus d'une séance absente, aucune propagation de la dernière valeur ne sont permis. Les anciens `research_ready` et masques à 18 features sont supprimés de l'artefact dérivé pour éviter leur réutilisation accidentelle.

### Semestre : qualification rétrospective de la couverture

Un semestre est `GO_DATA_COVERAGE` uniquement si les quatre conditions sont satisfaites :

- au moins 80 % des lignes candidates sont `profile_row_ready` ;
- au moins 80 % des séances officielles XPAR disposent d'au moins 20 lignes complètes ;
- au moins 40 séances sont prêtes ;
- la période couvre le semestre civil complet.

Le dénominateur des séances inclut les journées officielles sans aucune ligne candidate. Pour un semestre partiel, les ratios décrivent seulement la plage observée, mais le semestre reste bloqué. Les bornes inclusives de 80 % et 40 séances sont testées.

`offline_qualified` est l'intersection de `profile_row_ready` et d'un semestre GO. **Ce champ n'est pas un signal PIT de trading** : connaître la couverture d'un semestre entier nécessite d'en connaître la fin. Il qualifie hors ligne les jeux de données ; il ne doit jamais devenir une règle live ni un veto de backtest utilisant le futur. Le futur backtest devra appliquer les masques de séance, conserver les périodes difficiles et publier une sensibilité sur les semestres bloqués, pas les effacer pour embellir la performance.

## Résultat du gel

170 046 lignes candidates conservées dans l'artefact pour audit ; 146 799 lignes complètes, 146 293 prêtes séance par séance, soit 86,03 % des candidates. Parmi celles-ci, 121 016 appartiennent aux 12 semestres complets qualifiés.

| Période | Lignes prêtes / candidates | Couverture lignes | Séances prêtes / officielles | Qualification |
|---|---:|---:|---:|---|
| 2018H1–H2 | 0 | — | 0 / 255 | Burn-in de l'univers 6-B, non utilisable |
| 2019H1 | 6 100 / 8 165 | 74,71 % | 77 / 125 | Bloqué |
| 2019H2 | 8 460 / 10 336 | 81,85 % | 117 / 130 | GO données |
| 2020H1 | 9 230 / 11 373 | 81,16 % | 105 / 126 | GO données |
| 2020H2 | 9 266 / 11 176 | 82,91 % | 110 / 131 | GO données |
| 2021H1 | 6 328 / 11 726 | 53,97 % | 71 / 126 | Bloqué |
| 2021H2 | 10 256 / 11 410 | 89,89 % | 128 / 132 | GO données |
| 2022H1 | 10 561 / 11 390 | 92,72 % | 127 / 127 | GO données |
| 2022H2 | 10 410 / 10 425 | 99,86 % | 130 / 130 | GO données |
| 2023H1 | 10 485 / 10 510 | 99,76 % | 127 / 127 | GO données |
| 2023H2 | 9 320 / 10 360 | 89,96 % | 128 / 128 | GO données |
| 2024H1 | 8 291 / 10 704 | 77,46 % | 105 / 126 | Bloqué : lignes < 80 % |
| 2024H2 | 10 600 / 10 770 | 98,42 % | 130 / 130 | GO données |
| 2025H1 | 8 932 / 10 993 | 81,25 % | 104 / 125 | GO données |
| 2025H2 | 12 243 / 12 301 | 99,53 % | 130 / 130 | GO données |
| 2026H1 | 11 253 / 12 228 | 92,03 % | 125 / 125 | GO données |
| 2026H2 au 2 octobre | 4 558 / 6 179 | 73,77 % | 51 / 68 | Bloqué, partiel |

Un semestre bloqué conserve ses lignes et ses raisons dans le manifeste. Le manque n'est pas nécessairement aléatoire : différences de composition et quarantaines peuvent influencer les conclusions. Les labels H5/H10/H20, leurs maturités, les folds, la purge et l'embargo devront encore être qualifiés ; ces comptes ne sont pas des tailles de jeux supervisés définitifs.

## Implémentation, artefacts et reproduction

- Configuration : `config/features_fr/fr_price_short_v1.yaml`.
- Construction : `modelFactory/fr_feature_profile_freeze.py`.
- Source gelée : `artifacts/fr/features/fr_price_v1/fr-feature-20180101-20261002-18ba6e1d8d31/panel.parquet`.
- Dérivé : `artifacts/fr/features/fr_price_short_v1/fr-price-short-v1-938c3b93b038/`.
- `panel.parquet` conserve les candidates, les 14 features et les masques explicites ;
- `frozen_profile.json` conserve configuration, dictionnaire, périodes, raisons, compteurs et empreintes.

```powershell
python -u -m modelFactory.fr_feature_profile_freeze --verify-rebuild
```

La source est vérifiée contre son SHA-256 inscrit dans la configuration et son rapport. Le code, le calendrier, la politique et le rapport source participent à l'identifiant de version. Deux reconstructions ont donné le même panel : `156ed1c1d4b0352274734d75577705b7600934a689ade9814fa47c34ee0093be`. Une divergence conserve l'ancien artefact et provoque une erreur. Pour changer features, gates ou source, créer une nouvelle version documentée ; ne pas modifier silencieusement ce gel.

Disponibilité conservée : `RESEARCH_J1_HYPOTHESIS_NOT_VERIFIED_PUBLICATION`. Le profil ne transforme pas les preuves de recherche en autorisation tradable. Aucune base, migration, tâche planifiée, IHM ou batch en cours n'a été modifié. Le profil n'est pas automatiquement branché sur un entraînement existant.

Validation : 152 tests ciblés passants (France, routage FR, contexte marché et panel CN), dont 10 nouveaux tests portant sur le contrat, les bornes, les séances absentes, la cross-section complète, les périodes partielles, l'invariance des masques de séance aux lignes futures, les doublons et l'altération de source. Cette suite n'est pas l'ensemble des tests de l'application.

## Prochaine étape autorisée

Le [Sprint 7-B — features relatives au benchmark](sprint_7b_features_relatives_benchmark.md) est désormais réalisé : profil dérivé à 26 features, 119 505 lignes communes prêtes et quatre semestres qualifiés selon les gates inchangés. Ce résultat ne change ni ce gel prix-only ni ses réserves ; aucun entraînement n'a été effectué.

Ajouter les features relatives au benchmark 6-C comme **nouveau profil dérivé**, avec disponibilité J+1, états KNOWN/UNKNOWN et segments explicites. Aucun rendement relatif ne doit franchir un segment UNKNOWN. Comparer prix seul et prix + benchmark sur leur intersection de lignes admissibles, en publiant aussi la perte de couverture. Ne pas redéfinir ces 14 features ou assouplir les gates pour favoriser le nouveau profil. Les secteurs restent bloqués faute de memberships historiques validés.
