# B / B + anti-SL — liquidation puis vol20 + régime pendant la protection

Demande du 18 novembre 2026 : remplacer la demi-taille des anciennes simulations par une liquidation totale à chaque ON, puis des achats avec budget vol20 et filtre de régime, avant de revenir aux règles habituelles à OFF.

## Protocole figé

2021–1er octobre 2026, 4 000 $ continus. Deux témoins B et B+anti-SL, plus quatre variantes : B_RATE, B_SHADOW, SL10_RATE, SL10_SHADOW. Les mêmes modèles annuels, sélections et états de bascule des expériences précédentes sont réutilisés. Aucun nouvel entraînement, label ou seuil optimisé.

ON : taux de LONG profitables du TOP10 per-symbol B avant anti-SL, 20 séances mûres contre les 120 précédentes, inférieur de plus de 5 points pendant trois clôtures. Référence figée à l’activation. OFF RATE : taux revenu à référence moins deux points pendant cinq clôtures ; OFF SHADOW : compte virtuel de la famille sans cette protection à plus de +5 % sur vingt séances, pendant cinq clôtures. Les deux modes de reprise restent séparés, sans OU ajouté. Les états sont connus à la clôture J et utilisés à J+1 ; les labels H10 ne sont exploités qu’à maturité open11.

À chaque ON : liquidation de toutes les positions à l’ouverture officielle suivante, après les stops et sorties open11 déjà exécutables à cette ouverture. Annulation confirmée des protections, journal EXIT, frais et comptabilité natifs, aucun double sell. Une position sans prix d’ouverture ne peut pas être liquidée fictivement.

Pendant l’état actif : mêmes candidats Oracle/per-symbol, quantité approuvée native entière, éventuellement réduite par une cible de volatilité annualisée de 20 %, covariance des 60 séances passées. Filtre d’entrée SPY : clôture J supérieure à 98 % de sa moyenne 200 séances. Pas de demi-taille supplémentaire et pas de journée cash imposée : un rachat dès la même ouverture après liquidation est possible si les candidats et tous les contrôles prévus passent. Pas de remplacement des candidats refusés.

À OFF : vol20 et filtre SPY désactivés pour les nouvelles entrées de la séance suivante ; retour au portefeuille témoin. Les positions déjà détenues gardent SL5/open11, sans liquidation à OFF. L’anti-SL reste actif dans la famille B+anti-SL dans les deux états.

Base : TOP10 % Oracle H10 → TOP10 LONG, score>0,50/AUC≥0,50 ; entrée journalière J+1, position complète, SL5 %, sans TP/trailing/renforcement, open11. Risque1,25 %, poids20 %, 20 positions, minimum50 $, plafond achats1×/capacité margin2×. Frais8pb/côté, financement6,5 % annuel. B4/DD/facteurs/corrélation/limites sectorielles/pause100 supplémentaires désactivés. Aucun compteur de DD ou capital remis à zéro.

## Fidélité et exécution

Les deux témoins sont d’abord rejoués et doivent reproduire les courbes quotidiennes, intraday et trades archivés, avant les quatre nouveaux cas. Cinq fichiers de sélection/serving/entraînement ont changé lors du raccordement natif anti-SL ; ces changements sont identifiés dans le nouveau manifeste, sans réécrire les anciens. Les sélections sont déjà figées et les prédictions ne sont pas recalculées. Toute autre modification inattendue bloque la préparation.

La liquidation utilise le coordinateur Winner et le broker de simulation ; son adaptateur reste dans les scripts de recherche et ne modifie pas le moteur partagé ou la production. Les entrées utilisent le budget vol20 et le filtre de régime existants, activés conditionnellement par l’état figé. Données de marché archivées, aucune collecte ni SQL. Contrôles comptables, revue prix/événements et préfixes causaux avant consolidation.

Commande : `.venv\Scripts\python.exe -X utf8 -u -m scripts.research.us_q051_internal_liquidation_20261118 --phase all`.

Archives/suivi : `artifacts/research/us_q051_internal_liquidation/20261118-v1`, `progress.json`, `cases/<cas>/progress.json`, `logs/`. Deux témoins simultanés puis quatre variantes simultanées. À la fin : tableau, résultats annuels, liquidation/états de protection, capital engagé, courbes complètes et zoom novembre2024–juin2025.

Limites : historique déjà exploré, univers contemporain, prix révisés, intraday partiel avec repli OHLC, pas de nouveau holdout ni de certification PIT/parité live. SPY de comparaison : prix seuls, sans dividendes ni frais. Les critères de reprise SHADOW utilisent toujours le compte virtuel continu de référence, pas la performance du compte protégé. Aucun changement de configuration, compte ou ordre réel.

<!-- Q051_INTERNAL_LIQUIDATION_RESULTS_20261118 -->

# B / B + anti-SL — liquidation puis vol20 + régime

2021–1er octobre2026, 4000$ continus, deux témoins rejoués identiques aux archives. Activation/reprise figées comme les tests demi-taille ; liquidation à l’ouverture suivante, puis vol20/covariance60 et filtre SPY>98%SMA200 seulement en protection. À OFF : retour aux règles habituelles. Rachat à la même ouverture possible après liquidation si les limites passent.

| Cas | Capital final | Rendement | DD intraday | Gagnants | Trades | Engagé moyen |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B témoin | 15894.14$ | +297.35% | -40.99% | 37.63% | 1419 | 6401.43$ |
| B + anti-SL témoin | 16140.82$ | +303.52% | -34.98% | 38.13% | 1356 | 7069.05$ |
| B — liquidation / vol20+régime / sortie taux | 6196.90$ | +54.92% | -48.00% | 37.81% | 1251 | 2766.33$ |
| B — liquidation / vol20+régime / sortie témoin+5% | 8190.38$ | +104.76% | -39.12% | 36.37% | 1284 | 3224.83$ |
| B + anti-SL — liquidation / vol20+régime / sortie taux | 7933.75$ | +98.34% | -44.81% | 37.35% | 1178 | 3306.87$ |
| B + anti-SL — liquidation / vol20+régime / sortie témoin+5% | 7667.96$ | +91.70% | -42.19% | 36.48% | 1198 | 3260.23$ |

Revue : ARITHMETIC_CONTROL_PASS_WITH_PRICE_OR_EVENT_RESERVES. Réserves prix 0 ; écarts de labels 6/7667.
Frais et financement natifs, capital partagé, quantités entières, SL5/open11 et mêmes signaux. Aucun appel fournisseur/LLM, entraînement, SQL ou ordre réel ; pas de changement de production. Historique déjà exploré, univers contemporain, prix révisés et intraday incomplet/repli OHLC : résultat exploratoire.
Archives : `artifacts\research\us_q051_internal_liquidation\20261118-v1`.

## Revue finale : règle appliquée, compromis dégradé

`matched-controls.json` confirme la reproduction des deux témoins (courbes daily/5m et trades, tolérance absolue1e−8). `liquidation-validation.json` est PASS : 14/13/14/15 activations et liquidations, chacune à l’ouverture officielle suivant le ON, quantités rapprochées des trades `INTERNAL_PROTECTION`, pas de liquidation DD/B4. Le filtre SPY n’est consulté qu’en protection et correspond exactement à close>98%SMA200 ; toutes les décisions de covariance sont qualifiées, datées du passé et ne peuvent augmenter la quantité native. Les 66/66/66/76 trades clôturés de force paient les frais natifs.

Le DD maximal des quatre nouvelles variantes survient en **2022** : 14juillet pour B_RATE, 24janvier pour B_SHADOW, 15juillet pour SL10_RATE, 3novembre pour SL10_SHADOW. Les deux témoins ont leur pire DD le7avril2025. Voir `dd-episodes.csv`.

Sur novembre2024–juin2025, le DD sur clôtures est réduit : B témoin−39,40% contre−26,50%/−26,26% ; anti-SL témoin−34,08% contre−29,14%/−31,37%. Mais le capital récupère moins bien et le DD global reste dominé par les pertes de2022. Les nouvelles variantes anti-SL sont dominées par leur témoin à la fois en rendement et DD ; B_SHADOW ne réduit que modestement le DD global, avec beaucoup moins de rendement. Ne pas qualifier cette nouvelle protection d’amélioration robuste.

La réserve d’événement est la même observation BIDU du26février2021 dans les six cas : label daily première séance SL alors que le replay clôture plus tard par STOP. Aucun changement de label ou seuil après observation des résultats. Aucun déploiement de cette protection.

## Vérification des courbes avant ON et après OFF

Les quatre variantes sont rigoureusement identiques à leur témoin jusqu’au10août2021 (écart quotidien maximal0$). Premier ON le10août, première liquidation et première différence le11août2021. Le24décembre2024 est donc le début d’un épisode ultérieur ; des épisodes existaient notamment en avril, juillet et août2024. La mention précédente « activation fin2024 » concernait seulement le zoom novembre2024–juin2025.

Hors protection,3266décisions de sélection sont sans veto supplémentaire, et aucune décision de covariance vol20 n’est prise en état OFF. Les capitaux, positions et historiques de pertes/entrées restent ceux de chaque compte ; ils ne sont pas alignés sur le témoin à OFF. Du dernier OFF de mai2025 au27octobre2025 (avant ON suivant), B_RATE fait+22,10% contre+25,21% pour son témoin, B_SHADOW+26,77% contre+33,62%, SL10_RATE+35,84% contre+15,24%, SL10_SHADOW+49,41% contre+15,38%. Voir `post-off-comparison.csv`, `phase-validation.json` et `post-off-normalized.png`, qui ramène chaque paire à100 à sa date OFF.

Réactivations communes après mi2025 :28octobre2025,24février2026,17juin2026. Les modes SHADOW ont aussi des réactivations en mars et le15septembre2026 ; SL10_SHADOW reste protégé du28octobre2025 au20janvier2026. Détails dans `post-mid2025-transitions.csv`.

Sur les188séances d’entrée2026, jusqu’au1eroctobre : B_RATE protégé113séances, rendement+48,53% contre témoin+66,61% ; B_SHADOW87séances,+64,49% contre+66,61% ; SL10_RATE113séances,+33,69% contre+68,99% ; SL10_SHADOW92séances,+31,55% contre+68,99%. Les courbes en dollars amplifient aussi les écarts de capital accumulés auparavant : B_SHADOW démarre2026 à4979,31$, contre9539,46$ pour B témoin. Voir `protection-2026-summary.csv`.
