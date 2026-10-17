# Politique actions US : SIP uniquement et migration des quotes anciennes

État vérifié le **17 octobre 2026**, base `alpha_trade`. Cette intervention ne
modifie ni les bases FR/CN, ni les modèles, ni les ordres du courtier.

## Décision et limites

L’utilisateur a confirmé : **SIP historique, et blocage des nouvelles entrées
si le SIP temps réel n’est pas accessible**, en préservant les protections et
sorties des positions existantes. Les tests HTTP en lecture seule sur le compte
principal `default` ont renvoyé **403** sur les quotes/latest et les snapshots
actions SIP. Le SIP historique a, lui, fonctionné réellement.

Le SIP historique exige une borne de fin suffisamment ancienne ; les nouveaux
collecteurs de référence appliquent vingt minutes de retard. Ce n’est pas une
quote temps réel d’exécution. Voir la [FAQ officielle Alpaca](https://docs.alpaca.markets/us/docs/market-data-faq).

**Un changement de libellé n’est pas une conversion.** Aucune donnée IEX n’est
simplement renommée SIP. Une ligne ne devient SIP qu’après récupération effective
du flux, validation et archivage de la réponse.

## Inventaire réel avant rattrapage global

Les chiffres ci-dessous sont ceux de l’inventaire, pas des compteurs maintenus en
temps réel. Les quotes progressent depuis cette mesure.

| Table | Provenance observée | Lignes | Action |
| --- | --- | ---: | --- |
| `stock_bars` | `eodhd_eod` | 33 618 757 | conserver : pas d’IEX à remplacer |
| `stock_bars_daily` | `eodhd_eod` | 33 622 362 | conserver ; fournisseur EODHD inchangé |
| `stock_bars_intraday` | `alpaca_sip` | 62 117 194 | conserver : déjà SIP |
| `stock_opening_window_bars` | Alpaca / SIP | 2 810 608 | conserver : déjà SIP |
| `stock_opening_window_bar_versions` | Alpaca / SIP | 2 810 608 | conserver les versions |
| `stock_quote_snapshots` | fournisseur/flux NULL | 9 010 526 | anciennes quotes non qualifiées, remplacement progressif réel |
| `stock_quote_snapshots` | Alpaca / SIP | 1 648 | déjà qualifiées le 16 octobre ; ne pas écraser |
| `stock_option_snapshots` | Alpaca / `indicative` | 283 088 | options, pas un flux actions IEX/SIP |
| `stock_option_bars_delayed` | Alpaca / `historical_default` | 1 736 175 | options, ne pas réétiqueter SIP |

Les anciennes quotes sans provenance couvrent le 27 juillet 2020 au 16 octobre
2026. Leur absence de marqueur ne prouve pas individuellement qu’elles venaient
toutes d’IEX : elles sont **non qualifiées**, et non artificiellement certifiées.
Les tables daily couvrent 1996–2026 et l’intraday présent 2025–2026.

## Chemins opérationnels modifiés

- Client actions Alpaca : SIP par défaut ; barres et dernières quotes refusent
  explicitement IEX. Les helpers historiques de bas niveau restent utilisables
  par les audits comparatifs explicites, sans être un fallback opérationnel.
- Daily, backfill daily et intraday : SIP obligatoire côté Alpaca. Les nouveaux
  inserts legacy de barres déclarent leur vraie source SIP ; le choix courant
  `market_data.bars_provider: eodhd` reste inchangé.
- Page intraday : SIP uniquement. Un ancien plan IEX est refusé avant lecture
  SQL/cache ; un vrai nouveau plan SIP est nécessaire.
- Étape 4 / `latest_quotes_sync` : historique SIP, preuve brute, contrôle de
  provenance à la reprise. Le mode latest utilise Alpaca sans second fournisseur
  masquant un refus de droits.
- Référence actions des collecteurs options : dernières barres SIP retardées,
  déclarées comme telles. **Le flux des contrats options ne change pas.** Un
  refus ou une pagination tronquée bloque la référence au lieu de prendre IEX.
  Les anciens plans/cache de backfill options dont le contrat change doivent
  être repris sous un nouveau plan, sans recycler leur référence IEX.
- Selector / publication tradable : seules les quotes SIP qualifiées avec
  archive correspondante sont admises. Le relâchement de spread spécifique IEX
  ne peut plus « sauver » un titre ; les seuils SIP du preset restent appliqués.
- BrokerAdapter : avant une intention `ENTRY` ou `REBALANCE_BUY`, contrôle de
  l’accès à une quote SIP temps réel valide. Refus/absence/incohérence : pas de
  soumission de cette entrée, même si une cible risque antérieure existe.
  `EXIT`, SL, TP et trailing ne passent pas par cette nouvelle condition d’entrée.
  Pour les protections existantes, le prix de position fourni par le courtier
  reste utilisable ; aucun faux prix SIP n’est créé. L’efficacité continue des
  protections locales exige toujours que leur watcher fonctionne.

Les anciennes clés de métriques `quote_iex_*`, types reconnaissant les anciennes
provenances, schémas historiques Alembic et expériences gelées ne sont pas
globalement renommés : cela falsifierait leur sens ou casserait la compatibilité.
Le proxy mid de quote / close daily n’est **pas** une mesure directe IEX/SIP.
Les scripts comparatifs et les études historiques IEX gardent donc ce mot et
leur vraie source. Leur présence ne signifie pas un fallback en production.

## Schéma déployé, sans upgrade global

La migration additive `0106_quote_provenance` est appliquée sur la branche issue
de `0088_us_fact_instrument_constraints`. La migration `0108_sip_bar_defaults`,
appliquée ensuite, ne change que les valeurs par défaut futures des sources de
barres. Les ALTER exigent `ALGORITHM=INSTANT` et une courte attente de verrou,
sans fallback vers une reconstruction. Aucun ancien prix/volume n’est modifié
par ce DDL.

Marqueur constaté après cette intervention : **`0108_sip_bar_defaults`**.
`0107_merge_quote_provenance` fusionne les branches dans le graphe du dépôt,
sans DDL ; il n’a pas été appliqué à la base. Les migrations intermédiaires
`0089`–`0105` n’ont pas été exécutées globalement dans cette intervention.
Ne pas interpréter ces numéros comme une autorisation d’upgrade général.

## Rattrapage réel des quotes : état et reprise

Programme : `scripts.operations.migrate_legacy_quotes_to_sip`.

1. Test limité : **100** quotes du 15 octobre réellement remplacées.
2. Test du plan global : **1 000** autres quotes remplacées ; reprise vérifiée
   sans retraiter ses tranches déjà commitées. APD du 16 octobre reste rejeté
   pour bid/ask croisé.
3. Les **1 100** quotes SIP du 15 octobre ont été relues : zéro défaut de
   qualité ou de correspondance d’archive.
4. Le plan global a ensuite été repris le 17 octobre à **23:24:59 Paris**,
   sans limite de nombre de tranches, avec durée maximale de six heures.
   **La migration de neuf millions de lignes n’est pas déclarée terminée.**

Dossier principal :
`artifacts/operations/iex_sip_project_migration/20261017-all/`.

- `protocol.json` : dates, table, chunk et flux figés ;
- `days/` : manifestes figés des clés à remplacer par date ;
- `tasks/` : un checkpoint seulement après commit SQL ;
- `before/` : sauvegardes compressées des anciennes lignes avant chaque commit ;
- `raw/` : toutes les pages SIP brutes compressées, avec requête sans secrets ;
- `progress.json`, `report.json` : progression et état final/pause ;
- `artifacts/quotes/alpaca/sip/` : preuves par quote, empreintes liées aux lignes SQL.

Pièces de contrôle et journal courant :
`artifacts/operations/iex_sip_project_migration/20261017-v1/`, notamment
`validation_1100.json`, `realtime_access.json`, `migration.log` puis
`migration_retry1.log` (reprise après un délai réseau).
Le test initial de cent lignes a son dossier séparé `20261017-smoke` ; ses
cent lignes ne sont pas incluses dans `rows_replaced` du plan global.

Suivre sans relancer :

```powershell
Get-Content F:\projets\artifacts\operations\iex_sip_project_migration\20261017-all\progress.json
Get-Content F:\projets\artifacts\operations\iex_sip_project_migration\20261017-v1\migration_retry1.log -Tail 15 -Wait
```

La reprise, **seulement si aucun processus du même plan n’est encore actif** :

```powershell
python -u -m scripts.operations.migrate_legacy_quotes_to_sip `
  --start-date 2020-07-27 --end-date 2026-10-16 --chunk-size 500 `
  --output artifacts/operations/iex_sip_project_migration/20261017-all `
  --write --max-seconds 21600
```

Le verrou du plan interdit les doubles lancements. Pause entre requêtes : 0,5 s.
Le traitement s’arrête avant la prochaine tranche si un fichier `STOP` existe
dans le dossier principal, si l’espace libre passe sous 50 Go, après six heures,
ou entre **07:00 et 20:00 Paris**. Une tranche déjà commencée peut finir avant
l’arrêt. Cela laisse une marge avant l’absence de 07:30 ; aucune tâche planifiée
de reprise automatique n’a été installée.

Pour demander une pause : créer un fichier vide nommé `STOP` dans le dossier
principal. Le retirer avant une reprise volontaire. Une pause n’est pas un échec
ni une preuve de migration complète.

### Garanties et non-résolus

La collecte bulk respecte l’ordre symbole/temps du fournisseur et déroule toutes
les pages avant un commit. `asof=-` interdit un remappage automatique des tickers.
Les fenêtres de recherche s’élargissent de la dernière seconde jusqu’aux quinze
dernières minutes, uniquement pour les symboles absents. Une quote plus récente
mais croisée n’est pas remplacée opportunément par une ancienne quote valide.
Documentation : [quotes historiques multi-symboles](https://docs.alpaca.markets/us/reference/stockquotes-1).

Chaque UPDATE ne cible qu’une clé déjà présente dont le flux n’est pas SIP : pas
d’ajout de lignes, pas d’écrasement concurrent d’une quote devenue SIP. Les quotes
absentes ou invalides restent anciennes et **inutilisables comme preuve SIP**,
avec motifs dans le checkpoint. HTTP 403/429, réponse invalide ou troncature :
arrêt visible, sans fallback IEX et sans commit partiel de cette tranche.
Une fin avec manquants est `PARTIAL_UNRESOLVED`, pas `COMPLETED`.

Le premier passage global s’est arrêté sur un timeout réseau après **5 346**
remplacements validés (plus les cent du test séparé), sans perte de checkpoints.
La reprise ajoute au maximum trois tentatives sur timeout/connexion ou HTTP
500/502/503/504, avec attente bornée. Les HTTP 401/403/429 ne sont pas repris
automatiquement. Les compteurs et `updated_at_utc` de `progress.json` indiquent
désormais chaque avancement ; une erreur ancienne n’est pas conservée comme
erreur active après reprise.

Le rattrapage ne republie pas les anciens univers et ne réécrit pas les résultats
de recherche, cibles risque, réponses LLM ou modèles entraînés avec d’anciennes
données. Une future étude doit annoncer les sources et la version utilisées.
`collected_at` reste la date réelle de récupération : aucun timestamp de
disponibilité historique « connu à l’époque » n’est inventé.

Conserver **base + archives de quotes + sauvegardes de migration** ensemble.
Les anciennes lignes ne sont pas supprimées en masse pour masquer les trous.

## Validation du correctif

**644 tests réussis, deux tests ignorés** lors de la passe finale consolidée,
couvrant collecteurs, IHM, risque,
exécution et watcher, ainsi que refus d’entrée sans SIP, sorties sans ce nouveau
prérequis, refus des anciens plans IEX, archives scellées, pagination et reprises
réseau. Les tests désactivent les identifiants SQL et les notifications externes ;
aucun ordre réel ou PAPER n’a été soumis pour les réaliser.

Le premier essai sous environnement restreint avait rencontré des erreurs de
répertoire temporaire/certificats Windows, puis trois chemins temporaires trop
longs. La passe finale utilise un dossier Windows court et réussit. Le contrat
de test IHM respecte aussi le blocage Yahoo déjà décidé : il vérifie son refus
au lieu d’exiger artificiellement une commande exécutable pour ce collecteur.
Les 21 avertissements `market_code absent` proviennent de cas de compatibilité
historiques de tests, et ne sont pas des échecs SIP.

Journal de cette passe : `20261017-v1/tests_644.log`. Les scénarios vérifient
également qu’une quote SIP valide laisse passer l’entrée LONG ou SHORT, tandis
qu’une quote absente, croisée ou non finie empêche toute soumission au courtier.

Au dernier pointage intermédiaire, le plan global avait dépassé **8 000 quotes
effectivement remplacées** et continuait normalement. Les quatre quotes invalides
déjà rencontrées restaient anciennes, archivées et non qualifiées. Ce pointage
n’est pas un bilan terminal : lire `progress.json` pour l’avancement exact.
