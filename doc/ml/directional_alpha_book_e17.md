# E17 — Bibliothèque d’alphas directionnels price-only à H60/H120

## 1. Décision

E17 est terminé avec le verdict **`NO_GO` pour une stratégie directionnelle
LONG/SHORT autonome**.

L’expérience détecte néanmoins une information de **classement relatif** à
H120. Le meilleur diagnostic est le momentum résiduel 120–10 jours : son IC et
le rendement du portefeuille long/short ont des intervalles de confiance
positifs. Ce résultat reste un **`DISCOVERY_CANDIDATE`**, car :

- le candidat primaire pré-enregistré était le composite de tendance à H60 ;
- le momentum résiduel H120 a été choisi après lecture des résultats ;
- sa jambe SHORT perd de l’argent en valeur absolue ;
- l’univers et les métadonnées d’instrument sont des snapshots actuels et
  introduisent un risque de survivorship bias ;
- les frais d’emprunt des positions short ne sont pas disponibles.

E17 ne modifie donc ni le serving, ni les prédictions, ni le backtest, ni le
live.

## 2. Question de recherche

L’objectif est de répondre à une question différente de celle de l’Oracle :

> Les prix quotidiens seuls permettent-ils de construire un alpha directionnel
> autonome, stable à H60 et confirmé à H120, sur l’ensemble de l’univers
> actions tradable ?

L’Oracle Extreme n’est utilisé à aucune étape :

```text
barres quotidiennes PIT jusqu’au close J
        │
        ├── signaux price-only
        │
        ├── classement cross-sectionnel quotidien
        │
        ├── TOP 20 %  → jambe LONG
        │
        └── BOTTOM 20 % → jambe SHORT
                    │
                    └── mesure open J+1 → open J+H+1
```

Le rapport machine enregistre explicitement `oracle_used=false`.

## 3. Population et contrat PIT

| Élément | Contrat E17 |
|---|---|
| Univers demandé | `universe-file:univers_filtred_equities.txt` |
| Symboles observés | 1 798 |
| Période | 2018-07-01 au 2025-12-31 |
| Séances | 1 886 |
| Lignes du panel | 3 333 794 |
| Lignes éligibles | 2 369 379, soit 71,07 % |
| Information du signal | close J au plus tard |
| Entrée | open ajusté J+1 |
| Sortie | open ajusté J+H+1 |
| Horizons | H60 primaire, H120 confirmation |
| Benchmark | SPY |
| Cible de classement | rendement futur excédentaire à SPY |
| Portefeuille | top/bottom 20 %, équipondéré, 50/50 dollar-neutral |
| Rebalance | toutes les 20 séances |
| Coûts | 6 bps aller-retour par jambe |

Les rendements utilisent les opens ajustés des splits. Les observations futures
servent uniquement à construire les cibles et ne participent pas aux signaux.

### 3.1 Éligibilité marché à la date J

Une ligne n’est tradable que si toutes les conditions suivantes sont vraies à
J :

- barre exacte, positive et non synthétique ;
- au moins 252 séances d’historique valides ;
- cours ajusté supérieur ou égal à 10 USD ;
- volume moyen 20 jours supérieur ou égal à 50 000 actions ;
- dollar-volume moyen 20 jours supérieur ou égal à 10 MUSD ;
- instrument classé comme action éligible.

Le TOP/BOTTOM est recalculé après ce filtre pour chaque date. Il n’existe ni
imputation d’une barre future, ni fallback Oracle.

### 3.2 Limites PIT

Les barres et les calculs de signal sont temporellement corrects. En revanche,
le fichier d’univers, le secteur et l’identité de l’instrument proviennent de
métadonnées actuelles non historisées. Les sociétés disparues et les anciennes
classifications peuvent donc manquer. Cette limite interdit une promotion en
production même si les gates statistiques avaient été franchis.

## 4. Alphas évalués

Tous les signaux sont déterministes et calculés avec les données disponibles au
close J.

### 4.1 Momentum 252–21

```text
close(J-21) / close(J-252) - 1
```

Il mesure la tendance longue en excluant le dernier mois, afin de limiter la
contamination par le retournement très court terme.

### 4.2 Momentum 120–10

```text
close(J-10) / close(J-120) - 1
```

Version plus réactive, avec exclusion des dix dernières séances.

### 4.3 Momentum relatif à l’industrie

```text
momentum_120_10 du titre
  - médiane momentum_120_10 de son secteur à J
```

Le signal n’est défini que si le secteur contient au moins cinq membres
éligibles à la date considérée.

### 4.4 Momentum résiduel 120–10

Une bêta glissante sur 126 séances est d’abord estimée contre le rendement de
SPY. Le rendement résiduel quotidien est :

```text
r_titre - beta_126 × r_SPY
```

Le signal est la somme des rendements résiduels sur la fenêtre 120–10. Il vise
donc la persistance propre au titre plutôt que la simple exposition au marché.

### 4.5 Qualité de tendance 120 jours

```text
rendement_120 / (volatilité_120 × sqrt(120))
```

Le signal favorise les tendances fortes relativement à leur bruit réalisé.

### 4.6 Retournement cinq jours

```text
-(close(J) / close(J-5) - 1)
```

Il sert de contrôle de retournement court terme et n’entre pas dans le
composite de tendance.

### 4.7 Composite primaire pré-enregistré

Chaque alpha est transformé en percentile cross-sectionnel quotidien, puis en
score centré dans `[-1, +1]`. Le composite est la moyenne équipondérée des cinq
signaux de tendance — tous sauf le retournement cinq jours — avec au moins
quatre composantes présentes.

Ce composite à H60 était le candidat primaire. H120 était sa confirmation ;
les signaux individuels étaient des diagnostics.

## 5. Méthode d’évaluation

### 5.1 IC quotidien

L’IC est la corrélation de Spearman, calculée chaque jour entre le score à J et
le rendement futur du titre excédentaire à SPY. Les jours non exploitables sont
écartés, puis la moyenne et son IC95 sont estimés par block bootstrap.

### 5.2 Portefeuille de cohortes

Toutes les 20 séances :

1. classer les titres éligibles ;
2. acheter les 20 % les mieux classés ;
3. vendre à découvert les 20 % les moins bien classés ;
4. équipondérer chaque jambe ;
5. allouer 50 % à chaque jambe ;
6. déduire 6 bps de chaque rendement de jambe ;
7. mesurer H60 ou H120 sans lifecycle tactique intermédiaire.

Les cohortes se chevauchent lorsque H > 20. Le block bootstrap tient compte de
cette dépendance temporelle avec une taille de bloc adaptée à l’horizon.

### 5.3 Gates figés du candidat primaire

Le composite H60 devait simultanément satisfaire :

- IC moyen positif et IC95 entièrement supérieur à zéro ;
- rendement long/short positif et IC95 entièrement supérieur à zéro ;
- rendement net positif des deux jambes séparément ;
- au moins 70 % de semestres positifs ;
- aucun semestre au-dessus de 35 % du PnL positif ;
- résultat positif depuis 2023 ;
- composite H120 avec IC et long/short positifs ;
- au moins 60 cohortes H60.

Un seul échec impose `NO_GO`.

## 6. Résultats du candidat primaire

| Métrique | Composite H60 | Composite H120 |
|---|---:|---:|
| Observations | 2 369 327 | 2 365 810 |
| IC quotidien moyen | +0,0138 | +0,0373 |
| IC95 de l’IC | [+0,0022 ; +0,0245] | [+0,0250 ; +0,0503] |
| Cohortes | 95 | 95 |
| Taille moyenne d’une jambe | 250,9 | 250,8 |
| Jambe LONG nette | +3,115 % | +7,056 % |
| Jambe SHORT nette | **−2,288 %** | **−4,546 %** |
| Portefeuille 50/50 net | +0,414 % | +1,255 % |
| IC95 portefeuille | **[−0,430 % ; +1,102 %]** | **[−0,266 % ; +2,449 %]** |
| Semestres positifs | **46,67 %** | 73,33 % |
| Depuis 2023 | +0,894 % | +2,619 % |

### 6.1 Gates

| Gate H60 primaire | Résultat |
|---|---|
| IC positif | PASS |
| IC95 de l’IC > 0 | PASS |
| long/short positif | PASS |
| IC95 long/short > 0 | **FAIL** |
| deux jambes positives | **FAIL** |
| au moins 70 % de semestres positifs | **FAIL** |
| concentration ≤ 35 % | PASS, 28,70 % |
| positif depuis 2023 | PASS |
| confirmation H120 positive | PASS |
| au moins 60 cohortes | PASS, 95 |

Le `NO_GO` ne vient donc pas d’une absence totale d’information. Le classement
possède un petit IC positif, mais il ne produit pas une stratégie symétrique,
statistiquement robuste et stable à H60.

## 7. Diagnostic principal : relatif n’est pas directionnel

Tous les signaux ont une jambe LONG positive et une jambe SHORT négative. La
notation SHORT représente le gain d’une vente à découvert : une valeur négative
signifie que les titres du bottom ont eux aussi monté en moyenne.

Le portefeuille long/short légèrement positif signifie donc :

```text
les titres du TOP montent davantage
que les titres du BOTTOM
```

et non :

```text
le TOP monte tandis que le BOTTOM baisse
```

E17 trouve une faible capacité de classement relatif. Il ne résout pas la
question D1/D10 ni l’identification autonome d’actions qui vont réellement
baisser.

## 8. Découverte exploratoire : momentum résiduel H120

Le momentum résiduel 120–10 à H120 est le meilleur diagnostic :

| Métrique | Résultat |
|---|---:|
| IC quotidien | +0,0474 |
| IC95 de l’IC | [+0,0365 ; +0,0590] |
| LONG net | +7,696 % |
| SHORT net | **−4,368 %** |
| Long/short 50/50 net | +1,664 % |
| IC95 portefeuille | [+0,552 % ; +2,527 %] |
| Semestres positifs | 80 % |
| Depuis 2023 | +2,691 % |

Il est négatif sur trois des quinze semestres : 2021H2, 2022H2 et 2023H1. Il
devient ensuite positif sur chacun des cinq semestres de 2023H2 à 2025H2.

Cette série est intéressante, mais ne constitue pas une validation : elle a été
retenue après comparaison de plusieurs signaux et horizons. La sélectionner
maintenant puis réutiliser 2018–2025 comme confirmation serait une fuite de
recherche.

## 9. Ce qui est autorisé ensuite

E17-B a été pré-enregistrée le 11 septembre 2026 avant sa première date
prospective. Le contrat retenu est :

1. **alpha relatif long-only** fondé uniquement sur le momentum résiduel H120 ;
2. **confirmation prospective** à partir du 14 septembre 2026 ;
3. signal, coûts, filtre, calendrier, preuve minimale et gates verrouillés par
   empreinte.

Voir [E17-B — confirmation prospective H120](directional_alpha_book_confirmation_e17b.md).

Une stratégie SHORT autonome nécessiterait une cible ou une information
spécifique aux baisses. Abaisser le percentile, optimiser les poids du composite
ou choisir H120 sur les mêmes données n’est pas une confirmation valide.

## 10. Reproductibilité et artefacts

Commande canonique :

```powershell
.\.venv\Scripts\python.exe -u -m modelFactory.directional_alpha_book --symbol-source universe-file:univers_filtred_equities.txt --start-date 2018-07-01 --end-date 2025-12-31 --bootstrap-samples 2000 --log-level INFO
```

Artefact canonique :

```text
artifacts/research/directional_alpha_book/directional-alpha-book-20260911194051/
├── report.json
├── alpha_panel.parquet
├── daily_ic.csv
└── portfolio_cohorts.csv
```

Implémentation : `modelFactory/directional_alpha_book.py`.

Tests : `tests/test_directional_alpha_book.py`.
