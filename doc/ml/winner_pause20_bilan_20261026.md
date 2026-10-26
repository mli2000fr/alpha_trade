# Bilan DD15 : pause20, avec ou sans reprise temporaire SL1

26 octobre 2026. Les deux comptes sont `COMPLETED_AUDITED_EXPLORATORY`.
Empreintes des sources et fichiers de sortie revérifiées après achèvement ;
la comparaison hybride est `READY`, avec parité des courbes avant la première
reprise. Aucun nouveau replay, SQL, appel fournisseur, entraînement ou ordre.

## Périmètre commun

TOP20 Oracle LONG dans l'ordre d'origine, 2 janvier 2020–31 décembre 2024,
capital initial 4 000 USD, minimum70 USD, positions complètes, sans renfort,
exposition brute plafonnée à1x, frais8pb/jambe, sans TP ni trailing,
détention20 séances puis sortie à l'ouverture suivante. Capital final valorisé
incluant les positions encore ouvertes, sans remise à zéro annuelle.
Plafond d'admission historiqueSL3 conservé : les phases SL1 ne peuvent pas
augmenter la quantité au-delà de ce plafond.

Après liquidation DD15 du cycle : vingt séances NYSE complètes de pause,
jour de liquidation exclu. Reprise à l'ouverture de la21e séance suivante.
Dans le bras hybride, la reprise démarre vingt séances d'entrées SL1, séance
de reprise incluse ; retour SL5 pour les nouvelles entrées seulement. Les lots
SL1 conservent leur stop. Un nouveau DD15 recommence liquidation/pause/reprise.

## Résultats globaux

| Variante | Capital final USD | Rendement cumulé | DD maximal historique | Clôtures | Taux gagnant |
| --- | ---: | ---: | ---: | ---: | ---: |
| SL5 sans pause | 13 641,66 | +241,04 % | −36,25 % | 1 022 | 21,33 % |
| SL5 DD15/pause3mois | 14 559,54 | +263,99 % | −39,12 % | 373 | 27,35 % |
| SL5 DD15/pause20séances | 10 007,19 | +150,18 % | −66,16 % | 575 | 25,74 % |
| Pause20 puis SL1 pendant20séances | 7 034,62 | +75,87 % | −41,06 % | 743 | 14,80 % |

Pause20 simple : gains des clôtures gagnantes42 625,68USD, pertes des clôtures
perdantes−36 682,47USD ; gain moyen288,01USD, perte moyenne−85,91USD.
Capital brut moyen utilisé5 171,16USD, exposition moyenne/capital courant50,73%.
21 liquidations de cycle et21 reprises. 581 achats, six positions encore ouvertes.

Hybride : gains23 147,46USD, pertes−20 296,53USD ; gain moyen210,43USD,
perte moyenne−32,06USD. Capital brut moyen3 044,38USD, exposition moyenne46,34%.
17 liquidations et17 reprises. 749 achats :333 sous SL5 et416 sous SL1 ;
six positions encore ouvertes. Les749 politiques d'achat sont contrôlées.

Les gains/pertes ci-dessus concernent les lots clôturés ; ils ne sont pas à eux
seuls la variation totale du compte avec positions ouvertes et frais associés.

## Rendements annuels des comptes continus

| Année | Pause20 / SL5 | Pause20 / repriseSL1 |
| --- | ---: | ---: |
| 2020 | +132,35 % | +1,06 % |
| 2021 | +64,06 % | +18,41 % |
| 2022 | −52,08 % | +21,40 % |
| 2023 | +66,16 % | +70,05 % |
| 2024 | −17,57 % | −28,81 % |

## Interprétation bornée

La reprise SL1 réduit le DD observé de25,10points par rapport à la pause20
simple, mais abandonne74,31points de rendement cumulé. Elle ne domine pas
le SL5 sans pause : rendement inférieur et DD historique plus profond.
Pause20 simple ne domine pas non plus ce témoin. Ne pas promouvoir les deux
variantes en production sur ce résultat.

Le DD15 est un seuil de liquidation/réarmement PAR CYCLE, pas un plafond des
pertes depuis le sommet historique : les pertes de plusieurs cycles peuvent
se cumuler. En2022 la pause20 simple perd52,08% sur l'année, expliquant une
grande partie de son DD historique66,16%. Réinitialiser le sommet local ne
réinitialise ni le vrai capital ni le DD historique.

Comparaison exploratoire sur historique déjà vu : secteurs actuels et biais
de disponibilité future hérités, ni holdout vierge ni parité live complète.
Parité actuelle/ancien moteur contrôlée seulement sur un pont20séances pour
les témoins sans liquidation ; ne pas prétendre à une preuve intégrale sur5ans.

## Archives et graphique

- Pause20 : `artifacts/research/us_winner_cycle15_pause20_min70/20261026-v1`.
- Hybride : `artifacts/research/us_winner_pause20_restart_sl1/20261026-v1`.
- Comparaison des quatre comptes : `comparison.json` dans le dossier hybride.
- Six variantes terminées +SPY :
  `artifacts/research/us_winner_completed_spy_visuals/20261026-v2`.

Le SPY est un repère de cours : achat fractionnel à l'ouverture initiale,
8pb de frais d'entrée, position conservée jusqu'au terme, sans dividendes.
Il finit à7 240,05USD/+81,00%. Ce n'est pas son rendement total dividendes
réinvestis. Les courbes sont quotidiennes ; les DD des replays sont intraday5m.
