# Collectes CN : SQL est le stockage principal

À partir du 1er novembre 2026, les données CN, documents sources,
observations, bilans et checkpoints de collecte utilisent exclusivement
**`alpha_trade_cn`**, route **`cn_primary`**. `config_cn.yaml` et les
catalogues de batchs indiquent `storage_backend: sql`.

Les chemins `artifacts/cn/...` et `artifacts/research/cn_...` utilisés dans
les contrats et reçus sont désormais des **clés logiques SQL**. Les lecteurs
ne reviennent pas vers un ancien fichier lorsqu'une ressource SQL manque.
Une erreur SQL reste une erreur, elle ne déclenche pas un téléchargement
automatique. Les tests hors de ces racines peuvent employer des fixtures
temporaires locales ; ce n'est pas un autre mode de stockage opérationnel.

## Tables consultables

| Table | Contenu |
| --- | --- |
| `cn_raw_payloads`, `cn_staging_rows`, `cn_ingestion_runs` | Réponses BaoStock/Tushare, lignes de staging et suivi d'ingestion existants. |
| `stock_bars_daily`, `market_sessions`, `instrument_adjustment_factors`, `cn_daily_price_limits`, `cn_corporate_actions` | Données canoniques existantes, sans réécriture par la migration des fichiers. |
| `cn_dragon_tiger_snapshots` | Session, observation UTC réelle, phase, nombre d'événements, réserves PIT. |
| `cn_dragon_tiger_events` | Événements de chaque snapshot : place, code, raison, première observation et empreinte. |
| `cn_oracle_prospective_candidates` | Candidats Oracle, date de décision, code, score, disponibilité UTC et ligne originale. |
| `cn_dragon_tiger_matches` | Appariements exposé/témoin, date de décision et ligne complète. |
| `cn_collection_reports` | Rapports, statuts et bilans opérationnels/de recherche. |
| `cn_collection_resources` | Version courante de chaque clé logique. |
| `cn_collection_versions` | Versions successives, empreintes et véritable date d'enregistrement SQL. |
| `cn_collection_objects`, `cn_collection_object_parts` | Contenu source exact, y compris XLSX, PDF, JSON, archives gzip et anciens jeux Parquet, découpé en blocs de taille bornée. |
| `cn_collection_file_migrations` | Preuve d'import, empreinte, taille, date de vérification et date de suppression de chaque fichier source. |

Les tables normalisées sont liées aux octets sources par `content_sha256`.
Le stockage des octets permet de conserver les documents et les anciens
reçus sans transformer un PDF ou une réponse fournisseur en données
arbitrairement imputées. Les versions identiques sont dédupliquées.

Exemple de consultation des événements de la session :

```sql
SELECT s.trade_date, s.observed_at_utc, s.phase,
       e.exchange, e.code, e.reason, e.first_seen_at_utc
FROM cn_dragon_tiger_snapshots s
JOIN cn_dragon_tiger_events e USING (content_sha256)
WHERE s.trade_date = '2026-09-30'
ORDER BY s.observed_at_utc, e.exchange, e.code;
```

## Producteurs et lecteurs

- D6 après clôture et avant ouverture : écrit les snapshots et leurs
  événements en SQL, relit les observations précédentes en SQL.
- D9 : collecte et promotion canoniques inchangées, checkpoints et bilans
  SQL, publication Oracle atomique en SQL. Un résultat après le cutoff ne
  devient pas une décision valable ; la quarantaine reste appliquée.
- D10 : lit les observations et les candidats SQL, stocke les appariements
  et le bilan SQL. Il ne charge toujours aucun rendement futur.
- Qualité 17-C : lit les tables et les preuves SQL, stocke le bilan SQL.
  Il reste sans collecte ni écriture canonique de marché.
- Reprise BaoStock/Tushare : état SQL ; les verrous des campagnes D9 et
  incrémentales utilisent des verrous MySQL nommés, libérés avec la connexion.
- Lecteurs cumulés, shadow, historiques IHM et outils CN de recherche :
  résolution SQL des anciennes clés ; lecture Parquet/gzip en mémoire.

Le champ historique `database_modified=false` de certains reçus exprime
leur ancien contrat de recherche sans écriture canonique. Ces reçus sont
conservés **octet pour octet** ; leur import n'en modifie ni les dates,
ni les empreintes, ni les réserves. L'écriture SQL de leur contenu est
attestée séparément par les tables de versions et de migration.

Les restrictions existantes de collecte, recherche, PIT, serving et trading
sont conservées. Une importation en SQL ne réactive aucun fournisseur et
ne crée aucune publication historiquement connue qui n'existait pas.

## Migration et nettoyage

Schéma : migrations Alembic CN `0008_collection_sql_primary` et
`0009_collection_lookup_indexes` (index et scores Oracle en double précision).

```powershell
python -m alembic -c alembic_cn.ini upgrade head
python -m service.market.cn_collection_migration
python -u -m service.market.cn_collection_migration --apply
python -u -m service.market.cn_collection_migration --apply --verify-projections
python -u -m service.market.cn_collection_migration --apply --cleanup-only --delete-sources
```

La première commande de migration sans `--apply` est un inventaire. L'import
relit chaque objet SQL et compare ses octets à la source. Aucun fichier
n'est supprimé avant la réussite de l'ensemble de l'import. Le nettoyage
contrôle de nouveau la version, la taille, la modification locale et les
octets SQL immédiatement avant chaque suppression. Un fichier modifié,
non vérifié, un lien ou un chemin hors périmètre entraîne un refus.
Les reçus de nettoyage et les bilans finaux sont eux-mêmes stockés en SQL.

Les poids et reçus associés aux modèles, l'environnement Python, le code,
les configurations et les sauvegardes MySQL indépendantes restent des
éléments d'infrastructure. Ils ne sont pas supprimés avec les copies locales
des données collectées. Les anciens fichiers de log et de verrou ne sont
pas interprétés comme des données fournisseur à importer.

L'inventaire initial comporte 33 399 fichiers de données et reçus, soit
7 035 258 860 octets. Le bilan SQL de migration/nettoyage est la référence
pour les quantités effectivement traitées.

### Bilan exécuté

Import terminé le **1er novembre 2026 à 01:03 Paris**, nettoyage terminé à
**01:07 Paris** : **33 399 fichiers importés et vérifiés, puis 33 399 fichiers
supprimés**, soit **7 035 258 860 octets**. Un dernier passage à **01:10 Paris**
a importé, vérifié puis supprimé les trois états techniques résiduels
(deux anciens verrous et un état temporaire, **12 772 octets**).
Le registre contient donc **33 402 fichiers vérifiés/supprimés**, pour
**7 035 271 632 octets**. Aucun fichier source restant dans le périmètre de
migration, y compris ces anciens états. Aucun appel fournisseur et aucune
réactivation.

Contrôle réel après suppression : **3 snapshots, 217 événements,
1 034 candidats Oracle et 78 appariements** ; **1 864 rapports** au moment
du relevé, hors bilan de contrôle ajouté ensuite. La lecture des scores et
l'audit cumulatif fonctionnent depuis SQL alors que les fichiers n'existent
plus. L'échantillon reste qualifié
`INSUFFICIENT_PROSPECTIVE_MATCHED_SAMPLE` : ce transfert ne démontre aucun
avantage de trading supplémentaire.

Les reçus sont consultables dans `cn_collection_reports` et
`cn_collection_resources`, sous les clés logiques
`artifacts/research/cn_storage_migration/` : rapport d'import, nettoyage,
`projections.json` et `cutover-verification.json`. Les empreintes des sources
et les dates réelles de suppression figurent dans
`cn_collection_file_migrations`. Les contenus identiques sont dédupliqués
dans `cn_collection_objects` ; le nombre d'objets est donc inférieur au
nombre de fichiers importés.

## Vérifications connues hors migration

Le contrat Oracle prospectif ancien pointe vers un modèle dont le reçu
fige l'empreinte de `sprint10b_oracle.yaml` à
`087851551f0a287d8b30d8eac40cb9148748f04c3f7e6e5cc6c30da027f963d9`.
Le fichier de configuration actuel a une autre empreinte
(`5781559b87552370c14111dc837d3de2e9346c9fbc0c85b0d41bf913ae0efcb7`).
Le chargement reste donc refusé par le contrôle de provenance, comme avant
la bascule. La migration ne réécrit pas cette preuve pour rendre un modèle
artificiellement compatible.

Validation du raccordement : **400 tests CN réussis** sur la suite isolée
des quatre fichiers de tests affectés par des états préexistants
(contrat Oracle/calendrier figé, ancien catalogue « tous les batchs arrêtés »,
ancien inventaire FR). Les tests spécifiques SQL comprennent un appariement
D10 complet sans fichier local, l'idempotence, la lecture gzip/Parquet, la
détection d'une corruption, le refus d'écrire sur US et le refus de nettoyer
un fichier modifié. Les assertions préexistantes non satisfaites ne sont
pas présentées comme des tests réussis.
