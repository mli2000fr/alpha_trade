# Sprint planning détaillé — Intégration du marché chinois dans α-Trade

> Document d’exécution associé à `roadmap_integration_marche_chinois_audit_code.md`.  
> Date : 19 septembre 2026.  
> Cible : une intégration durable US + Chine permettant ingestion, recherche, entraînement, prédiction et backtest ; paper/live vient ensuite.  
> Ce document planifie les travaux. Il ne constitue pas une autorisation de modifier le code ni d’activer le trading réel.
> Architecture retenue : `alpha_trade` pour US, `alpha_trade_cn` pour la Chine, code et schéma logique partagés. Les entrées CN sont `config_cn.yaml` et `batch_cn.yaml`, et les autres fichiers propres à la Chine portent le suffixe `_cn`.

## Avancement Sprints 0 à 5

Les Sprints 0 à 5 sont terminés. Le gate Sprint 4 est **GO** : migration 0086 appliquée, calendrier US canonique 2010–2035, hash US inchangé, sessions CN segmentées chargeables, cutoffs PIT par dataset et aucun fallback weekday-only autorisé pour CN. Voir [Sprint 4 — calendrier et PIT multi-marchés](./sprint_4_calendrier_pit_multi_marches.md). Le gate Sprint 5 est également **GO** : 33 tables US migrées vers `instrument_id`, couverture critique de 100 %, parité US validée et aucune écriture canonique CN. Voir [Sprint 5 — migration canonique US](./sprint_5_migration_canonique_us.md). Le Sprint 6 est débloqué.

## 1. Mode d’emploi

Ce planning est volontairement séquentiel sur les contrats structurants et parallélisable uniquement à l’intérieur d’un sprint lorsque les dépendances sont stables.

Règles :

1. ne jamais charger de données CN dans les tables canoniques avant validation du Sprint 5 ;
2. conserver US comme comportement par défaut jusqu’à la fin du Sprint 14 ;
3. chaque migration possède une migration Alembic, un SQL de référence, un test upgrade et, lorsque sûr, un downgrade ;
4. chaque nouveau chemin market-aware est testé avec US avant CN ;
5. aucune jointure critique ne repose uniquement sur `symbol` après sa migration ;
6. aucun rang, label ou modèle cross-sectionnel ne mélange les marchés ;
7. chaque sprint produit des preuves dans `artifacts/audits/market_integration/` ;
8. un gate en échec bloque les sprints dépendants ;
9. paper/live reste désactivé jusqu’au Sprint 18 ;
10. les règles de marché et coûts sont versionnés, jamais enfouis dans le code.

## 2. Vue d’ensemble

| Sprint | Objet | Résultat principal | Bloque |
|---:|---|---|---|
| 0 | Baseline et ADR | Références US gelées, décisions d’architecture | tous les suivants |
| 1 | `MarketContext` | Registre de marchés sans changement fonctionnel | 4, 10, 14 |
| 2 | Référentiel instruments | Identité immuable + symboles fournisseurs | 3, 6, 7 |
| 3 | Migration des parents | Batches/runs/univers portent le marché | 4, 8, 10 |
| 4 | Calendrier et PIT génériques | Sessions US/CN paramétrables | 7, 10, 12 |
| 5 | Migration canonique US | `instrument_id` propagé, parité US validée | toute ingestion CN canonique |
| 6 | Sources gratuites BaoStock et staging multi-fournisseurs | Collecte brute idempotente sans clé | 7 |
| 7 | Canonicalisation CN P0 | Master, barres, ajustements, statuts, sessions | 8, 9, 10 |
| 8 | Univers CN PIT | Univers quotidien sans survivorship bias | 9, 10 |
| 9 | Features CN baseline | Panel prix/volume/benchmark/secteur | 10 |
| 10 | Oracle et ranking CN | Labels et modèles OOS mono-marché | 11, 13 |
| 11 | Direction CN baseline | LONG/SHORT/veto comparés OOS | 13 |
| 12 | Moteur backtest CN | T+1, limites, suspensions, lots, coûts | 13 |
| 13 | Validation économique | Stratégie OOS après coûts et stress | 14, 18 |
| 14 | IHM multi-marchés | Usage recherche CN sûr dans l’application | 15, 18 |
| 15 | Collectes directionnelles | Flow, margin/lending, analystes, événements | 16 |
| 16 | Campagne D1/D10 | Ablations et combinaison OOF pré-enregistrées | 17 |
| 17 | Industrialisation recherche | Monitoring, batchs, reprise, documentation | 18 |
| 18 | Broker/shadow/paper | Abstraction broker et shadow CN | 19 |
| 19 | Canary live | Activation graduelle, optionnelle | exploitation réelle |

Les numéros sont des dépendances logiques, pas des dates. Un sprint ne doit pas être compressé si ses preuves ne sont pas disponibles.

## 3. Artefacts communs à tous les sprints

Chaque sprint doit produire :

```text
artifacts/audits/market_integration/sprint_<NN>/
├── effective_config.json
├── git_state.txt
├── migrations_checked.json
├── tests_summary.json
├── data_quality.json              si données
├── parity_report.json             si chemin US touché
├── decisions.md
└── gate_result.json
```

`gate_result.json` :

```json
{
  "sprint": 0,
  "status": "GO|NO_GO|BLOCKED",
  "checks": [],
  "blocking_findings": [],
  "approved_artifacts": [],
  "created_at": "UTC timestamp"
}
```

Chaque commande longue doit avoir :

- batch/run ID ;
- log stdout/stderr ;
- mécanisme de reprise ;
- compteur demandé/reçu/persisté/échoué/alertes ;
- état final persistant ;
- aucune modification silencieuse d’un batch en cours.

## 4. Sprint 0 — Baseline US et décisions d’architecture

### Objectif

Figer la vérité actuelle avant toute évolution, afin de prouver ensuite que le marché US n’a pas régressé.

### Entrées

- dépôt actuel ;
- base US actuelle ;
- batches ML représentatifs ;
- backtests golden existants ;
- documents de `doc/cn/`.

### Travaux

#### 0.1 Écrire les ADR

Créer :

```text
doc/architecture/adr_market_context.md
doc/architecture/adr_instrument_identity.md
doc/architecture/adr_market_data_partitioning.md
doc/architecture/adr_cn_execution_rules.md
```

Décisions à verrouiller :

- codes marchés `US_EQ`, `CN_A`, `CN_BJ` ;
- `instrument_id` interne ;
- MIC officiels ;
- staging fournisseur séparé, contrat canonique commun mais bases physiques `alpha_trade` et `alpha_trade_cn` isolées ;
- batch ML mono-marché ;
- risque consolidable mais labels/rangs mono-marché ;
- symbole = attribut d’affichage, non identité ;
- US reste le défaut pendant la migration ;
- `database_alias` est obligatoire et vérifié contre `market_code` ;
- `config.yaml`/`batch.yaml` restent US, `config_cn.yaml`/`batch_cn.yaml` sont réservés à la Chine ;
- les migrations sont paramétrables et appliquées séparément aux deux bases.

#### 0.2 Inventorier les tables et contrats

Produire une matrice :

```text
table
clé actuelle
colonnes symbole/date/run
lecteurs
écrivains
risque de collision
sprint de migration
```

Inclure stock, ML, news, risque, exécution, corporate actions et forward PIT.

#### 0.3 Figer des références US

Sélectionner :

- un chargement d’univers ;
- un screener ;
- un entraînement court déterministe ;
- un Oracle ;
- une prédiction ;
- un backtest représentatif ;
- un test lifecycle ;
- un test de parité live/backtest.

Conserver :

- lignes SQL extraites ;
- hashes des DataFrames intermédiaires ;
- hashes des artefacts ;
- signaux/trades/PnL ;
- paramètres effectifs.

#### 0.4 Relever la dette symbol-only

Établir une allowlist temporaire des requêtes utilisant uniquement `symbol`, classée :

- P0 : barres, labels, prédictions, univers, positions ;
- P1 : fundamentals, sentiment, analystes, scores ;
- P2 : rapports historiques et outils de recherche.

### Tests

- exécuter la suite existante sans modification ;
- exécuter `test_backtest_live_parity_golden.py` ;
- exécuter les tests calendrier/PIT/Oracle ;
- capturer tous les échecs préexistants séparément.

### Definition of Done

- ADR approuvés ;
- baseline US reproductible ;
- matrice des tables complète ;
- aucun changement de code métier ;
- gate Sprint 0 = GO.

### Rollback

Aucun changement runtime ; suppression possible des seuls artefacts d’audit.

## 5. Sprint 1 — `MarketContext` et registre de marchés

> **Terminé — GO le 19 septembre 2026.** Implémentation et preuves : [Sprint 1 — MarketContext et registre](./sprint_1_market_context.md).

### Objectif

Introduire le marché comme contrat explicite sans modifier les résultats US.

### Conception

Créer des objets immuables :

```text
MarketCode
MarketContext
MarketRegistry
MarketCompatibilityError
```

Champs minimaux : marché, pays, devise, timezone, calendrier, benchmark, secteur, règles d’exécution, coûts, capacités.

### Fichiers cibles probables

```text
common/market_context.py                 nouveau
common/config_loader.py                  chargement registre
config/markets/market_us.yaml                nouveau
config/markets/market_cn.yaml                 nouveau mais disabled
config/markets/market_cn_bj.yaml                nouveau mais disabled
tests/test_market_context.py             nouveau
```

### Étapes

1. définir les schémas de configuration ;
2. valider les codes et timezones ;
3. résoudre `US_EQ` par défaut ;
4. empêcher un contexte inconnu ;
5. ajouter fingerprint stable ;
6. rendre l’objet sérialisable dans les manifests ;
7. ne brancher encore aucun comportement CN ;
8. ajouter une compatibilité temporaire quand `market_code` est absent : US + warning.

### Tests

- résolution US par défaut ;
- résolution CN explicite ;
- contexte immuable ;
- fingerprint déterministe ;
- erreur sur devise/timezone/calendrier incohérents ;
- absence d’état global partagé entre threads/runs ;
- config US identique aux constantes historiques.

### Gate

- toutes les commandes US sans nouveau flag se comportent à l’identique ;
- aucune page IHM ne change encore de sélection par défaut ;
- CN est visible uniquement comme contexte désactivé.

## 6. Sprint 2 — Référentiel instruments et mappings fournisseurs

> **Terminé — GO le 19 septembre 2026.** Implémentation, audit à blanc et preuves : [Sprint 2 — référentiel instruments](./sprint_2_referentiel_instruments.md).

### Objectif

Créer l’identité stable qui remplacera progressivement `symbol`.

### Migrations

Créer :

```text
markets
instruments
instrument_provider_symbols
instrument_status_history
market_sessions
market_execution_rules
```

Livrables obligatoires :

```text
alembic/versions/00xx_market_instrument_foundation.py
database/sql/market/markets.sql
database/sql/market/instruments.sql
database/sql/market/instrument_provider_symbols.sql
database/sql/market/instrument_status_history.sql
database/sql/market/market_sessions.sql
database/sql/market/market_execution_rules.sql
```

### Contraintes

- PK interne `instrument_id` ;
- unique `(exchange_mic, local_symbol)` ;
- périodes fournisseur non chevauchantes ;
- devise ISO ;
- dates listing/delisting cohérentes ;
- aucun symbole fournisseur orphelin ;
- marché cohérent avec la place.

### Repository

Créer des méthodes :

```text
resolve_instrument(market_code, mic, local_symbol)
resolve_provider_symbol(provider, provider_symbol, as_of)
list_instruments(market_code, as_of, filters)
load_status_asof(instrument_id, date)
```

### Backfill US à blanc

Avant écriture :

- simuler le mapping de tous les `stock_metadata.symbol` ;
- lister ambiguïtés, symboles avec point, ADR, OTC et classes ;
- ne pas inventer de MIC si l’exchange est insuffisant ;
- prévoir un état `mapping_pending` plutôt qu’un faux mapping.

### Tests

- même symbole local sur deux MIC ;
- changement de ticker dans le temps ;
- mapping Tushare/EODHD/Alpaca distinct ;
- résolution as-of ;
- refus de deux mappings primaires actifs ;
- migration idempotente.

### Gate

- schéma installé ;
- aucune table actuelle modifiée fonctionnellement ;
- taux de mapping US mesuré ;
- ambiguïtés documentées avant Sprint 5.

## 7. Sprint 3 — Marché sur les parents de runs et batches

### Objectif

Faire porter le scope marché par les objets parents avant les données détaillées.

### Tables à étendre

- `model_training_batch` ;
- `model_training_run` par héritage/contrôle ;
- registry et serving batch ;
- `tradable_universe_runs` ;
- runs screener/backtest/risque concernés ;
- manifests d’artefacts.

### Colonnes batch recommandées

```text
market_code
calendar_id
base_currency
benchmark_instrument_id
universe_id
universe_fingerprint
sector_taxonomy
market_context_fingerprint
```

### Étapes

1. colonnes nullable ;
2. backfill `US_EQ` ;
3. vérifier enfants incohérents ;
4. mettre à jour l’écriture des nouveaux runs ;
5. rendre obligatoire sur les nouveaux batches ;
6. conserver lecture legacy avec warning ;
7. exposer dans diagnostics et rapports ;
8. ajouter index par `(market_code, status, started_at)`.

### Tests

- batch US hérite du défaut ;
- batch CN exige contexte explicite ;
- enfant incompatible refusé ;
- manifest différent si benchmark/calendrier change ;
- ancienne campagne US lisible ;
- nouveau batch sans marché impossible.

### Gate

- 100 % des nouveaux runs marqués ;
- 100 % des anciens batches classés US ou placés en quarantaine explicite ;
- aucun changement de résultat ML.

## 8. Sprint 4 — Calendrier et PIT multi-marchés

### Objectif

Remplacer les dépendances temporelles implicites NYSE par un service générique.

### API cible

```text
get_market_calendar(context)
session_dates(context, start, end)
session_bounds(context, date)
next_session(context, date, nth)
previous_session(context, date, nth)
advance_sessions(context, date, count)
dataset_cutoff(context, dataset, date)
```

### Compatibilité

Conserver :

```text
nyse_session_dates(...)
get_nyse_session_bounds(...)
next_trading_day(...)
```

comme wrappers US dépréciés.

### Source des sessions

Priorité :

1. table canonique `market_sessions` ;
2. calendrier bibliothèque validé ;
3. aucun fallback weekday-only en production CN ;
4. fallback US historique seulement avec warning actuel.

### PIT

Faire évoluer `DataAvailabilityInfo` :

- pas de timezone New York implicite dans les appels critiques ;
- cutoff fourni par dataset ;
- timestamps timezone-aware ;
- politique de publication par source ;
- quality state suspension/closed/not-yet-available.

### Tests

- DST US sans heure UTC fixe ;
- `Asia/Shanghai` ;
- jours fériés différents ;
- segments matin/après-midi ;
- H20 = 20 sessions ;
- annonce publiée après cutoff ;
- erreur si calendrier CN absent ;
- wrappers NYSE identiques.

### Gate — **GO (20 septembre 2026)**

Preuves : [Sprint 4 — calendrier et PIT multi-marchés](./sprint_4_calendrier_pit_multi_marches.md).

- hash des dates US inchangé sur plusieurs années ;
- aucun code Oracle/backtest CN ne peut appeler directement le calendrier NYSE ;
- calendrier CN chargeable mais non encore consommé par des données canoniques.

## 9. Sprint 5 — Migration canonique US vers `instrument_id`

### Objectif

Prouver que l’architecture multi-marché fonctionne avec le marché existant avant CN.

### Lot 5A — Barres, univers et scores

Ajouter `instrument_id` à :

- `stock_metadata` ou vue de compatibilité ;
- `stock_bars_daily` ;
- `stock_bars` ;
- `stock_quote_snapshots` ;
- `stock_scores` ;
- `stock_scores_history` ;
- `tradable_universe_history`.

### Lot 5B — ML

- `model_predictions` ;
- `global_rank_history` ;
- `global_oracle_labels` ;
- `oracle_extreme_predictions` ;
- registry/metrics/diagnostics lorsque nécessaire.

### Lot 5C — Features PIT

- fondamentaux ;
- earnings ;
- analystes ;
- sentiment ;
- corporate actions.

### Stratégie technique

1. ajout nullable ;
2. backfill chunké et reprenable ;
3. double écriture ;
4. comparaison symbol/instrument ;
5. nouvelle clé/index ;
6. lecture instrument-first ;
7. FK obligatoire ;
8. ancienne clé conservée temporairement ;
9. rapport des requêtes symbol-only restantes.

### Points sensibles

- longueurs incohérentes `VARCHAR(10|20|32|50|100)` ;
- classes `BF.A`, suffixes fournisseurs et ADR ;
- tables historiques volumineuses ;
- durée de verrouillage MySQL lors de reconstruction d’index ;
- reprise après interruption ;
- sauvegarde avant chaque migration destructive.

### Tests

- repository symbol et instrument retournent le même US ;
- hashes DataFrame identiques ;
- Oracle labels identiques ;
- prédictions identiques ;
- backtest golden identique ;
- contraintes empêchent orphelins et incohérences ;
- performance SQL mesurée.

### Gate majeur

```text
US parity = PASS
critical instrument coverage = 100%
critical symbol-only joins = 0
CN canonical writes = still disabled
```

### Gate — **GO (21 septembre 2026)**

- migrations `0087` et `0088` appliquées ;
- `34 091` instruments US canoniques ;
- `33/33` tables couvertes à 100 % ;
- hashes legacy/canoniques identiques sur barres, prédictions, rangs et Oracle ;
- `33` FK, `33` index et `66` triggers actifs ;
- jointures critiques symbol-only : `0` ;
- écritures canoniques CN : `0` ;
- suite complète : `5 796` tests réussis, aucun échec.

Le Sprint 7 n''est plus bloqué par le Sprint 5, mais reste dépendant des gates
de staging et de qualité du Sprint 6.

## 10. Sprint 6 — Sources gratuites BaoStock et staging brut multi-fournisseurs

### Décision fournisseur gratuite

BaoStock est la source primaire du socle marché. AKShare est facultatif et non bloquant. RQData/Tushare ne sont pas requis. Le détail exécutable, les commandes et les limites sont dans [sprint_6_sources_gratuites_baostock.md](./sprint_6_sources_gratuites_baostock.md).

### Objectif

Créer et migrer la base physique `alpha_trade_cn`, puis collecter les sources chinoises de façon idempotente sans les exposer aux modules métier. La base US `alpha_trade` n’est jamais utilisée comme destination d’un batch CN.

### Fichiers probables

```text
service/tushare/__init__.py
service/tushare/client.py
service/tushare/accounts.py
service/tushare/quota.py
service/tushare/retry.py
service/tushare/adapters.py
service/tushare/symbols.py
service/tushare/models.py
dataIntegrityEngine/cn_ingestion.py
config/markets/market_cn.yaml
batch_cn.yaml
```

### Endpoints P0

- security master ;
- trade calendar ;
- daily bars ;
- adjustment factors ;
- suspension/resumption ;
- daily price limits ;
- name/ST/board history ;
- benchmark index bars ;
- sector membership si accessible.

### Staging

Créer tables brutes avec :

```text
provider
provider_symbol
business_date
payload_hash
raw_payload/reference
observed_at
available_at
source_revision
run_id
```

### Batchs

Séparer :

- master/calendrier, faible fréquence ;
- daily market data ;
- statuts/suspensions/limites ;
- backfill historique ;
- data quality.

Tous doivent suivre les notifications et compteurs communs du projet.

### Smoke

Échantillon obligatoire :

- Shanghai Main ;
- Shenzhen Main ;
- STAR ;
- ChiNext ;
- titre ST historique ;
- titre suspendu ;
- titre délisté ;
- IPO récent ;
- corporate action.

### Tests

- token absent ;
- quota atteint ;
- 429/5xx/retry ;
- page vide ;
- reprise ;
- doublon ;
- correction fournisseur ;
- encodage chinois ;
- zéros initiaux des codes ;
- hash et lineage.

### Gate

- aucune écriture canonique ;
- smoke validé manuellement ;
- compteurs exacts ;
- coûts/quota mesurés ;
- reprise démontrée.

## 11. Sprint 7 — Canonicalisation CN P0

### Objectif

Transformer le staging en données utilisables par le moteur commun.

### Étapes

#### 7.1 Instruments

- mapping Tushare → instrument ;
- MIC/board/devise/type ;
- listing/delisting ;
- noms chinois/anglais ;
- statuts historisés.

#### 7.2 Sessions

- calendrier par place ;
- jours fermés exceptionnels ;
- segments de session ;
- contrôle croisé Shanghai/Shenzhen.

#### 7.3 Barres

- unités prix/volume/montant ;
- OHLC brut ;
- facteurs d’ajustement séparés ;
- convention des rendements ;
- source et qualité ;
- aucune barre inventée sur suspension.

#### 7.4 Limites et suspensions

- prix limites officiels/fournisseur ;
- état atteint/verrouillé si disponible ;
- suspension effective ;
- exceptions IPO/relisting ;
- statut ST et board à la date.

#### 7.5 Corporate actions

- splits/dividendes/rights si disponibles ;
- date ex, record, paiement et publication ;
- ajustement réconcilié.

### Contrôles

- OHLC cohérent ;
- volume/montant non négatif ;
- facteur valide ;
- aucune session non ouverte ;
- pas de barre réelle et suspension simultanées sans justification ;
- prix dans les limites avec tolérance de tick ;
- couverture par place/année.

### Gate

- échantillon manuel approuvé ;
- taux d’instruments non mappés sous seuil défini ;
- historique des délistés présent ;
- qualité suffisante pour publier un univers, pas encore pour entraîner.

## 12. Sprint 8 — Univers CN Point-In-Time

### Objectif

Publier pour chaque session la population réellement éligible à la date.

### Politique V1

Inclure :

- A-shares XSHG/XSHE ;
- boards identifiés ;
- historique minimal ;
- prix et liquidité valides ;
- barres réelles récentes.

Exclure ou marquer :

- non encore listé ;
- déjà délisté ;
- suspension ;
- données insuffisantes ;
- types non actions ;
- anomalie corporate action ;
- politique ST selon expérience ;
- entrée impossible car locked limit.

### Sorties

- `universe_run_id` avec `market_code=CN_A` ;
- membres par `instrument_id` ;
- reason codes ;
- métriques de couverture ;
- fingerprint ;
- fichier/manifest exportable.

### Anti-survivorship

Tester au moins :

- une date ancienne avec sociétés depuis délistées ;
- une IPO pas encore cotée à la date ;
- un changement ST ;
- une suspension longue ;
- un changement de ticker.

### Gate

- aucune utilisation de la liste actuelle pour reconstruire le passé ;
- raisons déterministes ;
- mêmes entrées = même fingerprint ;
- pas de mélange US ;
- tailles quotidiennes plausibles et expliquées.

## 13. Sprint 9 — Feature engine CN baseline

### Objectif

Produire un panel CN sans réutiliser des facteurs US sous de faux noms.

### Profil `cn_price_v1`

- rendements 1/3/5/10/20/60 ;
- momentum ;
- distances moyennes mobiles ;
- ATR/range/volatilité ;
- volume et turnover ;
- gaps ;
- position 52 semaines avec ancienneté suffisante ;
- rangs intra-CN ;
- rangs intra-secteur CN ;
- relatif benchmark ;
- breadth/dispersion ;
- indicateurs suspension/limit/ST/board.

### Refactor requis

- `benchmark_*` au lieu de `SPY_*` pour nouveaux artefacts ;
- groupements par marché/date ;
- assertions mono-marché ;
- secteur avec taxonomy/version ;
- montants en devise locale ;
- masque de données manquantes explicite.

### Validation

- distribution par board ;
- taux de NaN ;
- stabilité temporelle ;
- corrélations anormales ;
- features constantes ;
- importance dominée par un identifiant ;
- aucune valeur future ;
- reproductibilité.

### Gate

- panel généré sur plusieurs années ;
- couverture par famille documentée ;
- aucune feature macro US implicite ;
- benchmark validé ;
- prêt pour labels, pas encore de conclusion alpha.

## 14. Sprint 10 — Oracle Extreme et global ranking CN

### Objectif

Valider que le moteur d’amplitude et de classement fonctionne correctement sur le marché CN.

### Pré-enregistrement

Fixer avant le run :

- période ;
- univers ;
- horizons H5/H10/H15/H20 ;
- folds ;
- minimum cross-section ;
- métriques ;
- seuils GO/NO-GO ;
- sous-groupes board/année/régime ;
- politique d’ajustement des comparaisons multiples.

### Labels

- rendements futurs par sessions CN ;
- D1–D10 intra-date et intra-marché ;
- `available_date` après réalisation de l’horizon ;
- D et D+H réels ;
- quarantaine si suspension/corporate action invalide ;
- univers quotidien PIT.

### Entraînement

- baseline simple ;
- LightGBM/CatBoost selon protocole ;
- walk-forward ;
- OOS persistant ;
- aucune calibration utilisant le futur ;
- comparaison horizons.

### Diagnostics

- AUC/PR amplitude ;
- precision TOP20 ;
- lift vs hasard ;
- mouvement absolu futur ;
- répartition D1/D10 ;
- stabilité par fold ;
- couverture ;
- monotonicité des scores ;
- résultats économiques indicatifs sans optimisation d’exits.

### Gate

- Oracle supérieur à la baseline pré-enregistrée ;
- plusieurs folds valides ;
- pas de semestre unique dominant ;
- artefact CN complet ;
- aucune ligne US dans features/labels/prédictions.

## 15. Sprint 11 — Direction CN baseline

### Objectif

Mesurer la capacité prix-only à distinguer D1/D10 après Oracle, sans confondre amplitude et direction.

### Variantes

1. branche LONG seule ;
2. branche SHORT utilisée comme veto ;
3. modèle directionnel mutualisé ;
4. per-sector ;
5. per-symbol uniquement si support suffisant ;
6. règle simple momentum/abstention.

### Cible

Comparer :

- direction générique ;
- direction conditionnée sur les événements Oracle OOF ;
- first-touch si pertinent ;
- retour signé H5/H10/H20 ;
- abstention avec marge minimale.

### Métriques

- F1 LONG/SHORT ;
- precision conditionnelle Oracle ;
- AUC ;
- calibration ;
- rendement par tranche de probabilité ;
- couverture ;
- stabilité fold/semestre/board ;
- gain vs Oracle pur ;
- erreur catastrophique.

### Gate

Le sprint peut conclure NO-GO directionnel sans bloquer la suite infrastructure. Dans ce cas :

- Oracle reste utilisable pour recherche amplitude ;
- SHORT reste veto seulement si prouvé ;
- Sprint 15 devient prioritaire ;
- aucune sélection de seuil sur le holdout final.

## 16. Sprint 12 — Backtest chinois réaliste

### Objectif

Créer un moteur économique spécifique par politiques, sans dupliquer le simulateur.

**État Sprint 12-A (25/09/2026)** : [contrat d'exécution daté CN](./sprint_12a_contrat_execution.md)
installé et audité dans `alpha_trade_cn`, avec règles 2018–2025 et coûts
`RESEARCH_PROXY` explicitement non live. La simulation d'ordres,
l'inventaire/cash et la validation économique complète restent au
Sprint 12-B ; une éligibilité proxy n'est pas un fill.

**État Sprint 12-B (25/09/2026)** : [moteur de replay CN_A](./sprint_12b_replay_portefeuille_cn.md)
implémenté et testé, avec lecture seule de `alpha_trade_cn`, scénarios de
fills hypothétiques, inventaire T+1, cash, coûts et journal de non-fills.
Le gate technique est passé ; **le gate économique n'est pas passé** :
les corporate actions canoniques sont encore non classifiées et aucune
politique OOS de sélection/allocation/sortie n'a été figée puis rejouée
sur le portefeuille. Aucun rendement de 11-B n'est requalifié en PnL net.

### 12.1 Quantités et lots

- achats arrondis au lot ;
- fractions désactivées ;
- odd lots de vente ;
- minimum de ticket dans la devise locale ;
- rejet documenté.

### 12.2 T+1

- inventaire par lot/date ;
- quantité vendable ;
- protections différées ;
- aucune sortie impossible ;
- cash settlement séparé du settlement des titres.

### 12.3 Suspensions et limites

- calendrier instrument ;
- non-fill conservateur ;
- report d’ordre configurable ;
- annulation fin de journée ;
- logs des opportunités non exécutées ;
- scénarios permissif/base/conservateur.

### 12.4 Coûts

- profil versionné ;
- commission/minimum ;
- frais de place/transfert ;
- taxe selon côté ;
- slippage ;
- conversion FX optionnelle ;
- aucun nom `*_usd` dans le nouveau contrat métier.

### 12.5 Corporate actions/delisting

- rendement total ;
- position lors d’une suspension ;
- sortie forcée/delisting selon données disponibles ;
- aucune disparition silencieuse du portefeuille.

### Tests de scénarios

- achat veille d’une suspension ;
- stop le jour d’achat ;
- limit-down plusieurs jours ;
- IPO sans limite standard ;
- board 20 % ;
- odd lot ;
- corporate action ;
- fin de période avec position bloquée.

### Gate

- aucune règle CN simulée par accident avec le profil US ;
- rapports détaillent non-fills et coûts ;
- résultats reproductibles ;
- documentation des hypothèses.

## 17. Sprint 13 — Validation économique OOS

**État Sprint 13-A (26/09/2026)** : [préflight et protocole
gelé](./sprint_13a_preflight_economique.md). Les prédictions H20 des
huit semestres ont été auditées sans lire les labels futurs. Couverture
de fenêtre Oracle 97,75 % (gate 95 % passé), mais 6,01 % des fenêtres
Oracle croisent une action d'entreprise non classifiée (gate 5 %
dépassé). Verdict `BLOCKED_ACTION_NORMALIZATION` : normaliser les
événements, puis relancer le même audit avant la comparaison économique.
Ces prédictions OOS ont déjà été inspectées ; elles ne constituent pas
une confirmation indépendante d'une politique choisie aujourd'hui.

**État Sprint 13-A2 (26/09/2026)** : [normalisation ciblée des actions
CN](./sprint_13a2_normalisation_actions.md) terminée : 13 984 réponses,
14 630 événements réconciliés, 1 695 non résolus. Le gate inchangé de
5 % passe pour les quatre politiques (0,51–0,65 % de fenêtres encore
exposées), mais le replay doit encore appliquer les droits économiques
et gérer les cas non résolus avant toute comparaison de PnL. Aucun GO
économique ou live n'est émis.

**État Sprint 13-B (26/09/2026)** : [lanceur de replay
économique](./sprint_13b_validation_economique.md) et prérequis
fill-linked/corporate actions implémentés. Le smoke 2022H1 détecte
deux positions détenues touchées par des événements non résolus : leurs
marks ne sont pas des PnL valides. Le diagnostic des huit semestres est
terminé : 40 sous-runs, dont 8 invalides, sans GO économique. Le
[Sprint 13-B2](./sprint_13b2_remediation_positions.md) réconcilie trois
opérations détenues par une preuve séparée et rejoue les deux semestres
concernés ; une sortie 2025H1 reste censurée par suspension. Aucun
seuil ou modèle n'est ajusté.

**État Sprint 13-B3 (26/09/2026)** : la [campagne multi-seeds et l'audit
des huit titres bloquants](./sprint_13b3_audit_huit_blocages.md) montrent
398/480 replays valides. Un transfert d'actions de 2022 est réconcilié
dans une nouvelle preuve versionnée ; les autres cas restent censurés.
Les moyennes sur cellules valides ne constituent pas un GO économique.

**État Sprint 13-B4 (27/09/2026)** : les [preuves officielles de
dilution due aux actions rachetées](./sprint_13b4_dilution_actions_rachetees.md)
réconcilient trois autres opérations sans élargir la tolérance des
facteurs ni modifier la base CN. Deux replays ciblés totalisent 24/24
cellules valides, mais ne montrent aucun avantage économique stable :
2024H1 reste négatif et Oracle seul surpasse les veto en 2025H1.
Les autres positions censurées demeurent bloquées ; aucun GO
économique ou live.

**État Sprint 13-B5 (27/09/2026)** : [audit de matérialité et preuve
économique ciblée](./sprint_13b5_materialite_et_preuve_economique.md)
sur deux dividendes dont le facteur fournisseur est contradictoire et
sur un changement officiel de code sans droit nouveau. Les sorties
non négociables et les fractions de titre restent censurées. Le
référentiel historique du symbole `302132` doit être audité avant la
production ; aucun PnL issu de preuves différentes n'est agrégé.
Les 36 cellules ciblées B5 sont valides. Le replay homogène complet est
terminé : **462/480 cellules valides**, **18 censurées** et **154/160
triplets appariés valides**. Les comparaisons descriptives favorisent
faiblement les veto en moyenne, mais leur classement varie selon le
semestre ; le rapport garde `economic_go_allowed=false`. Ces périodes
OOS déjà inspectées ne constituent pas un holdout indépendant.

**État Sprint 13-C (27/09/2026)** : [audit de décision économique
appariée](./sprint_13c_decision_economique.md) terminé en lecture seule.
Le comparateur momentum a été rejoué avec la même preuve B5 : 138/160
cellules valides. Les quatre politiques ont 34/40 cohortes communes
au coût standard et 33/40 sous stress. Les rendements semestriels
moyens de ces cohortes restent négatifs et aucun veto ne domine de
manière stable. Verdict de recherche : NO_GO_ECONOMIC sur les cohortes
valides déjà inspectées ; 26 cohortes non comparables restent
inconnues, et le GO serving/live reste fermé.

### Objectif

Décider si les signaux baseline méritent une poursuite économique, sans optimiser le holdout.

### Protocole

- périodes train/validation/test figées ;
- coûts base et stress ;
- politique de fills base et conservatrice ;
- Oracle pur ;
- Oracle + LONG ;
- Oracle + LONG/SHORT-veto ;
- benchmark buy-and-hold pertinent ;
- stratégie naïve momentum ;
- exposition comparable.

### Rapports

- rendement net ;
- Sharpe/Sortino ;
- max drawdown ;
- turnover ;
- win rate et payoff ;
- profit factor ;
- exposition brute/nette ;
- capacité/liquidité ;
- pertes dues aux non-fills ;
- résultats par board, année, régime et capitalisation ;
- intervalle de confiance/bootstrap par date.

### Décision

```text
GO_BASELINE
GO_ORACLE_ONLY
NO_GO_DIRECTION_BUT_CONTINUE_DATA
NO_GO_ECONOMIC
BLOCKED_DATA_QUALITY
```

### Gate

Pas de live. Le GO autorise seulement l’IHM recherche et la collecte directionnelle.

## 18. Sprint 14 — IHM multi-marchés

**État Sprint 14-A (27/09/2026)** : [sélecteur de marché et vue de recherche CN_A isolée](./sprint_14a_ihm_recherche_isolee.md) en place sur Pipeline, Diagnostic ML et Backtesting. US reste le défaut. Les commandes CN d'entraînement, prédiction, backtest opérateur et live ne sont pas ouvertes ; les points ci-dessous sont le périmètre du Sprint 14 complet, pas des capacités déjà livrées.

**État Sprint 14-B (27/09/2026)** : [registre et diagnostic CN_A](./sprint_14b_diagnostic_campagnes_cn.md) accessibles depuis Diagnostic ML. Quatre campagnes de recherche ont un rapport et un protocole vérifiés ; la stabilité OOS par semestre est visible. Aucun batch de production CN ni lanceur CN n'est activé.

**État Sprint 14-C (27/09/2026)** : [replay CN_A de recherche depuis Backtesting](./sprint_14c_replay_recherche_ihm.md) disponible pour une cellule gelée du protocole 13-B, après préflight OOS/preuves/base CN. Historique et logs propres aux runs CN. Aucun GO économique, serving ou live ; les autres commandes CN et batchs ne sont pas ouverts dans l'IHM.

**État Sprint 14-D (27/09/2026)** : [folds Oracle/Ranking de recherche depuis Pipeline](./sprint_14d_pipeline_recherche_cn.md). Un lancement entraîne un fold CN et écrit ses prédictions OOS avec préflight de provenance, sortie et historique isolés. Il n'existe toujours pas de prédiction future/servable CN ; les commandes US restent masquées en vue CN.

### Objectif

Rendre le chemin CN utilisable sans permettre les erreurs de configuration.

### Pipeline

- sélecteur marché en premier ;
- univers filtrés ;
- fournisseurs compatibles ;
- benchmark/profils automatiques ;
- commande affiche `--market-code` ;
- résumé avant lancement ;
- CN live non proposé.

### Diagnostic ML

- marché, devise, calendrier, benchmark, horizon ;
- entraînés/servables ;
- qualité Oracle ;
- stabilité folds ;
- performance directionnelle ;
- lineage données ;
- exports filtrés.

### Backtest

- marché déduit du batch ;
- changement manuel interdit si incompatible ;
- profil CN automatique ;
- T+1/limites/lots/coûts visibles ;
- résultats en CNY et devise consolidée ;
- avertissement si hypothèse de fill dégradée.

### Batchs

- collectes CN chargées depuis `batch_cn.yaml`, séparées de `batch.yaml` ;
- base cible et `market_code` affichés ;
- couverture ;
- quota ;
- dernière session attendue ;
- qualité ;
- notifications.

### Tests IHM

- isolation des listes ;
- persistance état par page sans singleton dangereux ;
- commandes générées ;
- defaults US inchangés ;
- CN indisponible tant que gates absents ;
- messages non techniques et actionnables.

### Gate

- utilisateur débutant ne peut pas mélanger batch/univers/marché ;
- US reste inchangé ;
- recherche CN entièrement lançable depuis l’IHM.

## 19. Sprint 15 — Données directionnelles CN

### Objectif

Ajouter les données absentes du marché US susceptibles d’aider D1/D10.

### 15A Money Flow

**Audit 15-A0 (27/09/2026) :** [rapport de faisabilité PIT](./sprint_15a0_audit_money_flow_pit.md). Le flux individuel Eastmoney/AKShare est accessible mais le smoke réel plafonne à 120 séances récentes ; la variante historique B1 de Sprint 16 reste `NO_GO_HISTORICAL_FREE`. Une collecte prospective de recherche demeure possible sous réserve de qualité et de disponibilité PIT.

- normalisation montant/taille ;
- petits/moyens/grands/très grands ordres si définition fournisseur ;
- ratios au turnover ;
- surprises/z-scores PIT ;
- trajectoires J-1/J-5/J-10 ;
- divergence prix/flux.

### 15B Margin/Lending

**Audit 15-B0 (27/09/2026) :** [rapport source et PIT](./sprint_15b0_audit_margin_lending_pit.md). Relevés historiques par titre SSE/SZSE réellement accessibles depuis le poste (`GO_SOURCE_CANDIDATE`), mais la couverture quotidienne et les vintages/horaires historiques ne sont pas encore prouvés (`NO_GO_ML_PIT_YET`). Sprint 15-B1 = backfill pilote et contrôle, sans ouvrir l'ablation B2.

**15-B1 terminé le 28/09/2026 :** [rapport du pilote](./sprint_15b1_backfill_pilote_margin_lending.md). 16 ancrages et 40 journées hebdomadaires 2018–2025 collectés, zéro échec de lecture ; éligibilité, écarts détail/résumé et disponibilité PIT restent à résoudre en 15-B2 avant le ML.

**15-B2 audité le 28/09/2026 :** [contrat et résultats](./sprint_15b2_eligibilite_et_contrat_pit.md). Listes Shenzhen rapprochées sur les 16 ancrages : 100 % des actions éligibles du référentiel ont un détail. Shanghai : liste historique non qualifiée et 3 019 transitions non réconciliées conservées en quarantaine. Proxy à la clôture de la deuxième séance suivante, explicitement non certifié PIT. Aucun entraînement ni écriture métier. Les gates de sortie PIT ne sont pas satisfaits ; prochaine tranche proposée 15-B3 = qualification des blocages, pas ablation ML.

- financing balance/change ;
- financing buys/repayments ;
- lending balance/change ;
- disponibilité réelle vs activité ;
- ratios au float/turnover ;
- retard de publication.

### 15C Analystes et forecasts

**15-C0 audité le 29/09/2026 :** [audit des analystes et prévisions PIT](./sprint_15c0_audit_analystes_pit.md). Aucun historique analyste dans `alpha_trade_cn`. Eastmoney/AKShare retourne des rapports anciens, mais pas les versions ni horodatages d'ingestion d'époque ; seulement 5/16 titres d'un petit échantillon Oracle ont un rapport en 2024, et 5/16 en 2025. RQData documente des timestamps d'ingestion et une option excluant les compléments historiques, mais accès et couverture réelle non vérifiés. **Pas de 15-C1 ML historique sur l'archive gratuite actuelle ; serving inchangé.**

- ancienne estimation ;
- nouvelle estimation ;
- horizon/période fiscale ;
- nombre d’analystes ;
- dispersion ;
- révision normalisée ;
- timestamp publication/available_at ;
- consensus reconstruit uniquement avec observations connues.

### 15D Événements

**15-D0 audité le 29/09/2026 :** [audit PIT des événements](./sprint_15d0_audit_evenements_pit.md). CNINFO expose des PDF officiels de prévisions de résultats avec identifiant et date ; sur 279 paires Oracle d'un petit échantillon 15-B5, seules 21 ont une annonce dans les 20 jours précédents (93 dans les 90 jours). Horodatages souvent normalisés à minuit, corrections et extraction encore à qualifier : 15-D1 limité à un pilote documentaire sous proxy PIT. Les listes Dragon/Tiger historiques sont consultables, mais l'agrégat Eastmoney contient des rendements futurs `D1…D30` interdits comme features ; 15-D2 est un audit séparé. **Aucun modèle ni serving modifié.**

**15-D1 terminé le 29/09/2026 :** [pilote documentaire et couverture complète](./sprint_15d1_pilote_guidance_pit.md). Huit PDF CNINFO lus et une paire annonce/correction vérifiée visuellement ; l'inventaire de masse Eastmoney recouvre seulement 23 831/464 834 décisions Oracle TOP20 dans les 20 jours antérieurs (5,13 %). L'archive n'est pas un historique de versions PIT certifié et les valeurs numériques restent en quarantaine. **Pas de GO ML historique, aucun serving modifié.** 15-D2 Dragon/Tiger reste séparé.

**15-D2 terminé le 29/09/2026 :** [audit officiel Dragon/Tiger](./sprint_15d2_audit_dragon_tiger_pit.md). Les tableaux SSE principal + STAR et SZSE ont été rapprochés de l'archive Eastmoney sur quatre séances : 228/228 couples marché–titre actions A concordants. Les montants/motifs par siège, l'heure historique de publication et l'apport directionnel restent non établis ; rendements futurs et taux de réussite de l'agrégateur exclus. **Pas de GO ML PIT ni de changement serving.**

**15-D3 terminé le 30/09/2026 :** [robustesse historique des listes Dragon/Tiger](./sprint_15d3_robustesse_historique_dragon_tiger.md). Deux séances mécaniquement choisies par an sur 2018–2025 : **985/985 couples séance–marché–titre actions A concordants** après séparation de deux avis de financement 2018. Les deux listes de sièges SSE sont présentes sur 395/396 lignes ; les montants présents sont structurellement cohérents et 16 détails SZSE sont lisibles. Les montants entre fournisseurs et l'heure historique de diffusion ne sont pas certifiés. **Toujours aucun entraînement ni serving.**

**15-D4 terminé le 30/09/2026 :** [contrat temporel et couverture Oracle](./sprint_15d4_contrat_temporel_couverture_dragon_tiger.md). Archive assainie 2023-11 à 2025-12 : 32 469 événements titre–séance mappés à leur identifiant daté. Sur 464 834 décisions Oracle TOP20 OOF, couverture fraîche ≤ 5 séances de 14,435 % sous J+1 et 12,138 % sous J+2. Même séance interdite, heures de publication historiques non certifiées. **Aucune ablation ML ni production autorisée à ce stade.**

**15-D5 terminé le 30/09/2026 :** [préflight directionnel et observations prospectives](./sprint_15d5_preflight_dragon_tiger_et_observations.md). Le diagnostic brut J+2/5 montre 19 526 D1 pour 7 704 D10 parmi les extrêmes couverts, mais n'est pas apparié au mouvement antérieur et ne permet pas de règle. Les droits de réutilisation de l'archive et les heures historiques restent non qualifiés : **NO_GO ML**. Un journal manuel officiel, horodaté et append-only, a passé un smoke rétrospectif de 76 motifs ; aucun batch planifié ni serving.

**15-D6 mis en service recherche le 30/09/2026 :** [deux passages prospectifs officiels](./sprint_15d6_collecte_prospective_dragon_tiger.md) installés sous deux tâches Windows distinctes, 17:30 après clôture et 08:30 avant ouverture Shanghai. Calendrier officiel 2026 explicite, 2027 fail-closed ; premier passage manuel avant ouverture : 64 motifs pour le 29/09, lus avant 09:15 le 30/09. Observations horodatées et corrections suivies, sans certification PIT, ML ou live. Telegram local reste bloqué par une erreur de chaîne TLS ; aucune désactivation de la vérification HTTPS.

**15-D7 pré-enregistré le 30/09/2026 :** [appariement outcome-blind Dragon/Tiger](./sprint_15d7_protocole_appariement_dragon_tiger.md), exact même séance et board, calipers figés sur rang Oracle et mouvement préalable, refus des scores tardifs et des colonnes de futur. Prévalidation réelle de l'export D8 du 08/10 : 1 034 candidats et snapshot officiel contrôlés, statut `WAITING_FOR_DECISION_CUTOFF`. Appariement réel seulement après 09:15 Shanghai le 08/10 et contrôle du dernier passage D6 ; aucun résultat D1/D10, entraînement ou serving.

**15-D7a rattrapage terminé le 30/09/2026 :** [chemin canonique incrémental](./sprint_15d7a_rattrapage_canonique_2026.md) borné à 2026 et insert-only : 210/210 lots, 5 242 actions, 180 séances ouvertes et 936 103 barres d'actions jusqu'au 29/09. Les empreintes des séances 2018–2025 ne changent pas. Ce backfill ne transforme pas les décisions de septembre en prédictions PIT.

**15-D8 premier export prospectif réel le 30/09/2026 :** [Oracle CN H20 TOP20 avant 09:15 Shanghai](./sprint_15d8_export_oracle_prospectif.md) sur artefact figé, univers pré-ouverture et séance du 30/09 collectée en 209/209 lots. Préflight `READY_TO_SCORE`, 5 166 titres éligibles, 1 034 candidats pour la décision du 08/10 ; fichier et empreinte contrôlés. Collecte et score encore manuels, D7 en attente du cutoff futur, aucun serving ni ordre.

**15-D9 journal quotidien installé le 30/09/2026 :** [chaîne prospectif CN après clôture](./sprint_15d9_journal_oracle_prospectif_quotidien.md), batch IHM et tâche Windows à 18:15 Shanghai. Collecte J reprenable et vérifiée, score D8 K immuable uniquement avant cutoff, notifications communes, aucune rétrodatation/serving/trading. Contrôle réel `SKIP_CLOSED` pendant les congés d'octobre ; premier nouveau cycle utile attendu le 08/10 après clôture. Calendrier 2027 et session Windows Interactive restent des dépendances opérationnelles.

**15-D10 journal d'appariement quotidien préparé le 30/09/2026 :** [enchaînement D8 × D6 après cutoff](./sprint_15d10_appariement_d7_quotidien.md), lecture des seuls scores et snapshots disponibles avant 09:15, paires outcome-blind, sans labels, serving ni trading. Première séance possible : 08/10 à 09:30 Shanghai ; elle n'établira pas à elle seule les gates D7.

**15-D11 cumul pré-enregistré le 30/09/2026 :** [progression D7 sans lecture d'issues](./sprint_15d11_cumul_d7_outcome_blind.md), contrôle des empreintes D8/D10 et des lacunes quotidiennes, agrégation des paires et bilan de chaque gate figé. Premier rapport réel : `WAITING_FOR_FIRST_PROSPECTIVE_MATCH`, zéro séance ; aucun résultat D1/D10 n'a été consulté.

- Dragon/Tiger list ;
- motif ;
- annonces ;
- guidance/forecast ;
- changements actionnaires/holdings ;
- features uniquement après disponibilité.

### Qualité

Pour chaque famille : couverture, fraîcheur, révisions, unités, outliers, biais board/taille, coût/quota, duplications.

### Gate

Une famille insuffisamment PIT n’entre pas dans les modèles, même si elle paraît prédictive en analyse naïve.

## 20. Sprint 16 — Campagne pré-enregistrée D1/D10

### Objectif

Tester les nouvelles familles sans data snooping.

### Variantes

```text
B0 prix-only gelé
B1 + money flow
B2 + margin/lending
B3 + analyst revisions
B4 + events/top-list
B5 combinaison des seules familles ayant passé leur gate individuel
```

Chaque famille est testée :

- LONG ;
- SHORT/veto ;
- D1 vs D10 ;
- amplitude ;
- horizons multiples prévus ;
- modèle simple puis challengers.

### Discipline

- holdout final inaccessible pendant le choix ;
- mêmes folds ;
- même univers ;
- mêmes coûts ;
- mêmes seeds ;
- correction multiple ;
- résultat par date, pas seulement par ligne ;
- combinaison interdite avant preuve individuelle.

### Critères GO indicatifs à pré-enregistrer

- delta AUC/precision OOF minimal ;
- amélioration économique nette ;
- majorité de folds favorable ;
- pas de dépendance à un seul semestre ;
- couverture minimale ;
- signal conservé après neutralisation taille/secteur/board.

### Sortie

- profil CN final candidat ;
- familles rejetées documentées ;
- features et sources gelées ;
- décision sur achat éventuel de RQData.

## 21. Sprint 17 — Industrialisation recherche et données

**17-A audité le 30/09/2026 :** [audit opérationnel CN](./sprint_17a_audit_exploitation_cn.md) en lecture seule, quatre findings : sauvegarde CN non planifiée (critique), contrôle qualité staging désactivé, collecteur général désactivé à ne pas activer sans réconciliation avec D9, et quatre batchs de recherche CN encore dans `batch.yaml`. Aucune tâche installée ni base n'a été modifiée. Ordre de suite : 17-B sauvegarde/restauration séparée, 17-C propriétaire unique de la collecte et qualité quotidienne, 17-D migration contrôlée du catalogue après le premier cycle réel.

**17-B terminé le 30/09/2026 :** [sauvegarde CN et restauration isolée](./sprint_17b_sauvegarde_restauration_cn.md). Une archive complète `alpha_trade_cn` existe dans `backups/cn/db` ; sa restauration dans une base temporaire a été vérifiée sur 21 tables et 57 188 133 lignes sans écart, puis la base temporaire a été supprimée. Le batch hebdomadaire de `batch_cn.yaml` est actif et la tâche Windows dédiée est installée. Aucun effet sur les sauvegardes US ni sur les tâches CN prospectives.

**17-C implémenté le 01/10/2026, validation opérationnelle en attente :** [propriétaire unique et qualité CN](./sprint_17c_qualite_quotidienne_proprietaire_collecte.md). D9 conserve seul les écritures canoniques quotidiennes ; le collecteur générique reste désactivé. Un contrôle read-only D6/D9/D10, conscient des jours fériés, est installé à 23:30 Shanghai, après la fenêtre de collecte D9, et notifie les échecs. Le rattrapage manuel du 30/09 ne vaut pas preuve D9. Gate de clôture : sept séances ouvertes consécutives sans anomalie critique inexpliquée, au plus tôt du 08 au 16/10/2026. Aucun serving ou ordre CN activé.

**17-D préparé, non basculé :** [plan de migration contrôlée des catalogues](./sprint_17d_preparation_bascule_catalogues.md). L'IHM, les lanceurs Windows et les trois runners D6/D9/D10 acceptent désormais le futur catalogue CN explicite et refusent doublon ou route US ; les tests de simulation passent. Les quatre tâches installées lisent encore `batch.yaml` et restent sans changement. Leur déplacement vers `batch_cn.yaml` attend au minimum un premier cycle réel complet après le 8 octobre, puis une bascule hors fenêtre et une vérification de parité. Le gate des sept séances de 17-C reste distinct.

### Objectif

Rendre le pipeline CN maintenable au quotidien.

### Batchs

- backfill ;
- incrémental ;
- calendrier/master ;
- bars/limits/suspensions ;
- directionnel ;
- data quality ;
- sauvegardes ;
- réconciliation.

### Exigences

- `batch_cn.yaml` ;
- timezone explicite ;
- rattrapage J-N/J ou second passage conditionnel ;
- idempotence ;
- notification mail/Telegram ;
- état DB ;
- quotas ;
- procédures de relance ;
- page Batch ;
- sauvegarde séparée de `alpha_trade_cn`, restauration testée sans toucher `alpha_trade`, et artefacts CN isolés.

### Monitoring

- dernière session CN ;
- barres attendues/reçues ;
- instruments non mappés ;
- suspensions/limites ;
- révisions fournisseur ;
- drift features ;
- drift Oracle/direction ;
- taille staging/canonique ;
- latence de publication.

### Documentation

- onboarding ;
- runbooks ;
- incident fournisseur ;
- quota ;
- reprocessing ;
- ajout d’un endpoint ;
- renouvellement univers ;
- promotion modèle.

### Gate

- sept cycles quotidiens consécutifs sans anomalie critique non expliquée ;
- reprise après interruption démontrée ;
- restauration backup testée ;
- qualité affichée dans l’IHM.

## 22. Sprint 18 — Abstraction broker et shadow mode CN

**État 18-D (01/10/2026)** : [port OMS complet et doubles mock/replay](./sprint_18d_port_oms_et_doubles.md) ajoutés sans route paper/live CN. L'adaptateur Alpaca US et ses commandes restent en place ; les doubles sont explicitement exclus du routeur paper/live. Le pilote 18-C est préparé, mais sa tentative attend les observations post-clôture du 8 octobre.

### Objectif

Préparer l’exécution sans envoyer d’ordre réel.

### Refactor

Séparer :

```text
ExecutionBrokerPort
AlpacaBrokerAdapter
MockBrokerAdapter
ReplayBrokerAdapter
ChinaBrokerAdapter futur
BrokerRouter
```

Supprimer les imports Alpaca du contrat générique ; conserver les conversions de payload/status dans l’adaptateur Alpaca.

### Shadow CN

- générer les intentions ;
- valider lots/T+1/limites ;
- simuler accept/reject/fill ;
- ne jamais appeler un endpoint d’ordre ;
- comparer prix théorique aux données suivantes ;
- conserver audit complet.

### Choix broker

Évaluer :

- accès géographique et réglementaire ;
- Stock Connect/A-shares ;
- paper API ;
- market data ;
- ordres/positions/fills ;
- devise/FX ;
- corporate actions ;
- short/borrow ;
- coût et stabilité.

### Gate

- Alpaca US non régressé ;
- routeur bloque un marché incompatible ;
- shadow CN fonctionne sans broker ;
- symbologie future raccordable via mappings ;
- aucune activation live en config.

## 23. Sprint 19 — Paper/canary/live optionnel

### Prérequis absolus

- stratégie CN économiquement validée ;
- fournisseur quotidien stable ;
- broker choisi ;
- contrats/permissions confirmés ;
- règles et coûts du canal vérifiés ;
- rapprochement opérationnel ;
- conformité/fiscalité examinées par le propriétaire du compte.

### Étapes

1. paper si disponible ;
2. shadow contre paper ;
3. canary un instrument ;
4. canary petit univers ;
5. capital minimal ;
6. monitoring rapproché ;
7. promotion graduelle ;
8. rollback immédiat possible.

### Kill switches

- global ;
- par marché ;
- par compte ;
- données stale ;
- calendrier incohérent ;
- limite/suspension inconnue ;
- FX absent ;
- divergence positions ;
- taux de rejet ;
- perte/drawdown.

### Gate final

Une décision humaine explicite est obligatoire. Aucun GO recherche ou backtest ne vaut autorisation live.

## 24. Matrice de dépendances

```text
S0
 ├── S1 ── S4 ───────────────┐
 └── S2 ── S3 ── S5 ────────┼── S7 ── S8 ── S9 ── S10 ── S11
                    S6 ──────┘                     │
                                                  ├── S12 ── S13 ── S14
                                                  └── S15 ── S16 ── S17
                                                                  │
                                                                  S18 ── S19
```

S6 peut commencer après les contrats S0/S2 pour développer le staging, mais S7 ne peut écrire dans le canonique qu’après le GO S5.

S12 peut développer les règles avec des fixtures synthétiques dès S4, mais sa validation réelle dépend de S7–S10.

## 25. Ordre des migrations recommandé

```text
M1 markets + instruments + provider symbols
M2 status history + sessions + execution rules
M3 market columns on parent batches/runs
M4 instrument_id nullable on bars/universe/scores
M5 backfill US + validation
M6 instrument_id nullable on ML/features
M7 backfill US ML/features + validation
M8 new unique keys/indexes/FK
M9 Tushare staging
M10 CN canonical auxiliary tables
M11 constraints NOT NULL after dual-read transition
M12 risk/execution identity before live
```

Ne pas reconstruire plusieurs grandes PK dans une seule migration. Chaque migration volumineuse doit être chunkée, mesurée et précédée d’une sauvegarde restaurable.

## 26. Stratégie de compatibilité

### Anciennes commandes

Pendant la transition :

- absence de `--market-code` → `US_EQ` avec warning ;
- batch ancien → US si vérifié, sinon quarantaine ;
- fichier univers ancien → US tant qu’il réside dans l’emplacement legacy ;
- date de suppression de cette compatibilité documentée.

### Anciens artefacts

Créer un lecteur legacy qui enrichit en mémoire :

```text
market_code=US_EQ
currency=USD
calendar=NYSE
benchmark=SPY
```

Le lecteur ne doit jamais enrichir un artefact ambigu ou CN.

### Anciennes tables

Conserver `symbol` comme colonne de présentation/index secondaire. Ne pas la supprimer tant que rapports, exports et outils opérateur en dépendent.

## 27. Check-list de revue de code par sprint

Pour chaque PR/lot :

- [ ] marché transmis explicitement ;
- [ ] pas de singleton mutable ;
- [ ] pas de jointure symbole seule sur chemin critique ;
- [ ] timestamps timezone-aware ;
- [ ] `available_at` respecté ;
- [ ] groupes cross-sectionnels mono-marché ;
- [ ] unités et devise documentées ;
- [ ] idempotence ;
- [ ] logs sans secrets ;
- [ ] migration + SQL de référence ;
- [ ] tests unitaires ;
- [ ] tests intégration ;
- [ ] test US golden ;
- [ ] test CN spécifique si applicable ;
- [ ] documentation mise à jour ;
- [ ] rollback décrit.

## 28. Critères de programme

### Succès technique

- aucune collision instrument ;
- aucun mélange de marchés ;
- calendrier/PIT corrects ;
- US inchangé ;
- CN reproductible de l’ingestion au backtest ;
- reprise et monitoring opérationnels.

### Succès ML

- Oracle amplitude stable OOS ;
- direction mesurée indépendamment ;
- nouvelles données évaluées sans fuite ;
- couverture servable explicite ;
- aucune promotion sur métrique in-sample.

### Succès économique

- performance après coûts et non-fills ;
- robustesse aux hypothèses conservatrices ;
- drawdown/capacité acceptables ;
- valeur incrémentale face aux baselines.

### Succès opérationnel

- un opérateur peut choisir CN sans mélanger US ;
- toute donnée et tout signal ont un lineage ;
- incidents détectés ;
- live impossible avant autorisation explicite.

## 29. Première action concrète recommandée

Commencer par le Sprint 0, puis réaliser Sprints 1 à 5 comme un programme de fondation multi-marché exclusivement testé sur les données US.

La première donnée chinoise peut être collectée en staging pendant le Sprint 6, mais elle ne doit rejoindre le canonique qu’après cette preuve :

```text
Golden US avant migration
        ==
Golden US après MarketContext + instrument_id
```

Cette discipline paraît plus lente au départ, mais elle évite le scénario le plus coûteux : découvrir après plusieurs entraînements CN que les labels, les barres ou les rangs ont été mélangés avec des hypothèses US.

## 30. Documents de référence

**15-B6 exécuté et audité le 29/09/2026 :** [calendrier et extension OOF](./sprint_15b6_calendrier_et_extension_oracle_oof.md). Nouvelle campagne distincte de B4 : développement 2024H1/H2, confirmation historique 2025H1/H2, fenêtres directionnelles 504/126 avec gaps 20/20 et contrôles de disponibilité. Les deux extensions Oracle H20 LightGBM 2021H1/H2 sont terminées et vérifiées `OOS_RESEARCH_ONLY` ; 2020 manque d'historique. 57 tests ciblés passaient au jalon B6. Aucun modèle directionnel ni serving modifié.

**15-B7 préflight terminé le 29/09/2026 :** [jointures 2021 et gates directionnels réels](./sprint_15b7_jointures_2021_preflight_directionnel.md). TOP20 calculé sur tous les scores CN avant restriction XSHE, puis jointures aux retards 2/3/5 ; 4 978/5 166 paires complètes 2021H1/H2 au lag principal. Huit gates tâche × fold 2024–2025 passent sur les lignes et classes réelles ; 62 tests ciblés passent. Couverture étroite, PIT sous proxy, aucun entraînement directionnel ni conclusion de performance.

**15-B8 ablation terminée le 29/09/2026 :** [ablation directionnelle de la marge](./sprint_15b8_ablation_directionnelle_marge.md). Baseline prix comparée sur lignes identiques aux variantes flux, encours et combinée, deux tâches × deux modèles × quatre folds. Les 12 hypothèses principales donnent `NO_GO_INCREMENTAL_MARGIN` ; gain maximal d'AUC +0,0011 contre +0,015 requis, bornes inférieures corrigées toutes négatives. Aucun modèle en serving et PIT historique toujours non certifié.

**15-B5 clôturé le 29/09/2026 pour la préparation :** [features et jointures temporelles](./sprint_15b5_features_et_jointures_temporelles.md). Fenêtres 5/20 sans pont sur les trous, ratio atypique isolé, 24 jointures Oracle OOF H20 × retards 2/3/5 strictement antérieurs aux décisions ; audit indépendant réussi et 47 tests passent. Six semestres ne disposent pas des 630 séances OOF antérieures requises ; seuls 2025H1/H2 passent ce contrôle avant purge. Le masque complet prix/marge/labels conserve 8,50–19,66 % du TOP20 XSHE. Aucun entraînement ni changement de serving : prochaine tranche proposée, audit/pré-enregistrement d'un calendrier réalisable et du périmètre de baseline.

**15-B4 clôturé le 29/09/2026 pour la collecte et l'audit :** [dataset et protocole](./sprint_15b4_dataset_szse_et_preregistration.md). 1 942 séances terminées, zéro échec, 2 229 667 observations sur 2 229 675 lignes éligibles (99,9996 %), empreintes vérifiées et aucun doublon ; 35 tests ciblés passent. Huit observations absentes et deux séances sans proxy restent exclues des features utilisables ; un ratio supérieur à 1 est identifié et devra être isolé dans B5. Prochaine tranche proposée : fenêtres 5/20 séances et jointures temporelles Oracle/labels, avant évaluation. Archives sous proxy seulement : aucun modèle entraîné ni PIT strict certifié.

**15-B3 terminé le 28/09/2026 :** [qualification des blocages](./sprint_15b3_qualification_blocages.md). Les 40 listes quotidiennes Shenzhen correspondent aux 46 966 lignes du détail du pilote ; les huit relevés Shanghai sont stables à la relecture, mais les écarts comptables et l'éligibilité exhaustive restent non qualifiés. Les flux Shenzhen concordent avec le résumé sur la date contrôlée, les encours non. PIT strict toujours NO-GO. Prochaine tranche proposée 15-B4 : pré-enregistrement et dataset quotidien **Shenzhen uniquement, sous proxy explicite**, avant tout entraînement. Aucun batch métier ni modèle modifié.

- [Audit du code et roadmap d’intégration](./roadmap_integration_marche_chinois_audit_code.md)
- [Architecture des bases, batchs et configurations CN](./architecture_bases_batchs_configuration_cn.md)
- [Comparaison des données fournisseurs](./comparaison_data_fournisseur.md)
- [Actualisation des fournisseurs Chine](./actualisation_fournisseurs_chine.md)
- [Étude d’opportunité historique](./Étude%20d’opportunité%20—%20Extension%20d’α-Trade%20au%20marché%20actions%20chinois.md)

