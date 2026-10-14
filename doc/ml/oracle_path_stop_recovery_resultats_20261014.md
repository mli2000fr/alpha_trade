# Sorties SL5 du TOP5 Oracle parcours — résultats du diagnostic

## Conclusion — terminé, pas de nouveau portefeuille lancé

Le stop5 % est inférieur à un ATR20 pour la majorité des entrées. Certaines
positions stoppées récupèrent ensuite jusqu'à +20 %, mais beaucoup traversent
d'abord−10 %. **Cela justifie une question sur le placement du stop, pas une
preuve qu'élargir le stop ou utiliser l'ATR améliore le rendement.**

Voir le [protocole conservé tel que figé avant calcul](oracle_path_stop_recovery_20261014.md).
Source : les trois nouveaux modèles CatBoost annuels, référence LONG TOP5,
SL5/trailing15/TP20, entrées et sorties du ledger natif déjà calculé. Pas de
réentraînement ni de nouvel ordre ; aucune modification SQL, live ou batch.

## Distance du stop à la volatilité connue à J

| Période | Lots clos | ATR20/prix médian à J | SL5 en multiples d'ATR, médiane au fill | Entrées à moins d'un ATR |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 151 | 5,94 % | 0,84 ATR | 81,46 % |
| 2025 | 140 | 7,44 % | 0,67 ATR | 99,29 % |
| 2026 partiel | 146 | 8,27 % | 0,60 ATR | 99,32 % |

ATR20 = moyenne des20 true ranges ; ce n'est ni une probabilité ni une garantie
qu'un mouvement de cette taille va se produire. Les437 ATR ont été revérifiés
sur des préfixes de prix s'arrêtant à la date du signal J. L'unité est ajustée
au close J, avec la distance du SL5 calculée sur le fill réel J+1.

Le sous-groupe <1 ATR contient presque tout2025/2026 : on ne peut pas en tirer
un filtre séparant proprement gagnants/perdants. Aucun lot n'est >=2 ATR ; le
groupe [1,2[ ATR ne contient que18 stops2024, donc comparaison fragile.

## Après les sorties au stop initial : vingt séances depuis l'entrée

Ces taux portent sur les **lots stoppés qualifiés**, pas sur tout le TOP5 ni
sur tous les trades. HIGH cible recherché strictement après le jour du stop.
Un HIGH +20 % n'est pas un PnL réalisé ; coûts, capital et réinvestissement ne
sont pas simulés de nouveau.

| Période | Stops qualifiés | HIGH touche ensuite +20 % | CLOSE atteint ensuite +20 % | +20 % avant un éventuel SL10 depuis l'entrée, sans trailing |
| --- | ---: | ---: | ---: | ---: |
| 2024 | 101 | 15/101 = 14,85 % | 10/101 = 9,90 % | 13/101 = 12,87 % |
| 2025 | 82 | 22/82 = 26,83 % | 16/82 = 19,51 % | 13/82 = 15,85 % |
| 2026 partiel | 96 | 32/96 = 33,33 % | 28/96 = 29,17 % | 18/96 = 18,75 % |

Deux autres lots (un2024, un2025) sont stoppés à la dernière séance de la
fenêtre ou plus tard : aucun suivi post-stop dans ces20 séances. Ils restent
dans les archives et sont exclus explicitement de ce dénominateur.
Trails et TP sont distincts des stops initiaux :151/140/146 lots clos dont
102/83/96 SL initiaux, gaps compris ;18/19/14 trailing stops non inclus.

Parmi les récupérations à +20 %, le recul médian **depuis le fill**, avant la
cible, est−7,33/−9,45/−9,47 % (borne sans le LOW du jour cible). Délai médian
après le stop :8/9,5/9,5 séances. Le recul médian sur tout le suivi post-stop,
tous lots stoppés confondus, est−11,57/−15,03/−13,92 %.
Il serait donc trompeur de présenter les récupérations comme gratuites.

## Sensibilité soixante séances et dépendance

| Période | Stops qualifiés | HIGH +20 % après stop | +20 % avant SL10 depuis l'entrée, sans trailing |
| --- | ---: | ---: | ---: |
| 2024 | 102 | 46 = 45,10 % | 22 = 21,57 % |
| 2025 | 83 | 43 = 51,81 % | 20 = 24,10 % |
| 2026 partiel | 83 | 51 = 61,45 % | 17 = 20,48 % |

Treize lots2026 n'ont pas encore une fenêtre60 complète au9octobre : statut
`IMMATURE_WINDOW`, aucune conclusion sur leur récupération. Même lorsqu'un
lot a déjà touché une cible, on ne raccourcit pas sa fenêtre pour l'admettre.
Parmi les récupérations, recul médian avant cible−10,17/−10,43/−11,90 % :
une part importante ne survivrait donc pas à un SL10.

Sensibilité sans fenêtres chevauchantes par symbole :72/45/56 stops à20séances,
récupérationsHIGH16,67/33,33/30,36 %, avantSL10 13,89/17,78/17,86 %.
À60séances :59/38/43 lots ; récupérations45,76/60,53/53,49 %,
avantSL10 23,73/28,95/18,60 %. Les petites tailles, les symboles répétés et
les régimes communs empêchent de lire les lots comme des essais indépendants.

## Contrôles, artefacts et suite bornée

31 tests ciblés réussis : huit du nouveau diagnostic et23 du diagnostic de
qualité/résolution réutilisé. Les huit couvrent l'exclusion du jour du stop, cibleHIGH
vsCLOSE, gap d'open, collisionSL/TP conservatrice, bornes du LOW du jour cible,
absence de suivi, tranchesATR et sous-échantillonnage non dépendant du résultat.
Une seconde **vérification technique par le même assistant**, pas une revue
humaine indépendante, relit les prix sans appeler le résolveur du diagnostic :
547 fenêtres qualifiées vérifiées,437 lots clos et281 stops reconciliés,
15 réserves fenêtre/horizon. Toutes les empreintes originales sont inchangées.

Le seul cas où le LOW du jour cible aggrave la borne du recul est en2026,
avec ambiguïté intraday explicitement conservée, pas ordre inventé.
Les réserves héritées (univers actuel de survivants, prix historiques ajustés
actuels, dividendes incomplets, secteurs nonPIT et marge/coûts hypothétiques)
restent applicables.2024–2026 ont déjà été observées : pas nouveau holdout.

Artefacts : `artifacts/research/us_oracle_path_stop_recovery/20261014-v1/` :
`report.json`, `stopped-lots.parquet`, `closed-lot-atr.parquet`, `atr-strata.csv`,
`completion-audit.json` et `second-check.json`. Le protocole et ses empreintes
restent intacts ; ce compte rendu est séparé pour ne pas les modifier.

**Pas d'intégration.** Une suite éventuelle, après un nouveau GO, serait une
comparaison économique unique : référenceSL5/trailing15/TP20 contre une règle
ATR fixée à l'entrée, sans desserrer ensuite le stop, TP/trailing inchangés,
quantité recalculée au même budget de risque et levier plafonné2.
La majorité des stops ne récupère pas à20séances ; un gain économique net
reste entièrement à démontrer. Aucun coefficient ATR « optimal » choisi ici.
