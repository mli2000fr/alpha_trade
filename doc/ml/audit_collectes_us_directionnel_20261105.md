# Audit directionnel US des collectes — 5 novembre 2026

Le mois supplémentaire ne confirme pas encore un avantage directionnel exploitable des options ou du consensus sur les TOP Oracle. Les résultats récents sont moins favorables que les anciens petits échantillons rétrospectifs. Aucun réglage de production n’est modifié.

## Périmètre et chronologie

Extraction SQL US en lecture seule, figée au 2026-11-05 22:09:40.303978+00:00. Univers actuel : 1 790 titres du fichier `config/univers_batch/univers_filtred_tradable.txt`. TOP10/20/50 sont des nombres de titres, fixés avant toute exclusion de données ; aucun remplacement par le rang suivant.

Oracle parcours H20 existant : `model-factory-20261014113232-bc35a7` pour septembre et `model-factory-20261016180250-3b0515` pour octobre/novembre. Ce sont les horizons des issues qui varient H5/H10/H15/H20 ; aucun Oracle H5/H10 nouvellement entraîné n’est substitué. 25 séances de classement qualifiées au seuil actuellement configuré de 90 %, avec contrôle de sensibilité à 95 %. Les jours sans scores restent absents. Dix classements seulement étaient intégralement présents avant la décision : 16, 23, 26–30 octobre, puis 2–4 novembre. Les classements de septembre ont été reconstruits en octobre : leurs résultats sont séparés.

## Données effectivement présentes

Comptages dans l’univers tradable, sur les disponibilités du 10 septembre au cutoff. Ce sont des jours de réception, pas forcément des séances indépendantes ni des observations utiles à tous les TOP.

| Famille | Lignes | Jours de réception | Première disponibilité | Dernière disponibilité |
|---|---:|---:|---|---|
| `stock_option_snapshots` | 427,346 | 39 | 2026-09-14 20:20:02.570920 | 2026-11-05 01:17:08.445515 |
| `stock_option_bars_delayed` | 1,846,702 | 39 | 2026-09-14 21:07:51.098599 | 2026-11-04 23:11:26.992139 |
| `stock_analyst_consensus_eodhd_history` | 3,819,015 | 26 | 2026-10-11 13:15:06.150667 | 2026-11-05 21:37:40.905752 |
| `stock_borrow_status_snapshots` | 71,418 | 41 | 2026-09-13 13:05:44.165923 | 2026-11-05 20:45:11.363637 |
| `stock_opening_window_bars` | 4,197,200 | 39 | 2026-09-14 14:50:03.895508 | 2026-11-05 20:54:25.229062 |
| `sec_filing_raw` | 3,594 | 42 | 2026-09-14 04:00:03.677668 | 2026-11-05 19:00:05.615122 |
| `sec_corporate_events` | 10 | 8 | 2026-09-16 04:00:03.807838 | 2026-11-03 19:00:04.245023 |
| `sec_ownership_snapshots` | 2,928 | 8 | 2026-10-06 04:00:05.374637 | 2026-11-04 19:00:04.566361 |
| `stock_fundamentals_daily` | 81,003 | 23 | 2026-09-11 19:20:39 | 2026-11-05 21:00:42 |
| `stock_earnings_calendar` | 13,391 | 24 | 2026-09-20 12:59:55 | 2026-11-04 23:35:54 |
| `ticker_daily_sentiment_features` | 1,077,827 | 8 | 2026-09-20 13:00:45 | 2026-10-31 02:09:51 |
| `stock_short_volume_daily` | 0 | 0 | — | — |

## Cible mesurée

Décision cinq minutes avant l’ouverture officielle de J+1, entrée de référence à cette ouverture. On compare le meilleur parcours LONG et SHORT pendant toutes les H séances, avant le stop propre à chaque sens de 10 %. Un ordre inconnu des hauts/bas le jour du stop produit des bornes ; une direction ambiguë n’est pas forcée. Des mesures sans stop et sur le signe de la clôture H sont conservées comme cibles distinctes. Aucun maximum futur n’est utilisé comme prix de vente réalisable.

Une fenêtre doit être entièrement arrivée à maturité et disposer de cours valides, non remplis, d’identité stable et ajustés des splits. Priorité à la ligne entière du fournisseur configuré, sans mélange des champs EODHD/SIP. Les ruptures d’identité recensées sont exclues. Les derniers cours disponibles sont des versions actuelles de la base, pas une certification de leur disponibilité historique.

## Résultat principal à H5 : classements déjà disponibles avant décision

AUC moyenne des séances comprenant au moins quatre observations valides et les deux directions. 0,50 correspond à une absence de pouvoir de classement. Le nombre de couples valides peut dépasser celui des couples utilisés pour l’AUC : les petites séances ou à une seule classe restent comptées mais sans AUC quotidienne.

| Signal | TOP10 AUC / couples valides / dates informatives | TOP20 | TOP50 |
|---|---|---|---|
| Volume CALL–PUT | 0.289 / 21 / 2 | 0.370 / 51 / 3 | 0.479 / 114 / 5 |
| Open interest CALL–PUT | 0.375 / 20 / 2 | 0.304 / 48 / 2 | 0.461 / 110 / 5 |
| Mélange options 50/50 | 0.350 / 15 / 2 | 0.281 / 30 / 2 | 0.438 / 78 / 5 |
| Révisions EPS 30 jours | 0.415 / 39 / 4 | 0.470 / 88 / 5 | 0.362 / 231 / 6 |
| EPS actuel vs point J−30 du fournisseur | 0.438 / 39 / 4 | 0.460 / 88 / 5 | 0.415 / 230 / 6 |
| Variation revenus réellement observée | 0.504 / 50 / 5 | 0.491 / 97 / 5 | 0.481 / 235 / 6 |
| Variation EPS réellement observée | 0.475 / 34 / 4 | 0.466 / 80 / 5 | 0.476 / 212 / 6 |
| Options + révisions EPS, 50/50 | 0.125 / 12 / 1 | 0.157 / 27 / 2 | 0.417 / 75 / 5 |

Le mélange options TOP20 a 30 issues valides sur 19 sociétés et trois dates, dont seulement deux dates permettent une AUC. Le filtre de production exact (moitié supérieure, score strictement >0,50) retient 33 signaux récents ; 19 sont encore non mûrs et deux ont des cours non qualifiés. Sur les 12 restantes, une seule a un parcours dominé par LONG (8,33 %), contre 16,67 % dans les 30 cas couverts des mêmes dates. **Ce ne sont pas des taux de trades gagnants**, et quelques séances fortement corrélées ne permettent pas de condamner définitivement le signal. Elles ne confirment toutefois pas le filtre.

Le bon ancien résultat options provient surtout de septembre reconstruit : tous cas confondus, le mélange TOP20 affiche AUC H5 0,741, H10 0,734, H15/H20 0,610. Ces chiffres ne constituent pas une validation prospective. Sur les dates déjà observables avant entrée : H5 0,281 ; aucun cas options TOP20 mûr à H10/H15/H20. TOP50 ne compte que cinq issues options à H10, sur une date, AUC 0,333. H15/H20 récents : aucun cas mûr.

Le contrôle sans chevauchement réduit encore l’échantillon : pour options TOP20 H5, une seule date avec 11 observations, AUC groupée 0,396. La sensibilité au premier cas de chaque société donne 19 observations, AUC groupée 0,392. Les intervalles rééchantillonnés par date restent descriptifs : ils ne corrigent pas la dépendance sérielle ni les essais multiples.

## Consensus : qualité et instabilité

Les 5 782 lignes 0q exportées pour les sociétés rencontrées dans TOP50 passent le contrôle du hash du payload intégré, des valeurs normalisées et des heures de réception/run terminé. Aucune erreur de normalisation trouvée. Ce contrôle n’est pas une relecture exhaustive des enveloppes `pit_raw_payloads`.

Les données sont utilisées seulement après réception et finalisation du run, avec fraîcheur maximale de 72 h. L’ancrage 0q est choisi sur une période fiscale à ±100 jours du signal, sans comparaison entre deux périodes différentes. Pour les changements réellement observés, nombre d’analystes inchangé et au moins trois ; cela ne prouve pas que les analystes soient les mêmes. Les points EPS J−30 sont ceux présents dans le snapshot reçu, jamais rétrodatés.

EODHD ne fournit pas de base EPS GAAP/non-GAAP par ligne ni de devise dans Trends ; les dates fiscales sont normalisées. Les variations sans dimension restent des diagnostics de recherche, pas une surprise de résultats qualifiée ni des features automatiquement promues. Les révisions EPS TOP20 passent de bonnes à mauvaises séances : AUC H5 0,654 / 0,844 / 0,429 / 0,183 / 0,238 pour les signaux 16/23/26/27/28 octobre. Moyenne 0,470 : pas de stabilité. À H10, le 0,821 de l’EPS/J−30 TOP20 repose seulement sur 16 observations d’une date. H15/H20 : pas d’issues consensus mûres.

La combinaison est comparée sur les mêmes cas : options + révisions TOP20 H5, 27 observations, deux dates informatives. AUC options 0,180, révisions 0,367, mélange 0,157. Ajouter le consensus ne montre pas d’amélioration sur cette intersection. Pas de recherche de poids ni d’inversion du score après constat.

## Autres collectes

- News/sentiment : les features sont mutables. Seules les lignes dont la dernière modification précède la décision sont admises. TOP20 H5 : 11 observations sur une date, AUC 0,600 en J et 0,700 sur trois jours, dix LONG sur onze au départ. Cette apparence favorable est trop petite pour conclure ; les recalculs plus tardifs ne sont pas antidatés.
- Borrow : statuts shortable/easy-to-borrow utiles à l’exécution, sans frais de prêt ni pression vendeuse signée ; aucune direction artificiellement attribuée à ces booléens.
- SEC : dépôts présents mais seulement dix événements normalisés sur le périmètre et la période. La présence d’un dépôt ne suffit pas à déterminer une surprise ou une guidance nouvelle. Pas de score directionnel inventé.
- Calendrier des résultats, fondamentaux/capitalisations, macro : contexte et risque ; aucune nouvelle règle directionnelle choisie après observation des rendements. La macro commune à une date ne classe pas les titres de la même séance.
- Opening-window : quatre millions de lignes ne représentent pas autant d’événements indépendants. Ces données arrivent pendant/après l’ouverture ; elles ne sont pas injectées dans une décision antérieure à l’ouverture.
- Short volume : aucune ligne récente dans le périmètre ; pas de score de substitution.

## Conclusion et reproduction

Continuer à archiver sans modifier les seuils sur ce petit échantillon. L’audit actualisé ne justifie ni un nouveau filtre directionnel ni un entraînement sur un mois. Les prochains résultats utiles sont la maturation des cas récents et leur évaluation séparée, avec les mêmes règles figées. Aucun batch ni ordre n’est lancé par l’audit.

Artifacts : `artifacts/research/us_collected_directional_refresh/20261105-v2/`. Résultat final : `analysis-v2/report.json`, tableau synthétique `analysis-v2/summary.csv`, décisions/scorings `analysis-v2/top10-scores.csv`, `top20-scores.csv`, `top50-scores.csv`, chemins complets dans les fichiers `*-paths.parquet`. `analysis-v1` est une sortie intermédiaire conservée ; `analysis-v2` ajoute le filtre exact et les comparaisons à couverture commune.

Contrôles : 41 tests ciblés réussis ; 710 couples de features identiques à la définition de production. Recalcul hors ligne de 88 AUC par comparaisons de paires, écart maximal 2,22×10⁻¹⁶ ; 20 parcours recalculés ; 12 fichiers finaux scellés vérifiés. Relecture du même assistant, pas une revue humaine indépendante. Aucun téléchargement fournisseur, appel LLM, fit, inférence nouvelle, écriture SQL, ordre ou changement de production.

Commandes :

```powershell
python -m scripts.research.us_collected_directional_refresh_20261105 --phase inventory --output <nouveau-dossier>
python -m scripts.research.us_collected_directional_refresh_20261105 --phase snapshot --output <meme-dossier>
python -m scripts.research.us_collected_directional_metrics_20261105 --snapshot <meme-dossier>
```

Les dossiers sont exclusifs ; aucune sortie scellée n’est écrasée. Les anciennes sources référencées par le protocole initial d’inventaire ont ensuite évolué pendant la construction du script ; le protocole de snapshot conserve les empreintes exactes du code de capture utilisé.
