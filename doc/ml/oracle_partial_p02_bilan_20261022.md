# P02 — confirmation Winner + prise de bénéfice partielle : bilan

22 octobre 2026. **TERMINÉ / NO_GO_P02_NOT_CONFIRMED / AUCUNE PROMOTION.**

P02 fonctionne mieux en portefeuille en2026, mais beaucoup moins bien en2025.
Le taux gagnant augmente les deux années, sans amélioration transversale du
rendement ou du DD. Ne pas promouvoir cette règle fixe sur ces résultats.
Il s'agit du test de **50 % vendus à+10 %**, pas d'un rejet de toute prise partielle.

[Protocole figé avant PnL](oracle_partial_p02_20261022.md).
Canonique : `artifacts/research/us_oracle_partial_p02/20261022-v1`.
Inspiration : [AlphaTrend/KAMA et prise partielle](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/AlphaTrend%E4%B8%8EKAMA%E7%BB%93%E5%90%88%E7%9A%84%E8%87%AA%E9%80%82%E5%BA%94%E8%B6%8B%E5%8A%BF%E8%B7%9F%E8%B8%AA%E4%B8%8E%E9%A3%8E%E9%99%A9%E7%AE%A1%E7%90%86%E7%AD%96%E7%95%A5Adaptive-Trend-Following-Strategy-Combining-AlphaTrend-and-KAMA-with-Risk-Management.md),
commit de la revue FMZ. Seule l'idée de sortie partielle est adaptée ; aucun
code distant exécuté ni reprise des signaux ou performances annoncés.

## La confirmation d'entrée demandée est bien incluse

`winner_pyramiding.confirmation_bars: 2` dans `config.yaml` : deux clôtures
consécutives de bougies régulières5m **au-dessus du plus haut brut de la veille**,
après son franchissement frais. Entrée à l'open contigu suivant. Ce n'est pas
attendre exactement cinq minutes après l'ouverture, ni simplement deux bougies
vertes/deux clôtures plus hautes l'une que l'autre.

Cette entrée Winner est identique dans les deux bras ; **pas de filtre P01**.
P02 ajoute uniquement une vente unique de `floor(quantité_initiale/2)` à+10 %,
sans BE automatique ni desserrement du stop. Pour une seule action : aucune
vente partielle. Solde sous SL7 % / trailing15 %, échéance inchangée : vingt
séances depuis l'entrée incluse, vente à l'ouverture de la21e.
`enabled:false` dans la configuration de production est resté inchangé.

Même capital annuel4 000USD, plafond1x, demi-cible initiale, formule de sizing,
contraintes natives, frais et B4DD15. Deux comptes annuels indépendants, pas
une courbe continue réinvestie de2025jusqu'en2026. Frais hypothétiques parnotionnel,
pas de parité NBBO/queue/fills certifiée.

## Résultats : frais8bps parjambe inclus

| Année | Variante | Capital final USD | Rendement net | DDmax | Campagnes fermées | Gagnants | Capital utilisé moyen USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025 | Winner sans vente partielle | 4 803,41 | **+20,09 %** | **18,79 %** | 90 | 33,33 % | 2 262,00 |
| 2025 | Winner + P02 | 3 712,97 | **−7,18 %** | 21,03 % | 90 | 38,89 % | 1 530,91 |
| 2026 au30/09 | Winner sans vente partielle | 4 077,42 | +1,94 % | **18,60 %** | 61 | 36,07 % | 1 563,60 |
| 2026 au30/09 | Winner + P02 | 5 122,95 | **+28,07 %** | 20,05 % | 71 | **53,52 %** | 2 000,77 |

2025 : six positions encore ouvertes dans chaque bras à la borne annuelle,
valorisées au marché avec leur coût d'entrée restant ; pas de liquidation
inventée. Aucun ouvert en2026 à la borne. Les taux gagnants comptent seulement
les **campagnes complètement fermées**, pas chaque vente partielle comme un
nouveau gagnant indépendant.

P02 :34ventes partielles en2025 et33en2026. Respectivement124et104jambes de
vente, mais90et71campagnes fermées. Le solde peut perdre alors que le bilan
global de la position reste gagnant : la classification additionne ses jambes.

| Mesure P02, frais normaux | 2025 | 2026 |
| --- | ---: | ---: |
| Campagnes gagnantes / perdantes | 35 / 55 | 38 / 33 |
| Gains cumulés USD | +2 767,81 | +3 117,60 |
| Pertes cumulées USD | −3 079,41 | −1 994,65 |
| Gain moyen USD | +79,08 | +82,04 |
| Perte moyenne USD | −55,99 | −60,44 |
| Séances moyennes détenues, gagnantes | 17,09 | 13,71 |
| Séances moyennes détenues, perdantes | 4,95 | 5,21 |

## Stress25bps parjambe

| Année | Rendement Winner | Rendement P02 | DDWinner | DDP02 |
| --- | ---: | ---: | ---: | ---: |
| 2025 | +25,72 % | −7,54 % | 19,85 % | **18,46 %** |
| 2026 | −0,24 % | **+26,68 %** | 19,90 % | **19,34 %** |

Le résultat ne devient pas transversal en augmentant les frais. Les trajectoires
de risque/réinvestissement changent avec les frais : le Winner2025 à25bps n'est
pas la même liste de trades à laquelle on aurait seulement soustrait un tarif.

## Pourquoi les résultats portefeuille et unitaires peuvent diverger

La prise partielle coupe une partie des grands gagnants mais libère du cash.
Elle peut changer les prochaines admissions, la taille réellement approuvée et
les passages en mode dégradé de B4. Mêmes règles ne veut pas dire mêmes quantités
ou exactement mêmes trades après divergence de l'equity.

En2025, Winner/P02 : une/deux activations B4,70/105séances d'allocation dégradée.
En2026 : deux/une activations,83/46séances dégradées. Le capital moyen mobilisé
diminue en2025 mais augmente en2026 ;71campagnes P02 entrent et ferment en2026
contre61Winner. Ces différences sont effectivement rejouées, pas une multiplication
des anciens rendements par50 %. Elles décrivent les trajectoires observées, sans
prouver qu'on saurait choisir à l'avance l'année favorable à P02.

Contrôle par occasion, **mêmes entrées et notionnel initial** : le rendement
unitaire moyen baisse avec P02 les deux années, avant interactions de portefeuille.

| Année du signal Oracle | Winner8bps | P028bps |
| --- | ---: | ---: |
| 2025 | +3,24 % | +1,55 % |
| 2026 | +3,22 % | +2,40 % |

Contrôle sans chevauchement parsymbole, blocage conservateur OracleJ+40 :

| Année Oracle | Occasions | Touches partielles | Surplus P02−Winner | Intervalle95 % mensuel |
| --- | ---: | ---: | ---: | --- |
| 2025 | 81 | 35 | **−1,46point** | [−2,98 ; −0,23] |
| 2026 | 60 | 29 | **−0,93point** | [−3,97 ; +1,43] |

Aux frais stressés, surplus−1,45/−0,93point. Les effectifs minimums passent,
mais pas le surplus positif des deux années, pas le DDnon dégradé aux frais
normaux ni la confirmation unitaire mensuelle. Aucun seuil ajusté après lecture.

Les occasions unitaires sont groupées parannée Oracle, les portefeuilles parannée
d'entrée ; quelques signaux de décembre2025 entrent enjanvier2026, comme dans
le témoin archivé. Ce décalage est connu, pas une erreur de table.

## Vérification et limites

- **141 tests ciblés passent**, dont21nouveaux P02.
- Les **quatre témoins reproduisent exactement** les fichiers de trades,
  courbes, décisions, financement et événements B4 du Winner P01v2.
- Huit portefeuilles audités : quantités partielles et restantes, séquence
  stop/TP/horizon, gaps, frais, cash, valorisations et risque B4 reconstruits
  par arithmétique distincte du moteur natif.
- **800 rendements unitaires** revérifiés séparément sur200entrées.
- Coût/flux d'entrée réparti au prorata : pas de frais d'entrée doublés,
  pas de seconde entrée, peak/stop/échéance conservés. Le compteur de pertes
  consécutives ne reçoit le PnL total qu'à la fermeture complète.
- Collision intrabar : stop d'abord ; cash d'un TP intrabar inutilisable
  à l'open antérieur de cette même bougie. Gap favorable plafonné à la limite.

Même assistant, pas revue humaine indépendante. Couverture héritée :200campagnes,
69titres après13réserves communes P01 ; sélection future/survivants, pas tout le
TOP10 quotidien ni le champion LightGBM de production. Oracle CatBoost PATH H20
de recherche. Années déjà examinées, pas de holdout vierge. Pas de2024 simulée
sur cette archive. Les coûts/ordres5m restent hypothétiques ; pas de garantie
d'un DDplafonné à15 %, ni de parité live complète des ordres partiels.

Résultats : `annual-summary.csv`, `report.json`, `final-audit.json`, courbes,
`trades.parquet` (jambes) et `campaign-trades.parquet` (positions complètes).
Documentation et archives conservées. Aucun appel fournisseur/LLM, accès SQL,
entraînement, ordre, activation ou modification de modèle/batch/config production.

**Conclusion : pas d'activation de P02 en production et pas d'autre piste lancée.**
