# Q051 TOP10 — plafond deux séances, anti-SL et vol20 + régime

2021–1 octobre 2026 ; 4 000 USD, portefeuille continu. Même Oracle et LONG per-symbol classiques ; SL5 %, sans TP/trailing, sortie à l’ouverture de la 11e séance détenue. Aucun changement de production.

| Variante | Capital final $ | Rendement | DD max | Gagnants | Trades | Capital engagé moyen $ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Plafond, attente deux séances — témoin | 18593.49 | +364.84 % | -46.26 % | 34.63 % | 1444 | 6842.92 |
| Plafond, attente deux séances + anti-SL | 6119.53 | +52.99 % | -43.28 % | 33.06 % | 1352 | 5042.75 |
| Plafond, attente deux séances + vol20 et régime | 7299.69 | +82.49 % | -23.30 % | 35.89 % | 1134 | 2368.58 |

Anti-SL : poids annuels SL10 figés, seuil passé percentile90, appliqués à J après TOP10 et avant attente, sans remplacement. Le modèle vise le SL de J+1 ; sa pertinence pour une entrée retardée est précisément une limite testée ici.
Vol20 + régime : covariance 60 séances passées, cible annualisée 20 %, SPY > 98 % SMA200 à la veille de chaque entrée effective. Réduction des nouvelles entrées uniquement.
Limites : période déjà étudiée, univers rétrospectif, prix révisables et couverture 5m partielle. Les entrées tardives sont limitées ex post aux séances complètes qualifiées ; aucune parité live certifiée.

Archives : `artifacts\research\us_q051_ceiling_overlays\20261128-v2`. Témoin conservé à l’identique par réutilisation vérifiée ; validation arithmétique PASS.


## Lecture de la comparaison et contrôles finaux

Le témoin est une **réutilisation vérifiée de l’archive**, conservée à l’identique, et non une nouvelle simulation. Les deux variantes ont été rejouées sur les mêmes prix, modèles Oracle/LONG et configuration de portefeuille.

Le transfert anti-SL SL10 réduit très peu le DD (−46,26 % → −43,28 %) et dégrade fortement le rendement (+364,84 % → +52,99 %) et le taux gagnant. Ce résultat concerne ce transfert de têtes figées, pas toutes les configurations anti-SL possibles.

Vol20 + régime réduit approximativement de moitié le DD maximal (−23,30 %) mais diminue aussi fortement le rendement (+82,49 %). L’exposition moyenne / equity passe de 88,61 % à 45,97 %. Aucun refus pour historique de covariance manquant : les 4 244 décisions proviennent du budget qualifié ; 167 concernent des ouvertures 5 minutes et 4 077 des ouvertures journalières.

Les SL de première séance représentent 10,96 % des achats pour le témoin, 10,38 % avec anti-SL et 10,04 % avec vol20 + régime. Ces taux sont calculés sur les achats réellement simulés, après réallocation du capital ; ils ne sont pas les labels de tous les signaux exclus.

Validation supplémentaire **PASS** : frais/PnL/capital/DD réconciliés, fenêtres J+1/J+2 et plafonds respectés, sorties horizon à open11, absence d’achat d’un signal exclu, régime admissible et budget vol20 raccordé aux deux chemins d’entrée. Les trois résultats sont importés dans l’historique IHM.

[Protocole détaillé et conditions de reconstruction](q051_ceiling_overlays_20261128_protocol.md).
