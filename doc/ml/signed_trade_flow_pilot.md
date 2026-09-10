# Flux signé trades/NBBO après Oracle TOP20

## Statut

**POC de faisabilité validé ; signal simple de clôture `NO_GO`.**

Cette expérience vérifie une famille d'information réellement nouvelle par
rapport aux barres quotidiennes : qui agresse le bid ou l'ask dans les dernières
minutes de la séance, et quel déséquilibre de profondeur est visible dans le
NBBO. Elle ne modifie ni les tables applicatives, ni les profils de features, ni
le serving et ni la cascade.

Code : `modelFactory/directional_data_research/signed_flow_pilot.py`.

Tests : `tests/test_signed_flow_pilot.py`.

Premier artefact complet :
`artifacts/research/eroya_directional/signed-flow-pilot-20260907232251-0e94ac/`.

Pré-gate terminé de 200 événements :
`artifacts/research/eroya_directional/signed-flow-pilot-20260907233012-0e94ac/`.

## Pourquoi cette piste est différente

Les expériences précédentes utilisaient surtout OHLCV quotidien, données
fondamentales, événements, sentiment, Options agrégées ou une quote de clôture
isolée. Elles ne permettaient pas de reconstruire honnêtement le côté
agresseur des transactions.

Eroya expose séparément :

- les transactions historiques avec prix, taille, place, conditions et
  timestamps nanoseconde ;
- les cotations NBBO historiques avec bid/ask, tailles, places, conditions et
  timestamps nanoseconde ;
- une pagination par `next_url`.

Référence fournisseur : [catalogue officiel Eroya](https://docs.eroya.co/llms.txt).

L'accès du compte a été vérifié par deux requêtes minimales sur SPY : trades et
quotes répondent HTTP 200. Le client réutilise les racines de confiance Windows
du projet ; aucun contournement TLS et aucune désactivation de validation des
certificats ne sont employés.

## Population et absence de fuite

Les événements sont tirés uniquement parmi les lignes du fichier
`_oracle_oof_gate.parquet` qui vérifient simultanément :

```text
directional_oracle_eligible = true
directional_oracle_oof_available = true
date comprise dans la fenêtre demandée
```

La sélection est déterministe, équilibrée approximativement par semestre et
ordonnée par le hash de `date|symbol`. Aucun rendement futur n'est utilisé pour
choisir les événements. Les labels corrigés ne sont joints qu'après la
collecte, pour l'évaluation.

Le batch Oracle de référence est
`model-factory-20260907170018-0e94ac`. Les labels H20 corrigés proviennent de
`model-factory-20260904192500-0802c8-h20-quality.parquet` et seules les lignes
`target_quality_valid=1` sont conservées par le préparateur commun.

## Fenêtre et calcul du côté signé

Le premier contrat observe les cinq dernières minutes de la séance régulière :

```text
15:55:00 America/New_York <= événement <= 16:00:00 America/New_York
```

Les bornes sont converties en UTC en tenant compte automatiquement de l'heure
d'été. Chaque trade est associé à la dernière quote NBBO connue, avec une
tolérance maximale de cinq secondes.

Classification du trade :

```text
prix trade > milieu NBBO  -> +1, achat agressif
prix trade < milieu NBBO  -> -1, vente agressive
prix trade = milieu NBBO  -> tick rule sur la dernière variation non nulle
pas de quote appariable   -> côté inconnu, jamais forcé
```

Les features événementielles sont :

| Feature | Définition | Lecture |
|---|---|---|
| `signed_volume_ratio` | somme(côté × taille) / somme(taille) | pression acheteuse ou vendeuse en actions |
| `signed_dollar_ratio` | somme(côté × prix × taille) / somme(prix × taille) | pression pondérée par le notionnel |
| `mean_quote_size_imbalance` | moyenne((bid_size-ask_size)/(bid_size+ask_size)) | asymétrie affichée du NBBO |
| `quote_match_rate` | trades associés à une quote valide / trades | qualité de reconstruction |
| `trade_vwap` | notionnel / volume | contrôle descriptif |
| `last_mid` | dernier milieu NBBO | contrôle descriptif |

Les trades au milieu ne sont pas arbitrairement déclarés acheteurs : la tick
rule n'intervient que dans ce cas. Les transactions sans quote récente restent
non signées.

## POC de faisabilité sur 12 événements

Le premier run couvre douze événements Oracle OOF de 2023–2024 :

- 12/12 événements produisent des features complètes ;
- 18 261 transactions et 21 267 cotations ont été collectées ;
- aucun endpoint n'a été tronqué ;
- 11/12 événements ont un taux d'appariement supérieur à 97,6 % ;
- NCLH atteint seulement 51,8 % et devra être traité comme cas de qualité faible.

Les ratios de volume signé varient effectivement d'un événement à l'autre,
d'environ -0,409 à +0,209 dans cet échantillon. Le pipeline ne produit donc pas
une constante technique. Ce résultat valide seulement l'accès, la pagination,
l'alignement temporel et le calcul des features ; douze événements ne disent
rien sur la valeur prédictive.

## Pré-gate directionnel de 200 événements

Le run élargi utilise 200 événements répartis sur les semestres disponibles de
mars 2022 à juin 2025. Il compare séparément les trois features aux tails H20 :

```text
LONG tail  : future_return >= +3 %
SHORT tail : future_return <= -3 %
milieu     : exclu de l'AUC D1/D10, conservé pour l'IC rendement
```

L'orientation d'une feature est fixée une seule fois sur l'ensemble du pilote,
puis appliquée sans inversion opportuniste dans chaque semestre. Les gates
préfixés avant tout modèle multivarié sont :

| Gate | Seuil |
|---|---:|
| tails valides | au moins 150 |
| distance AUC à 0,50 | au moins 0,03 |
| corrélation de Spearman avec le rendement | valeur absolue au moins 0,03 |
| semestres dont l'AUC orientée dépasse 0,50 | au moins 70 % |

Une seule famille devait passer tous les gates pour autoriser l'étape suivante.
Les seuils sont évalués conjointement : une bonne AUC agrégée instable dans le
temps ne suffit pas.

### Résultats

- 200 événements sélectionnés sans outcome futur ;
- 182 événements avec features complètes ;
- 159 tails directionnels valides ;
- 200/200 réponses trades et quotes terminées, sans troncature ;
- 18 événements vides, principalement titres OTC/étrangers ou identités
  historiques sans séquence NBBO exploitable ;
- taux d'appariement médian sur les événements complets : 99,28 % ;
- corrélation entre ratios de volume et de dollars signés : 0,999999, donc ces
  deux variantes ne constituent pas deux signaux indépendants sur cinq minutes.

| Feature | AUC brute | AUC orientée | Spearman rendement | Semestres AUC > 0,50 | Verdict |
|---|---:|---:|---:|---:|---|
| volume signé | 0,44 | 0,56 | -0,14 | 4/7 = 57 % | `NO_GO` |
| dollars signés | 0,44 | 0,56 | -0,14 | 4/7 = 57 % | `NO_GO` |
| déséquilibre tailles NBBO | 0,47 | 0,53 | -0,07 | 4/7 = 57 % | `NO_GO` |

Le signe agrégé du flux est contrariant : davantage de ventes agressives près
de la clôture est associé, en moyenne, au tail LONG futur. Mais cette relation
s'inverse nettement selon la période. Pour le volume signé, l'AUC orientée vaut
0,37 en 2022H1, 0,69 en 2022H2, 0,59 en 2023H1, 0,83 en 2023H2, 0,37 en
2024H1, 0,42 en 2024H2 et 0,60 en 2025H1. Une moyenne à 0,56 masque donc trois
semestres franchement inversés.

Les gates N, distance AUC et IC passent ; le gate de stabilité échoue pour les
trois features. `go_multivariate=false` : aucun CatBoost, seuil de trading ou
profil LONG/SHORT ne doit être entraîné à partir de cette version simple.

## Décisions possibles

- `NO_GO` : verdict obtenu pour le snapshot agrégé des cinq dernières minutes ;
  aucun modèle multivarié n'est autorisé sur cette formulation.
- `GO_MULTIVARIATE_RESEARCH` : au moins une feature passe ; collecter une
  population plus large, ajouter contrôles de qualité, spreads et variations
  multi-fenêtres, puis entraîner un modèle Walk-Forward.
- jamais de `GO_PRODUCTION` à partir de ce pilote : une confirmation postérieure
  indépendante, une calibration et un backtest net restent obligatoires.

## Artefacts et reproductibilité

Chaque run écrit exclusivement dans son dossier de recherche :

```text
trades.parquet
quotes.parquet
features.parquet
labeled_features.parquet   # seulement si --labels-path est fourni
report.json
```

La clé API n'est jamais sérialisée. Aucune donnée n'est écrite en base. Les
statuts de pagination et de troncature sont conservés événement par événement
dans `report.json`.

## Audit temporel 30 minutes

Le résultat simple n'a pas autorisé de modèle, mais un dernier diagnostic de
formulation a utilisé la même source nouvelle : fenêtre fixe de trente minutes
et calcul séparé de `J-30→J-15`, `J-15→J-5` et `J-5→clôture`. Cette
décomposition avait été enregistrée avant la nouvelle collecte.

Artefact :
`artifacts/research/eroya_directional/signed-flow-temporal-20260907234204-0e94ac/`.

Le run couvre les mêmes 200 événements sélectionnés sans outcome, dont 182
complets et 159 tails. Dix signaux préfixés ont été évalués avec correction de
Bonferroni.

| Signal | AUC orientée | Spearman | Stabilité | p brute | p Bonferroni | Verdict |
|---|---:|---:|---:|---:|---:|---|
| accélération volume signé | **0,567** | **-0,102** | 5/7 | 0,149 | 1,000 | `NO_GO` |
| volume signé 30→15 min | 0,538 | -0,067 | 5/7 | 0,405 | 1,000 | `NO_GO` |
| volume signé 5→0 min | 0,560 | -0,140 | 4/7 | — | — | `NO_GO` |
| meilleur déséquilibre NBBO | 0,533 | -0,058 | 5/7 | — | — | `NO_GO` |

L'accélération passe les gates descriptifs N, AUC, IC et stabilité, mais échoue
nettement le contrôle statistique de multiplicité. Les autres variables
échouent au moins un gate descriptif et aucune ne passe le test corrigé.
`go_next_stage=false`.

La famille **côté signé / déséquilibre de tailles** est donc fermée : pas de
nouveau découpage, pas de modèle multivarié, pas d'intégration. La prochaine
famille éventuelle doit être distincte. Les ticks déjà collectés peuvent servir
à un audit exploratoire séparé de trajectoire de prix, spread et liquidité,
avec verdict direction et amplitude séparés ; tout signal découvert exigera un
nouvel échantillon indépendant avant confirmation.
