# Relance PAPER des étapes 11 et 12 — 30 octobre 2026

Demande utilisateur : compte `default`, puis les autres comptes papier.
Séance signal : 29/10/2026. Sélection : BAND, COHU, UCTT, SIMO.

## Résultat final vérifié

| Compte | Capital broker utilisé | Risque | Exécution |
| --- | ---: | --- | --- |
| default | 1 940,70 $ | 0 accepté, 4 refus pour sizing insuffisant | aucune cible, étape 12 terminée sans nouvel achat |
| test1 | 57 013,40 $ | 0 accepté ; 2 refus pour concentration du facteur marché à 61,1 % contre 60 %, 2 pour nombre de titres par secteur | aucune cible, étape 12 terminée sans nouvel achat |
| test2 | 61 791,24 $ | 4 acceptés | 3 ordres limites acceptés par Alpaca, aucun rempli à la vérification |

Ordres d'achat de test2 : BAND 55 à limite 53,16 $, COHU 56 à 53,45 $,
SIMO 14 à 227,97 $. UCTT (53 actions proposées) reste bloqué lors de la
revalidation native avant envoi : `Native correlation cap blocks candidate`.
Les ordres acceptés sont en attente, leur exécution à l'ouverture n'est pas garantie.

Les trois watchers sont vérifiés sains. Politique Winner figée des nouvelles
campagnes : entrée standard sans confirmation, quantité entière, fraction
initiale 1, SL 5 %, TP 18 %, aucun trailing ni renforcement, 20 séances de
détention puis sortie à l'ouverture suivante. Les paramètres des anciennes
campagnes restent inchangés.

## Préparation et incidents résolus

Un nouvel univers a été publié avec `selector_earnings_blackout_days=-1` :
`universe-7de5c544f84742268185aa6dcab4aa87`, 1 537 tradables / 1 790 titres.
Les quatre candidats sont tradables, flags earnings à zéro. Nouvelle sélection
partagée `opt-f0c25d0c946e4178b97617c27b916e02`, sans nouvel appel Oracle ni LLM.
Les anciens résultats et claims ont été conservés.

Une première tentative a échoué avant publication du risque : bougie BAND du
18/06/2026 à volume nul côté EODHD. Une requête historique Alpaca SIP confirme
les mêmes OHLC et un volume de 1 997 939. L'original complet est archivé ; la
ligne corrigée porte la source `alpaca_sip`, sans attribuer ce volume à EODHD.
Les facteurs ont été recalculés et sont qualifiés pour les quatre candidats.

Les presets de sizing ont été résolus avec l'equity broker de chaque compte,
sans reprendre le secours à 100 000 $ du vieux plan. Kelly reste désactivé car
le rang Oracle d'amplitude n'est pas une probabilité directionnelle calibrée.
Les services watchers obsolètes ont été redémarrés après vérification du PID
de heartbeat et, sur Windows, de sa filiation avec le lanceur venv. Les ordres
broker n'ont pas été supprimés pendant cette opération.

Les notifications email échouent séparément sur le certificat TLS SMTP.
Le refus SIP temps réel 403 est encore journalisé par l'enrichissement de
l'étape 12 ; il n'a pas empêché les trois ordres standards, le contrôle de quote
ayant été explicitement désactivé dans cette politique. Aucun contournement TLS
ni désactivation des autres limites de risque n'a été ajouté.

## Preuves

- Bilan final et confirmation broker :
  `artifacts/operations/options_accounts_blackout_disabled/20261030T065342Z-9f5fca31/summary.json`
  et `final_verification.json` ; sous-dossiers par compte pour les workflows,
  presets de sizing, redémarrages de watchers et confirmations.
- Correction BAND :
  `artifacts/operations/options_accounts_blackout_disabled/20261030T064720Z-153f42a3/`
  (`band_original_daily_row.json`, `band_sip_response.json`, `factor_repair.json`).
- Risques finaux : default `7af26f73aa1049d3`, test1 `cba754fcfac240de`,
  test2 `4b609d460d6a4881`.
- Exécution test2 : `369b5badd7c64388`.
