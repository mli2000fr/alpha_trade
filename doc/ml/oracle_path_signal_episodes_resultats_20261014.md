# TOP5 Oracle parcours — une entrée par épisode : résultats

## Conclusion — NO_GO_STABLE_EPISODE_ENTRY_ADVANTAGE

**Six portefeuilles complets, zéro échec technique.** La règle empêche bien
toutes les réentrées dans un même épisode, mais réduit le rendement dans les
trois périodes. **Expérience clôturée sans intégration.** Pas de délai de
cooldown ou de variante réglé après observation des pertes.

[Protocole figé avant l'audit et le replay](oracle_path_signal_episodes_20261014.md).
Mêmes trois nouveaux modèles CatBoost annuels437ed1/102eca/bc35a7, TOP5
original, LONG explicite, SL5/TP20/trailing15, budget2 % equity par entrée,
capital initial4000USD réinitialisé par année/bras, plafond entrée levier2.
Frais natifs, financement6,5 % ACT/360 et contraintes natives conservés.
Pas d'entraînement, SQL, ordre courtier, batch ou réglageLIVE modifié.

## Audit préalable : répétitions assez fréquentes, pas toujours perdantes

| Année | Achats exécutés du témoin | Réentrées même épisode | PnL réalisé de ces réentrées USD | Gagnants parmi ces réentrées closes |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 153 | 27 (26 closes,1 ouverte) | −322,89 | 19,23 % |
| 2025 | 143 | 43 (toutes closes) | −47,77 | 27,91 % |
| 2026 partiel | 150 | 44 (43 closes,1 ouverte) | +507,83 | 32,56 % |

Gate technique d'au moins10 réentrées même épisode dans **chaque** période
passé27/43/44. Le passage au replay n'a pas dépendu du signe du PnL :2026
était déjà favorable aux réentrées. La règle n'a pas été modifiée pour sauver
cette année après lecture du diagnostic.

Un épisode est une présence continue au TOP5 en séancesNYSE observées, même
si le risque ou la qualitéJ refuse une entrée. Absence du TOP5 puis retour =>
nouvel épisode. Une date de scoring inconnue fait échouer la préparation,
pas de réarmement inventé. Les cinq rangs originaux sont conservés, aucune
substitution par le rang6.27/43/44 ne sont pas des trades indépendants.

Les épisodes originaux observés sont337/276/279. Ils ne sont pas tous tradés.
Premier épisode de l'année censuré à gauche ; état et capital réinitialisés
annuellement, pas preuve de continuitéLIVE multi-années.

## Résultat économique réel du portefeuille simulé

Capital final incluant les positions encore ouvertes MTM, sans vente terminale
ou àH20.2026 couvre2 janvier…30 septembre uniquement.

| Période | Rendement témoin | Une entrée/épisode | Écart | Capital final témoin USD | Capital final règle USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2024 | −16,74 % | −47,93 % | −31,19 points | 3330,30 | 2082,79 |
| 2025 | +33,12 % | +32,40 % | −0,72 point | 5324,92 | 5295,97 |
| 2026 partiel | +36,14 % | −12,23 % | −48,37 points | 5445,76 | 3510,98 |

| Période | DD témoin | DD règle | Lots clos témoin/règle | Gagnants clos témoin/règle |
| --- | ---: | ---: | ---: | ---: |
| 2024 | −32,83 % | −50,75 % | 151 /127 | 20,53 % /13,39 % |
| 2025 | −21,79 % | −28,15 % | 140 /120 | 29,29 % /28,33 % |
| 2026 partiel | −26,19 % | −23,99 % | 146 /97 | 26,71 % /20,62 % |

La règle réduit un peu le DD2026, mais transforme le gain annuel en perte ;
elle aggrave les DD2024/2025. Aucune dominance stable à promouvoir.

## Gains, pertes et exposition

PNL réalisés avec frais de trade natifs ; financement séparé. Ne pas confondre
somme des gains, capital final et rendement net du compte.

| Période | Bras | Gains réalisés USD | Pertes réalisées USD | Latent USD | Intérêts USD |
| --- | --- | ---: | ---: | ---: | ---: |
| 2024 | Témoin | 5807,60 | −6385,68 | −22,81 | 68,81 |
| 2024 | Règle | 1933,50 | −3847,85 | +18,95 | 21,81 |
| 2025 | Témoin | 7758,26 | −6480,69 | +118,24 | 70,89 |
| 2025 | Règle | 6232,20 | −5007,52 | +123,26 | 51,97 |
| 2026 | Témoin | 6399,92 | −5142,77 | +205,56 | 16,95 |
| 2026 | Règle | 3490,04 | −4028,20 | +57,16 | 8,02 |

Achats exécutés règle128/122/99, contre153/143/150. Zéro réentrée même
épisode dans le challenger, contre27/43/44 dans le témoin. Maximum par épisode1
dans chaque année. Journées-candidats bloquées alors que le titre n'était
pas détenu270/374/210 : ce ne sont pas270/374/210 achats qui auraient été
exécutés, car le risque pouvait également les refuser.

Levier brut moyen témoin→règle :1,03→0,72 /0,83→0,76 /0,48→0,43.
Moins d'exposition moyenne ne garantit donc pas un DD inférieur.

### Pourquoi soustraire les pertes des réentrées aurait donné une fausse conclusion

Le diagnostic2024 attribuait−322,89USD aux réentrées du même épisode. Les
supprimer ne permet pas de simplement ajouter322,89USD au résultat original.
Capital, quantités, positions disponibles, limites natives et réinvestissements
divergent chronologiquement. Les deux portefeuilles partagent seulement67/67/47
clés de lots clos (symbole,date d'entrée) selon l'année, sans garantie de mêmes
quantités/PNL.21/20/31 gagnants clos du témoin n'ont pas de lot clos de même
clé dans le challenger ; ce comptage n'attribue pas à lui seul tout l'écart de PnL.
Il confirme qu'on n'a pas seulement effacé un petit groupe de pertes inchangé.

## Contrôles et artefacts

**50 tests ciblés réussis**, dont neuf dédiés : épisodes invariants aux préfixes,
qualitéJ refusée qui ne réarme pas, changement de rang sans nouvel épisode,
date inconnue refusée, consommation seulement après fill, achat après nouveau
signal, rejet de gap qui laisse réessayer, callback de fill idempotent et témoin
exact sur fixtures. Avertissements pandas de concaténation, pas échecs de tests.

Revue technique du même assistant, pas un deuxième humain : construction des
épisodes relue indépendamment par symbole/séances, compteurs de consommations
reconstruits depuis les fills réels, causalité des décisions et absence de
réentrée vérifiées ; stops SL5/TP20/trailing15, risques natifs et réconciliation
cash/latent/intérêts/DD vérifiés. Les trois témoins reproduisent **exactement**
les trades et courbes des FIXED_REFERENCE archivés. Les PnL des lots du
diagnostic se réconcilient avec les lots clos natifs dans chaque année.

Dossier : `artifacts/research/us_oracle_path_signal_episodes/20261014-v1`.
`diagnostic.json`, `membership.parquet`, `reference-entry-diagnostic.parquet`,
`report.json`, `annual-summary.csv`, `completion-audit.json`, décisions/fills
par épisode et trades/courbes des six portefeuilles. Aucun run encore en cours.

Réserves : périodes déjà explorées, univers actuel de survivants et secteurs
nonPIT, prix historiques réajustés actuels, dividendes incomplets, macro sans
vintages de publication certifiés, hypothèses de marge/spreads/fills. Ce test
ne démontre ni rentabilitéLIVE du témoin ni capacité directionnelle nouvelle.
**Ne pas intégrer ce veto d'épisode et ne pas l'affiner sur ces mêmes pertes.**
