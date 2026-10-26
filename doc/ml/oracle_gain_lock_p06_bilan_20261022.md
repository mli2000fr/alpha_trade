# P06 — protection d'une fraction du gain : bilan

22 octobre 2026. **TERMINÉ / NO_GO_P06_NOT_CONFIRMED / AUCUNE PROMOTION.**

La protection de50 % du gain après+10 % améliore le portefeuille2026, mais
dégrade2025. Elle augmente le taux gagnant sans avantage transversal de
rendement/DD. Le test ne justifie pas d'activer cette règle en production ni
de choisir rétrospectivement une sortie différente selon l'année.

[Protocole figé avant résultats](oracle_gain_lock_p06_20261022.md).
Dossier canonique : `artifacts/research/us_oracle_gain_lock_p06/20261022-v1`.
Inspiration : [K Consecutive Candles, fraction du gain](https://github.com/fmzquant/strategies/blob/7853bb2bf262c4567ac238d3552d97f0e50cb801/K%E7%BA%BF%E8%BF%9E%E7%BB%AD%E6%95%B0%E7%9B%AE%E7%89%9B%E7%86%8A%E5%88%A4%E6%96%AD%E7%AD%96%E7%95%A5-K-Consecutive-Candles-Bull-Bear-Strategy.md),
document483 de la revue FMZ. Adaptation distincte des entrées/code/performances
annoncés par cette source ; aucun code distant exécuté.

## Règle testée

Même confirmation Winner dans les deux bras : deux clôtures régulières5m au-dessus
du haut brut de la veille, précédées d'une clôture en dessous/au niveau ; entrée
au prochain open contigu. Pas une simple attente de cinq minutes ni deux bougies
vertes. Pas de P01 compression, pas de P02 vente partielle.

P06 garde toutes les actions et le SLinitial7 %. Après un sommet observé sur
bougie terminée d'au moins+10 %, le stop devient `E + 50 %*(P−E)`, borné par
le SLinitial ; E=prix exécuté et P=plus haut **déjà connu**. Il remplace TR15.
Seuil d'activation et stop arrondis au cent. Exemple100→120 : stop110 au lieu
de102avec TR15. Aucun stop relevé rétroactivement dans la même bougie ; gap
adverse exécuté au prix ouvert, pas au stop théorique garanti.

Vingt séances de détention entrée incluse, sortie à l'open21, sans réinitialiser
l'échéance lors de l'activation. Mêmes4 000USD annuels, plafond d'admission1x,
demi-cible, sizing/comptabilité/contraintes natifs et B4DD15. Même formule de
quantité, pas mêmes admissions effectives après divergence du cash/equity.

## Portefeuille : frais8bps parjambe inclus

| Année | Variante | Capital final USD | Rendement net | DDmax | Trades fermés | Gagnants | Capital utilisé moyen USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2025 | Winner TR15 | **4 803,41** | **+20,09 %** | **18,79 %** | 90 | 33,33 % | 2 262,00 |
| 2025 | P06 | 4 290,19 | +7,25 % | 19,30 % | 95 | **40,00 %** | 1 771,35 |
| 2026 au30/09 | Winner TR15 | 4 077,42 | +1,94 % | **18,60 %** | 61 | 36,07 % | 1 563,60 |
| 2026 au30/09 | P06 | **4 558,87** | **+13,97 %** | 18,93 % | 75 | **56,00 %** | 1 548,90 |

P06 comporte38activations en2025 et42en2026. Cinq positions restent ouvertes
au terme2025, valorisées au marché, contre sixWinner ; aucun ouvert au terme2026.
Le taux gagnant porte seulement sur les trades fermés. Comptes annuels remis
à4 000USD, pas une courbe continue de réinvestissement sur deux ans.

| Mesure P06 à8bps | 2025 | 2026 |
| --- | ---: | ---: |
| Gagnants / perdants | 38 / 57 | 42 / 33 |
| Gains cumulés USD | +3 270,35 | +2 666,16 |
| Pertes cumulées USD | −2 972,87 | −2 107,29 |
| Gain moyen USD | +86,06 | +63,48 |
| Perte moyenne USD | −52,16 | −63,86 |
| Séances moyennes gagnants | 9,42 | 6,31 |
| Séances moyennes perdants | 5,18 | 4,64 |

## Stress25bps parjambe

| Année | Rendement Winner | Rendement P06 | DDWinner | DDP06 |
| --- | ---: | ---: | ---: | ---: |
| 2025 | **+25,72 %** | **−1,28 %** | **19,85 %** | 20,71 % |
| 2026 | −0,24 % | **+9,33 %** | 19,90 % | **18,78 %** |

P06 ne devient pas robuste avec les coûts stressés. Les coûts changent aussi
les passages B4 et les réinvestissements : les résultats ne sont pas la simple
soustraction d'un tarif sur une liste de trades identique entre frictions.

## Contrôle unitaire : la protection coupe aussi les grandes continuations

Même entrée et notionnel initial, avant interactions de portefeuille :

| Année Oracle | Winner8bps | P068bps |
| --- | ---: | ---: |
| 2025 | +3,24 % | +1,54 % |
| 2026 | +3,22 % | +0,91 % |

Sans chevauchement parsymbole, blocage conservateur OracleJ+40 :

| Année Oracle | Occasions | Activations | Surplus P06−Winner | Intervalle95 % mensuel |
| --- | ---: | ---: | ---: | --- |
| 2025 | 81 | 35 | **−2,03points** | [−3,70 ; −0,48] |
| 2026 | 60 | 29 | **−2,72points** | [−8,21 ; +1,57] |

Aux frais stressés, surplus−2,02/−2,71points. Les minimums d'effectifs passent,
mais pas les critères de gain positif parannée/friction, de DDnon dégradé aux
frais normaux, ni de confirmation unitaire mensuelle. Aucun seuil retouché.

Un meilleur résultat portefeuille2026 n'est pas une contradiction : sorties plus
précoces, cash disponible et B4 changent les trades suivants. En2026, Winner/P06
ont deux/une activations B4,83/46séances d'allocation dégradée et61/75trades
fermés. En2025, une activation B4 chacun et70/66séances dégradées, mais le filtre
de sortie coupe des gains intermédiaires qui auraient pu continuer. Le taux
gagnant supérieur ne suffit pas à démontrer une meilleure sélection directionnelle.

## Vérifications

- **160tests ciblés passent**, dont19nouveaux P06.
- Quatre témoins reproduits **octet pour octet** : trades, courbes, décisions,
  financement et événements B4 de Winner P01v2.
- Huit portefeuilles vérifiés par reconstruction scalaire distincte des sorties,
  puis vectorielle du cash/frais/valorisations et des snapshots B4.
- **800 rendements unitaires** revérifiés séparément,200occasions×2bras×2frictions.
- **160 événements d'activation** vérifiés sur les quatre cas P06 (38/42 aux
  frais normaux et38/42enstress), pas160observations indépendantes.
- Première activation disponible après la bougie, pas de high futur, stop
  exact, horizon conservé, aucune activation manquante ou surnuméraire.
- Fabriques de rejeu substituées uniquement en mémoire et restaurées, même en
  cas d'échec. Sources/tables/modèles/batchs de production non modifiés.

Même assistant, pas revue humaine indépendante ; coûts5m/NBBO/queue/latence
de remplacement d'ordre non certifiés. B4DD15 ne garantit pas un DDplafonné
à15 %. Population héritée :200campagnes/69titres TOP10 CatBoost PATH H20 de
recherche, après réserves communes de couverture/maturité, sélection future et
survivants. Pas tout le TOP10 quotidien ni le LightGBM production, pas de2024
simulée, années déjà explorées. Unités groupées parannée Oracle, portefeuilles
parannée d'entrée avec les reports décembre→janvier déjà présents.

## Archives et conclusion

`annual-summary.csv`, `report.json`, `final-audit.json`, signaux, unités,
non-chevauchement, trades/courbes/risque et traces d'activation sont conservés
dans le dossier canonique. Les résultats P01/P02 restent inchangés.

**Ne pas activer P06 en production.** Ce rejet concerne la règle figée10 %/50 %
sur ce périmètre ; pas toutes les sorties possibles. Aucune nouvelle grille,
aucun autre test, fournisseur/LLM/SQL, entraînement, ordre ou changement de
configuration de production n'a été lancé.
