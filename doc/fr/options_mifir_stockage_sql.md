# Options FR — tables de recherche MiFIR/FIRDS

> Depuis le **28 octobre 2026**, [SQL est le stockage principal](stockage_sql_principal_20261028.md),
> pour les sources, checkpoints, snapshots et bilans. Les descriptions et
> commandes d'import de fichiers ci-dessous concernent les archives antérieures.

Livraison et import vérifiés le **27 octobre 2026**. Le batch concerné est
`fr_options_mifir_trade_sync`, toujours actif à 06h Paris du lundi au samedi.
La source, les horaires, l'univers FR et les notifications sont conservés.

## Tables dans `alpha_trade_fr`

| Table | Contenu | Lignes après import |
|---|---|---:|
| `fr_option_mifir_snapshots` | Version de collecte, univers/couverture, sources, horloges et archive JSON complète | 19 |
| `fr_option_mifir_contracts` | Versions FIRDS : ISIN option/sous-jacent, symbole, CALL/PUT, strike, échéance, multiplicateur, style/livraison | 11 014 |
| `fr_option_mifir_trades` | Transactions acceptées et lignes rejetées, quantités/prix déclarés et ligne source JSON | 26 345 |
| `fr_option_mifir_observations` | Reçus des tentatives de collecte, dont les échecs, reliés au snapshot lorsqu'il existe | 21 |

Les transactions comprennent **26 329 acceptées et 16 rejetées**, sur les
séances du **5 au 26 octobre 2026** : 16 dates et 61 symboles observés au total.
Ces volumes comptent les **versions archivées**, pas nécessairement autant de
transactions économiquement distinctes. Une transaction présente dans deux
snapshots est conservée dans les deux versions ; ne pas les additionner sans
sélectionner une version par séance et cutoff.

Les rejets sont séparés par `acceptance_status='REJECTED'`, avec
`rejection_reason`. `source_occurrences` conserve la multiplicité lorsqu'une même
ligne rejetée apparaît plusieurs fois. Une transaction `ACCEPTED` a passé les
contrôles du parseur ; cela ne certifie pas son volume en nombre de contrats.

## Horloges et qualification

- `traded_at` / `published_at` : horloges fournisseur, converties en UTC.
- `observed_at` / `available_at` du snapshot : disponibilité réellement conservée
  dans les fichiers, jamais remplacée par la date du trade.
- `imported_at` : heure UTC réelle de l'insertion dans SQL, distincte de la
  disponibilité passée des fichiers. Ces lignes SQL n'existaient pas auparavant.
- `quantity_unit_qualified=false`, `ml_eligible=false`, `canonical=false`,
  `historical_pit_qualified=false` : statuts conservés, sans promotion automatique.
- `collection_complete` du reçu décrit la complétude de la collecte source.
  Il ne remplace pas le statut global du runner : un échec SQL rend ce dernier FAILED.

L'OI, le NBBO et les Greeks absents ne sont pas inventés ni remplacés par zéro.
Aucun ratio CALL/PUT en volumes qualifiés ni filtre de trading n'est activé.
Les trades corrigés/annulés restent visibles dans les sources et rejets.

## Intégrité et reprise

`service.fr.mifir_options_store` vérifie chaque objet brut par SHA256, les horloges,
la clé historique du snapshot et la reproduction de son analyse depuis les
archives Euronext/FIRDS. Une source manquante/corrompue ou une analyse modifiée
bloque l'import. Aucun téléchargement fournisseur n'est nécessaire.

Chaque snapshot et ses contrats/transactions sont insérés dans une même
transaction SQL. Les clés composées empêchent les doublons à la reprise ; une
version existante n'est jamais écrasée. Un contenu contradictoire ou des enfants
manquants provoquent une erreur. Les reçus sont identifiés par leur empreinte.
Un second import réel a confirmé **zéro insertion** et 19 snapshots réutilisés.

Le collecteur valide les quatre tables **avant tout appel fournisseur**. Après
archivage, il alimente SQL, y compris les preuves partielles et les rejets.
Une panne SQL conserve les fichiers et remonte comme échec, au lieu de publier
un succès limité aux fichiers. Le rapport d'exploitation conserve les compteurs
historiques en titres et ajoute `sql_snapshots`, `sql_contracts`, `sql_trades`,
`sql_observations`, `sql_snapshots_reused`. Aucun changement dans les bases US/CN
ou dans les tables canoniques FR.

## Commandes

Migration explicite, limitée à la base physique FR :

```powershell
python -m alembic -c alembic_fr.ini upgrade 0009_fr_mifir_options_research
```

Contrôle hors ligne, sans connexion SQL ni réseau :

```powershell
python -m service.fr.mifir_options_store
```

Import ou reprise SQL des archives, idempotent et sans appel fournisseur :

```powershell
python -m service.fr.mifir_options_store --apply --report artifacts/fr/research/mifir_options_sql_20261027/nouveau-rapport.json
```

Le fichier de rapport doit être neuf. La simulation du batch (`--dry-run`)
reste sans connexion SQL et sans appel réseau. `sql_storage_enabled: true` est
obligatoire pour une collecte réelle complète ; le runner ne crée pas le schéma.

## Consultation sans additionner les versions

Exemple : transactions acceptées de la dernière version complète de chaque
séance à la date de consultation. Pour une étude datée, ajouter aussi
`available_at <= <cutoff UTC>` dans la sélection des snapshots.

```sql
WITH versions AS (
  SELECT snapshot_id,
         ROW_NUMBER() OVER (
           PARTITION BY first_trade_date
           ORDER BY available_at DESC, snapshot_id DESC
         ) AS n
  FROM alpha_trade_fr.fr_option_mifir_snapshots
  WHERE collection_status = 'COMPLETE'
    AND first_trade_date = last_trade_date
)
SELECT t.symbol, t.trade_date, t.option_type,
       t.price, t.reported_quantity, t.traded_at, t.option_isin
FROM alpha_trade_fr.fr_option_mifir_trades t
JOIN versions v ON v.snapshot_id = t.snapshot_id AND v.n = 1
WHERE t.acceptance_status = 'ACCEPTED';
```

Ne pas interpréter les quantités déclarées comme des nombres de contrats tant
que leur unité n'a pas été qualifiée. Ne pas utiliser ces lignes en ML/trading
par le seul fait qu'elles sont maintenant en SQL.

## Vérification effectuée

**66 tests ciblés réussis** : collecteur, stockage SQL isolé, idempotence,
rollback, rejet des archives altérées, absence de fallback US, dry-run,
qualification, POC et runner FR. Migration 0009 appliquée en base France.
La relecture réelle a vérifié les 19 empreintes d'archives et les prix/quantités
des 26 345 lignes SQL. Le dry-run du runner retrouve 294 titres sans réseau.

Preuves : `artifacts/fr/research/mifir_options_sql_20261027/` contient
`preflight-v1.json`, `import-v1.json`, `idempotence-v1.json` et
`sql-verification-v1.json`. Aucun entraînement, ordre ou appel fournisseur
supplémentaire pour cette livraison.
