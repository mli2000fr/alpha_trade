# US 2025 — Audit univarié des features entre vrais D1 et D10

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

## Verdict

**281 features calculées et examinées ; aucune séparation directionnelle
forte et fiable n'est démontrée.** Deux familles méritent une confirmation
verrouillée : volatilité/ATR (faible mais plus régulière en 2025), et
momentum long relatif (meilleur en H2 mais fragile en H1). Le sentiment
agrégé reste proche du hasard. Pas de modèle entraîné, pas de backtest,
pas de modification du serving ou de table.

## Périmètre et population

- Année 2025 ; univers statique de 1 798 symboles
  `config/univers/univers_filtred_tradable.txt`.
- Sélection figée : ATR20 TOP20 × Oracle H20 TOP20 du batch
  `model-factory-20261003082853-e98332`, entraîné jusqu'à fin 2024.
- 67 084 couples symbole/séance dans la sélection, puis analyse des
  **12 177 vrais D1 et 14 877 vrais D10**, soit 27 054 couples.
- Les déciles sont ceux du rendement ajusté H20 dans tout l'univers
  quotidien, pas recalculés dans la sélection.
- **Aucun filtre sentiment >0,9 ajouté** pour cet audit : il s'agit de
  comparer les features dans l'intersection, pas dans les sous-groupes news.
- 234 colonnes canoniques demandées, plus rangs cross-sectionnels et
  extras Oracle disponibles : 281 colonnes, aucune colonne demandée absente.
  Ce nombre inclut des alias/transforms corrélés, pas 281 signaux indépendants.
- Toutes les familles supportées par `oracle.dataset.build_feature_matrix`
  demandées : expert, sentiment, screener/short score, VIX/VXN/VIX3M/MOVE,
  fondamentaux, facteurs, régime macro, composants scores, volume.
  Les familles secteur et stacking global ne sont pas calculées par ce
  constructeur ; cet audit n'est pas exhaustif de tous les modules applicatifs.

## Mesures et correction méthodologique

Pour chaque feature : moyenne/médiane D1 et D10, écarts dans l'unité native,
écart moyen standardisé par dispersion des deux groupes, AUC brute,
AUC sur rangs quotidiens, semestres, mois, couverture et valeurs constantes.

Une AUC de 0,50 correspond à un classement sans séparation. Une AUC de
0,54 ne signifie **pas** 54 % de trades gagnants ou 54 % de vrais D10.
L'AUC compare ici seulement D1 et D10, en excluant D2–D9 de l'évaluation.
Elle ne donne donc pas P(D10 | feature élevée) dans tous les candidats.

Les écarts absolus de features d'unités différentes ne sont pas comparables.
Un écart standardisé proche de 0,05 est petit ; 0,23 reste modeste et ne
suffit pas à prouver une stratégie. Les moyennes sensibles aux outliers
doivent être confrontées aux médianes et à l'AUC.

**Rapport initial corrigé :** les rangs de l'analyse initiale avaient été
calculés uniquement parmi les futurs extrêmes. Le rapport de revue les
recalcule sur les **67 084 candidats figés avant filtrage des labels**.
Il remplace le premier pour les conclusions de classement relatif.
Les moyennes, médianes et AUC brutes du premier rapport ne changent pas.

Le sens croissant/décroissant est fixé d'après l'AUC relative H1, puis
appliqué à H2 et aux mois. Choisir ensuite les meilleures features sur H2
reste exploratoire : H2 n'est plus une confirmation indépendante.

## Meilleures familles : chiffres relatifs

Tableau des AUC orientées vers D10 ; rang calculé par date dans tous les
candidats de l'intersection. Pour H1/H2, orientation définie sur H1.

| Feature | Sens associé à D10 | AUC H1 | AUC H2 | Mois >0,50 | Plus mauvais mois |
|---|---|---:|---:|---:|---:|
| `momentum_120_zscore` | Plus élevé | 0,5085 | 0,5758 | 9/12 | 0,3643 |
| `momentum_120` | Plus élevé relativement aux autres titres | 0,5154 | 0,5730 | 8/12 | 0,3697 |
| `sma200_distance` | Plus élevé | 0,5089 | 0,5631 | 8/12 | 0,3604 |
| `sma50_minus_sma200` | Plus faible | 0,5131 | 0,5613 | 8/12 | 0,3637 |
| `atr20_pct` | Plus élevé | 0,5252 | 0,5419 | 11/12 | 0,4680 |
| `atr_14_norm` | Plus élevé | 0,5208 | 0,5406 | 11/12 | 0,4480 |
| `rolling_volatility_60` | Plus élevé | 0,5329 | 0,5395 | 11/12 | 0,4883 |
| `beta_252` | Plus élevé | 0,5253 | 0,5402 | 6/12 | 0,4539 |

### Momentum long : intéressant en H2, pas robuste sur l'année

Le classement relatif `momentum_120` semble orienter un peu vers D10 en H2.
Mais son AUC **brute** passe de 0,4479 en H1 à 0,5581 en H2 : le sens d'une
règle absolue « momentum élevé ⇒ D10 » s'inverse entre semestres.
Février est fortement défavorable au sens retenu. Même réserve pour
distance SMA200 : brute H1 0,4530, H2 0,5522.

Ne pas convertir ces résultats en seuils absolus de momentum ou SMA200.
La corrélation Spearman `momentum_120`/`sma200_distance` est **0,9432**
dans les extrêmes : les combiner ne représente pas deux preuves indépendantes.
Les alias `_xs_rank` ont le même ordre par date et la même séparation relative.

### Volatilité/ATR : la piste la plus régulière, mais faible

Volatilité60 est positive 11 mois sur 12 et présente des AUC relatives
similaires H1/H2. Sa brute annuelle 0,5778 surestime ce que l'on obtient
pour départager des titres à une date donnée : relative annuelle 0,5356.
Brute H1 0,6332, brute H2 0,5396 : forte dépendance aux niveaux de régime.
ATR20 donne relative annuelle 0,5342 et pas de séparation forte.

Ces effets peuvent refléter différences de composition, secteur, taille,
bêta ou concentration par symbole. La stabilité n'est pas encore qualifiée
par un bootstrap groupé ou par plusieurs années.

## Écarts absolus : exemples lisibles

Valeurs moyennes sur l'année ; les pourcentages ci-dessous expriment les
unités des features, pas des rendements futurs.

| Feature | Moyenne D1 | Moyenne D10 | Différence D10−D1 | Écart standardisé |
|---|---:|---:|---:|---:|
| Momentum120 | +6,29 % | +9,44 % | +3,14 points | +0,062 |
| Distance SMA200 | −0,90 % | +0,50 % | +1,40 point | +0,044 |
| ATR20 / prix | 5,205 % | 5,462 % | +0,257 point | +0,123 |
| Volatilité60 des rendements journaliers | 3,737 % | 4,008 % | +0,271 point | +0,230 |
| Bêta252 | 1,315 | 1,477 | +0,162 | +0,167 |

Les médianes momentum120 sont **−5,11 % D1 / −3,40 % D10**, malgré les
moyennes positives. Cela illustre les distributions asymétriques et le
danger d'une conclusion fondée sur les seuls écarts moyens.

## Sentiment, fondamentaux et effets trompeurs

- `sentiment_net_mean_1d` : AUC brute 0,5054, moyenne 0,0232 D1 / 0,0320
  D10 ; médiane zéro dans les deux groupes. Pas de séparation convaincante.
- `sentiment_intensity` : AUC brute 0,5045 ; médiane zéro également.
- `fund_revenue_growth_yoy` : médiane 11,64 % D1 / 8,00 % D10, mais moyenne
  25,64 % /38,76 % (sens opposé). H1 relatif ≈0,50 ; le classement décroissant
  choisi très marginalement sur H1 donne 0,5532 H2. Outliers, qualité/PIT et
  valeurs manquantes à auditer avant toute interprétation économique.
- Les indicateurs de fondamentaux manquants apparaissent dans certains
  classements. Ils peuvent surtout capter la couverture fournisseur et la
  composition de l'univers. Ne pas les promouvoir comme alphas.
- 14 colonnes constantes, dont consensus/estimations et révisions forward,
  `company_idio_component` et `macro_regime_component`. On n'a donc pas
  testé leur information économique réelle ; on a constaté son absence.
- 28 colonnes constantes **à chaque date**, incluant les 14 précédentes,
  SPY/VIX et niveaux de régime. Une AUC brute élevée du `SPY_SMA_200_slope`
  inversé (≈0,5988) distingue surtout des dates/régimes, pas deux titres
  lors d'une même séance. Exclu de la shortlist de séparation cross-sectionnelle.

Couverture numérique 100 % ne signifie **pas** couverture de source 100 % :
le moteur natif remplit certaines absences et produit des flags de manque.
Les logs signalent notamment des symboles sans fondamentaux. Les scores
sentiment historiques de ce corpus ont été créés après 2025 : PIT non certifié.

## Ce que l'on peut conclure / prochaine confirmation

On dispose de pistes faibles, pas d'une règle D1/D10 exploitable démontrée.
Si une suite est autorisée : pré-enregistrer deux familles seulement,
volatilité/ATR et momentum120 relatif ; vérifier les sources/PIT, confirmer
sur d'autres années, contrôler secteur/taille/symbole et intervalles de
confiance groupés, puis calculer D10/D1/D2–D9 et rendement net d'une
sélection réellement disponible à J. Garder une période réellement intacte.
Ne pas entraîner immédiatement un gros modèle sur la shortlist choisie
dans 2025 et appeler son résultat une validation indépendante.

## Artefacts, reproduction et contrôle

- Panel complet : `artifacts/research/us_atr_oracle_sentiment/feature-separation-20261004-v1/features.parquet`.
- Rapport initial (rangs supersédés) : même dossier, `report.json`.
- **Rapport à utiliser** : `artifacts/research/us_atr_oracle_sentiment/feature-separation-review-20261004-v1/report.json`.
- Construction : `python -m scripts.research.us_feature_separation_audit`.
- Revue du panel sans SQL : `python -m scripts.research.us_feature_separation_review`.
- Les scripts refusent un dossier existant ; modifier le chemin de sortie
  pour une nouvelle reproduction sans effacer les preuves archivées.
- Aucun fit/SQL ; les observations H20 se chevauchent et sont corrélées.
  Pas de test de significativité ni correction pour 281 comparaisons.

Voir aussi [les expériences ATR/Oracle/news](us_2025_atr_oracle_news_sentiment.md).
