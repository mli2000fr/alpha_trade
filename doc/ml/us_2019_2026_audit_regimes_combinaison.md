# US — Audit des régimes de la combinaison D10, 2019–2026 T1

**Mise à jour du 4 octobre 2026 après alimentation :** les indices macro
2026 sont désormais complets sur les dates testées. Voir le
[recalcul du régime T1](us_2026_regime_macro_actualise.md). Les réserves
de couverture ci-dessous décrivent le premier instantané, pas l'état actuel.

Date : 4 octobre 2026. Statut : **audit descriptif terminé ; aucun veto prédictif validé**.

## 1. Question et conclusion

Peut-on reconnaître, avec les informations disponibles à J, les périodes où
la combinaison favorise réellement D10 plutôt que D1 ? L'audit ne cherche
pas à optimiser des poids sur les mois perdants.

La combinaison enrichit D10 sur plusieurs années, mais elle reste une
sélection de titres à forte amplitude : elle conserve aussi beaucoup de D1.
Elle ne domine les deux blocs seuls en rendement moyen que sur **2 années
sur 7**. Sur 87 mois examinés, 27 présentent un rendement moyen H20 négatif.
Les indicateurs de marché, de volatilité et de concentration apportent du
contexte ; **aucune règle simple et stable d'anticipation n'est démontrée**.

Les pertes ne sont pas exclusivement liées à un marché déjà baissier à J.
Des groupes sectoriels concentrés et des retournements de titres auparavant
forts expliquent une partie des épisodes. Cela ne prouve pas qu'un filtre
sectoriel aurait été capable de les éviter avant leur apparition.

## 2. Contrat figé et périmètre

- Univers actuel statique : `config/univers/univers_filtred_tradable.txt`,
  1 798 symboles. Ce n'est pas un univers historique sans biais de survivance.
- Batch Oracle H20 : `model-factory-20261003082853-e98332`.
- Pool quotidien : intersection ATR20 TOP20 et Oracle prédit TOP20.
- M : percentile quotidien de `momentum_120` dans ce pool.
- V : moyenne des percentiles `rolling_volatility_60` et `atr20_pct`.
- MV : moyenne égale de M et V, sans sentiment, sans modification des poids.
- Sélection principale : TOP10 du pool, effectif arrondi au supérieur,
  ex æquo départagés par symbole. Les scores sont calculés avant la jointure
  des labels futurs.
- D1 et D10 réels : déciles natifs de rendement ajusté H20 dans l'univers
  quotidien complet, jamais redéfinis dans le sous-ensemble sélectionné.
- Rendement : clôture ajustée J vers clôture ajustée J+20 séances.

Pour 2019–2024, le rejeu choisit le dernier champion dont le début de test
est antérieur ou égal à J ; il ne réutilise pas un modèle de 2024 en 2019.
Le code Walk-Forward entraîne sur train/validation et purge les labels non
disponibles à la frontière. L'année 2025 réutilise les panels initiaux pour
assurer la comparaison. Le T1 2026 utilise le dernier champion causal du
batch, **sans nouvel entraînement jusqu'à fin 2025**.

Cette extension reste rétrospective : les features ont été explorées en
2025 et 2026 a déjà été consulté. Ce n'est pas une confirmation prospective
intacte. Aucun portefeuille, coût, stop ou ordre exécuté n'est simulé ici.

## 3. Résultats annuels de MV TOP10

Les effectifs sont des observations symbole–date, pas des trades
indépendants. Les pourcentages utilisent les labels valides.

| Période | Observations sélectionnées | D10 réel | D1 réel | Rendement H20 moyen brut |
|---|---:|---:|---:|---:|
| 2019 | 6 519 | 27,43 % | 24,03 % | +3,75 % |
| 2020 | 7 054 | 27,22 % | 20,61 % | +6,78 % |
| 2021 | 7 271 | 30,01 % | 29,68 % | +3,44 % |
| 2022 | 7 472 | 30,39 % | 21,28 % | +3,39 % |
| 2023 | 6 932 | 22,32 % | 24,80 % | +2,13 % |
| 2024 | 6 729 | 19,96 % | 23,23 % | +1,01 % |
| 2025 | 6 814 | 32,05 % | 20,08 % | +4,91 % |

Une observation de 2019 et trois de 2020 n'ont pas de label valide ; elles
restent dans les effectifs sélectionnés mais pas dans les proportions.

### Comparaison avec les blocs seuls

| Année | Pool entier | M TOP10 | V TOP10 | MV TOP10 |
|---|---:|---:|---:|---:|
| 2019 | +2,55 % | +2,62 % | +4,32 % | +3,75 % |
| 2020 | +6,22 % | +7,32 % | +10,93 % | +6,78 % |
| 2021 | +1,66 % | +3,03 % | +1,86 % | +3,44 % |
| 2022 | +1,08 % | +3,32 % | +3,61 % | +3,39 % |
| 2023 | +2,53 % | +2,28 % | +4,43 % | +2,13 % |
| 2024 | +1,48 % | +2,32 % | +0,93 % | +1,01 % |
| 2025 | +2,51 % | +4,10 % | +4,28 % | +4,91 % |

MV fait moins bien que le pool en 2023 et 2024. Le résultat favorable de
2025 ne suffit donc pas à conclure que la combinaison est généralement
supérieure. En 2021, D10 et D1 sont presque aussi fréquents ; en 2023–2024,
D1 dépasse D10 malgré un rendement moyen positif. Fréquence D10 et gain
moyen sont deux mesures différentes.

## 4. Janvier, février et mars 2026

| Mois du signal | Observations | D10 | D1 | MV H20 moyen | Pool H20 moyen |
|---|---:|---:|---:|---:|---:|
| Janvier | 563 | 29,13 % | 13,68 % | +6,60 % | −0,09 % |
| Février | 521 | 23,61 % | 10,75 % | −0,03 % | −2,42 % |
| Mars | 596 | 53,69 % | 9,23 % | +18,27 % | +7,56 % |
| T1 complet | 1 680 | 36,13 % | 11,19 % | +8,68 % | +1,90 % |

Ces résultats **ne confirment pas une dégradation uniforme sur janvier–mars**.
Février est presque neutre, mars très favorable dans cette sélection.
Les signaux de mars sont évalués jusqu'en avril : ce n'est pas la seule
variation de prix à l'intérieur du mois de mars. Ces rendements ne
contredisent pas automatiquement un backtest perdant : l'univers, les
entrées, les sorties, le sizing et les coûts ne sont pas les mêmes.

Le D10 de février reste à 23,61 % mais le rendement moyen est nul :
appartenir à un décile relatif ne garantit pas une hausse absolue suffisante.

## 5. Marché : pourquoi « baisse du marché → veto » est insuffisant

Contexte SPY reconstruit depuis ses cours ajustés : rendements passés
5/20/60 séances, distance SMA200, volatilité quotidienne sur 20 séances,
drawdown sur 252 séances. Les fenêtres se terminent à J ; une décision
utilisant la clôture J doit intervenir après sa disponibilité.

Le rendement SPY futur H20 est enregistré séparément, suffixe `expost`.
Il sert seulement à expliquer les résultats, jamais aux associations de
features supposées disponibles à J.

| Mois défavorable | MV H20 | D10 / D1 | SPY passé 20j à J* | Distance SMA200* | VIX* |
|---|---:|---:|---:|---:|---:|
| 2020-02 | −30,08 % | 11,34 / 21,64 % | ≈0,00 % | +8,10 % | 19,63 |
| 2025-02 | −13,74 % | 10,36 / 44,42 % | +1,17 % | +6,32 % | 17,05 |
| 2021-11 | −10,03 % | 14,85 / 44,05 % | +4,49 % | +9,68 % | 18,50 |
| 2024-07 | −6,35 % | 5,54 / 33,56 % | +2,15 % | +12,18 % | 14,47 |

*Moyennes des contextes quotidiens du mois, pas une information disponible
au premier jour du mois. Elles ne constituent pas un signal mensuel anticipé.

En mars et juin 2021, MV perd respectivement environ 3,15 % et 4,56 % alors
que le SPY futur H20 moyen gagne environ 5,17 % et 2,67 %. Le problème n'est
donc pas seulement un marché global qui baisse : la sélection peut subir
un retournement spécifique à ses titres ou secteurs.

### États fixes descriptifs, sans recherche du meilleur seuil

Moyennes à poids égal par date, contrairement aux tableaux annuels pondérés
par observation. Les groupes VIX excluent les dates sans VIX.

| Contexte à J | Dates | Rendement H20 moyen | D10 | D1 |
|---|---:|---:|---:|---:|
| SPY sous SMA200 | 383 | +7,56 % | 30,89 % | 19,33 % |
| SPY au-dessus SMA200 | 1 438 | +2,72 % | 26,41 % | 23,96 % |
| VIX ≥20 | 683 | +6,90 % | 29,97 % | 21,42 % |
| VIX <20 | 1 077 | +1,46 % | 25,20 % | 24,65 % |

Interdire systématiquement les périodes sous SMA200 ou à VIX élevé
supprimerait aussi des périodes favorables de rebond dans cet historique.
Inversement, ce tableau n'autorise pas à inventer après coup un filtre
« acheter seulement quand VIX élevé » : il faut une confirmation séparée.

## 6. Secteurs et concentration : explications partielles

Les secteurs proviennent des métadonnées **actuelles**, non d'une
classification historique PIT. Ils sont utilisables ici pour décrire les
groupes, pas pour certifier un filtre historique exécutable.

### Février 2025

- Technology : 34,26 % des observations, rendement moyen −18,99 %,
  D1 66,86 % ; contribution −6,50 points au rendement moyen total.
- Industrials : 25,50 %, rendement −12,57 % ; contribution −3,20 points.
- Ensemble : environ 59,76 % des observations et −9,71 points sur les
  −13,74 % de rendement moyen total.

La contribution est `part des observations × rendement du groupe`,
**pas une contribution à un PnL de portefeuille**. Elle indique où la perte
se concentre, pas pourquoi elle était prévisible.

### Autres épisodes

En juillet 2024, Industrials et Technology représentent respectivement
32,18 % et 24,57 % de la sélection ; leurs contributions sont −2,09 et
−2,02 points. En novembre 2021, les pertes se répartissent notamment entre
Energy, Technology, Healthcare et Real Estate : il n'existe pas un secteur
unique responsable de tous les échecs.

En février 2026, Technology représente 46,26 % des observations et sa
contribution est −0,62 point ; les autres groupes compensent une partie
de la perte. En mars, Technology représente 40,10 %, mais gagne en moyenne
26,90 % et contribue +10,79 points au total. **La présence de ce secteur
ne permet donc pas à elle seule de décider abstention ou achat.**

### Répétitions par symbole

Les cinq symboles les plus présents pèsent 18,92 % des observations en
février 2025, 18,23 % en février 2026 et 18,46 % en mars 2026. Exemples de
titres présents à chaque séance du mois (plusieurs ex æquo possibles) :
CLS/LMND/APP/GEO/ASAN en février 2025 ; WDC/TTMI/CIEN/STX/COHR en février
2026 ; ICHR/WDC/UCTT/COHR/LASR en mars 2026.

Cela réduit fortement l'indépendance des observations : vingt signaux
sur un même titre ne sont pas vingt paris indépendants. La corrélation
mensuelle concentration TOP5/rendement est −0,285 en 2024–2025 mais
−0,010 en 2019–2023 ; **elle ne fournit pas un indicateur stable**.

## 7. Associations de features : pistes, pas seuils utilisables

Corrélations de Spearman sur les moyennes mensuelles :

- VIX/rendement : +0,263 sur 2019–2023 et +0,297 sur 2024–2025.
- VIX3M/rendement : +0,255 puis +0,463 ; avec D10 : +0,213 puis +0,552.
- Momentum120/rendement : +0,052 puis −0,320.
- Variation du taux 10 ans sur 20 séances/rendement : −0,205 puis +0,155.

Volatilité et rebonds semblent associés aux résultats, mais les relations
momentum/taux/concentration sont instables. Les trois mois de 2026 sont
insuffisants pour calculer une corrélation de régime crédible ; aucune
n'est publiée. Les comparaisons sont exploratoires et multiples, sans
preuve de significativité robuste, causalité ou validation hors recherche.

## 8. Disponibilité et anomalies de qualité

| Famille | Couverture constatée | Réserve d'utilisation |
|---|---|---|
| SPY OHLC ajusté | Contexte local calculable | Disponible après clôture ; corrections historiques possibles |
| VIX, VXN, VIX3M, MOVE | 100 % des dates sélectionnées 2019–2025 ; **0 % au T1 2026** | Absence jamais remplacée par zéro ou assimilée à un régime calme |
| Taux 10 ans | 100 % des dates sélectionnées 2019–2026 T1 | Horodatage de publication/vintage non certifié |
| Secteurs | Métadonnées actuelles | Non PIT ; changements de classification non reconstruits |
| Bêta252 natif | Constant dans de nombreux panels anciens, souvent valeur par défaut 1 | Pas une mesure indépendante fiable d'exposition marché sur tout l'historique |

Les champs `created_at/updated_at` de la table macro prouvent un
enregistrement technique, pas automatiquement la disponibilité économique
à J ni l'absence de révisions. Une couverture complète ne vaut pas
certification PIT. Pour le bêta, aucune conclusion de stabilité historique
n'est retenue ; une étude de bêta nécessiterait une reconstruction dédiée
sur rendements passés alignés titre/SPY, avec minimum d'observations.

Le champ natif `market_return_20` est une moyenne glissante de rendements
quotidiens, pas un rendement cumulé sur 20 séances. L'audit reconstruit le
rendement cumulé SPY pour éviter de confondre les deux définitions.

## 9. Suite recommandée, sans implémentation automatique

Ne pas ajouter immédiatement un veto macro/secteur en production.

Une prochaine expérience pourrait tester **la faiblesse relative des
candidats par rapport à leur secteur**, avec quelques indicateurs fixés
avant calcul : force relative passée, dispersion, breadth et proportion
de candidats sous leur moyenne courte. Il faudrait reconstruire le bêta,
qualifier les métadonnées historiques et séparer développement et
confirmation chronologiquement avec purge H20.

Comparer systématiquement pool, M, V et MV ; contrôler le nombre de
candidats retenus, les D10 conservés, les D1 évités et le rendement restant.
Ne pas sélectionner la règle gagnante sur février puis annoncer qu'elle
anticipe février. Le but reste une abstention robuste, pas l'explication
parfaite de chaque perte après coup. Cette suite requiert un nouveau GO.

## 10. Reproduction et preuves

- [Protocole historique](us_2019_2025_combinaison_regimes.md).
- Script : `scripts/research/us_combination_history_regimes.py`.
- Audit : `scripts/research/us_combination_regime_review.py`.
- Historique : `artifacts/research/us_atr_oracle_sentiment/combination-history-2019-2025-20261004-v1/`.
- T1 : `artifacts/research/us_atr_oracle_sentiment/combination-history-2026q1-20261004-v1/`.
- Audit : `artifacts/research/us_atr_oracle_sentiment/combination-regime-review-20261004-v1/`.

Le dernier dossier contient `report.json`, `monthly_diagnostics.parquet`,
`daily_regimes.parquet` et `market_macro_context.parquet`. Les rapports
historiques détaillent aussi TOP20 et les comparateurs non retenus ici.
Les deux progressions historiques sont COMPLETED. Aucun modèle n'a été
modifié, aucun entraînement lancé, aucune écriture SQL réalisée et aucun
batch existant touché par cet audit.
