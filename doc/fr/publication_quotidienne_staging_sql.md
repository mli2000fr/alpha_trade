# Publication quotidienne des barres FR en staging SQL

## Livraison du 9 octobre 2026

Le batch existant `fr_daily_bars_sync` collecte toujours EODHD en fichiers
versionnés. Il publie maintenant les archives validées dans le **staging de
recherche** de `alpha_trade_fr`, après collecte. Aucun nouveau batch nécessaire,
aucune tâche Windows réinstallée et aucun accès courtier utilisé.

Dans `batch_fr.yaml` :

```yaml
fr_daily_bars_sync:
  publish_daily_staging: true
```

`false` revient au mode fichiers seuls. Ce booléen ne modifie pas les gardes
`canonical_writes_enabled: false` et `serving_enabled: false`. Un dry-run ne
publie jamais. Un smoke limité conserve le même sous-ensemble pour la collecte
et le SQL ; les collectes légalement bloquées restent bloquées.

## Tables et périmètre

Le service `service/fr/publish_daily_bars_staging.py` écrit exclusivement dans :

- `fr_ingestion_runs` : état et compteurs de chaque publication ;
- `fr_raw_payloads` : chemin, hash et disponibilité des archives quotidiennes ;
- `fr_provider_bars_staging` : OHLCV fournisseur, qualité et version brute ;
- `fr_staging_progress` : checkpoint atomique par payload/classificateur.

Le dataset `eod_daily` distingue ces payloads du backfill historique. Aucune
écriture dans `stock_bars_daily`, `fr_provider_bars_daily`, `instruments`,
`market_sessions` ou `fr_corporate_actions`. Aucune promotion implicite d'identité,
de segment de cotation, de modèle ou de prix qualifié indépendamment.
**La publication des autres collectes quotidiennes n'est pas livrée par ce
service** : corporate actions, AMF/DILA et référentiel restent sous leur contrat
de fichiers actuel. Il ne faut pas annoncer que toutes les familles sont en SQL.

Les tables nécessaires existent déjà, avec la colonne `classifier_version`
de la migration FR 0005. Aucune nouvelle migration/Alembic ni table n'a été
nécessaire ; le SQL de référence est inchangé.

## Disponibilité et validation

Pour chaque archive : identité du symbole, fenêtre, timezone, chronologie,
hash brut, dates distinctes, séances et OHLCV sont contrôlés avant SQL. Les
payloads invalides restent exclus, avec un rapport d'erreurs. Une réponse vide
ne crée aucune barre. `ZERO_VOLUME` reste une qualité explicite, pas une preuve
de négociabilité. La validation est fournisseur, pas une preuve indépendante.

- `fr_raw_payloads.observed_at/available_at` conservent la première observation
  réelle de cette version, retrouvée dans les archives d'observations ;
- `fr_provider_bars_staging.observed_at` conserve cette observation source ;
- `available_at` des nouvelles lignes staging est au moins l'heure réelle de
  publication SQL. L'import d'octobre n'est pas rendu disponible artificiellement
  au jour historique du cours ;
- les valeurs et timestamps des versions déjà publiées ne sont pas remplacés
  lors d'une répétition. Une correction fournisseur distincte garde sa version.

Plusieurs fenêtres/révisions brutes peuvent contenir un même titre/date. Le
staging versionné les conserve via `raw_payload_id` : **4 085 lignes versionnées
ne signifient pas 4 085 séances indépendantes**. Un consommateur futur doit
qualifier la version et sa disponibilité avant décision, pas sommer les versions
ni supposer que la dernière barre par date lève une absence récente.
Les contradictions ARTO sont consignées dans `source_file_coverage` des rapports
et des détails d'ingestion ; elles ne sont pas blanchies par l'import.

## Reprise et incidents

Chaque payload est une transaction : brut référencé, lignes staging et checkpoint
committent ensemble. Une transaction en échec est annulée, les transactions
précédentes restent conservées. Relancer retrouve les versions déjà publiées et
ajoute uniquement les lignes manquantes, même si la fenêtre est ensuite élargie.

Le verrou `.publish.lock` empêche deux publications concurrentes sur la même
source. Après un arrêt brutal, vérifier le processus propriétaire et l'absence
d'exécution avant toute suppression manuelle du verrou ; ne pas le retirer
automatiquement sur un simple âge. Un run SQL resté `RUNNING` n'est pas un succès.
Son traitement administratif doit tenir compte des transactions déjà committées
et des rapports, puis la reprise peut vérifier ces lignes sans les réinsérer.

Une collecte partiellement en échec peut publier ses archives valides, mais le
batch reste FAILED. Une erreur SQL devient bloquante pour le batch, même si la
collecte fichiers a réussi. Le rapport SQL et sa progression sont conservés dans
`artifacts/fr/operations/staging_runs/` pour les passages du batch.

Les compteurs principaux du batch continuent à compter les fichiers/barres
collectées. `sql_persisted_count` et `daily_sql_publication` détaillent les lignes
SQL nouvelles, inchangées, payloads et réserves ; ces unités ne sont pas
additionnées à tort aux symboles demandés.

## Commandes de reprise manuelle

Prévisualisation sans écriture SQL :

```powershell
python -m service.fr.publish_daily_bars_staging --start 2026-10-02 --end 2026-10-08 --output artifacts/fr/research/collection_remediation/nouvelle-preview.json
```

Publication staging, aucune requête réseau et aucune canonicalisation :

```powershell
python -m service.fr.publish_daily_bars_staging --start 2026-10-02 --end 2026-10-08 --write --output artifacts/fr/research/collection_remediation/nouvel-import.json
```

Le chemin de rapport doit être nouveau et dans `artifacts/fr`. Fenêtre bornée à
31 jours, source et identités FR uniquement. L'audit de couverture peut ensuite
être refait avec `service.fr.collection_coverage_remediation` (rapport de sortie
dans un nouveau répertoire FR). Aucun secret à envoyer ou placer dans la commande.

## Qualification réelle en base

Première publication de la semaine 2–8 octobre : **1 171 payloads**, **4 085
lignes nouvelles**, zéro échec SQL. Rapport
`artifacts/fr/research/collection_remediation/staging-import-20261009-v1.json`.

Répétition réelle : **0 ligne nouvelle**, **4 085 inchangées**, zéro échec SQL.
Rapport `…/staging-repeat-20261009-v1.json`. Empreinte avant/après des valeurs et
timestamps strictement identique :
`5ded0bdf55b94c0dfd7f6c78cb4f839c49a8f6ee2ed14b32e682481f3d0de859`.
Preuve : `…/staging-idempotence-20261009.json`.

Après import : `fr_provider_bars_staging` atteint **2 105 185 lignes**, jusqu'au
8 octobre ; `fr_raw_payloads` atteint **5 827**. Les cinq tables canoniques/
identités/calendrier précitées restent vides, vérifié en base après répétition.

Présence SQL : **1 460/1 470 = 99,32 %**, avec LHYFE/PERR absents.
Les deux dates ARTO non reconfirmées restent en réserve : couverture fournisseur
reconfirmée **1 458/1 470 = 99,18 %**, pas un taux de données tradables admises.
Le statut COMPLETED de l'import signifie que les versions valides ont été
publiées, pas que la couverture est complète ou que le shadow est autorisé.

## Suite

**101 tests ciblés réussis**, sans échec ni test ignoré :
`artifacts/fr/research/collection_remediation/staging-tests-20261009-v3.xml`.
Ils couvrent archives invalides, sentinelles DILA, isolation FR, dates,
répétition, fenêtre élargie, sous-ensemble smoke, dry-run et échec partiel non masqué.

Vérifier le prochain passage planifié complet et ses compteurs SQL, traiter les
réserves fournisseur/segment, puis qualifier séparément identités, PIT et
canonicalisation du sous-ensemble. Ne pas activer le LIVE ni raccordement d'ordres
sur la seule base de cette publication.

Références : [remédiation des collectes](remediation_collectes_couverture_20261009.md),
[TODO de reprise](TODO_reprise_exploitation_sprints_16_18.md).
