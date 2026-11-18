# B / B + anti-SL TOP10 — quatre tests de protection interne

Demande du17novembre2026, suite à l’audit des taux de réussite et de la reprise des comptes.

## Cas figés

| Cas | Famille | Sortie de protection |
| --- | --- | --- |
| B_RATE | B seul TOP10 | Rétablissement du taux de réussite |
| B_SHADOW | B seul TOP10 | Compte témoin B à+5% sur20séances |
| SL10_RATE | B + anti-SL dix séances TOP10 | Rétablissement du taux de réussite |
| SL10_SHADOW | B + anti-SL dix séances TOP10 | Compte témoin B+anti-SL à+5% sur20séances |

Déclencheur commun aux quatre : taux LONG profitable du TOP10 per-symbol B **avant anti-SL**, sur20séances de maturité, inférieur de5points à la référence des120séances de maturité précédentes pendant3clôtures. Référence figée lors de l’activation. Sortie RATE : taux revenu à référence moins2points pendant5clôtures. Sortie SHADOW : rendement20>+5% sur le compte virtuel continu de la famille pendant5clôtures.

Décisions à la clôtureJ pour l’ouvertureJ+1. Maturité complèteopen11 des labels même pour les stops précoces. Taux de rentabilité LONG, pas taux d’amplitude Oracle ou AUC. Couverture≥80%, minimum40labels récents et160de référence. Fenêtres non qualifiées : aucune nouvelle activation, état courant conservé. La sortie SHADOW peut être confirmée indépendamment de la qualification du taux courant. Pas de reset annuel.

## Protection et portefeuille

En protection, quantité nouvelle = moitié arrondie à l’entier inférieur de la quantité approuvée nativement, puis revalidation native. Les minimums, réserves et plafonds restent appliqués. Une petite position peut être refusée. Les positions déjà détenues gardent leurs paramètres ; aucun renforcement, changement de SL, TP/trailing ou liquidation forcée. Cette règle ne garantit pas une division par deux de l’exposition du portefeuille.

Période1erjanvier2021–1eroctobre2026, capital4000$ continu. Modèles annuels et signaux identiques, TOP10%Oracle179→TOP10LONG, score>0,50/AUC≥0,50, veto anti-SL existant pour la familleSL10. Entrée journalièreJ+1 sans confirmation, position entière, SL5%, sortieopen11. Risque1,25%, poids20%,20positions, minimum50$, plafond achats1×/capacité margin2×, frais8pb/côté, financement annuel6,5%. Aucun paquet SPY/vol20, B4/DD ou pause100 ajouté.

## Exécution et limites

Commande : `.venv\Scripts\python.exe -X utf8 -u -m scripts.research.us_q051_internal_protection_20261117 --phase all`.

Archives : `artifacts/research/us_q051_internal_protection/20261117-v1`. Suivi global `progress.json`, cas `cases/<cas>/progress.json`, logs `logs/`. Quatre simulations simultanées au maximum. Consolidation après validation arithmétique et revue des détentions : courbes, rendement/DD, taux gagnant, capital engagé, résultats annuels, basculements et fenêtres fin2024–mi2025.

Les modèles, labels et témoins existants sont réutilisés sans SQL, téléchargement ou appel LLM. Aucun ordre ou changement de production. Les historiques sont déjà explorés ; aucune validation indépendante. Intraday incomplet avec repli OHLC, prix révisés et univers contemporain. Des labels de fin d’année restent manquants ; début du taux qualifié en août2021, pas de protection inventée avant ce warmup.

<!-- Q051_INTERNAL_HALF_PROTECTION_RESULTS_20261117 -->

# B / B + anti-SL TOP10 — protection interne, nouvelles entrées à demi-taille

2021–1er octobre2026,4000$ continus. Quatre replays natifs. Déclencheur commun : taux LONG profitable du TOP10 per-symbol B avant anti-SL, 20 séances mûres contre les120précédentes. Baisse>5points pendant3clôtures pour activer. Sortie A : retour à référence figée moins2points pendant5clôtures. Sortie B : compte témoin virtuel de la famille >+5% sur20séances pendant5clôtures. Décisions àJ pourJ+1 ; étiquettes connues à maturité complèteopen11. Taux inconnu : pas de nouvelle activation ; état existant conservé.
Protection : floor(quantité approuvée native/2), puis revalidation native ; minimums et quantités entières conservés. Elle ne divise pas nécessairement l’exposition globale par deux : positions existantes, candidats suivants et capital disponible restent dans le moteur. Positions détenues : SL5/open11 inchangés. Sans TP/trailing, sans SPY/vol20/B4/DD/pause100 supplémentaires. Modèles/signaux/risque de base, frais et financement identiques aux témoins.

| Cas | Capital final | Rendement | DD intraday | Gagnants | Trades | Capital engagé moyen |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B témoin | 15894.14$ | +297.35% | -40.99% | 37.63% | 1419 | 6401.43$ |
| B + anti-SL témoin | 16140.82$ | +303.52% | -34.98% | 38.13% | 1356 | 7069.05$ |
| B — demi-taille / sortie taux | 8489.41$ | +112.24% | -38.00% | 35.65% | 1742 | 4524.90$ |
| B — demi-taille / sortie témoin+5% | 10315.79$ | +157.89% | -33.96% | 34.72% | 1754 | 4646.06$ |
| B + anti-SL — demi-taille / sortie taux | 8678.67$ | +116.97% | -40.43% | 36.59% | 1607 | 4144.02$ |
| B + anti-SL — demi-taille / sortie témoin+5% | 6606.19$ | +65.15% | -42.67% | 35.64% | 1574 | 3557.28$ |

Revue : ARITHMETIC_CONTROL_PASS_WITH_PRICE_OR_EVENT_RESERVES. Réserves prix 0, écarts de labels première séance 4/6664.
Les deux témoins continus existaient avant ce test et servent aussi de comptes virtuels pour la sortie B ; leurs cours/capitaux futurs ne sont jamais lus à une décisionJ. Les labels de fin d’année manquants restent inconnus ; le warmup qualifié débute en août2021, sans inventer une protection sur le début2021. Les taux sont des proportions de LONG profitables parmi les sélections, pas la précision d’amplitude Oracle ni l’AUC du modèle.
Recherche rétrospective sur années déjà explorées, univers contemporain et prix révisés ; intraday partiel avec repli OHLC. Aucun nouvel entraînement, label, SQL, fournisseur/LLM, ordre ou changement de production ; pas de holdout neuf ou de parité live.
Archives : `artifacts\research\us_q051_internal_protection\20261117-v1`. Voir comparaisons annuelles, fenêtres de baisse, basculements et reçus de dimensionnement.
