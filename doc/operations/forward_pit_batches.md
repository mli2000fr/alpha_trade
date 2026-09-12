# Batchs de collecte Forward PIT

## Pilotage depuis l'IHM

La page **Workflow & Orchestration → Batch** constitue le catalogue opérationnel de
batch.yaml. Elle affiche pour chaque traitement sa finalité, sa priorité P0 à P4,
les tables alimentées, le calendrier configuré et l'état réel de la tâche Windows.
Elle rapproche également la dernière exécution du Planificateur avec le dernier run
présent dans pit_collection_runs (volumes demandés, reçus, persistés, alertes et
échecs). Les trois traitements historiques qui ne renseignent pas encore cette table
restent observables via leur tâche Windows et leur journal dédié.

Les boutons **Installer / réinstaller** et **Lancer maintenant** exécutent les mêmes
scripts PowerShell que l'exploitation manuelle. Un lancement depuis l'IHM est
asynchrone : quitter la page ne coupe pas le traitement. Les batchs désactivés ou en
attente de fournisseur/quota restent documentés mais leur bouton de lancement est
bloqué. Les notifications email et Telegram sont envoyées par le launcher du batch ;
la notification générique de l'IHM est neutralisée afin d'éviter un doublon.

## Objectif et contrat

Ce dispositif construit, à partir de maintenant, l’historique réellement observable par Alpha‑Trade. Il ne reconstitue pas artificiellement le passé : chaque payload reçu porte un `observed_at`, un `available_at`, un hash de contenu, un hash de schéma et l’identifiant du run. Les données normalisées conservent ce lignage.

Le code métier est dans `service/forward_pit/batch.py`. `scripts/windows/forward_pit_launcher.ps1` est uniquement un adaptateur d’exploitation Windows : lecture de `batch.yaml`, contrôle heure/jour/fuseau, mutex anti-chevauchement, journal et notification email/Telegram. Toutes les valeurs d’exploitation sont dans `batch.yaml`, jamais dans `config.yaml`.

Principes invariants :

- RAW append-only avant normalisation ;
- idempotence par clés naturelles et hash ;
- corrections conservées au lieu d’écraser l’historique source ;
- `available_at` utilisé pour les futurs joins PIT ;
- réponse globalement vide considérée comme erreur, sauf absence légitime de nouveaux filings SEC, signalée comme avertissement ;
- aucune disparition du security master ne devient automatiquement un delisting ;
- aucune source expérimentale n’est activée sans fournisseur et quota validés.
- timestamps persistés en UTC ; la date de séance reste calculée en heure New York.

## Inventaire opérationnel

| Priorité | Batch | Source | Table(s) normalisée(s) | État initial |
|---|---|---|---|---|
| P0 | `daily_bars_sync` | Business Quant `/quotes`, mode `eod` | `stock_bars_daily_versions` RAW | actif |
| P0 | `security_master_snapshot` | Nasdaq Symbol Directory quotidien, Business Quant Universe hebdomadaire | `security_master_snapshots`, `security_master_changes` | actif |
| P0 | `corporate_actions_sync` | Business Quant market-wide + Alpaca | `corporate_action_source_events` | actif |
| P0 | `sec_edgar_incremental` | SEC daily master index + submissions | `sec_filing_raw` | actif |
| P0 | `pit_data_quality_daily` | contrôles locaux | `pit_data_quality_metrics`, `pit_data_quality_issues` | actif |
| P1 | `borrow_status_snapshot` | Alpaca Assets | `stock_borrow_status_snapshots` | actif |
| P1 | `analyst_snapshot_collection` | Yahoo/yfinance | tables analystes existantes | actif, stabilisé à un passage après clôture |
| P1 | `business_quant_analyst_snapshot` | Business Quant `/estimates` | `stock_analyst_consensus_snapshots` | désactivé, décision quota requise |
| P1 | `finra_short_volume_sync` | fournisseur à arrêter | — | désactivé ; famille de contrôle déjà NO_GO |
| P2 | `oracle_options_indicative_snapshot` | Alpaca indicative | `stock_option_snapshots` | désactivé jusqu’à alimentation d’`oracle_top20.txt` |
| P2 | `official_options_nbbo_sync` | fournisseur requis | — | désactivé |
| P3 | `oracle_opening_window_sync` | Business Quant minute-bars | `stock_opening_window_bars` | désactivé jusqu’à alimentation d’`oracle_top20.txt` |
| P3 | `sec_corporate_events_normalize` | RAW SEC 8‑K/6‑K | `sec_corporate_events` | actif |
| P4 | `sec_institutional_ownership_normalize` | RAW SEC 13F/13D/13G | `sec_ownership_snapshots` | actif |
| P4 | `fred_alfred_vintage_sync` | FRED/ALFRED | `macro_vintage_observations` | actif |
| attente | `auction_imbalance_sync` | fournisseur requis | — | désactivé |
| attente | `securities_lending_sync` | fournisseur requis | — | désactivé |

Les batchs déjà présents `earnings_calendar_sync` et `market_cap_sync` sont conservés : ils ne font pas doublon. Le premier stocke calendrier/estimates/actuals d’earnings ; le second ne collecte que capitalisation et secteur via Yahoo puis Finnhub. Les états financiers historiques demeurent issus de SEC EDGAR.

## Tables et flux

```text
Fournisseur
   │
   ├── payload brut ──> pit_raw_payloads
   │                         │ hash + schema_hash + available_at
   │                         ▼
   └── normaliseur ──> tables PIT thématiques
                              │
                              ├── contrôle couverture/fraîcheur
                              ▼
                    pit_data_quality_metrics/issues

Chaque exécution ──> pit_collection_runs ──> statut + compteurs + erreur
```

La migration `0075_forward_pit_collection` crée les 16 tables du socle. Le DDL de référence indépendant est `database/sql/forward_pit/forward_pit_tables.sql`.

## Détails par famille

### Barres journalières

Business Quant est interrogé par lots de 100 symboles sur une fenêtre glissante de dix jours afin de récupérer les séances tardives et corrections. Une version différente pour un même `(provider, symbol, trade_date)` est conservée et marquée `is_correction=1`. Ces prix sont enregistrés avec `adjustment_mode=raw`. Le service refuse explicitement `canonical_upsert: true` : `stock_bars_daily` exige actuellement des prix ajustés des splits. Un canonicaliseur fondé sur les corporate actions devra être validé avant de lever ce garde-fou ; étiqueter directement ces prix `split` créerait une série incohérente. L’univers courant d’environ 2 300 titres représente environ 23 appels par passage.

### Security master

Nasdaq apporte le répertoire de cotation officiel ; Business Quant complète hebdomadairement CIK, type, classe d’actif, secteur et industrie. Le service compare le snapshot courant au snapshot précédent du même fournisseur. `NEW_SYMBOL`, `MISSING_FROM_DIRECTORY` et les changements de champs sont enregistrés avec `confirmed=0`. Une radiation doit être confirmée par corporate action ou plusieurs observations : une absence isolée n’est jamais suffisante.

### Corporate actions

Les événements Business Quant et Alpaca restent séparés par fournisseur. `conflict_group_key` rapproche les événements portant sur le même symbole, type et date sans supprimer les désaccords. Les splits, dividendes, changements de ticker, fusions, spin-offs et delistings restent donc auditables source par source.

### SEC EDGAR et normalisations

`sec_edgar_incremental` lit les daily indexes des derniers jours, ne télécharge que les accessions absentes et conserve le dépôt complet. `SEC_EDGAR_USER_AGENT` est obligatoire au format `NomApplication contact@domaine`. L’heure d’acceptation SEC est extraite du header SGML lorsqu’elle existe ; `available_at` reste l’heure réellement reçue par l’application, choix volontairement conservateur.

Les batchs P3/P4 relisent ce RAW local : aucun second téléchargement SEC. P3 extrait les items 8‑K/6‑K. P4 normalise les holdings XML embarqués des 13F et conserve une ligne de dépôt lorsque la table d’information n’est pas analysable. Les champs non fiables restent `NULL` plutôt que d’être inventés.

### Borrow, analystes, options et ouverture

Alpaca Assets permet de suivre `shortable`, `easy_to_borrow`, `marginable` et `tradable` plusieurs fois par séance. Cela ne fournit ni borrow fee, ni utilization, ni lendable supply.

Le batch analyste Yahoo existant respecte désormais `enabled: false`, distingue couverture EPS et REVENUE et ne tourne plus deux fois le même jour avec un `resume` rendant le second passage vide. Business Quant analyste est un challenger désactivé et limité à l’univers Oracle pour maîtriser le quota.

Les options Alpaca sont explicitement étiquetées `indicative`, pas OPRA/NBBO. Le pilote opening-window conserve les barres minute et reconstruit le volume minute à partir du volume cumulé. Ces deux batchs ne doivent être activés qu’après génération quotidienne de `config/univers_batch/oracle_top20.txt`.

### FRED/ALFRED

Le batch conserve pour chaque observation la valeur, `realtime_start`, `realtime_end`, la date de vintage et l’heure de réception. Les futurs datasets doivent joindre sur `available_at <= decision_time` et sélectionner le dernier vintage alors disponible ; joindre seulement sur `observation_date` créerait une fuite de révision.

## Qualité et alertes

`pit_data_quality_daily` vérifie au minimum : âge des barres Business Quant, âge du security master, âge du borrow snapshot, âge du dernier vintage macro, runs échoués sur 24 heures et couverture sur sept jours de l’univers configuré. Le seuil de couverture par défaut est 90 %. Une anomalie critique crée une ligne dans `pit_data_quality_issues`, fait échouer le batch qualité et déclenche la notification du lanceur.

Les réponses brutes permettent ensuite d’ajouter sans perte d’historique : détection de changement de schéma, volumes anormalement faibles, conflits fournisseurs, trous par symbole et contrôle de cohérence OHLC.

### Notifications de fin de batch

Tous les nouveaux batchs installés par `install_forward_pit_task.ps1` passent par le même lanceur. Après chaque exécution réelle, réussie ou échouée, celui-ci transmet le statut, le code retour, la durée et les 300 dernières lignes du run à `scripts/send_batch_email.py`. Ce notificateur appelle les deux canaux historiques :

- email via `ihm.services.email_notifier` et les variables `ALPHA_TRADE_EMAIL_*` / `ALPHA_TRADE_SMTP_*` ;
- Telegram via `service.telegram`, `TOKEN_TELEGRAM_BOT` et `TELEGRAM_CHAT_ID`.

Les notifications sont best-effort : une panne SMTP ou Telegram est journalisée mais ne transforme pas un batch métier réussi en échec. Un batch désactivé ou ignoré parce qu’une instance est déjà active ne génère pas de fausse notification de succès.

## Mise en service

1. Appliquer `alembic upgrade head` avant le premier lancement.
2. Définir `BUSINESS_QUANT_API_KEY`, les identifiants Alpaca déjà utilisés par l’application, `KEY_FRED` et `SEC_EDGAR_USER_AGENT`.
3. Vérifier les chemins `symbols_file` et laisser désactivés les pilotes marqués `PENDING_*` ou `ENABLE_AFTER_*`.
4. Tester un batch manuellement avec :

   `powershell -ExecutionPolicy Bypass -File .\scripts\windows\forward_pit_launcher.ps1 -BatchName daily_bars_sync -Force -DryRun`

5. Installer un batch :

   `powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_forward_pit_task.ps1 -BatchName daily_bars_sync`

6. Installer tous les nouveaux batchs actifs :

   `powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_all_forward_pit_tasks.ps1`

Le mode `-DryRun` appelle le fournisseur et valide le parsing mais n’écrit ni RAW, ni table normalisée, ni ligne de run. `-Force` ignore seulement le calendrier du lanceur ; il n’active pas une section ayant `enabled: false` au niveau du service.

## Activation progressive recommandée

Commencer par P0 et observer une semaine les taux de couverture et corrections. Activer ensuite borrow P1. Les options et opening window exigent d’abord un producteur fiable de l’univers Oracle quotidien. Business Quant analyste doit rester désactivé jusqu’à comparaison du coût et du contenu avec Yahoo. Auction imbalance, prêt de titres complet et options NBBO restent des contrats de données à pourvoir, pas des collecteurs simulés.
