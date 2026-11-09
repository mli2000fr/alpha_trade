# Audit US CALL/PUT + open interest — 9 novembre 2026

## Fournisseurs et stockage

- `options_delayed_bars_sync` : **Alpaca**, endpoint historique options, barres `30Min`, `stock_option_bars_delayed`, feed enregistré `historical_default`, provenance `UNVERIFIED_OPRA`.
- `oracle_options_indicative_snapshot` : **Alpaca**, snapshots `indicative` et métadonnées des contrats pour l’open interest, `stock_option_snapshots`.
- Les deux batchs collectent le fichier `config/univers_batch/stock_bars_daily.txt`. Yahoo complète uniquement des références de prix du sous-jacent manquantes dans le périmètre tradable ; il ne fournit pas le volume/OI étudié.
- Audit restreint au fichier tradable canonique de 1 790 symboles, TOP10/20/50 Oracle fixés avant couverture et labels. Pas de remplacement N+1.

## Règles figées

Le filtre de production est réutilisé : échéances à 15–25 jours calendaires, cible 20, OI CALL et PUT appariée au même strike proche du cours (±5 %), volume CALL/PUT de même échéance pour chaque mesure. Échéances volume et OI éventuellement différentes mais enregistrées. Rangs relatifs volume et OI pondérés 50/50 ; score >0,50, moitié supérieure des couverts, minimum quatre couverts.

**Taux gagnant économique** : chaque signal est un trade LONG indépendant, achat à l’ouverture officielle J+1, SL5 %, sans TP ni trailing, sortie à l’ouverture après H séances de détention (open6/11/16/21), 8 pb de frais/slippage à chaque opération. Stop franchi à l’ouverture : sortie au prix d’ouverture, pas au stop théorique. Toutes les séances et l’ouverture de sortie doivent être disponibles ; aucun remplissage des prix manquants.

Ce diagnostic n’est pas un replay complet Winner : pas de confirmation 5m, capital partagé, sizing, gestion des positions déjà détenues, intérêts de marge ni dividendes. Prix canoniques daily split-adjusted actuels avec préférence fournisseur figée. Les choix sont fixés avant l’examen des performances. Les trades gagnants sont strictement positifs après frais.

Comparateurs : (a) TOP brut sans filtre sur les mêmes dates où le filtre pouvait sélectionner ; (b) même population disposant de scores options, sans sélection par le score ; (c) retenus. (b) réduit le biais de couverture. Les champs nuls ne sont jamais interprétés comme 0 % de réussite.

## Priorité : classements H20 déjà observables avant décision

Archives scellées du 5 novembre réutilisées. Les dix classements complets et leur traçabilité étaient horodatés avant décision ; ces horodatages ont été recontrôlés pendant cet audit. Les modèles d’origine ont été supprimés depuis : on vérifie les métadonnées et empreintes archivées ; on ne prétend pas pouvoir reproduire actuellement leurs poids.

Le filtre a sélectionné 33 signaux TOP20 sur sept dates du 27 octobre au 4 novembre. Seulement 14 trades, neuf sociétés, trois dates du 27 au 29 octobre, sont arrivés au terme de H5 avec ouverture de sortie disponible. Les autres restent non mûrs. Il n’y a pas de sélection options mûre à H10/H15/H20. À H10, le seul classement Oracle mûr (16 octobre) n’a pas de sélection options qualifiée.

| Horizon | TOP20 brut, mêmes dates | Couverts, sans filtre | Après filtre | Gagnants après filtre |
|---|---:|---:|---:|---:|
| H5 | 11,67 % (60) | 7,89 % (38) | 0,00 % (14) | 0/14 |
| H10 | non évaluable (0) | non évaluable (0) | non évaluable (0) | — |
| H15 | non évaluable (0) | non évaluable (0) | non évaluable (0) | — |
| H20 | non évaluable (0) | non évaluable (0) | non évaluable (0) | — |

H5 : 7/60 gagnants dans le TOP20 brut contre 3/38 dans la population couverte et 0/14 après filtre. Sans SL, ces 14 retenus donnent également zéro trade gagnant à open6 après frais. Les mauvais résultats ne peuvent donc pas être attribués uniquement au SL5. Le diagnostic est trop petit pour généraliser à tous les mois.

## Complément rétrospectif : modèles annuels H10 et H20 entraînés avant 2026

Les poids ont des fenêtres causales vérifiées, mais les scores ont été calculés le 8 novembre : ils n’étaient pas physiquement disponibles aux anciennes décisions. Les modèles H10/H20 donnent respectivement 31/21 dates de rangs au total, mais les sélections options TOP20 évaluables se concentrent du 22 septembre au 1er octobre (H10) ou 30 septembre (H20). Ne pas mélanger avec la validation observable ci-dessus.

| Oracle | Détention | TOP20 brut, mêmes dates | Couverts sans filtre | Après filtre | Gagnants retenus | Sociétés / dates retenues |
|---|---:|---:|---:|---:|---:|---:|
| H10 | H5 | 49,38 % (160) | 53,45 % (58) | 61,54 % | 16/26 | 14 / 8 |
| H10 | H10 | 23,12 % (160) | 24,14 % (58) | 11,54 % | 3/26 | 14 / 8 |
| H10 | H15 | 12,50 % (160) | 12,07 % (58) | 3,85 % | 1/26 | 14 / 8 |
| H10 | H20 | 12,50 % (160) | 12,07 % (58) | 3,85 % | 1/26 | 14 / 8 |
| H20 | H5 | 48,57 % (140) | 55,17 % (58) | 68,00 % | 17/25 | 12 / 7 |
| H20 | H10 | 26,43 % (140) | 27,59 % (58) | 20,00 % | 5/25 | 12 / 7 |
| H20 | H15 | 17,14 % (140) | 18,97 % (58) | 8,00 % | 2/25 | 12 / 7 |
| H20 | H20 | 17,14 % (140) | 18,97 % (58) | 8,00 % | 2/25 | 12 / 7 |

Un petit avantage H5 apparaît rétrospectivement sur septembre ; il se renverse à H10/15/20 et n’est pas confirmé sur octobre observable. Réduire le chevauchement laisse seulement deux dates H5 et une date H10/15/20 dans la population TOP20 rétrospective : ce n’est pas une confirmation indépendante.

## Sens du pic et rentabilité ne sont pas la même cible

L’excursion dominante pendant H avant SL10 propre à chaque sens, les deux pics non protégés et le rendement sans SL sont conservés séparément dans les fichiers. Exemple : FORM, signal 22 septembre, entrée 125,39 ; sortie open6 142,30 (+13,30 % net), open11 137,27 (+9,30 %), open16 124,11 (−1,18 %), puis SL5 touché avant open21 (−5,15 % net). Un pic haussier intermédiaire n’est pas une garantie de trade gagnant si on attend.

## Annexes TOP10 / TOP50

| Groupe | TOP | H | Couverts sans filtre | Après filtre | N retenus |
|---|---:|---:|---:|---:|---:|
| H10 | 10 | 5 | 58,82 % | 66,67 % | 6 |
| H10 | 10 | 10 | 5,88 % | 0,00 % | 6 |
| H10 | 10 | 15 | 5,88 % | 0,00 % | 6 |
| H10 | 10 | 20 | 5,88 % | 0,00 % | 6 |
| H10 | 50 | 5 | 38,89 % | 42,86 % | 105 |
| H10 | 50 | 10 | 25,64 % | 21,90 % | 105 |
| H10 | 50 | 15 | 17,09 % | 13,33 % | 105 |
| H10 | 50 | 20 | 12,92 % | 7,29 % | 96 |
| H20 | 10 | 5 | 58,82 % | 71,43 % | 7 |
| H20 | 10 | 10 | 17,65 % | 0,00 % | 7 |
| H20 | 10 | 15 | 5,88 % | 0,00 % | 7 |
| H20 | 10 | 20 | 5,88 % | 0,00 % | 7 |
| H20 | 50 | 5 | 43,51 % | 45,07 % | 71 |
| H20 | 50 | 10 | 27,92 % | 21,13 % | 71 |
| H20 | 50 | 15 | 18,83 % | 12,68 % | 71 |
| H20 | 50 | 20 | 12,99 % | 4,23 % | 71 |
| H20_ARCHIVE_OBSERVABLE | 10 | 5 | 15,79 % | 0,00 % | 8 |
| H20_ARCHIVE_OBSERVABLE | 10 | 10 | non évaluable | non évaluable | 0 |
| H20_ARCHIVE_OBSERVABLE | 10 | 15 | non évaluable | non évaluable | 0 |
| H20_ARCHIVE_OBSERVABLE | 10 | 20 | non évaluable | non évaluable | 0 |
| H20_ARCHIVE_OBSERVABLE | 50 | 5 | 7,07 % | 2,33 % | 43 |
| H20_ARCHIVE_OBSERVABLE | 50 | 10 | 0,00 % | 0,00 % | 2 |
| H20_ARCHIVE_OBSERVABLE | 50 | 15 | non évaluable | non évaluable | 0 |
| H20_ARCHIVE_OBSERVABLE | 50 | 20 | non évaluable | non évaluable | 0 |
| H20_ARCHIVE_RECONSTRUIT | 10 | 5 | 56,25 % | 80,00 % | 5 |
| H20_ARCHIVE_RECONSTRUIT | 10 | 10 | 6,25 % | 0,00 % | 5 |
| H20_ARCHIVE_RECONSTRUIT | 10 | 15 | 0,00 % | 0,00 % | 5 |
| H20_ARCHIVE_RECONSTRUIT | 10 | 20 | 0,00 % | 0,00 % | 5 |
| H20_ARCHIVE_RECONSTRUIT | 50 | 5 | 48,54 % | 53,42 % | 73 |
| H20_ARCHIVE_RECONSTRUIT | 50 | 10 | 32,75 % | 31,51 % | 73 |
| H20_ARCHIVE_RECONSTRUIT | 50 | 15 | 21,64 % | 19,18 % | 73 |
| H20_ARCHIVE_RECONSTRUIT | 50 | 20 | 14,04 % | 9,59 % | 73 |

## Vérifications et limites

- Cinq tests de règles d’exécution réussis : sortie open H+1, SL, gap, frais, identité et prix manquants. 6 160 lignes de sélection recontrôlées avec le filtre de production et 144 cohortes de résultats recomptées sans écart.
- Tous les exports ont été comptés avant extraction, sans troncature, puis scellés. Les sources, classements, décisions et parcours sont conservés. Les rapports revus (`reviewed-report.json`) précisent les différences de provenance entre branches ; les rapports génériques originaux restent immuables.
- Même assistant ; pas de revue humaine indépendante. Plusieurs horizons/périmètres et sociétés répétées ; aucune recherche de meilleurs seuils, aucun entraînement ni promotion.
- Volumes non signés : un CALL échangé n’est pas nécessairement un achat haussier. OI provenant des métadonnées Alpaca, snapshots associés au feed indicative ; pas de certification OPRA/NBBO ni de disponibilité historique d’un spread réel.
- Aucun appel fournisseur/LLM, ordre, nouvelle prédiction, modification des batchs/configurations ou écriture SQL.

## Fichiers

- `artifacts/research/us_options_winrate/20261109-v1/analysis/` : modèles annuels H10/H20 reconstruits, `summary.csv`, `outcomes.parquet`, `reviewed-report.json`.
- `artifacts/research/us_options_winrate/20261109-archived-v1/analysis/` : anciens classements H20 observables/reconstruits séparés, mêmes exports.
- Scripts : `us_options_winrate_audit_20261109.py`, `us_options_archived_winrate_20261109.py`, `us_options_winrate_review_20261109.py` sous `scripts/research`.

**Conclusion : pas d’amélioration fiable des achats LONG démontrée. L’indice H5 de septembre est rétrospectif et ne se confirme pas sur le petit sous-échantillon observable d’octobre. H10/H15/H20 observables restent non évaluables pour les retenus options.**
