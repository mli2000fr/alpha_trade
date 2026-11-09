# Winner continu 2021–2026 avec six modèles annuels

Demande : un portefeuille unique du1er janvier2021 au1er octobre2026,4 000 USD
au départ, avec les modèles correspondant aux six backtests IHM transmis.

## Mapping des modèles

| Année des entrées | Run source | Batch | Début / fin du training |
| --- | --- | --- | --- |
| 2021 | 20261108_090441_57f9e2b2 | model-factory-20261107222539-837309 | 2014-01-01 / 2020-12-31 |
| 2022 | 20261108_091552_f146212e | model-factory-20261107222557-280d86 | 2015-01-01 / 2021-12-31 |
| 2023 | 20261108_093814_765b1b66 | model-factory-20261107222607-f44095 | 2016-01-01 / 2022-12-31 |
| 2024 | 20261108_094643_52aa43f9 | model-factory-20261107222618-89a4d2 | 2017-01-01 / 2023-12-31 |
| 2025 | 20261107_225127_babce5b8 | model-factory-20261106203103-91b063 | 2018-01-01 / 2024-12-31 |
| 2026, jusqu'au01/10 | 20261108_101309_93f8fb1b | model-factory-20261107222627-db80b0 | 2019-01-01 / 2025-12-31 |

Tous sont des bundles Oracle parcours H10, univers1 790, LONG/SHORT par titre.
La sélection et le replay restent LONG uniquement. Les empreintes des modèles,
des scores Oracle et des branches annuelles sont contrôlées ; aucun entraînement
ou calcul de nouvelles prédictions n'est lancé.

Le mapping concerne **l'année d'entrée J+1** : le premier signal du run2022
est le31/12/2021, pour une entrée le03/01/2022. Ce signal utilise le batch
du run2022, tout en conservant les exigences de disponibilité causale des poids
du fold Oracle et du modèle per-symbol annuel. Il ne faut pas concaténer les
scores en choisissant simplement le batch selon l'année du signal J.

## Conditions communes vérifiées

- Capital initial4 000 USD ; compte margin, exposition brute maximale2×.
- TOP10 LONG per-symbol ; score strictement >0,60 et AUC calibration ≥0,60.
- Risque1,25 % par entrée, poids maximal20 %,20 positions, minimum50 USD,
  quantités entières, position complète, aucun renforcement.
- Entrée au daily open J+1, sans confirmation5m ; SL5 %, sans TP ni trailing,
  dix séances de détention puis open11.
- B4/DD15 et perte quotidienne3 % actifs, liquidation50 % ; DD15 est un
  seuil de réaction et non un plafond garanti.
- Frais8 points de base par opération et financement6,5 % annuel.
- Mêmes limites de répétition et paramètres de risque que les six protocoles,
  aucun filtre options/GPT, aucun contrôle factoriel.

**Périmètre confirmé par l'utilisateur** : TOP20 % Oracle sur toutes les années,
soit 358 candidats sur l'univers de 1 790 titres, puis TOP10 LONG per-symbol.
Les runs sources 2021–2025 appliquaient déjà cette règle ; celui de 2026
prenait seulement TOP20 titres. Sa sélection est donc recalculée depuis les
scores archivés, sans nouvelle prédiction ni entraînement.
`replay-request.json` a été passé à `uniform20pct` le 08/11/2026 à
10:32:39 UTC, avant le démarrage du replay. La demande précédente est conservée
dans `replay-request.before-user-uniform20pct.json`. Le gel des prix inclut déjà
les deux périmètres et n'a pas besoin de recommencer.
La sélection uniforme comprend 5 606 candidatures, dont 1 078 en 2026,
avant les contrôles de risque et de capital : ce ne sont pas des trades exécutés.
Aucun rendement n'est déduit du produit des performances annuelles.

## Portefeuille et données

Un seul appel au moteur natif sur toute la période : capital, cash, positions,
âge réel de détention, financement, liquidations, état B4, DD et exclusions
temporaires par titre traversent les changements d'année. Aucun retour à4 000 $
au1er janvier, aucune liquidation annuelle artificielle. Les positions déjà
ouvertes conservent leurs protections et leur horizon d'origine.

Lecture SQL seulement pour figer les prix et opérations sur titres déjà stockés.
Préférence daily EODHD puis SIP, mêmes règles de qualification que les runs IHM.
Archives5m SIP régulières, sans téléchargement. Les lacunes restent des lacunes :
protections daily prudentes lorsqu'une séance5m est incomplète, sans exclusion
fondée sur la disponibilité future des bougies. Secteurs actuels, non PIT.

Programme : `scripts/research/us_winner_continuous_annual_models_20261108.py`.
Dossier actif : `artifacts/research/us_winner_continuous_annual_models/20261108-v6`.
Archives précédentes conservées dans `20261108-v2` et `20261108-v3`.
Trois tests couvrent les tailles de pool, les frontières annuelles signal/entrée
et le refus de fusionner des conditions de portefeuille différentes.

Première tentative v1 arrêtée avant toute lecture SQL : les AUC du modèle2025
sont dans son diagnostic complémentaire vérifié, pas dans son ancien manifeste.
v2 utilise le même lecteur AUC que l'IHM et vérifie les diagnostics correspondants ;
le contrôle n'est pas désactivé. La sélection enregistrée de chaque run doit
être reproduite avant toute simulation continue.

## Suivi et sorties

`progress.json` indique la vérification des modèles, le gel des prix puis les
séances simulées. `protocol.json` et `inputs/manifest.json` scellent sources,
mapping et prix. Le replay demandé sera dans `continuous-uniform20pct`.
Sorties : bilan global,
bilan annuel du même portefeuille, trades, événements, capital quotidien/5m et
état du risque. Les rendements annuels utilisent le capital effectivement
hérité de l'année précédente ; les trades sont attribués à leur année de sortie.

Statut initial : préparation des entrées en cours. Étude exploratoire, sans
certification PIT complète ni parité live. Aucun ordre ou paramètre de
production modifié.

## Reprise après volume nul, 8 novembre

v2 s'est arrêté le 18 juin 2026 pour TPB : les prix figés avant le correctif
rejetaient ses OHLC parce que le volume EODHD vaut zéro. Le lecteur daily
qualifie maintenant les prix séparément, sans changer le volume ni inventer
de bougies. Voir `doc/operations/winner_daily_volume_nul_20261108.md`.

v4 ajoute 125 lignes OHLC canoniques valides à volume nul, lues dans une
transaction SQL READ ONLY. Toutes les lignes initiales ont été comparées
champ par champ et restent identiques. Les autres entrées figées sont
réutilisées avec leurs empreintes exactes. Aucune nouvelle prédiction,
collecte fournisseur ou écriture SQL. La différence de code de fond est limitée
au lecteur daily ; les autres différences d'empreinte sont exclusivement des
fins de ligne Windows, vérifiées sur les octets normalisés.

`added-zero-volume-daily-prices.csv`, `protocol.json` et `inputs/manifest.json`
documentent la correction. v3 est une préparation interrompue avant la lecture
des prix par le garde SQL ; v4 a été scellé après correction de la génération
du manifeste. Le portefeuille v4 est rejoué depuis 2021, faute de checkpoint
complet du book et de B4 permettant une reprise exacte en juin 2026.
Commande :
`python -m scripts.research.us_winner_continuous_annual_models_20261108 replay --output-dir artifacts/research/us_winner_continuous_annual_models/20261108-v4 --selection-policy uniform20pct`.

Statut v4 au lancement : replay en cours, aucun résultat final publié.

## Registre de marchés figé — reprise v6

v4 s'est arrêté après le14/02/2025 (1 035 séances) pendant le suivi d'EGO :
« Le registre de marchés est vide ». Les fichiers étaient présents et valides
à l'inspection ; les helpers rechargeaient le registre depuis le disque à
chaque contrôle d'échéance. Le nouveau replay valide et archive le registre
au départ puis le conserve dans une portée locale pendant toute la simulation.
Les contextes US et la base compatible restent contrôlés, avec calendrier officiel.
La cause système exacte de la lecture vide reste inconnue.

67 tests passent, dont panne simulée du registre après démarrage avec trades et
capital identiques. Le témoin réel2025 reproduit les18 indicateurs de référence
(+6,89884 %, DD−10,85603 %,59 trades). Aucun autre changement financier.
v6 réutilise les mêmes prix et signaux scellés que v4, sans SQL, téléchargement,
inférence ou ordre. Elle repart du début pour reconstruire exactement le book,
les positions, les frais et B4. v5 est une préparation interrompue sur un refus
Windows de création de lien ; les entrées v6 sont copiées lorsque nécessaire.

Programme : `scripts/research/us_winner_continuous_registry_recovery_20261108.py`.
Journal : `artifacts/research/us_winner_continuous_annual_models/registry-recovery-v6.log`.
Protocole technique : `doc/operations/winner_registre_marche_fige_20261108.md`.
Statut : replay v6 terminé le08/11/2026 à15h15 Europe/Paris. Les1 443 séances
ont été simulées. `COMPLETED_EXPLORATORY` au niveau du traitement,
`INCOMPLETE_COVERAGE` au niveau des données intraday.

## Résultat du portefeuille continu v6

Capital initial4 000 USD, final6 186,50 USD :+2 186,50 USD, soit+54,66 %.
DD maximal−29,65 %.1 254 trades clôturés,485 gagnants et769 perdants,
taux gagnant38,68 %. Capital engagé moyen3 229,12 USD, exposition moyenne
57,36 % du capital courant, maximum engagé15 266,35 USD. Frais1 123,21 USD
et intérêts de marge221,97 USD inclus.

| Année | Capital hérité USD | Capital final valorisé USD | Rendement de l'année | Gagnants / trades clôturés |
| --- | ---: | ---: | ---: | ---: |
| 2021 | 4 000,00 | 4 297,85 | +7,45 % | 47/136 |
| 2022 | 4 297,85 | 4 306,33 | +0,20 % | 44/139 |
| 2023 | 4 306,33 | 5 358,15 | +24,42 % | 48/108 |
| 2024 | 5 358,15 | 5 311,08 | −0,88 % | 121/294 |
| 2025 | 5 311,08 | 5 946,24 | +11,96 % | 150/348 |
| 2026 au01/10 | 5 946,24 | 6 186,50 | +4,04 % | 75/229 |

Ce sont les années du même portefeuille, avec capital, positions et état du
risque hérités. Ce ne sont pas les six tests annuels repartant chacun de4 000 USD.
DD15/B4 déclenche les réactions prévues, dont liquidation50 %, et ne garantit
pas une perte maximale de15 %. Aucune remise à zéro annuelle du DD.

3 719 couples date/symbole signalent des lacunes de couverture, avec les
protections OHLC journalières prévues par le protocole ; aucun parcours5m n'a
été inventé. Secteurs actuels et données non certifiées PIT : étude exploratoire,
pas une reproduction intégrale des conditions live.

Sorties : `continuous-uniform20pct/report.json`, `annual-summary.csv`,
`trades.csv`, `events.csv`, `equity-daily.csv`, `equity-5m.parquet`, `risk-5m.csv`.

## Consultation dans la page Backtest

Résultat enregistré dans l'historique IHM, sans nouvelle simulation :
`20261108_continu_2021_2026_v6`, libellé « Continu 2021–2026 — modèles annuels ».
Dates01/01/2021–01/10/2026, badge orange « Terminé — couverture incomplète ».
L'heure de départ/fin reste celle du replay, pas celle de l'import.

Sélectionner ce run dans « Run à inspecter », puis activer « Charger le résumé
détaillé et les artefacts du run sélectionné ». La page propose les indicateurs,
le capital engagé moyen, la courbe, les trades et un bloc des résultats annuels
du même portefeuille avec les six modèles utilisés.

Copies de consultation dans
`artifacts/ihm_backtesting_runs/run/20261108_continu_2021_2026_v6/artifacts`.
`import.json` conserve l'origine et les empreintes des fichiers. Une suppression
depuis l'IHM ne supprime pas les archives de recherche. Import idempotent,
13 tests passants et lecture réelle par les lecteurs de la page vérifiée :
1 443 points de capital,1 254 trades,6 années, chiffres financiers identiques.
Programme d'import : `scripts/research/register_continuous_backtest_20261108.py`.

Le coordinateur local `scripts/research/us_winner_continuous_annual_models_followup.py`
attend le manifeste complet des entrées puis lance le replay choisi. Il ne
réessaie pas automatiquement une erreur de préparation ou de simulation et ne
fait aucun appel fournisseur/broker. Journaux dans `coordinator/`, suivi du
replay dans le `progress.json` global. Il s'agit du traitement de cette
simulation précise, sans automatisation récurrente.
