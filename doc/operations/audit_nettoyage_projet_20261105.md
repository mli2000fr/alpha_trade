# Inspection et plan de nettoyage de F:\projets

**Exécution après Go :** lot A terminé le 5 novembre 2026 à 23:59 Paris :
822 cibles, 62 593 fichiers et **8 097 113 844 octets supprimés**, zéro erreur.
Rapport : `artifacts/operations/workspace_cleanup_audit/20261105-v1/nettoyage-lot-a/report.json`.
Les bases, poids de modèles, résultats de backtests et archives FIRDS ont été
conservés. Les tests de l'import FIRDS ont ensuite recréé quelques caches et
temporaires ; ce bilan indique les suppressions effectuées, pas une promesse
sur une taille de cache future. L'import SQL FIRDS est une opération distincte,
autorisée ensuite : [stockage et suivi](../fr/import_archives_firds_sql_20261106.md).

Le reste du document conserve l'inspection **avant suppression**.

Inventaire commencé le **05/11/2026 23:38, heure de Paris**. **Aucune suppression, aucun déplacement, aucune modification des bases ou des paramètres de trading.** Ce document constitue une proposition soumise au Go de l’utilisateur.

Le projet contient **210,240 Go** de fichiers (195.80 Gio), **1,214,527 fichiers** et **227,254 sous-dossiers**. Il s’agit de tailles logiques : l’espace réellement libéré dépend de l’allocation et de la compression du volume. Le disque F disposait encore de 1.48 To libres au scan.

## Conclusion proposée

Valider d’abord le **lot A : 8,097 Go**, 62,593 fichiers dans 822 cibles explicites. Ce lot retire des caches et sorties techniques recréables, sans supprimer de données SQL, de modèle, de résultat économique ni de source du projet. Les comptes rendus de tests placés à la racine des dossiers temporaires sont conservés. Le prochain chargement d’un backtest devra relire ses données en base et pourra durer plus longtemps.

La majeure partie des 210 Go ne peut pas être déclarée obsolète simplement parce qu’elle est ancienne ou ignorée par Git : elle contient les jeux de recherche, les archives publiques originales et les entrées des modèles. Un nettoyage plus important nécessite d’accepter explicitement des pertes de reproduction, ou d’archiver ailleurs.

## 1. Répartition de l’espace

| Dossier | Taille logique | Diagnostic |
|---|---:|---|
| [artifacts/research](F:/projets/artifacts/research) | 72,534 Go | Résultats, données et preuves de nombreuses expériences ; dépendances croisées. |
| [artifacts/fr](F:/projets/artifacts/fr) | 62,526 Go | Dont 59,9 Go de ZIP historiques FIRDS ; pas de copie SQL intégrale démontrée. |
| [artifacts/models](F:/projets/artifacts/models) | 18,568 Go | Dix modèles terminés ; poids, contrats et données d’entraînement. |
| [artifacts/backtesting](F:/projets/artifacts/backtesting) | 15,152 Go | Résultats et traces historiques, dont 2,34 Go de logs à la racine. |
| [artifacts/intraday_backfill](F:/projets/artifacts/intraday_backfill) | 12,804 Go | Bruts et checkpoints de reprises ; plusieurs états RUNNING hérités. |
| [artifacts/sec_cache](F:/projets/artifacts/sec_cache) | 11,627 Go | Entrées SEC requises par la reconstruction historique de capitalisation. |
| [artifacts/backtest_cache](F:/projets/artifacts/backtest_cache) | 7,265 Go | Caches Parquet recréables ; pickle non qualifié conservé. |
| [.venv](F:/projets/.venv) | 6,069 Go | Environnement Python utilisé : conserver. |
| [artifacts/operations](F:/projets/artifacts/operations) | 1,183 Go | Reçus d’opérations, interventions et migrations : conserver par défaut. |
| [catboost_info](F:/projets/catboost_info) | 0,359 Go | Journaux d’entraînement, pas les fichiers de modèles. |
| [htmlcov](F:/projets/htmlcov) | 0,301 Go | Rapport HTML généré par les tests. |
| [.git](F:/projets/.git) | 0,186 Go | Historique Git et métadonnées du dépôt : conserver. |

## 2. Lot A — suppression recommandée après Go

Les sous-dossiers de tests et les fichiers listés sont détaillés dans `candidats_suppression_sure.csv` et `plan_suppression_sure.json`. Aucune cible de ce lot ne contient un fichier suivi par Git au moment de l’inspection.

| Catégorie | Cibles | Taille | Conséquence attendue |
|---|---|---:|---|
| Cache Parquet backtests | 80 fichiers `.parquet` de `artifacts/backtest_cache/` | 7,235 Go | Relecture SQL au prochain besoin ; pas de téléchargement fournisseur déclenché par la suppression elle-même. |
| Journaux CatBoost | `catboost_info/` | 0,359 Go | Perte des courbes et journaux d’entraînement anciens ; les poids sont stockés ailleurs. |
| Rapports de couverture | `htmlcov/`, `.coverage`, `coverage.json` | 0,312 Go | Regénérer la couverture avant de consulter ces rapports ou de lancer `check_coverage.py`. |
| Temporaires de tests | Sous-dossiers précis de `artifacts/test_tmp/`, `artifacts/test-tmp/`, `artifacts/tmp/` et `tmp/` | 0,115 Go | Fixtures recréées lors des prochains tests. Les reçus XML/JSON en racine et `tmp/pdfs/` sont conservés. |
| Cache Python | 75 dossiers `__pycache__` hors des données protégées et du `.venv` | 0,066 Go | Recompilation automatique du bytecode ; premier import éventuellement un peu plus lent. |
| Caches outils/tests | `.pytest_cache/`, `.ruff_cache/`, `.hypothesis/` | 0,010 Go | Les outils recréent leurs caches ; historique local des échecs/exemples mis en cache perdu. |

**Total lot A : 8,097 Go** (7.54 Gio). Aucun nettoyage du `.venv`, de Git, des fichiers de configuration ou des poids de modèles. Les répertoires parents des temporaires et leurs reçus de validation ne sont pas supprimés en bloc.

Justifications vérifiées :

- `backtesting/cache.py` et `backtesting/cli/_impl.py` utilisent `get_or_load` avec un chargeur SQL sur absence de cache. Le fichier `e34a_exits.pkl` ne relève pas de ce contrat ; il reste exclu du lot A.
- L’arbre `catboost_info` contient des `.json`, `.tsv`, `.tfevents` et quelques octets de `.tmp` ; aucun poids `.cbm`, `.pkl` ou `.ckpt` trouvé. `modelFactory/catboost_baseline.py` sauvegarde les poids via `artifact_dir`, séparément du `train_dir`.
- Les reçus `artifacts/test_tmp/winner-dd15-cycle20-global25-20261024.xml`, `short-final-qualification.xml` et les XML cités dans la documentation sous `artifacts/tmp` ne sont pas retirés.
- L’index Git a été contrôlé : aucun fichier versionné sous les cibles des caches/temporaires sélectionnés. Cette vérification sera refaite avant toute suppression.

## 3. Lot B — allègements possibles, avec impact à accepter ou contrôle restant

Ces éléments ne font **pas** partie du nettoyage « sans impact ». Ce tableau ne doit pas être ajouté au lot A implicitement. Les doublons cités plus bas sont déjà compris dans les archives de recherche.

| Piste | Volume | Impact / contrôle |
|---|---:|---|
| 41 logs à la racine de `artifacts/backtesting/` | 2,341 Go | Aucun impact attendu sur les ordres et les résultats numériques conservés, mais perte du diagnostic détaillé et d’éventuels liens de consultation ; vérifier leur absence des reçus avant suppression. |
| Dix sous-dossiers `artifacts/models/*/oracle_path/chunks/` | 16,158 Go | Predict charge les contrats/folds/poids, mais l’entraînement directionnel et plusieurs outils de recherche lisent ces chunks. Leur retrait affecterait les reprises et la reproductibilité. Conserver les modèles complets pour le lot A. |
| Sous-dossiers `raw/` des six plans intraday COMPLETED | 10,948 Go | Les bilans déclarent une persistance SQL, mais aucune comparaison exhaustive ligne par ligne avec SQL n’a été effectuée. Les bruts servent au retraitement sans API. Ne jamais supprimer `tasks/`, `plan.json`, les checkpoints ni les runs inachevés sur cette seule base. |
| `artifacts/operations/us_models_reset/20261013-v1/sql-metadata-before.json` | 0,957 Go | Ancien état avant suppression de modèles ; pas requis par Predict, mais c’est une preuve de l’intervention et potentiellement une seule copie de certaines métadonnées. |
| `artifacts/backtest_cache/e34a_exits.pkl` | 0,030 Go | Aucun consommateur nommé trouvé dans le code courant ; ce constat seul ne prouve ni sa régénération ni son inutilité. Conservé. |

### Doublons identiques prouvés par SHA-256

| Fichiers | Volume d’une copie | Constat |
|---|---:|---|
| `artifacts/research/oracle_path_lstm/20261013-v1/dataset/matrix.npy` et `20261013-v2/dataset/matrix.npy` | 3,164 Go | Strictement identiques, SHA-256 `d280ab6f9e788540a5c06d21e185960561be1f0c3053266a1e438aa15dac43b8`. |
| `artifacts/research/us_oracle_tp20_sl10_new/20261012-v5/features.parquet` et `20261012-v6/features.parquet` | 0,754 Go | Strictement identiques, SHA-256 `844b07ad753c5f312c3a6f47dbcdaecd5200b1518ce8d1ad50005b2b109bbf0b`. |

Environ **3,918 Go** de contenu est ainsi dupliqué. La version v1 du second `features.parquet`, pourtant de même taille, a une empreinte différente : elle n’est pas un doublon. Supprimer une copie identique casserait malgré tout le chemin attendu par certains scripts ou sceaux ; ces fichiers ne sont donc pas inclus dans le lot A. Une déduplication préservant les chemins serait une opération différente à qualifier.

## 4. Gros volumes à conserver dans ce nettoyage

**FIRDS historique : 59,764 Go sous `artifacts/fr/esma_firds/replay_2018/`.** Les dossiers 2018–2026 contiennent les archives officielles ZIP utilisées par les rejeux historiques. La vérification SQL en lecture seule dans `alpha_trade_fr` retrouve une tête de ressource pour `esma_firds/replay_2018/history_2026_observed_v2.json`, mais zéro tête pour les ZIP sous ce chemin. Cela ne prouve pas qu’aucun octet similaire n’existe ailleurs en SQL ; cela ne démontre surtout pas une migration intégrale de ces 59,8 Go. Les batchs FR opérationnels utilisent SQL ; les outils historiques utilisent toujours les ZIP et leurs empreintes. Ne pas supprimer ce répertoire comme un prétendu doublon de la base.

**SEC : 11,627 Go sous `artifacts/sec_cache/`, dont 11,625 Go de Company Facts.** Le nom « cache » est trompeur pour le nettoyage : `backtesting/historical_sec_capitalization.py` les lit directement hors réseau ; plusieurs audits SEC y prennent leurs entrées. Leur suppression pourrait dégrader ou bloquer les backtests avec facteur capitalisation, voire nécessiter de nouveaux appels SEC. Conserver également `company_tickers.json`.

**Recherche : 72,534 Go sous `artifacts/research/`.** Les plus gros ensembles sont `us_concentrated_replay` (12,711 Go), `oracle_path_lstm` (6,616 Go), `us_predictable_symbols` (5,800 Go), `us_winner_native_grid_2017_2026` (4,793 Go), `us_winner_global_selector` (4,154 Go). Une expérience abandonnée ou peu rentable n’implique pas que ses fichiers soient sans référence : d’autres expériences en dépendent et les documents pointent vers leurs preuves. Un retrait massif ferait perdre la possibilité de les rejouer/vérifier. Ne pas assimiler tout ce dossier à des temporaires.

**Modèles : 18,568 Go sous `artifacts/models/`.** Dix contrats terminés présents, dont les H20/H10 historiques et les cinq bundles annuels récents. Les poids, folds, profils, manifestes directionnels et contrats restent protégés, même pour un modèle qui n’est pas le modèle par défaut du pipeline. Les modèles annuels servent aux backtests.

**Reprises intraday : 12,804 Go sous `artifacts/intraday_backfill/`.** Trois dossiers ont encore un état RUNNING dans leur reçu (`intraday-6286ab46f093feadb926`, `intraday-75d9f29edb1bb670e48c`, `intraday-fbc507f68cbaf2824fe7`). Ce statut ne suffit pas à prouver qu’un processus fonctionne ; il suffit à refuser leur purge automatique. Le code relit `tasks/*.json` pour éviter les téléchargements déjà terminés, puis les `raw/*.json.gz` pour retraiter sans API. Aucun état n’a été modifié ni verrou libéré pendant cet audit.

**Traces et états opérationnels.** Conserver `artifacts/options_directional`, `artifacts/llm_directional`, les plans Winner, claims de risque/exécution, autorisations de reprise, snapshots de preuve et états de watchers. Ils servent à l’idempotence et à la qualification des ordres. Ne pas les effacer pour « réinitialiser » une exécution. Conserver `artifacts/quotes` et les dossiers de quotas/coupe-circuits fournisseur ; ils ne sont pas de simples fichiers décoratifs.

**Configuration et installation.** Conserver `.venv` (6,069 Go), `.git`, `alpha_trade.egg-info`, les variables/fichiers `.env`, les clés de `artifacts/config_vault`, `config`, `conf`, les prompts, le code, les tests et la documentation. L’absence de référence littérale à un script ou un fichier n’est pas une preuve suffisante de son inutilité : commandes CLI, imports dynamiques et tâches Windows peuvent le charger.

**Sauvegardes.** Le dossier `backups` ne contient plus de gros export T5.6 dans cette installation ; pas de gain significatif à annoncer. Aucun package de sauvegarde ni outil de restauration n’a été supprimé.

## 5. Vérifications effectuées et limites

- Parcours complet des métadonnées, sans suivre de lien/jonction ; aucun lien/jonction ni erreur de lecture signalé par le scan.
- Contrôle de cohérence : la somme des dossiers de premier niveau et des fichiers racine correspond au total récursif.
- Recherche des références dans les sources, configurations et documents ; lecture ciblée des contrats de cache, loaders de modèles, reprises intraday et stockage SQL FR.
- Contrôle de l’index Git sur les cibles proposées ; lecture des états des dix modèles et des neuf plans intraday.
- Vérification de métadonnées SQL FR en transaction READ ONLY puis rollback ; aucun chargement fournisseur, aucune écriture SQL.
- Empreintes de cinq gros fichiers comparées : deux paires identiques, une version de même taille différente.
- Recherche de processus liés au projet : aucun batch métier identifié dans les processus accessibles lors du scan. Ce n’est pas une garantie pour plus tard ; le contrôle sera refait au Go. Les états RUNNING hérités restent conservés.
- Le scan porte sur les tailles logiques des fichiers, pas sur un calcul de fragmentation/occupation NTFS. Les fichiers créés/modifiés après le scan seront revérifiés.
- Pas de prétention à une preuve formelle d’absence de dépendance sur l’ensemble du projet. Les cas non démontrés sont conservés ; les caches proposés ont un chemin explicite de régénération.

## 6. Go proposé et contrôles avant exécution

**Go recommandé : lot A uniquement, environ 8,10 Go.** Cela n’autorise pas automatiquement les éléments B ni la suppression globale de `artifacts`. Après accord : recontrôler les processus, résoudre les chemins absolus et vérifier qu’ils restent sous `F:\projets`, refuser les liens/jonctions, préserver les fichiers Git et les nouvelles données, puis consigner chaque suppression et chaque refus. Si une cible a changé ou appartient à un run actif, la laisser en place et l’indiquer au bilan. Aucune modification de schéma, aucun arrêt de service et aucune relance de collecte ne sont nécessaires pour ce lot.

Fichiers de suivi :

- `artifacts/operations/workspace_cleanup_audit/20261105-v1/inventory.json` : inventaire complet des dossiers, tailles et principaux fichiers.
- `occupation_dossiers.csv` : ventilation lisible des trois premiers niveaux.
- `plan_suppression_sure.json` : liste exacte et empreinte du lot A, avec `deletion_authorized: false`.
- `candidats_suppression_sure.csv` : les 822 cibles, taille et motif.
- `candidats_conditionnels.json` : pistes B sans autorisation de suppression.
- `selected-large-duplicates.json`, `code-references.json`, `sql-dependency-check.json`, `etats_modeles_et_backfills.json` : preuves ciblées.

L’audit lui-même a créé ces rapports et le script d’inventaire `scripts/workspace_cleanup_audit.py`. Aucun fichier préexistant n’a été supprimé ou déplacé.

## Complément après import FIRDS — 6 novembre 2026

La copie SQL des **5 671 fichiers / 59,903 Go** est maintenant terminée
et vérifiée intégralement : statut `VERIFIED_COMPLETE`, zéro erreur, neuf
archives annuelles relues uniquement depuis SQL. Les 5 665 contenus uniques
sont conservés dans les tables `fr_collection_*` de `alpha_trade_fr`.
L’évaluation antérieure « copie SQL non démontrée » décrit la situation avant
cette opération. Les ZIP n’ont pas été supprimés et certains outils historiques
hors contexte SQL les utilisent encore ; ils ne sont pas ajoutés au lot A.
La copie SQL occupe de l’espace dans MySQL, pas dans ce répertoire du projet.
[Rapport de migration](../fr/import_archives_firds_sql_20261106.md).

## Suppression FIRDS autorisée et terminée — 6 novembre 2026

À la demande suivante de l'utilisateur, les lecteurs historiques ont été
raccordés à SQL puis testés avec le dossier local réellement absent. Les
**5 671 fichiers / 59 903 375 259 octets (59,903 Go)** ont ensuite été supprimés
à **18:56:51 Europe/Paris**, séparément du lot A. Ni la base FR ni ses objets
binaires n'ont été supprimés, aucun service métier n'a été arrêté.

La copie SQL a été revérifiée avant suppression contre le manifeste inchangé.
**117 tests passent** ; le contrôle réel retrouve tous les ZIP/JSON, les
empreintes originales, les neuf historiques annuels, le même audit de lacunes
et les mêmes résultats de référence 2018. Le contrôle SQL après suppression
retrouve 5 630 ZIP, 41 JSON et la base historique de 5 604 archives.
Les réserves historiques de publication ne sont pas levées par cette opération.

Preuves : `artifacts/operations/firds_sql_removal/20261106-v1/`, dont
`removal-report.json`, `absent-local-validation/report.json`, `tests.xml` et
`post-removal-sql-check.json`. Les archives et preuves d'import dans
`artifacts/operations/firds_sql_history_import/20261105-v1` restent conservées.
La mention antérieure « outils historiques encore sur disque » décrit donc
l'état avant ce raccordement. Aucun autre lot conditionnel n'a été supprimé.
