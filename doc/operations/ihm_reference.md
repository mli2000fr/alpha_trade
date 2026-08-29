# IHM Streamlit — architecture, orchestration et extension

Retour : [IHM et opérations](../16_ihm_et_operations.md)

## Rôle et frontières

L’IHM est une console locale d’exploitation. Elle consulte l’état du système, prépare des options, lance les commandes publiques du projet et suit leurs sorties. Elle ne remplace ni les règles métier, ni leurs validations, ni leurs journaux d’audit.

- `ihm/pages/` contient le rendu et les interactions ;
- `ihm/components/` contient les composants réutilisables ;
- `ihm/services/` charge les données, traduit les options et supervise les processus ;
- les packages métier restent seuls responsables des calculs, contrôles et écritures.

Une règle de risque, de sélection ou d’exécution ne doit jamais exister uniquement dans Streamlit. La page transmet une option au backend canonique, puis présente son résultat.

## Cycle de démarrage

`ihm/app.py` réalise la configuration Streamlit, l’initialisation des métriques locales, l’application du thème, le contrôle d’accès éventuel, la construction de la navigation, la résolution du compte et le rendu de la page active.

Si `IHM_AUTH_TOKEN` est défini, `render_auth_gate()` conserve l’état authentifié dans la session. Une bannière signale également une écoute réseau non locale non protégée. Voir [supervision et sécurité](supervision_et_securite.md).

La navigation est construite explicitement par sections et boutons. Le mode avancé expose des informations de contexte comme le DSN non secret, le thème et certains réglages d’exploitation.

## Contexte de compte

L’IHM charge `AccountRegistry` et propose les comptes Alpaca configurés. Le compte choisi est transmis aux étapes dont `account_usage="alpaca"`, notamment risque, exécution et corporate actions.

Le registre accepte, dans l’ordre : `config.yaml/alpaca.accounts`, les paires `ALPACA_<ID>_API_KEY` / `ALPACA_<ID>_SECRET_KEY`, puis le fallback `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` enregistré sous `default`.

Une entrée YAML incomplète est ignorée. Seuls les modes `paper` et `live` sont valides. L’absence d’`account_id` conserve un fallback vers le premier compte pour rétrocompatibilité ; toute nouvelle fonction financière doit transporter l’identifiant explicitement.

## Modèle du pipeline

`ihm/services/pipeline_runner.py` est la référence de l’orchestration affichée. Chaque `PipelineStepDefinition` contient une clé, un numéro, un nom, une description, les tables, les dépendances et l’usage éventuel d’un compte.

| Étape | Clé | Fonction | Dépendance |
|---:|---|---|---|
| 1 | `import_alpaca_bar` | import incrémental via le provider configuré | aucune |
| 2 | `data_sanitizer_daily` | nettoyage et contrôles | 1 |
| 3 | `stock_screener` | scores de liquidité, force relative et historique | 2 |
| 4 | `sync_latest_quotes` | snapshot quotes/spread | 3 |
| 5 | `sync_earnings_calendar` | calendrier earnings | 4 |
| 6 | `publish_tradable_universe` | univers PIT full atomique | 5 |
| 7 | `alpha_scanner` | scoring avancé et sélection | 6 |
| 8 | `sentiment_pipeline` | ingestion et features sentiment | 6 |
| 9 | `signal_aggregator` | agrégation quant/sentiment/secteur | 8 |
| T1 | `ml_train` | entraînement et publication d’un champion | hors quotidien |
| 10 | `ml_predict` | inférence avec champion publié | 9 + champion |
| 11 | `risk_management` | sélection, sizing et contraintes | 9 + 10 |
| 12 | `execution` | ordres, fills, positions, réconciliation et TCA | 11 |
| 13 | `corporate_actions_sync` | collecte splits/dividendes | 12 |
| 14 | `corporate_actions_apply` | application et ledger cash | 13 |

Les étapes auxiliaires `B1 import_alpaca_assets`, `B2 update_sector` et `B3 eodhd_backfill_history` servent au bootstrap ou à la maintenance.

Le nom historique `import_alpaca_bar` ne fixe pas le provider. La commande et le libellé effectifs dépendent de `market_data.bars_provider`; le flux non sélectionné devient un no-op contrôlé.

## Options et commandes

Les widgets alimentent les dataclasses du runner, puis `build_pipeline_command(step_key, options)` produit une liste d’arguments, pas une commande libre concaténée. `build_subprocess_env()` complète l’environnement.

Les options couvrent date, historique, provider, compte, écriture/dry-run, sentiment, batch/horizon ML, entraînement, risque, exécution, paper/live, watcher et corporate actions. La dataclass vérifie certaines cohérences ; le backend appelé conserve ses propres validations.

La valeur affichée n’est pas une preuve de la configuration exécutée. Pour l’audit, conserver commande normalisée, compte, date, run id et fingerprints du module métier.

## Exécution et suivi

Une étape peut être lancée seule ou dans un workflow. Le résultat structuré conserve clé, commande, code retour, stdout, stderr, durée, date et compte. `process_registry.py` gère historique, fichiers de sortie, snapshots live et progression détectée dans les logs.

Un processus terminé n’est pas nécessairement un succès métier : rapprocher code retour, summary et tables attendues. Une sortie sans summary final est suspecte. Les artefacts sont sous `artifacts/ihm_pipeline_runs/`; leur rotation ne remplace pas l’audit en base.

## Verrou pipeline/backtest

`pipeline_lock.py` empêche workflow pipeline et backtest de partager simultanément `stock_scores`, `stock_bars_daily` et les artefacts ML. Les locks JSON résident dans `artifacts/ihm_pipeline_runs/.locks/` et contiennent scope, owner, run id, PID et date.

Le verrou est inter-processus avec mutex local. PID mort, fichier corrompu, PID réutilisé ou verrou orphelin peuvent être récupérés. `release_lock` est idempotent. Ne pas supprimer manuellement un lock avant vérification du PID et du run.

## Cache, erreurs et sécurité

Les services de lecture peuvent utiliser un cache Streamlit avec TTL. Après mutation, invalider la ressource concernée ou proposer un rafraîchissement. Pour une divergence, comparer timestamp du cache, date métier, dernière écriture DB et run id.

Une page opérationnelle affiche date, compte, mode, provider, run id, statut, étape, code retour et erreur actionnable. Une liste vide doit être distinguée d’un échec. Les exceptions inattendues sont interceptées au rendu, mais restent journalisées.

Secrets, headers, DSN complet et payload broker brut ne doivent jamais être rendus. Les actions live, destructives ou financières conservent confirmations et préflights backend.

## Ajouter une page

1. Identifier l’API métier ou la commande publique.
2. Créer un service de traduction ; ne pas placer le SQL métier dans le composant.
3. Définir compte, date et provider.
4. Ajouter la page à la navigation explicite de `app.py`.
5. Gérer chargement, vide, partiel, stale et erreur séparément.
6. Borner les entrées et masquer les secrets.
7. Tester le service sans dépendre d’un broker réel.
8. Documenter tables lues, commandes et effets de bord.

## Diagnostic rapide

| Symptôme | Vérifications |
|---|---|
| bouton sans effet | validation, lock, registre processus, stderr |
| étape bloquée | PID, dernière sortie, timeout provider/DB, summary |
| mauvais compte | `account_id` dans options, commande et tables |
| données anciennes | date métier, cache, dernier run, timezone |
| workflow refusé | lock pipeline/backtest, owner et run id |
| résultat incohérent | commande effective, config/fingerprint, summary |

