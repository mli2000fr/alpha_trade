# Q051 — répétitions des SL par symbole

Audit des six portefeuilles T0/A/B terminés, 2021–1er octobre 2026, LONG SL5/open11, trades clôturés uniquement.
`STOP` et `STOP_GAP` comptent comme SL. Une perte à open11 est comptée séparément. Aucun filtre, entraînement, ordre ou nouveau backtest n’est appliqué.

| Cas | Trades | Titres | SL | Taux SL | Titres ≥2 SL | Toujours perdants ≥5 trades | Toujours perdants ≥10 trades |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| T0 témoin | 1420 | 350 | 852 | 60.00 % | 188 | 6 | 0 |
| T0 vol20/régime | 1136 | 308 | 656 | 57.75 % | 166 | 0 | 0 |
| A marché témoin | 1418 | 326 | 827 | 58.32 % | 188 | 7 | 1 |
| A vol20/régime | 1101 | 289 | 660 | 59.95 % | 162 | 3 | 0 |
| B volatilité témoin | 1419 | 339 | 808 | 56.94 % | 182 | 4 | 0 |
| B vol20/régime | 1076 | 296 | 631 | 58.64 % | 149 | 7 | 0 |

## T0 témoin — titres avec le plus de SL

| Symbole | Trades | SL | Gagnants | Résultat net | Série SL max | Années perdantes / actives |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| NVDA | 21 | 17 | 19.05 % | +15.05 $ | 11 | 1/5 |
| YPF | 23 | 12 | 47.83 % | +969.25 $ | 3 | 2/3 |
| Z | 21 | 11 | 38.10 % | -19.40 $ | 5 | 2/4 |
| PBT | 18 | 11 | 33.33 % | +260.79 $ | 4 | 0/1 |
| STX | 16 | 11 | 25.00 % | +769.08 $ | 3 | 1/2 |
| HOV | 15 | 10 | 33.33 % | -87.21 $ | 5 | 2/3 |
| MMYT | 15 | 10 | 33.33 % | -143.74 $ | 4 | 2/2 |
| AMR | 17 | 9 | 41.18 % | -289.12 $ | 4 | 2/2 |
| BOOT | 14 | 9 | 28.57 % | -323.23 $ | 3 | 2/2 |
| CAR | 12 | 9 | 25.00 % | +294.08 $ | 6 | 0/1 |
| BBWI | 15 | 8 | 46.67 % | +116.92 $ | 2 | 1/3 |
| DDS | 15 | 8 | 46.67 % | +241.48 $ | 3 | 0/1 |

### Tous les trades perdants, au moins cinq entrées

| Symbole | Trades | SL | Résultat net | Années actives |
| --- | ---: | ---: | ---: | ---: |
| ALGN | 6 | 6 | -300.62 $ | 1 |
| VET | 6 | 6 | -195.89 $ | 1 |
| NEO | 6 | 6 | -124.86 $ | 1 |
| FUTU | 5 | 3 | -249.01 $ | 1 |
| AMKR | 5 | 5 | -140.43 $ | 3 |
| TREX | 5 | 5 | -136.67 $ | 1 |

## B volatilité témoin — titres avec le plus de SL

| Symbole | Trades | SL | Gagnants | Résultat net | Série SL max | Années perdantes / actives |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Z | 22 | 13 | 31.82 % | -30.23 $ | 5 | 1/3 |
| RARE | 19 | 12 | 26.32 % | -140.64 $ | 5 | 1/3 |
| PBT | 17 | 11 | 29.41 % | +86.64 $ | 4 | 2/3 |
| FN | 16 | 11 | 31.25 % | +53.37 $ | 3 | 1/2 |
| TAL | 13 | 11 | 15.38 % | -304.17 $ | 9 | 1/1 |
| STX | 15 | 10 | 33.33 % | +2216.15 $ | 3 | 0/1 |
| BOOT | 14 | 10 | 28.57 % | -185.21 $ | 3 | 2/2 |
| MMYT | 19 | 9 | 47.37 % | +34.21 $ | 2 | 0/1 |
| ANF | 17 | 9 | 47.06 % | +46.09 $ | 4 | 2/3 |
| ETSY | 16 | 9 | 43.75 % | +50.15 $ | 6 | 1/2 |
| EDU | 12 | 9 | 25.00 % | -425.63 $ | 4 | 2/2 |
| FTAI | 18 | 8 | 50.00 % | +559.51 $ | 3 | 2/4 |

### Tous les trades perdants, au moins cinq entrées

| Symbole | Trades | SL | Résultat net | Années actives |
| --- | ---: | ---: | ---: | ---: |
| PRIM | 7 | 7 | -503.01 $ | 2 |
| AGYS | 6 | 6 | -654.44 $ | 2 |
| SNAP | 5 | 5 | -476.09 $ | 1 |
| BJRI | 5 | 5 | -195.12 $ | 1 |

## Persistance après 2024

Les listes ci-dessous sont établies exclusivement avec les trades sortis avant le 1er janvier 2025, puis observées sur les entrées 2025–2026.
Règle 1 : au moins cinq trades historiques, aucun gagnant. Règle 2 : au moins dix trades, ≥80 % de SL et PnL historique négatif.
Cela mesure les trades observés ensuite sur ces titres, pas le capital final d’une stratégie les excluant. Aucune réallocation, nouvelle entrée ou capital libéré n’a été rejoué.

| Cas | Règle historique | Titres signalés | Titres revus ensuite | Trades futurs | Gagnants futurs | PnL futur observé |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| T0 témoin | zero_win_min5 | 4 | 0 | 0 | — | +0.00 $ |
| T0 témoin | sl80_min10_negative | 1 | 1 | 4 | 25.00 % | +103.59 $ |
| T0 vol20/régime | zero_win_min5 | 2 | 1 | 9 | 33.33 % | -2.59 $ |
| T0 vol20/régime | sl80_min10_negative | 0 | 0 | 0 | — | +0.00 $ |
| A marché témoin | zero_win_min5 | 4 | 0 | 0 | — | +0.00 $ |
| A marché témoin | sl80_min10_negative | 2 | 1 | 1 | 0.00 % | -14.27 $ |
| A vol20/régime | zero_win_min5 | 2 | 0 | 0 | — | +0.00 $ |
| A vol20/régime | sl80_min10_negative | 0 | 0 | 0 | — | +0.00 $ |
| B volatilité témoin | zero_win_min5 | 2 | 0 | 0 | — | +0.00 $ |
| B volatilité témoin | sl80_min10_negative | 1 | 0 | 0 | — | +0.00 $ |
| B vol20/régime | zero_win_min5 | 4 | 0 | 0 | — | +0.00 $ |
| B vol20/régime | sl80_min10_negative | 0 | 0 | 0 | — | +0.00 $ |

## Unités et limites

Les 7570 lignes des variantes correspondent à 4867 épisodes cohérents distincts et 0 épisodes à issues divergentes, exclus du résumé dédupliqué.
Une même entrée apparaît dans plusieurs variantes : ces observations ne sont pas des preuves indépendantes. Les dollars des variantes ne sont jamais additionnés en un portefeuille fictif.
Le PnL par titre reprend les frais et dividendes attribués aux trades, sans réaffecter les éventuels frais globaux de financement du portefeuille.
Le résumé par épisode dédupliqué utilise un rendement net normalisé, pas un cumul de PnL en dollars. Ce périmètre réunit des sélections qui ne seraient pas toutes détenues simultanément dans un seul compte.
Un titre sans gagnant sur une ou deux entrées n’est pas établi comme durablement perdant. Les seuils descriptifs de 5/10/20 trades sont fournis explicitement.
Les pertes sont dépendantes des dates, du marché et de la sélection Oracle ; les séries de SL comptent uniquement les trades de ce titre, et non les pertes consécutives de tout le portefeuille.
Pour les statistiques conditionnelles, seuls les résultats strictement connus avant l’entrée suivante sont utilisés ; les sorties à l’instant exact de l’entrée sont écartées de cette connaissance préalable.
L’audit porte sur les symboles des archives : changements d’identité/ticker, univers contemporain, cours révisés et repli OHLC restent des limites. Les positions encore ouvertes ne sont pas déclarées gagnantes ou perdantes.
Les règles historiques sont descriptives, préspécifiées pour cet audit ; 2025–2026 a déjà été observé dans les expériences antérieures. Aucun univers d’exclusion n’est activé.
Détails : `per-symbol.csv`, `per-symbol-year.csv`, `sl-count-distribution.csv`, `conditional-prior-sl.csv`, `frozen-history-check.csv` et `unique-episodes.csv`.

<!-- Q051_SL_RECURRENCE_SUPPLEMENT_20261116 -->

## Synthèse complémentaire — épisodes distincts et persistance

Après déduplication des entrées communes entre les six variantes : **21 titres**
ont uniquement des trades perdants sur au moins cinq épisodes distincts, avec
5 à 9 épisodes par titre ; aucun n’atteint dix épisodes tous perdants dans cette
union. La liste complète est dans `always-losing-unique-min5.csv`.
FIZZ et SAM comptent chacun 9 pertes/9 SL, BIDU 7/7, TFIN 7/7. Les pertes de
FIZZ, SAM et BIDU se concentrent sur 2021. Ce constat est rétrospectif, sur les
entrées sélectionnées par ces stratégies, pas sur toutes les entrées possibles.

En figeant la liste **avant 2025** sur les épisodes distincts (au moins cinq
trades, aucun gagnant), on trouve 17 titres. Seulement trois reviennent sur des
entrées en 2025–2026 : CCL, MRVL et TREX, pour **8 trades dont 4 gagnants**.
Leurs rendements nets normalisés cumulés représentent +4,33 points de pourcentage
à poids égal par trade, et non un rendement de portefeuille ou un PnL en dollars.
Cette faible couverture ne valide pas une exclusion durable par symbole.
TREX avait 10 SL/10 entrées avant 2025, puis un gagnant sur trois entrées futures.

Dans T0, après au moins trois SL consécutifs déjà résolus pour ce même titre,
les 101 trades suivants observés ont 41,58 % de gagnants et +2 345,06 $ de PnL
comptabilisé. Une interdiction générale après trois SL retirerait donc aussi
des gagnants ; aucune stratégie après exclusion ou réallocation n’a été rejouée.

Autre exemple : STX dans B a 10 SL sur 15 trades, mais +2 216,15 $ nets cumulés.
Un grand nombre de stops ne suffit pas à condamner le titre.

Compléments : `unique-episodes-history-check.csv`, `unique-episodes-history-symbols.csv`,
`always-losing-unique-min5.csv`, `always-losing-by-case-min5.csv` et
`sl-repetition-distribution.png`. Les quatre tests ciblés passent.
Aucun filtre ou fichier d’univers de trading n’est modifié.

<!-- Q051_EXISTING_SYMBOL_PAUSE_20261116 -->

## Protection déjà présente : précision pour interpréter l’audit

Les paramètres effectifs `risk_config` des replays T0/A/B prévoient
`concentration_max_consecutive_losses=3` et
`concentration_blacklist_duration_days=90` (jours calendaires).
Le chemin Winner reconstruit les remplissages et appelle
`execution_engine.winner_live_risk.concentration_allowed`, qui utilise
`ConsecutiveLossTracker`. Le résultat utilisé par ce compteur est la différence
brute entre prix d’achat et de vente, sans frais/dividendes ; il ne se limite
pas aux sorties STOP/STOP_GAP.

Les champs de premier niveau du formulaire peuvent afficher 5/30 dans
`configuration.json` ; le recheck Winner utilise ici les valeurs 3/90 de
`risk_config`. Aucun paramètre n’a été modifié lors de cette vérification.

Les trades observés après des SL ont donc déjà subi la sélection des pauses
existantes. Leurs profits ne mesurent pas les occasions qui ont été bloquées.
Une nouvelle règle « deux SL rapprochés → pause courte » doit être comparée au
contrôle existant dans un replay complet, avec capital et occasions réallouées.
Protocole retenu le 16 novembre : conserver 3 pertes/90 jours et comparer
l’ajout de **deux SL consécutifs du même titre dans 30 séances NYSE**, suivis
d’une **pause de 100 séances**, avec exclusion **avant le classement Oracle**.
La proposition 20 séances / pause 20 ou 40 est remplacée. Les résultats ne sont
connus qu’à la sortie ; les protections des positions ouvertes continuent.
Pas d’exclusion permanente. Préparation des scores complémentaires lancée ;
aucune conclusion de rendement à ce stade. Détails :
[protocole SL30 / pause100](q051_sl30_pause100_20261116.md).
