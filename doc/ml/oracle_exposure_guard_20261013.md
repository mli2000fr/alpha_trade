# Oracle TOP50 — protection progressive des nouvelles entrées LONG

13 octobre 2026. GO utilisateur « fait ton choix » : une expérience bornée,
sans nouveau modèle, sans SQL, sans broker et sans changement du live.
Ce protocole est écrit avant le nouveau replay, **après** examen des résultats
2024–2026. Ces années ne sont donc pas des tests vierges.

## Choix figé

Un seul bras nouveau : modèle TP20/SL10
`model-factory-20261012183840-6d6569`, TOP50, stratégie LONG.
Référence : baseline terminée et auditée de la comparaison des trois modèles.
Les prix, scores, coûts, sizing ATR, secteurs, régime macro/B4 et lifecycle
sont repris à l'identique. Capital initial : 4 000 USD par année.
TP20/SL10, pas de trailing, échéance à l'ouverture de la 21e séance de détention.
2026 : dernières décisions le 3 septembre, puis dénouement de la cohorte.

À la clôture J, calculer le rendement moyen équipondéré J−1 → J des **TOP50
Oracle sélectionnés à J−1**. Le panier est rééquilibré quotidiennement : il
s'agit d'un indicateur observé, pas d'un portefeuille tradé ni de labels H20.
Calculer son rendement composé sur cinq séances contiguës, et celui du SPY.
Faiblesse = panier en baisse **et** rendement inférieur à celui du SPY.

- Deux séances consécutives de faiblesse : plafonner le multiplicateur de
  risque des nouvelles entrées à 50 % de sa valeur native.
- Quatre séances de faiblesse : 25 %.
- Après amélioration (condition de faiblesse fausse), deux confirmations
  permettent 50 %, quatre permettent 100 %.
- Inconnu : 25 %, compteurs remis à zéro. Pas d'autorisation implicite.

Le multiplicateur peut être 25 %, 50 % ou 100 % ; il ne s'agit **pas** d'un
objectif d'exposition réellement atteint. Le sizing ATR et le minimum
notionnel existant de 155 USD peuvent transformer la réduction en absence
d'entrée. La garde ne force aucune liquidation, ne déplace aucun SL/TP,
ne remplace aucun candidat exclu et ne contourne pas le régime ou B4.

## Données et chronologie

Un panier exige au moins 90 % de ses 50 membres avec deux clôtures valides,
volumes positifs et barres non remplies. Les membres inconnus sont archivés.
Benchmark manquant ou fenêtre incomplète : inconnu ; ni forward-fill ni
remplacement de titres par ceux dont les rendements sont présents.
Le début 2024 est un warmup explicite à 25 % : pas de scores pré-2024 inventés.
L'indicateur et ses confirmations sont continus entre années ; chaque
portefeuille et son B4 redémarrent néanmoins comme dans la baseline annuelle.
Les décisions J ne s'exécutent qu'à J+1. Aucune valeur future n'entre dans
la garde ; les futurs prix restent exclusivement utilisés par le ledger
pour simuler les fills et dénouements.

## Comparaison et critères

Comparer par année : capital final, gain/perte nets, nombre et taux de trades
gagnants/perdants, DD maximum, profit factor et exposition moyenne.
Conserver les rejets de risque/sizing afin de ne pas confondre « meilleur
signal » avec « beaucoup moins de capital engagé ».

Ne pas promouvoir sur une amélioration isolée de février 2025. Examiner les
trois années, la perte éventuelle de rendement et les rebonds manqués.
Même un résultat favorable resterait exploratoire : confirmation prospective
ou historique réellement réservé nécessaire. Aucun balayage de seuils,
autre modèle, SHORT, entraînement de sortie ou TP/SL personnalisés lancé ici.

## Exécution et suivi

```powershell
python -u -m scripts.research.us_oracle_exposure_guard --output artifacts/research/us_oracle_exposure_guard/20261013-v1
Get-Content F:\projets\artifacts\research\us_oracle_exposure_guard\20261013-v1\progress.json
Get-Content F:\projets\artifacts\research\us_oracle_exposure_guard\20261013-v1\EXPOSURE_GUARD\2025-TOP50\progress.json
```

Un seul writer, sources et configuration figées. Protocole/empreintes avant
calcul ; indicateur archivé dans `exposure-policy.parquet`, audits quotidiens
dans `exposure-decisions.json`, résultats annuels et rapport final séparés.
Les réserves historiques de la baseline restent inchangées : univers actuel
survivant, secteurs actuels non PIT, prices/macro non certifiés comme versions
publiées à l'époque, corporate actions simulées et non fills broker réels.

Statut final : **TERMINÉ — NO-GO pour intégration de cette règle**.
Protocole et indicateur figés, **46 tests ciblés passent**
(`--no-cov` ; pas une certification de couverture globale). Replay lancé
dans `artifacts/research/us_oracle_exposure_guard/20261013-v1`.
L'indicateur couvre 671 séances, dont cinq de warmup inconnues ; niveaux
100 % / 50 % / 25 % sur 361 / 170 / 140 séances. Ce sont des niveaux de
risque théoriques, pas des expositions réellement atteintes.

## Résultats terminés et audités

| Année | Rendement baseline | Rendement garde | DD baseline | DD garde | Capital final garde |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024 | +16,44 % | +5,02 % | −8,46 % | −9,16 % | 4 200,81 USD |
| 2025 | −6,05 % | −3,00 % | −16,26 % | −18,25 % | 3 879,95 USD |
| 2026 partiel | +21,43 % | +7,38 % | −9,10 % | −7,92 % | 4 295,03 USD |

| Année | Gains nets garde | Pertes nettes garde | Positions | Gagnantes / perdantes | Taux gagnant |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024 | +1 808,65 USD | −1 607,84 USD | 147 | 68 / 79 | 46,26 % |
| 2025 | +1 378,01 USD | −1 498,06 USD | 120 | 47 / 73 | 39,17 % |
| 2026 partiel | +1 826,58 USD | −1 531,55 USD | 123 | 56 / 67 | 45,53 % |

La garde coûte 11,42 points de rendement en 2024 et 14,05 points en 2026.
En 2025, elle améliore le net annuel de 122,00 USD, mais aggrave le DD de
1,99 point. La cohorte des signaux de février perd **482,42 USD** au lieu de
424,27 USD ; neuf entrées issues de signaux de mars ajoutent −95,64 USD,
alors que la baseline n'a pas de nouvelle décision d'entrée ce mois-là.
Elle n'a donc pas protégé correctement l'épisode ciblé.

Ce n'est pas une multiplication a posteriori de chaque trade de référence :
les tailles, positions occupées et disponibilités modifient les décisions
suivantes et la trajectoire du contrôleur B4. Sa première réduction intervient
le **27 mars 2025** avec la garde contre le **3 mars** dans la référence.
Les contrôles ne sont pas contournés : ils voient un portefeuille différent.
L'exposition brute moyenne effectivement atteinte est 25,45 % avec la garde
contre 21,99 % sans en 2025, malgré les plafonds d'entrée supplémentaires.
En 2024 et 2026, elle est bien inférieure (33,15 % / 31,64 % contre
49,15 % / 38,34 %). Moyennes sur chaque replay, y compris sa queue de sortie.

`completion-audit.json` porte
`THREE_YEARS_AND_CAUSAL_TAPE_VERIFIED` : indicateur reproduit, préfixe identique
après retrait de toutes les données postérieures au 30 juin 2025, candidats
TOP50 vérifiés, décisions avant fills, LONG, TP20/SL10, échéances, portefeuilles
clos, cash réconcilié (erreur maximale < 10⁻⁶ USD), inputs et code source
inchangés. Le fichier contient aussi l'attribution par mois du signal,
l'exposition par mois calendaire et les dates de réduction B4.

Conclusion : **ne pas intégrer cette règle au live**, ne pas la réajuster sur
février 2025, ne pas annoncer une amélioration du régime. Le gain de taux
gagnant en 2024 ne compense pas la forte baisse de rendement. Cette expérience
ne démontre pas non plus qu'un modèle contextuel serait inutile : c'est une
hypothèse distincte, qui demanderait un nouveau GO et une validation purgée.
Les trois challengers ML précédemment suspendus n'ont pas été lancés.

Audit reproductible, sans rejouer ni entraîner :

```powershell
python -u -m scripts.research.us_oracle_exposure_guard_audit --root artifacts/research/us_oracle_exposure_guard/20261013-v1
```
