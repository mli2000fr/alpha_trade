# Sprint planning détaillé — Intégration du marché chinois dans α-Trade

> Document d’exécution associé à `roadmap_integration_marche_chinois_audit_code.md`.  
> Date : 19 septembre 2026.  
> Cible : une intégration durable US + Chine permettant ingestion, recherche, entraînement, prédiction et backtest ; paper/live vient ensuite.  
> Ce document planifie les travaux. Il ne constitue pas une autorisation de modifier le code ni d’activer le trading réel.

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
| 6 | Client et staging Tushare | Collecte brute idempotente | 7 |
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
- staging fournisseur séparé, canonique commun ;
- batch ML mono-marché ;
- risque consolidable mais labels/rangs mono-marché ;
- symbole = attribut d’affichage, non identité ;
- US reste le défaut pendant la migration.

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
config/markets/us_eq.yaml                nouveau
config/markets/cn_a.yaml                 nouveau mais disabled
config/markets/cn_bj.yaml                nouveau mais disabled
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

### Gate

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

Sans ce GO, ne pas démarrer le Sprint 7.

## 10. Sprint 6 — Connecteur Tushare et staging brut

### Objectif

Collecter les sources chinoises de façon idempotente sans les exposer aux modules métier.

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
config/markets/cn_a.yaml
batch.yaml
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

- collectes CN séparées ;
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

- normalisation montant/taille ;
- petits/moyens/grands/très grands ordres si définition fournisseur ;
- ratios au turnover ;
- surprises/z-scores PIT ;
- trajectoires J-1/J-5/J-10 ;
- divergence prix/flux.

### 15B Margin/Lending

- financing balance/change ;
- financing buys/repayments ;
- lending balance/change ;
- disponibilité réelle vs activité ;
- ratios au float/turnover ;
- retard de publication.

### 15C Analystes et forecasts

- ancienne estimation ;
- nouvelle estimation ;
- horizon/période fiscale ;
- nombre d’analystes ;
- dispersion ;
- révision normalisée ;
- timestamp publication/available_at ;
- consensus reconstruit uniquement avec observations connues.

### 15D Événements

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

- `batch.yaml` ;
- timezone explicite ;
- rattrapage J-N/J ou second passage conditionnel ;
- idempotence ;
- notification mail/Telegram ;
- état DB ;
- quotas ;
- procédures de relance ;
- page Batch ;
- sauvegarde des nouvelles tables et artefacts.

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

- [Audit du code et roadmap d’intégration](./roadmap_integration_marche_chinois_audit_code.md)
- [Comparaison des données fournisseurs](./comparaison_data_fournisseur.md)
- [Actualisation des fournisseurs Chine](./actualisation_fournisseurs_chine.md)
- [Étude d’opportunité historique](./Étude%20d’opportunité%20—%20Extension%20d’α-Trade%20au%20marché%20actions%20chinois.md)

