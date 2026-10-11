# US — Validation chronologique du contexte D10/D1 Oracle × ATR

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

## Résumé — 4 octobre 2026

Suite autorisée exécutée : [audit PIT et lineage](us_d10_d1_ratio_audit_pit_lineage.md).
Routage Oracle sans champion futur observé ; disponibilité historique macro,
sentiment et lineage complet non certifiés. Pas de correction de données
attestée permettant un rejeu différent : résultats conservés sans promotion.

**Verdict : `NO_STABLE_INCREMENTAL_REGIME_SIGNAL`.** Les corrélations du
[document analysé](alpha_trade_d10_d1_ratio_analysis.md) sont reproduites, mais
leur transformation en prédiction de composition D1/D10 n'apporte pas un
avantage stable sur 2023–2025. Un résultat plus favorable apparaît sur les
82 journées évaluables de 2026 ; il ne suffit pas à promouvoir une règle.
2026 était déjà exploré auparavant et n'est pas une confirmation vierge.

Aucune écriture SQL, aucun modèle de serving modifié, aucun entraînement de
production ni batch existant touché. De petites régressions de recherche sont
ajustées en mémoire. Aucun intérêt économique net ni direction par symbole
n'est démontré par cette expérience.

## 1. Données et audit de couverture

Lecture seule de `alpha_trade.oracle_atr_market_regime_daily` : 1 695 journées,
2 janvier 2020–30 septembre 2026, un seul groupe batch/horizon/univers :

- Batch `model-factory-20261003082853-e98332`, H20.
- Univers hash `d57d85d35c18717cc44747cdd99b2b0c8e48319a902402f19c515c2e8fb0001f`.
- 1 676 ratios non nuls ; 19 journées avec D1=0, donc ratio non défini.
- 1 584 journées admissibles aux analyses chronologiques, dont 1 502 avant 2026.
- 86 journées avec labels inconnus ; six avec features décalées incomplètes ;
  19 sous le support minimal des queues. Ces motifs peuvent se chevaucher.

L'admissibilité exige : aucun label inconnu, nombre évalué positif, au moins
20 titres D1+D10, les quatre features disponibles et une date de maturité
future renseignée. Ce filtrage de résultats sert à **l'évaluation**, pas à une
sélection de titres en live. L'absence des dates non évaluables doit rester
visible ; leur résultat n'est pas assimilé à zéro.

En 2026 : seulement 82 journées admissibles entre le 2 janvier et le 11 août.
Ce n'est ni une couverture dense de janvier–août ni de toute l'année 2026.

## 2. Cible et disponibilité

Le ratio original est `d10_count / d1_count`. Il dépend des rendements futurs
H20. Sa date J est la date du signal, **pas sa date de connaissance**.

La cible principale plus bornée est :

```text
tail_share(J) = D10(J) / [D1(J) + D10(J)]
```

50 % signifie autant de D10 que de D1 dans les deux queues. Ce n'est pas la
probabilité qu'un titre arbitraire du pool soit D10 ; les D2–D9 sont exclus
du dénominateur. On conserve aussi D10/n, D1/n et (D1+D10)/n dans les sorties.
D1=0 peut être évalué avec tail_share=1 si le support est suffisant.

La maturité est le maximum des `oracle_available_date` de tous les labels du
batch/date/horizon, lu depuis `global_oracle_labels`. C'est une borne prudente
par rapport au sous-ensemble de titres de l'intersection. Toute journée
d'entraînement doit avoir une maturité **strictement antérieure** au début de
la fenêtre test. Aucune proportion future contemporaine n'est une feature.

## 3. Protocole figé avant résultats

Le fichier `protocol.json` a été écrit avant lecture des données et calcul des
résultats, avec hash du script. Cette expérience est motivée par des résultats
déjà observés ; elle ne constitue donc pas une validation entièrement neuve.

Variables disponibles à la séance précédente :

1. VIX ;
2. VIX/VIX3M ;
3. variation du VIX sur cinq séances ;
4. sentiment_score de marché.

Le décalage d'une ligne est effectué sur la série de séances **avant** exclusion
des journées non admissibles. Le champ régime est également décalé. Ce choix
évite de prétendre connaître le VIX de clôture à l'ouverture de J.

**Réserve PIT :** les timestamps de publication et les vintages de la table
macro ne sont pas certifiés. Un décalage d'une séance n'annule pas une éventuelle
révision/backfill. La causalité de l'Oracle lui-même et son lineage OOF doivent
aussi être qualifiés avant une promotion. « OOS » ci-dessous désigne le modèle
de contexte, pas une certification intégrale des signaux Oracle historiques.

Entraînement expansif depuis 2020, tests annuels 2023, 2024, 2025, 2026. Pas de
réentraînement pendant l'année test ; aucune recherche d'hyperparamètre :

- Référence : moyenne historique de tail_share sur l'entraînement maturé.
- Référence régime : moyenne historique par régime précédent, fallback à la
  moyenne générale si régime inédit.
- Ridge alpha=10 avec standardisation apprise exclusivement sur entraînement :
  VIX seul ; VIX+structure+variation ; ces trois variables+sentiment.
- Prédictions bornées entre 0 et 1. Pondération égale des journées, pas des
  titres. Aucun seuil de trading sélectionné.

Erreurs MAE et MSE, corrélation, bandes de calibration figées. Comparaisons
d'erreur MSE appariées : bootstrap circulaire par blocs de 20 observations,
1 000 tirages, seed fixe. Ce n'est pas une preuve de journées indépendantes.
Sur les dates clairsemées, les blocs sont des **observations conservées**, pas
nécessairement 20 séances consécutives ; les intervalles restent exploratoires.
Des dépendances plus longues et les comparaisons multiples restent possibles.

Critère fixé : la combinaison complète doit améliorer les deux références
avec borne supérieure de l'intervalle de différence MSE négative dans chacune
des années 2023–2025. Aucun choix de variante selon le meilleur résultat 2026.

## 4. Corrélations reproduites

| Variable | Pearson ratio | Spearman ratio |
|---|---:|---:|
| VIX | +0,3177 | +0,2331 |
| VIX3M | +0,3289 | +0,2300 |
| VIX9D | +0,2815 | +0,2239 |
| VXN | +0,2778 | +0,1856 |
| Sentiment | −0,1513 | −0,1605 |
| Taux 10 ans | −0,1644 | −0,0236 |
| MOVE | −0,0670 | +0,0203 |
| Variation taux 10 ans | −0,0173 | −0,0428 |

1 676 observations par ligne. Ces chiffres descriptifs contemporains concordent
avec le document initial. Ils ne mesurent pas l'apport OOS ni une causalité.

## 5. Résultats chronologiques

MAE exprimée en **points de proportion D10 parmi D1+D10**, pas en points de
rendement ou erreur de classification individuelle. Plus faible est meilleur.

| Année test | Entraînement | Test | Moyenne historique | Régime existant | VIX seul | VIX+structure+variation | Avec sentiment |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2023 | 729 | 250 | 11,13 | 11,43 | 12,13 | 12,25 | 11,94 |
| 2024 | 979 | 252 | 6,86 | 6,49 | 5,99 | 6,31 | 6,10 |
| 2025 | 1 231 | 250 | 13,12 | 13,28 | 13,30 | 13,54 | 14,11 |
| 2026, partiel | 1 481 | 82 | 9,65 | 9,70 | 8,79 | 8,69 | 8,26 |

Pour la combinaison complète, corrélation prédiction/réalisation :
2023 +0,132 ; 2024 +0,318 ; 2025 +0,021 ; 2026 partiel +0,748.

Les intervalles de différence MSE de la combinaison face aux deux références
incluent zéro dans chacune des années 2023–2025. Le critère de stabilité échoue.
En 2026 ils sont négatifs : résultat intéressant localement, mais pas une
raison d'écarter les années défavorables ni d'affirmer une rentabilité.

### Calibration : exemple de rupture en 2025

| Bande prédite, combinaison complète | Journées | D10 parmi les queues réalisé | D10 parmi tout le pool | D1 parmi tout le pool |
|---|---:|---:|---:|---:|
| 40–50 % | 145 | 56,86 % | 23,09 % | 17,39 % |
| 50–60 % | 92 | 48,24 % | 19,30 % | 20,13 % |
| 60–70 % | 13 | 71,36 % | 31,40 % | 12,42 % |

Les bandes 40–50 et 50–60 s'inversent en réalisation : elles ne fournissent
pas une règle monotone fiable. La bande supérieure a seulement 13 journées,
avec dépendance H20 ; ne pas en tirer un seuil opportuniste.

## 6. Interprétation et décision

Il existe une association descriptive volatilité/composition des queues.
Elle n'est pas transformée ici en indicateur de régime stable et profitable.
Le sentiment ne renforce pas uniformément VIX : il dégrade notamment 2025.

**Ne pas modifier `market_regime` ni ajouter de veto LONG à partir de ces
résultats.** Pas de nouveau seuil VIX optimisé sur les années perdantes.
Pas de recherche de modèle plus complexe automatiquement déclenchée.

L'expérience ne rejette pas toutes les informations macro possibles. Elle
rejette la promotion de cette combinaison simple comme règle stable avec
les données et la validation actuelles. Un intérêt collectif n'identifierait
d'ailleurs pas automatiquement D1/D10 au niveau d'un symbole.

Une suite éventuelle, uniquement après nouveau GO : qualification PIT/lineage,
validation d'une hypothèse distincte figée, puis comparaison économique du
portefeuille avec coûts/risque si le signal de contexte devient robuste. Le
test économique n'a pas été lancé ici, faute d'avantage stable à promouvoir.

## 7. Reproduction et artefacts

```powershell
python -u -m scripts.research.us_ratio_regime_validation --output artifacts/research/us_ratio_regime_validation/nouveau-dossier
```

Le dossier doit être neuf ; la lecture SQL est bornée à deux tables et sans
écriture. Le runner refuse de mélanger plusieurs batchs/horizons/univers.
Résultats : `artifacts/research/us_ratio_regime_validation/fixed-20261004-v1` :

- `protocol.json` : définition figée et limites ;
- `raw_snapshot.parquet`, `maturity_snapshot.parquet` : entrées figées ;
- `daily_features.parquet` : couverture, maturité, features causales ;
- `oos_predictions.parquet` : prédictions et cibles par date ;
- `report.json` : corrélations, erreurs annuelles, bootstrap, calibration, verdict
  et hashes des snapshots.

Quatre tests ciblés passent : décalage, purge par maturité, exclusion des
labels inconnus, conservation de D1=0, non-influence des données futures sur
les features passées et reproductibilité du bootstrap.
