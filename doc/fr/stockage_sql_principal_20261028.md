# Collectes FR — SQL est le stockage principal

Bascule du **28 octobre 2026**, base physique `alpha_trade_fr`.

L'ancien `archive_research_sql` copiait les fichiers de collecte vers SQL en
fin de passage. Cette option est **supprimée**. Le catalogue utilise maintenant :

```yaml
defaults:
  storage_backend: sql
```

Les prochains passages du runner FR enregistrent les données et les états
directement en base. Une donnée absente de SQL n'est jamais recherchée dans
un ancien fichier ; une panne SQL rend le passage FAILED avant les appels
fournisseur si elle survient au démarrage. Un échec en cours de passage
conserve les acquisitions déjà engagées, sans annoncer un succès complet.

## Données et reprises

| Collecte active | Écriture/lecture opérationnelle |
|---|---|
| Calendrier XPAR | Document SQL et `fr_calendar_sessions_research` |
| Référentiel ESMA | Réponses binaires, checkpoint et versions SQL ; `fr_reference_versions_research` |
| Barres EODHD | Réponses et observations SQL, état de reprise SQL, puis `fr_provider_bars_staging` avec ses tables de suivi |
| Actions sur titres | Réponses, fenêtres et vues courantes SQL ; `fr_corporate_actions_research` |
| Positions AMF | Réponse, réserves et vue courante SQL ; `fr_amf_positions_research` |
| Annonces DILA | Réponse, rejets et vue courante SQL ; `fr_dila_disclosures_research` |
| Consensus EODHD | Réponses dans `eodhd_consensus_raw_payloads`, données dans `stock_analyst_consensus_eodhd_history`, budget journalier/checkpoint SQL |
| Options MiFIR/FIRDS | Sources binaires/checkpoints SQL, quatre tables `fr_option_mifir_*` |
| OI public Euronext | Réponses et contrats dans les trois tables `fr_option_oi_public_*`, progression et bilan SQL |

Les données restent **de recherche** : le mot concerne leur qualification,
pas un stockage secondaire. Les protections de disponibilité, d'identité et
de qualité restent appliquées. Aucun batch bloqué n'est réactivé, aucun
instrument ni prix canonique n'est créé par cette bascule.

## Tables communes

Migration `0012_fr_sql_primary`, appliquée :

- `fr_collection_objects` : empreinte SHA256 et longueur des objets bruts.
- `fr_collection_object_parts` : corps binaires en morceaux de 1 Mo maximum,
  pour éviter les très gros messages SQL lors du stockage des ZIP ESMA.
- `fr_collection_versions` : versions et horloges de disponibilité SQL.
- `fr_collection_heads` : état courant de chaque ressource/checkpoint.
- `fr_collection_runs` : passages et bilans opérationnels. La page Batch FR
  lit cette table pour le dernier état.

`fr_batch_research_documents` et les tables structurées existantes sont
alimentées directement lors des écritures, plus par un scan de fichiers en
fin de batch. `fr_batch_research_file_versions` conserve uniquement les
anciens liens d'import ; les nouvelles collectes n'y créent pas de fichiers.

Les clés héritées peuvent encore contenir `latest.json`, `windows/...` ou
`identities.jsonl.gz`. Ce sont des **identifiants logiques de ressources SQL**.
Le dépôt les utilise pour relire les états et références importés, sans ouvrir
le fichier portant cet ancien nom. Modifier un ancien fichier de référence
ne change donc pas silencieusement l'univers SQL : une nouvelle version
doit être importée et vérifiée explicitement.

Le corps d'une réponse est engagé avant sa normalisation. Une erreur de
parsing conserve l'objet brut, mais n'avance pas la tête d'un checkpoint
validé. Le corps est contrôlé par longueur et SHA256 à la lecture. Les
verrous MySQL par batch remplacent les fichiers `.lock` en exploitation.

## Transition réellement exécutée

Import sans appel fournisseur, sans suppression des anciennes archives :

- **342 ressources binaires**, soit **895 806 054 octets**, importées et
  relues avec comparaison intégrale des octets.
- Référence S6C et baseline ESMA importées avec leurs empreintes originales.
- Les documents JSON déjà présents en SQL ont tous été reconnus : zéro
  document et zéro ligne structurée réimportés. Leur lecture de compatibilité
  se fait depuis SQL, sans dépendre des anciens fichiers.
- Bilan `fr_sql_primary_migration` enregistré dans `fr_collection_runs`,
  terminé SUCCESS le 28 octobre à 00:15:14 UTC, soit 01:15:14 Paris.

Les anciens fichiers restent conservés comme historique de transition ; les
collectes opérationnelles ne les utilisent plus comme source de reprise.
Les outils historiques/offline d'import peuvent toujours lire une archive
sur demande explicite. Ils ne font pas partie du chemin planifié quotidien.

## Vérification réelle

Le 28 octobre à 00:18:52 UTC :

- Calendrier réellement exécuté : **SUCCESS, 266 séances**, bilan SQL
  `fr-operation-2334c0eb7c064a0d8236e1d493ecf924`.
- Publication des barres OR.PA sur la fenêtre du 20 au 27 octobre entièrement
  relue depuis SQL : **COMPLETED**, six payloads valides, zéro erreur,
  **21 lignes déjà présentes et zéro nouvelle ligne**. Reprise idempotente.
- Comparaison des fichiers d'opérations avant/après : **zéro création ou
  modification**. Aucun appel fournisseur pour ces vérifications.
- Bilan `fr_sql_primary_verification` conservé dans `fr_collection_runs`.
- Les **19 snapshots MiFIR antérieurs** ont ensuite été relus et rejoués
  uniquement depuis SQL, avec vérification des réponses brutes, sans appel
  fournisseur : SUCCESS, bilan `fr_sql_primary_mifir_verification`.
- **150 tests ciblés passent** sur les collecteurs, reprises et publications.

Les tests couvrent aussi les reprises SQL des barres, actions sur titres,
consensus, sources MiFIR et observations d'OI, l'absence de repli vers un
fichier pourtant présent, la corruption d'objet et la conservation d'un
brut dont le parsing échoue.

## Ce qui reste normalement un fichier

Configuration YAML, journaux d'exploitation et sauvegardes restent des
fichiers. Le téléchargement et le contrôle des gros ZIP ESMA utilisent un
dossier de travail temporaire automatiquement supprimé, puis le corps est
conservé en SQL. Les compteurs/circuits fournisseur partagés avec les autres
marchés gardent leur mécanisme technique commun ; ce ne sont pas des bases
de données marché ou des checkpoints de collecte FR.

`fr_db_backup` sauvegarde aussi les nouvelles tables. `fr_artifacts_backup`
reste utile pour les anciens dossiers de recherche et modèles. Les horaires
des batchs, le fournisseur des barres FR et les règles de trading ne changent pas.
