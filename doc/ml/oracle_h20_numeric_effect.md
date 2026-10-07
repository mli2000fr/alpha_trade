# Oracle H20 — mesure appariée de l'effet des corrections numériques

## Statut et objectif

GO utilisateur du 7 octobre 2026. Audit numérique complet, **24 entraînements
historiques et confirmation externe 2025–2026 TERMINÉS**.
Voir les [calculs corrigés](oracle_numeric_feature_corrections.md).

Question : à données, univers, cible, features et découpage identiques,
remplacer les anciens facteurs CAPM et six ratios améliore-t-il la détection
des extrêmes par l'Oracle H20 ? Ce n'est ni un nouveau classifieur D1/D10 ni un
backtest de portefeuille.

## Pourquoi deux réentraînements

Comparer directement le batch ancien, entraîné sur 1 798 titres, à un nouveau
batch sur 1 790 confondrait correction et exclusions. Deux bras sont donc
réentraînés sur **le même univers nettoyé de 1 790 titres** :

- `legacy` : les features archivées avant correction, après exclusions ;
- `corrected` : les features corrigées, sur les mêmes clés date/titre.

Les anciens modèles restent intacts. Le bras legacy est un témoin expérimental,
pas un retour de l'ancien calcul dans le code applicatif.

Entrées immuables :

```text
artifacts/research/us_concentrated_replay/
  oracle-h20-dataset-audit-20261007-v1/
  oracle-h20-dataset-audit-corrected-20261007-v2/
```

Ces caches contiennent 72 lots, 3 787 770 lignes par bras, de 2016 à 2024.
Avant tout entraînement, le script vérifie les empreintes de chaque Parquet,
l'égalité des clés et de **toutes les valeurs non concernées** par le correctif.
Seules les dix colonnes modifiées sont autorisées à différer : quatre facteurs
et six ratios. Les rangs cross-sectionnels sont reconstruits après assemblage
de l'ensemble des titres, jamais à l'intérieur d'un lot de 25 titres.

## Contrat figé

Référence : `model-factory-20261003082853-e98332`, Oracle H20 O0,
`static_bars`, profil EXPERT de 173 features, dont 44 rangs cross-sectionnels.
Les options sont relues depuis le batch ; ni famille ajoutée ni feature retirée.
Pas de changement de calibration : score binaire brut.

Le modèle utilisé par le chemin Oracle est LightGBM binaire. Les paramètres
LightGBM Per-Symbol affichés dans la commande Model Factory ne pilotent pas ce
trainer Oracle. Le protocole reprend ses paramètres effectifs :

| Paramètre | Valeur |
|---|---:|
| learning_rate | 0,05 |
| num_leaves | 31 |
| min_data_in_leaf | 50 |
| feature_fraction / bagging_fraction | 0,8 / 0,8 |
| bagging_freq | 1 |
| tours maximum / early stopping | 400 / 20 |
| seed | 42 |
| scale_pos_weight | négatifs/positifs du train, par fold |
| threads | 6, identiques sur les deux bras |

Aucune recherche d'hyperparamètres, aucune grille de seuils, un seul seed.
Le nombre de threads est borné pour ne pas monopoliser la machine ; cela ne
garantit pas l'identité bit à bit avec un ancien entraînement sur tous les cœurs.

Fenêtres : train minimum 504 dates, validation 126, test 126, pas 126,
maximum 15 splits. Sur les données disponibles, **12 folds de référence**, soit
**24 entraînements** pour les deux bras. Le script exige que les débuts des
folds correspondent exactement aux 12 modèles archivés ; sinon il s'arrête.

La purge de 20 dates est conservée. Pour chaque fold :

```text
train : label connu strictement avant le début de validation
validation : label connu strictement avant le début de test
test : prédiction uniquement, aucune influence sur l'early stopping
```

Les labels existants sont lus une fois, archivés et hachés. On conserve leur
définition sur l'univers original du batch, sans réécriture ni nouveau rang
cible sur le sous-ensemble. La mesure isole donc le calcul des features ; elle
n'est pas une expérience de changement de cible.

## Sélections et mesures

Pour chaque date OOF, avant filtrage par disponibilité future des labels :

1. `ORACLE_TOP20` : les `ceil(20 % × N)` meilleurs scores Oracle ;
2. `ATR_TOP20` : les `ceil(20 % × N)` meilleurs `atr20_pct` ;
3. `ORACLE_AND_ATR_TOP20` : l'intersection de ces deux listes, sans compléter
   jusqu'à 20 % et sans remplacer l'intersection par un score produit.

En cas d'égalité, ordre alphabétique du symbole. `N` est le nombre de titres
ayant leurs features à cette date, pas le nombre connu ultérieurement comme
évaluable. Un résultat futur invalide n'autorise pas à remplacer le candidat
par le suivant. On publie sélectionnés, évalués et couverture pour rendre cette
limite visible.

Mesures :

- précision de capture de `oracle_extreme10` : D1 ou D10 du label conservé ;
- proportions D1 et D10 séparées, sans prétendre les prédire ;
- moyenne du rendement futur absolu H20 ;
- moyenne du rendement signé, simple descriptif et **pas un PnL tradable** ;
- AUC par fold, sur tous les résultats test évaluables ;
- différences appariées de précision, globalement et par année ;
- intervalle descriptif de la différence, bootstrap par blocs de 20 séances,
  1 000 réplications, seed 42.

Les précisions globales sont des moyennes de précisions **quotidiennes** ; un
jour n'a pas plus de poids parce qu'il compte davantage de titres. L'intervalle
par blocs tient partiellement compte du chevauchement H20 ; ce n'est pas une
garantie de significativité après toutes les recherches historiques précédentes.
ATR étant inchangé, son résultat doit être identique entre les deux bras :
c'est aussi un contrôle de cohérence.

## Exécution et reprise

Script : `scripts/research/us_oracle_numeric_effect.py`.
Répertoire lancé le 7 octobre :

```text
artifacts/research/us_concentrated_replay/oracle-h20-numeric-effect-20261007-v1/
```

Il contient `protocol.json`, le snapshot `labels.parquet`, puis pour chaque bras
et fold : modèle, prédictions Parquet, métriques et métriques quotidiennes.
Chaque fold terminé dispose d'un `done.json` avec les empreintes de ses fichiers.
Une reprise vérifie le protocole et ces empreintes, puis saute les folds déjà
terminés. Ne jamais lancer deux processus sur le même répertoire.

Commande reproductible :

```powershell
python -u -m scripts.research.us_oracle_numeric_effect --before artifacts/research/us_concentrated_replay/oracle-h20-dataset-audit-20261007-v1 --after artifacts/research/us_concentrated_replay/oracle-h20-dataset-audit-corrected-20261007-v2 --output artifacts/research/us_concentrated_replay/oracle-h20-numeric-effect-20261007-v1 --threads 6
```

Suivi, sans attendre la fin dans un terminal bloqué :

```powershell
Get-Content F:\projets\artifacts\research\us_concentrated_replay\oracle-h20-numeric-effect-20261007-v1\progress.json
Get-Content F:\projets\artifacts\research\us_concentrated_replay\oracle-h20-numeric-effect-20261007-v1\stderr.log -Tail 20
Test-Path F:\projets\artifacts\research\us_concentrated_replay\oracle-h20-numeric-effect-20261007-v1\report.json
```

`completed/total` compte les entraînements terminés sur 24. Pendant le contrôle
initial et le chargement des caches, ce compteur peut rester à zéro. Les phases
`validate_cached_pair`, `load_features` et `train_fold` sont distinctes.
Le warning optionnel `triton not found` n'invalide pas le calcul CPU LightGBM.

Tests : 239 tests ciblés passent, dont 40 sur les deux nouveaux protocoles,
l'audit et les corrections,
dont un véritable petit entraînement LightGBM vérifiant que changer les labels
du test ne change ni ses scores ni son early stopping.

## Résultats historiques : effet faible, pas de gain net de capture démontré

Rapport `COMPLETED_PAIRED_HISTORICAL_OOF`, 1 512 dates de test du 5 juillet
2018 au 9 juillet 2024. 2018 et 2024 sont donc des années partielles.

| Sélection | Capture avant | Capture corrigée | Différence (points) | IC descriptif blocs 20, 95 % |
|---|---:|---:|---:|---:|
| Oracle TOP20 | 40,379 % | 40,435 % | +0,056 | [−0,054 ; +0,174] |
| ATR20 TOP20 | 38,601 % | 38,601 % | 0 | [0 ; 0] |
| Oracle ET ATR TOP20 | 42,186 % | 42,115 % | −0,071 | [−0,169 ; +0,023] |

L'amplitude réalisée moyenne H20 ne progresse pas non plus : Oracle seul
12,584 % → 12,556 % ; intersection 13,105 % → 13,070 %. Il s'agit de rendements
absolus futurs moyens des sélections, pas de gains de portefeuille.

Différences annuelles de capture en points :

| Année | Oracle TOP20 | Intersection Oracle ET ATR |
|---|---:|---:|
| 2018 partiel | +0,151 | +0,186 |
| 2019 | +0,149 | +0,089 |
| 2020 | +0,083 | −0,512 |
| 2021 | +0,062 | −0,195 |
| 2022 | +0,071 | +0,166 |
| 2023 | +0,004 | +0,029 |
| 2024 partiel | −0,215 | −0,177 |

L'AUC par fold augmente dans 9 folds sur 12 ; sa moyenne non pondérée passe
de 0,708763 à 0,711081 (+0,002318). La part moyenne de gain LightGBM des quatre
facteurs passe de 0,863 % à 8,971 %, et R² figure parmi les features importantes
du dernier modèle corrigé. Les nouveaux calculs ne sont donc pas simplement
ignorés par les arbres. Cette importance n'est pas une preuve causale d'alpha.

Cela ne suffit pas à améliorer la précision opérationnelle du TOP20.
Les deux intervalles de différence de
capture contiennent zéro. Conclusion limitée : **calculs mieux définis, pas
de gain net de capture historiquement démontré**. Ne pas annuler un correctif
mathématique parce qu'il ne crée pas d'alpha ; ne pas le présenter non plus
comme une amélioration de performance assurée.

## Confirmation externe figée terminée

Script séparé : `scripts/research/us_oracle_numeric_external.py`.

```text
artifacts/research/us_concentrated_replay/oracle-h20-numeric-external-20261007-v1/
```

Période figée : **1er janvier 2025 au 3 septembre 2026**. Cette borne de fin
correspond au dernier jour disposant de labels H20 valides dans le batch
référence lors du contrôle, et non à un choix sur la performance. Les labels
disponibles après le 7 octobre 2026 sont non évaluables.

Chaque bras utilise son modèle du dernier fold, `2024-01-08`. Important :
ce n'est pas un refit terminal sur tout 2024. Pour ce fold, les labels train
sont disponibles au plus tard le **7 juillet 2023**, ceux de validation au
plus tard le **5 janvier 2024**. L'expérience conserve ce vieillissement dans
les deux bras pour isoler les formules ; elle ne teste pas un nouveau calendrier
de réentraînement.

Les anciens calculs proviennent du commit local immuable
`36ca5e867a1cde7bef24ef1c13e0bb3ee90f0291` :

- source `features.py`, SHA256 `a6316ad4014b54c09ca0266c4bac8b3d22f16696c61b14505450bfdd4a030572` ;
- source `factor_features.py`, SHA256 `b1b078d2b254a820da9071164f89b5909fff0923a440f9e4695b3cce162871f0`.

Ces sources s'exécutent dans des espaces privés au processus de recherche.
L'import des facteurs y est relié à leur version archivée ; aucun monkeypatch
des modules applicatifs, aucun rollback ni fichier source de production changé.
Un commit contenant déjà les ratios corrigés est refusé comme témoin legacy.
Un smoke synthétique vérifie explicitement que l'ancien chemin reproduit R²=0
avec rendements benchmark NULL et les divisions par epsilon, tandis que le
chemin corrigé retrouve R²=1 et neutralise le ratio indéfini.

Par lot, les deux bras reçoivent des copies des **mêmes** barres, benchmark et
contextes screener chargés une seule fois. Même origine de warm-up qu'à
l'entraînement. Les clés et toutes les colonnes non traitées doivent être
identiques avant la sauvegarde ; sinon arrêt bloquant. Les rangs sont calculés
globalement après assemblage des 72 lots, puis les modèles figés prédisent sans
réentraînement. Les critères et les métriques sont inchangés.

### Résultats externes

Rapport `COMPLETED_FROZEN_EXTERNAL_CONFIRMATION`, **419 séances**, dont 250 en
2025 et 169 en 2026 jusqu'au 3 septembre inclus. Aucun modèle réentraîné sur
ces observations, aucun seuil choisi sur leurs résultats.

| Période | Oracle avant | Oracle corrigé | Intersection avant | Intersection corrigée |
|---|---:|---:|---:|---:|
| 2025 | 39,077 % | 39,034 % | 40,275 % | 40,390 % |
| 2026 au 3 septembre | 40,938 % | 40,811 % | 42,407 % | 42,505 % |
| Ensemble externe | 39,825 % | 39,748 % | 41,132 % | 41,240 % |

Différence globale de capture : Oracle **−0,077 point**, intervalle descriptif
95 % [−0,275 ; +0,096] ; intersection **+0,108 point**, intervalle
[−0,054 ; +0,234]. Les deux intervalles incluent zéro.

ATR seul reste strictement identique entre les bras : capture 37,285 % sur
l'ensemble externe. Son amplitude réalisée moyenne H20 est 12,141 % ;
Oracle seul 12,557 % → 12,470 % ; intersection 13,010 % → 12,997 %.
Il n'y a donc pas davantage de gain d'amplitude moyenne démontré.

Lecture par sous-période, sans ajustement des règles :

| Période | Séances | Oracle avant → corrigé | Intersection avant → corrigée |
|---|---:|---:|---:|
| 2025H1 | 122 | 38,438 % → 38,316 % | 39,459 % → 39,605 % |
| 2025H2 | 128 | 39,687 % → 39,717 % | 41,052 % → 41,138 % |
| 2026Q1 | 61 | 38,117 % → 37,682 % | 38,467 % → 38,542 % |
| 2026H1 | 123 | 40,152 % → 39,930 % | 41,274 % → 41,272 % |
| 2026H2 partiel | 46 | 43,086 % → 43,221 % | 45,506 % → 45,877 % |

Q1 est inclus dans H1 : ces deux lignes ne sont pas des blocs indépendants.
Sur 2026Q1, la correction ne démontre pas la résolution d'une dégradation
directionnelle : aucun modèle de direction n'est testé ici. Parmi
l'intersection corrigée, D1=17,340 % et D10=21,202 % des sélections évaluables ;
dans Oracle seul, D1=18,184 % et D10=19,498 %. Ce sont des proportions
rétrospectives, pas une règle disponible à J permettant d'identifier le côté.

Couverture des résultats sélectionnés : environ 99,64 % pour Oracle corrigé
et 99,66 % pour l'intersection sur l'ensemble externe ; 100 % en 2025 et Q1
2026. Sur juillet–3 septembre 2026, elle descend autour de 97,4–97,5 %.
Ces journées partielles sont conservées et annotées ; aucune substitution
des résultats manquants par des gagnants et aucun reclassement après constat
du résultat. Le pool observable peut compter moins de 1 790 lignes par jour.

Attention au contrat historique des labels : `oracle_decile=ceil(rank×10)`
mais le flag extrême utilise `rank>=0,90 OR rank<=0,10`. Exactement à 0,90,
une ligne peut donc être D9 et flaggée extrême. Le snapshot externe en contient
7 sur l'univers original. La capture utilise le flag appris par les modèles ;
les colonnes D1/D10 utilisent les déciles. Leurs sommes peuvent différer
très légèrement. Aucune redéfinition silencieuse de la cible dans cette mesure.

Commande reproductible (ne pas lancer une deuxième instance pendant le run) :

```powershell
python -u -m scripts.research.us_oracle_numeric_external --training-root artifacts/research/us_concentrated_replay/oracle-h20-numeric-effect-20261007-v1 --output artifacts/research/us_concentrated_replay/oracle-h20-numeric-external-20261007-v1 --legacy-commit 36ca5e867a1cde7bef24ef1c13e0bb3ee90f0291 --start 2025-01-01 --end 2026-09-03 --as-of 2026-10-07 --threads 6
```

Suivi :

```powershell
Get-Content F:\projets\artifacts\research\us_concentrated_replay\oracle-h20-numeric-external-20261007-v1\progress.json
Get-Content F:\projets\artifacts\research\us_concentrated_replay\oracle-h20-numeric-external-20261007-v1\stderr.log -Tail 20
Test-Path F:\projets\artifacts\research\us_concentrated_replay\oracle-h20-numeric-external-20261007-v1\report.json
```

Chaque lot est haché et reprenable. `READY_FEATURES_WAITING_MODELS` signifie
que les features sont prêtes mais que le modèle final apparié manque encore :
reprendre la même commande une fois les entraînements terminés. Ce cas n'est
pas un succès de la confirmation. Ne pas confondre avec `COMPLETED` et la
présence du rapport final.

## Limites de l'interprétation

Cette première phase est une validation **historique OOF 2018–2024** selon les
fenêtres effectivement reproduites, pas une confirmation externe 2025–2026.
Les neuf années du cache ne signifient pas neuf années de test : le début sert
à l'apprentissage et les dernières dates peuvent ne pas remplir un fold complet.
Les dates exactes sont archivées dans les métriques par fold.

Les deux phases sont terminées. Il ne faut pas alimenter le modèle ancien avec
les seules features corrigées pour fabriquer une comparaison avant/après.

2026 a déjà été examinée dans plusieurs expériences : il s'agira d'une
confirmation chronologique descriptive, **pas d'un holdout vierge**. Ne pas
optimiser les seuils sur ses pertes. Les données de prix et l'univers sont des
reconstructions actuelles, sans certification PIT exhaustive des cotations.

Tous les fichiers restent dans les artefacts de recherche. Aucun modèle
Per-Symbol/Ranking réentraîné, aucun SQL écrit, aucun modèle de serving remplacé,
aucun PnL ou batch métier existant modifié par cette expérience.

## Conclusion et décision

**GO qualité des calculs, pas de gain net de capture/amplitude démontré** dans
ce protocole. Conserver les corrections ; elles suppriment des résultats
mathématiquement indéfinis et rétablissent les facteurs benchmark. Elles ne
justifient ni une promesse de performance, ni une optimisation de seuils sur
2026, ni la relance automatique de toutes les pistes directionnelles rejetées.

Oracle × ATR reste descriptivement plus concentré en extrêmes que chaque
sélection seule dans cette expérience, avec un sous-ensemble plus petit.
C'est distinct de la question de l'effet des correctifs et ne démontre pas
la rentabilité LONG/SHORT. Aucun déploiement automatique des modèles recherche.

## Suite terminée : les dix premiers titres, pas les 10 %

L'[audit du TOP10 corrigé](oracle_h20_corrected_top10_audit.md) reprend les
prédictions archivées sans réentraînement ni SQL. Capture avant → corrigée :
61,17 → 59,85 % en OOF ; 55,74 → 55,26 % sur l'externe figée. Aucun gain stable
de ce classement concentré démontré ; conserver néanmoins les calculs justes.
Les dix premiers corrigés sont tous dans la double porte TOP20 % Oracle/ATR :
le filtre ATR ne change **aucun titre** de ces TOP10. L'avantage descriptif de
l'intersection sur tout le TOP20 % ne se transpose donc pas à ces dix rangs.
Rendements négatifs conservés, résultats manquants non remplacés, pas de PnL.
