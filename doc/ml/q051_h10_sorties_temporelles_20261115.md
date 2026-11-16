# Q051 vol20 + régime — sorties à l'échéance H10

Audit descriptif du 15 novembre 2026, sans nouvelle simulation ni modification
du pipeline. Référence annuelle causale 2021–1 octobre 2026, Q051 vol20/régime,
SL5 %, sans TP, trailing, confirmation ou renforcement ; vente temporelle à
l'ouverture de la 11e séance après dix séances de détention, entrée incluse.
Il ne s'agit pas du test c59bed avec anticipation autorisée.

## Périmètre et mesures

940 trades clôturés au total. **396 sorties `HORIZON_OPEN`**, soit **42,13 %**,
concernant 193 symboles distincts. Les autres sorties : 481 STOP, 63 STOP_GAP.
Les symboles réachetés à différentes dates comptent comme des trades distincts.
Chaque trade a le même poids dans les moyennes ; pas de pondération par capital.

Le rendement de sortie est le P&L net du trade rapporté au montant d'achat :
commissions d'entrée/sortie et dividendes tels que comptabilisés dans le replay.
Les frais simulés sont de 0,08 % par opération. Les pics sont des variations de
prix brutes depuis le prix d'achat, pas un rendement réalisé net.

Le pic principal est le maximum observé entre l'achat et la vente : plus-hauts
des dix séances entièrement détenues, avec les mêmes bougies qualifiées 5m ou
repli OHLC journalier que le replay, puis prix réel simulé de vente open11.
Le plus-haut de la journée de vente est exclu : il serait postérieur à la sortie.
Le pic strictement limité aux dix séances est également conservé séparément.

## Résultats

| Statistique par trade | Rendement net à la sortie | Pic depuis l'achat jusqu'à la vente |
| --- | ---: | ---: |
| Moyenne | +8,68 % | +13,83 % |
| Médiane | +7,14 % | +11,63 % |
| Minimum | −5,37 % | +0,90 % |
| 10e percentile | −0,85 % | +5,06 % |
| 25e percentile | +2,67 % | +7,58 % |
| 75e percentile | +13,74 % | +18,61 % |
| 90e percentile | +20,69 % | +25,02 % |
| Maximum | +42,11 % | +46,43 % |

Si l'on exclut même le prix de vente open11, le pic limité strictement aux
dix séances a une moyenne de **+13,69 %**, une médiane de **+11,55 %** et le
même maximum de +46,43 %.

| Tranche | Rendement net à la sortie | Pic avant/à la vente |
| --- | ---: | ---: |
| Négatif | 56 / 14,14 % | 0 / 0,00 % |
| 0 à moins de 5 % | 96 / 24,24 % | 38 / 9,60 % |
| 5 à moins de 10 % | 102 / 25,76 % | 119 / 30,05 % |
| 10 à moins de 15 % | 57 / 14,39 % | 96 / 24,24 % |
| 15 à moins de 20 % | 42 / 10,61 % | 61 / 15,40 % |
| 20 à moins de 30 % | 36 / 9,09 % | 66 / 16,67 % |
| Au moins 30 % | 7 / 1,77 % | 16 / 4,04 % |

**340 gagnants / 56 perdants, soit 85,86 % de gagnants dans ce sous-ensemble.**
Ce taux conditionnel ne remplace pas les 36,17 % de gagnants sur les 940 trades.
Ces trades ont évité le SL jusqu'à l'échéance ; les 544 sorties sur stop ne sont
pas incluses dans les moyennes ci-dessus. Un gap à open11 et les frais peuvent
laisser une sortie temporelle légèrement sous −5 %, d'où le minimum de −5,37 %.

Les 82 trades dont le pic atteint au moins 20 % représentent 20,71 % du groupe,
contre 43 trades (10,86 %) terminant à au moins +20 % net. Cela ne démontre pas
qu'un TP20 améliorerait le portefeuille : il faut aussi mesurer les parcours
des sorties STOP, la chronologie TP/SL et l'effet sur le capital libéré.
Les pics sont des observations rétrospectives, pas une règle de vente disponible
en temps réel ni des profits garantis au sommet.

## Ventilation par année de sortie

| Année | Trades H10 | Rendement net moyen | Rendement net médian | Pic moyen | Pic médian |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2021 | 55 | +10,20 % | +9,30 % | +15,21 % | +12,93 % |
| 2022 | 21 | +8,17 % | +6,11 % | +15,07 % | +11,91 % |
| 2023 | 68 | +8,76 % | +7,44 % | +13,22 % | +11,59 % |
| 2024 | 103 | +7,37 % | +5,80 % | +12,38 % | +10,07 % |
| 2025 | 85 | +6,94 % | +5,16 % | +12,54 % | +10,34 % |
| 2026 au 1 octobre | 64 | +11,89 % | +8,45 % | +16,91 % | +15,88 % |

## Contrôles et sources

396/396 trades ont dix séances officielles complètes entre entrée et vente,
deux exécutions à 09h30 New York et des rendements réconciliés avec le P&L.
Les prix d'entrée correspondent exactement aux ouvertures daily. Pour 37 sorties,
l'ouverture 5m effectivement exécutée diffère de l'ouverture daily d'un autre
flux ; ces prix sont réconciliés avec les archives 5m, sans forcer une égalité
incorrecte entre fournisseurs. La première tentative v1 s'est arrêtée sur ce
contrôle trop strict ; v2 le corrige sans modifier le backtest ou ses trades.

Sur 3 960 couples titre/séance de détention, 1 241 utilisent le repli daily
déjà déclaré dans le replay, les 2 719 autres les 5m qualifiées. Les limites de
qualité des prix historiques et d'univers contemporain de la référence restent
applicables. Fichiers de prix et traces scellés vérifiés ; isolation READ ONLY
terminée sans violation. Zéro téléchargement, appel broker ou écriture SQL.

Source : `artifacts/research/us_q051_global_rank_h10/20261115-v1/cases/Q051_REFERENCE/result/`.
Audit : `artifacts/research/us_q051_h10_time_exit_audit/20261115-v2/` avec
`report.json`, `time-exits-with-peaks.csv`, `distribution.csv`, `annual.csv`
et `intraday-source-receipt.json`. Script :
`scripts/research/us_q051_h10_time_exit_audit_20261115.py`.
