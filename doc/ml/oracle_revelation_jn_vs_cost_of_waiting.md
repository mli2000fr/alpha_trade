# Oracle TOP20 H20 — révélation D1/D10 à J+N et coût économique de l'attente

Date : 17 septembre 2026. Statut : **diagnostic descriptif terminé, aucune politique promue**.

## Question

Parmi les candidats Oracle TOP20 identifiés au close J, le signe du chemin déjà observé permet-il progressivement de reconnaître les futurs D1 et D10 ? À quel N ? Et, si l'on attend ce N avant d'entrer, quel rendement reste réellement jusqu'au terme H20 original ? Cette dernière question est indispensable : reconnaître correctement un D10 lorsque son mouvement est presque terminé ne crée pas une entrée rentable.

Ce calcul complète [E9](oracle_post_signal_confirmation.md), qui avait testé J+1/J+2/J+3/J+5, et [E20-B](oracle_opening_price_confirmation_e20b.md), qui avait testé les premières minutes de J+1. Il ne réentraîne aucun modèle.

## Cohorte et horloge

- Source : [événements Oracle OOF d'E20-B](../../artifacts/research/oracle_opening_price_confirmation/e20b-opening-price-only-20260914051444/oracle_price_only_events.parquet), batch `model-factory-20260909051302-323684` ; 582 306 événements TOP20, 1 472 symboles, juillet 2018–juillet 2025 ; décile H20 et qualité de cible valides sur toutes les lignes retenues.
- Probabilités de base dans ce TOP20 : D10 **21,95 %**, D1 **22,16 %** ; parmi les événements qui finiront effectivement D1 ou D10, part D10 **49,77 %**.
- Prix : 2 596 434 barres de `stock_bars_daily`, ajustées comme dans E9 avec `adj_close / close` ; lecture seule.
- À chaque N de 1 à 19 séances : observer `close(J+N) / close(J) - 1`. Si ce rendement est ≥ +0,50 %, signal LONG ; s'il est ≤ −0,50 %, signal SHORT ; sinon abstention. Le seuil est **figé pour la description**, non optimisé sur les résultats de cette courbe.
- Entrée immédiate contrefactuelle : open J+1. Entrée retardée réalisable après observation : open J+N+1. Sortie **identique** dans les deux cas : open J+21, après vingt séances de détention théorique de la branche immédiate. Frais simples : 1 bp de commission + 2 bps de slippage par côté, soit **6 bps aller-retour**. Pas de frais d'emprunt SHORT ; le SHORT est donc optimiste.
- Les chiffres « moyenne par date » sont des rendements d'événements théoriques équipondérés par date de signal, avec zéro pour abstention. **Ce n'est pas un PnL portefeuille** : les trades se chevauchent, sans taille de position, contrainte de capacité ni taxe/borrow.

Code de reproduction : [oracle_reveal_vs_wait_cost.py](../../scripts/research/oracle_reveal_vs_wait_cost.py). Résultat exhaustif J+1…J+19, périodes complète/développement/contrôle : [curve.csv](../../artifacts/research/oracle_reveal_vs_wait_cost/e20b-h20-v3/curve.csv) ; [manifeste](../../artifacts/research/oracle_reveal_vs_wait_cost/e20b-h20-v3/report.json).

## Quand connaît-on mieux le décile final ?

Les pourcentages ci-dessous sont conditionnels à une **hausse déjà observée d'au moins 0,50 %**. « Parmi les vrais tails » est une statistique d'évaluation : on ne sait pas en temps réel quels titres finiront D1 ou D10. « Parmi tout le TOP20 » est la probabilité directement pertinente pour un candidat quelconque satisfaisant cette règle.

| Checkpoint | P(D10 \| hausse, **vrai D1 ou D10**) | P(D10 \| hausse, **tout TOP20**) | D10 : LONG net immédiat sur ces mêmes titres | D10 : LONG net après attente | Gain D10 non capturé |
| --- | ---: | ---: | ---: | ---: | ---: |
| J+1 | 61,1 % | 27,3 % | +20,0 % | +16,7 % | 3,3 points |
| J+4 | 71,7 % | 31,8 % | +20,7 % | +12,7 % | 8,0 points |
| J+5 | 74,2 % | 32,9 % | +20,8 % | +11,7 % | 9,0 points |
| J+8 | 80,9 % | 35,9 % | +20,8 % | +9,2 % | 11,6 points |
| J+10 | 84,7 % | 37,5 % | +20,8 % | +7,6 % | 13,2 points |
| J+13 | 90,0 % | 39,6 % | +20,6 % | +5,2 % | 15,4 points |
| J+15 | 93,4 % | 41,1 % | +20,4 % | +3,7 % | 16,7 points |
| J+19 | 99,0 % | 43,4 % | +20,0 % | +0,6 % | 19,4 points |

Lecture : 70 % de reconnaissance **parmi les futurs vrais tails** est franchi à J+4, 80 % à J+8, 90 % à J+13. Mais 80 % **ne signifie pas** qu'un candidat Oracle haussier a 80 % de chances d'être D10 : cette chance est 35,9 % à J+8 sur l'ensemble du TOP20. À J+19, la reconnaissance du résultat final devient presque tautologique, alors qu'il ne reste presque rien à capter. Les grands rendements D10 dans les deux colonnes sont calculés **après sélection par le chemin futur J→J+N** : la colonne « entrée immédiate sur les mêmes titres » est un contrefactuel de coût d'attente, pas une stratégie exécutable à J.

## Le mouvement restant est-il exploitable ?

À toutes les dates N, les politiques « hausse observée → LONG ; baisse observée → SHORT » ont un rendement théorique restant moyen **négatif** sur la cohorte complète (entre −0,30 % et −0,07 % par date de signal avec abstentions à zéro). La branche LONG-only avec abstention est moins mauvaise, mais ne rattrape jamais l'entrée Oracle LONG immédiate sur la même population.

| Règle / période | J+1 | J+5 | J+10 | J+15 |
| --- | ---: | ---: | ---: | ---: |
| LONG/SHORT après attente, ensemble | −0,20 % | −0,29 % | −0,13 % | −0,15 % |
| LONG-only après attente, ensemble | +0,42 % | +0,29 % | +0,22 % | +0,08 % |
| Oracle LONG immédiat, ensemble | +1,14 % | +1,14 % | +1,14 % | +1,14 % |
| LONG-only après attente, contrôle 2024–2025 | +0,18 % | +0,05 % | −0,02 % | −0,05 % |
| Oracle LONG immédiat, contrôle 2024–2025 | +0,84 % | +0,84 % | +0,84 % | +0,84 % |

Sur les candidats haussiers choisis par le chemin à J+5, le rendement LONG net moyen depuis J+1 aurait été +6,48 %, mais l'entrée réelle à J+6 ne laisse que **+0,55 %** jusqu'à l'open J+21 ; sur le contrôle récent, seulement **+0,10 %**. Cette différence mesure le gain déjà consommé. La précision du **signe du rendement restant** sur les LONG choisis reste proche de 50 % (environ 48–52 % selon la période et N) ; le résultat de décile final ne doit donc pas être pris pour une précision de trading résiduel.

## Décision et limites

**On peut calculer N pour la reconnaissance du décile final, mais aucun N de 1 à 19 ne ressort comme politique directionnelle économiquement meilleure dans cette règle simple.** Il ne faut pas choisir opportunément J+4, J+8 ou J+13 après lecture de la courbe. Les résultats convergent vers le décile final parce que celui-ci incorpore le chemin J→J+20 ; ce n'est pas une information prospective nouvelle sur J+N→H20.

Limites : univers de symboles courant appliqué au passé (survivance), dernier fold OOF en juillet 2025, pas de contrôle intact postérieur, pas de filtre de tradabilité PIT, pas de mesure d'incertitude par bootstrap de dates, ni de portefeuille/replay de risque. Les labels D1/D10 servent uniquement à évaluer, jamais à décider. Toute suite doit figer une nouvelle règle **sur une autre période**, comparer à Oracle LONG immédiat et à LONG retardé sans filtre, puis simuler exécution, coûts et risque. Une source directionnelle nouvelle pourrait aussi changer ce résultat ; l'attente du seul prix ne suffit pas ici.
