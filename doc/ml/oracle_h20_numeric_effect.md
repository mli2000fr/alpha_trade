# Oracle H20 — mesure appariée de l'effet des corrections numériques

## Statut et objectif

GO utilisateur du 7 octobre 2026. Audit numérique complet terminé ; expérience
de réentraînement historique **EN COURS**. Aucun gain prédictif annoncé avant
lecture du rapport. Voir les [calculs corrigés](oracle_numeric_feature_corrections.md).

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

Tests : 36 tests passent sur le nouveau protocole, l'audit et les corrections,
dont un véritable petit entraînement LightGBM vérifiant que changer les labels
du test ne change ni ses scores ni son early stopping.

## Limites et suite déjà identifiée

Cette première phase est une validation **historique OOF 2018–2024** selon les
fenêtres effectivement reproduites, pas une confirmation externe 2025–2026.
Les neuf années du cache ne signifient pas neuf années de test : le début sert
à l'apprentissage et les dernières dates peuvent ne pas remplir un fold complet.
Les dates exactes sont archivées dans les métriques par fold.

Après lecture du rapport : confirmer les deux derniers modèles figés sur
2025 et 2026 avec leurs calculs respectifs, un même pool observable et des
labels matures. Cette seconde phase nécessitera des features avant/après hors
des caches 2016–2024 ; elle n'est pas annoncée comme déjà exécutée. Ne pas
alimenter le modèle ancien avec les seules features corrigées pour fabriquer
une comparaison avant/après.

2026 a déjà été examinée dans plusieurs expériences : il s'agira d'une
confirmation chronologique descriptive, **pas d'un holdout vierge**. Ne pas
optimiser les seuils sur ses pertes. Les données de prix et l'univers sont des
reconstructions actuelles, sans certification PIT exhaustive des cotations.

Tous les fichiers restent dans les artefacts de recherche. Aucun modèle
Per-Symbol/Ranking réentraîné, aucun SQL écrit, aucun modèle de serving remplacé,
aucun PnL ou batch métier existant modifié par cette expérience.
