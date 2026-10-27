# Batchs FR — stockage SQL des données et archives

Livraison du **27 octobre 2026**, base physique **`alpha_trade_fr`** uniquement.
La migration `0010_fr_batch_research_storage` complète les tables options de
la migration 0009 et les stockages barres/consensus déjà existants.

## Inventaire après bascule

| Batch / famille | Stockage des données | État |
|---|---|---|
| `fr_calendar_snapshot` | `fr_calendar_sessions_research` | Raccordé ; calendrier de bibliothèque, pas preuve officielle |
| `fr_security_master_sync` | `fr_reference_versions_research` | Raccordé ; versions ESMA par ISIN/MIC, sans promotion d'instrument |
| `fr_corporate_actions_sync` | `fr_corporate_actions_research` | Raccordé ; événements EODHD, valeurs et réserves conservées |
| `fr_amf_short_sync` | `fr_amf_positions_research` | Raccordé ; positions publiques censurées par seuil, pas borrow ni intérêt vendeur total |
| `fr_dila_disclosures_sync` | `fr_dila_disclosures_research` | Raccordé ; métadonnées, aucune prétendue extraction des PDF |
| `fr_daily_bars_sync` | `fr_provider_bars_staging`, `fr_raw_payloads`, `fr_ingestion_runs`, `fr_staging_progress` | Publication métier existante conservée, archives aussi copiées dans le miroir commun |
| `fr_consensus_snapshot` | `stock_analyst_consensus_eodhd_history`, `eodhd_consensus_raw_payloads` | Publication existante conservée, aucun fallback Yahoo réactivé |
| `fr_options_mifir_trade_sync` | Les quatre tables `fr_option_mifir_*` | Publication existante conservée, toujours sans OI qualifiée |
| `fr_options_open_interest_sync` | Trois tables `fr_option_oi_public_*`, migration 0011 | [OI publique](options_open_interest_public.md) brute/par contrat, dates exactes inconnues, recherche seulement ; reçus et rapports aussi archivés dans le miroir commun |
| `fr_fundamentals_sync` | Documents de mapping/reçus existants dans le miroir commun | **Toujours bloqué INPI**, aucun nouveau téléchargement ni compte normalisé inventé |
| `fr_borrow_snapshot`, `fr_options_snapshot` | Aucun jeu de données disponible à importer | **Toujours en attente de fournisseur** |
| Sauvegardes FR | Reçus d'exécution dans le miroir commun | Dumps/ZIP restent des sauvegardes, pas des données marché à réinsérer dans la base |
| Ancien `fr_pit_quality_daily` | Rapport historique dans le miroir commun | Ne réinstalle ni ne réactive le batch retiré |

Deux tables communes conservent aussi les archives et les traces d'exploitation :

- `fr_batch_research_documents` : contenu JSON intégral, fournisseur, batch,
  empreinte du contenu, version du parseur, horloges, nombre de lignes structurées,
  statuts de recherche ; les CSV AMF encapsulés dans le JSON sont conservés.
- `fr_batch_research_file_versions` : liens vers les fichiers et leurs versions,
  chemins, empreintes et date d'import. Un fichier remplacé conserve ses anciens
  contenus dans SQL. La date de modification n'est qu'une métadonnée technique.

Les fichiers sources sont conservés comme preuves et pour la reprise. Les archives
binaires ESMA et les sauvegardes restent sur disque : les observations FR qui en
sont issues sont en SQL, sans copier tous les instruments européens hors périmètre
ni réimporter un dump de base dans lui-même. Les dossiers de recherche manuelle
des anciens sprints et les modèles ne sont pas des collectes du catalogue.

## Import réellement exécuté

Après import des archives puis passage réel du calendrier local :

| Table structurée nouvelle | Lignes versionnées |
|---|---:|
| `fr_calendar_sessions_research` | 1 330 |
| `fr_reference_versions_research` | 42 273 |
| `fr_corporate_actions_research` | 178 |
| `fr_amf_positions_research` | 240 863 |
| `fr_dila_disclosures_research` | 4 946 |

**Ces nombres ne sont pas des nombres d'événements indépendants.** Une même
position AMF ou une version historique ESMA peut apparaître dans plusieurs
snapshots sources. Les clés évitent de réimporter une même version ; elles
n'effacent pas les réceptions successives de sources différentes. Pour analyser
un instant, sélectionner les documents/snapshots disponibles avant son cutoff,
puis traiter les répétitions économiques selon le contrat de la famille.

Le second import réel de tout le périmètre a créé **zéro document, zéro lien et
zéro ligne structurée**. Le passage local du calendrier a ensuite ajouté 266
sessions versionnées et son reçu SQL, avec un résultat global SUCCESS.

Les preuves sont dans `artifacts/fr/research/batch_sql_20261027/` :
`preflight-v1.json`, `import-v1.json`, `reconcile-v2.json`,
`sql-verification-v1.json`, `sql-verification-v2.json`.

## Disponibilité et qualification

- `source_observed_at`, `source_available_at` : horloges réellement connues dans
  les archives ou leurs reçus ; elles restent **NULL** en l'absence de preuve.
- `sql_available_at` : date réelle d'insertion SQL. L'import d'octobre n'est pas
  présenté comme une publication SQL disponible en 2018.
- Les dates métier — position AMF, publication, dividende, version ESMA ou séance —
  ne remplacent pas les horloges de disponibilité.
- Les horaires de séances futures du calendrier sont des dates d'événements
  planifiés, distinctes des horloges d'observation : ils sont conservés, sans
  autoriser une réception ou une disponibilité source future.
- `ml_eligible=false`, `canonical=false`, `historical_pit_qualified=false` :
  aucune validation financière, de licence pour un nouvel usage, de tradabilité,
  de modèle ni de trading par le seul fait de stocker en SQL.
- Les unités, devises et dates manquantes ne sont pas inventées. Les sentinelles
  DILA restent dans le brut et ne deviennent pas des dates de publication valides.
  Les événements fournisseur invalides restent explicitement marqués `INVALID`.
- Le mapping INPI existant est conservé, mais `BLOCKED_INPI_RETENTION` reste actif.
  Toute future gestion des retraits devra couvrir aussi ces copies SQL.

Les tables canoniques `instruments`, `market_sessions`, `stock_bars_daily` et
`fr_corporate_actions` ne sont pas alimentées par ce miroir. Les garde-fous
`canonical_writes_enabled: false` et `serving_enabled: false` restent inchangés.

## Raccordement des prochaines exécutions

`batch_fr.yaml → defaults.archive_research_sql: true` active le raccordement dans
`service.fr.operational_batch_15a`. Le runner vérifie le schéma **avant les appels
fournisseur**, conserve les acquisitions fichiers, puis publie les archives et
le reçu final dans SQL. Les stockages métier existants barres/consensus/options
continuent à fonctionner ; ils ne sont pas remplacés par le miroir générique.

Une acquisition partielle peut conserver ses données en SQL, mais reste FAILED.
Une panne SQL rend le batch FAILED, même si les fichiers ont été acquis. Les
preuves restent utilisables pour une reprise hors ligne. Aucun DDL automatique
dans le batch et aucune baisse des seuils de qualité. Les horaires, les univers,
les tâches Windows et les destinataires de notification n'ont pas été changés.

Les publishers SQL sont sérialisés par un verrou MySQL par batch, pour qu'un
import manuel et une collecte planifiée ne publient pas la même version en
concurrence. Les transactions annulent ensemble un document et ses lignes si
une insertion échoue. Les fichiers nommés par empreinte sont vérifiés aussi
lorsqu'ils sont déjà connus de SQL.

## Commandes

Sur une nouvelle installation :

```powershell
python -m alembic -c alembic_fr.ini upgrade 0010_fr_batch_research_storage
```

Vérification hors ligne, sans connexion SQL ni téléchargement :

```powershell
python -m service.fr.batch_research_store --report artifacts/fr/research/batch_sql_20261027/nouvelle-preview.json
```

Import/reprise de tout le catalogue sans appel fournisseur :

```powershell
python -m service.fr.batch_research_store --apply --report artifacts/fr/research/batch_sql_20261027/nouvel-import.json
```

Une seule famille : ajouter `--batch fr_amf_short_sync` par exemple. Le chemin du
rapport doit être neuf ; un échec reste FAILED avec les familles déjà committées
dans le rapport. La reprise réutilise leurs données au lieu de les doubler.

Les sauvegardes globales `fr_db_backup` incluent automatiquement ces nouvelles
tables, tandis que `fr_artifacts_backup` conserve les fichiers. La restauration
ancienne du 5 octobre ne constitue pas une nouvelle validation de restauration
du schéma 0010.

## Vérifications

**128 tests ciblés réussis** : 113 sur les collecteurs, le runner et le nouveau
stockage, plus 15 sur le staging de barres existant. Contrôles d'isolation FR,
timestamps inconnus, versions et reprises, rollback, archives corrompues,
verrouillage et absence de faux succès du reçu final.

En base : empreintes des documents JSON, somme des compteurs et absence de lignes
orphelines vérifiées. Un passage réel du calendrier local a validé le raccordement
runner → données SQL → reçu SQL, sans appel fournisseur externe ni ordre.
Les 1 330 horaires de séances ont aussi été confrontés à leurs lignes sources,
y compris les dates futures, avec le reçu `calendar-schedule-verification-v1.json`.
Une relecture finale a confirmé sans écart les 240 863 ratios AMF, les 178 valeurs
d'actions sur titres et les 1 330 horaires : `typed-values-verification-v1.json`.
