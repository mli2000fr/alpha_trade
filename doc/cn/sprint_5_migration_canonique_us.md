# Sprint 5 — Migration canonique US vers `instrument_id`

## 1. Résultat recherché

Le Sprint 5 retire `symbol` de son rôle d’identité technique. Un ticker reste
affiché, exporté et accepté par les interfaces historiques, mais les faits sont
reliés par une clé immuable : `instruments.instrument_id`.

Cette migration est volontairement réalisée sur le marché US avant toute
écriture canonique chinoise. Elle prouve que l’architecture multi-marchés ne
modifie ni les données, ni les labels, ni les prédictions existantes.

Le gate de fin est strict :

```text
parité US                         = PASS
couverture des lignes titre      = 100 %
incohérences symbol/instrument   = 0
jointures critiques symbol-only  = 0
faits canoniques CN              = 0
```

### Statut exécuté — **GO (21 septembre 2026)**

Le Sprint 5 a été exécuté sur la base US réelle et son gate est vert :

- `34 091` instruments `US_EQ`, dont `33 560` issus de `stock_metadata` et
  `531` identités historiques conservées en `mapping_pending` ;
- `33` tables de faits équipées de `instrument_id` ;
- `157 751 541` lignes auditées, avec couverture critique `100 %`, aucune
  incohérence `symbol/instrument_id` et aucun orphelin critique ;
- `33` index, `33` clés étrangères et `66` triggers de compatibilité présents ;
- parité exacte des lectures legacy/canoniques sur les cinq jeux critiques ;
- `0` jointure critique encore limitée à `symbol` et `0` écriture canonique CN ;
- suite complète : `5 796 passed`, `34 skipped`, couverture `70,91 %`.

Les preuves machine sont conservées dans
`artifacts/audits/market_integration/sprint_05/`. Le Sprint 6 est débloqué ;
le Sprint 7 ne pourra publier des données CN qu''après ses propres gates de
staging et de qualité.

## 2. Pourquoi `symbol` ne suffit pas

`symbol` est une représentation locale et mutable. Un même texte peut exister
sur deux places, un fournisseur peut ajouter un suffixe et un émetteur peut
changer de ticker. À l’inverse, `instrument_id` désigne le même titre pendant
toute sa vie.

Le contrat devient :

```text
market_code + exchange_mic + local_symbol
                 │
                 ▼
        instruments.instrument_id
                 │
       ┌─────────┼─────────┐
       ▼         ▼         ▼
     barres    labels   prédictions
```

Les codes fournisseurs restent historisés dans
`instrument_provider_symbols`. Le provider de compatibilité
`legacy_us_symbol` représente le ticker utilisé par les anciennes tables US.

## 3. Périmètre migré

### 3.1 Marché, prix, sélection et univers

- `stock_metadata` ;
- `stock_bars_daily` ;
- `stock_bars` ;
- `stock_quote_snapshots` ;
- `stock_scores` ;
- `stock_scores_history` ;
- `tradable_universe_history`.

### 3.2 ML, Oracle et gouvernance

- `model_predictions` ;
- `global_rank_history` ;
- `global_oracle_labels` ;
- `oracle_extreme_predictions` ;
- `model_registry` ;
- `model_metrics`, `model_metrics_full` ;
- `model_batch_diagnostics`, `model_directional_oos_metrics` ;
- `champion_history`, `model_governance`.

### 3.3 Features PIT et événements

- `stock_fundamentals_daily` ;
- calendrier et historiques analystes ;
- `ticker_daily_sentiment_features`, `news_ticker_sentiment` ;
- événements et applications de corporate actions ;
- dépôts et événements SEC.

La liste exécutable unique est `FACT_TABLES` dans
`service/market/bootstrap_us_instruments.py`. Les migrations 0087 et 0088 ont
un test qui vérifie qu’elles couvrent exactement ce même ensemble.

## 4. Déroulement de la migration

### Phase A — Colonnes sans verrou fonctionnel

La migration `0087_us_fact_instrument_columns` ajoute un `BIGINT UNSIGNED`
nullable. L’application reste compatible pendant le remplissage.

SQL de référence :
`database/sql/migration_0087_us_fact_instrument_columns.sql`.

### Phase B — Bootstrap des instruments US

Le bootstrap :

1. lit `stock_metadata` hors crypto ;
2. normalise le ticker en majuscules ;
3. convertit l’exchange legacy en MIC (`NASDAQ→XNAS`, `NYSE→XNYS`,
   `AMEX→XASE`, `ARCA→ARCX`, `BATS→BATS`, `OTC→OTCM`) ;
4. construit un UUID déterministe ;
5. crée le mapping `legacy_us_symbol` ;
6. recherche les anciens tickers présents uniquement dans les faits ;
7. crée pour ces derniers une identité inactive `mapping_pending`, sans
   inventer de place de cotation.

Les lignes agrégées ML ne sont pas des instruments. `__GLOBAL__` et les noms
de secteurs restent donc volontairement avec `instrument_id=NULL`.

### Phase C — Backfill reprenable

Commande canonique :

```powershell
python -u -m service.market.bootstrap_us_instruments --mode backfill --symbol-chunk 50 --id-chunk 100000 --symbol-workers 8
python -u -m service.market.bootstrap_us_instruments --mode reconcile
```

L’état est persisté dans :

```text
artifacts/audits/market_integration/sprint_05/backfill_state.json
```

Chaque table est `PENDING` ou `COMPLETED`, avec son curseur et le nombre de
lignes mises à jour. Une interruption ne détruit rien : seules les lignes
encore nulles sont reprises. Les faits indexés par ticker sont traités par
petits groupes d’instruments, ce qui suit l’ordre physique des clés historiques
et évite de revisiter toutes les pages pour chaque mois. Les tables applicatives
et ML passent avant les deux historiques de barres volumineux.

### Phase D — Audit avant contrainte

```powershell
python -u -m service.market.bootstrap_us_instruments --mode audit
python -u -m scripts.audit_sprint5_us_parity --reuse-coverage-report
```

Le premier contrôle la couverture et les incohérences. Le second compare des
lectures par `symbol` et par `instrument_id`, calcule des hashes stables, audite
les jointures critiques et vérifie l’absence de faits CN.

Artefacts :

```text
artifacts/audits/market_integration/sprint_05/
├── backfill_state.json
├── coverage_report.json
├── parity_report.json
├── gate_result.json
├── post_ddl_reconciliation_state.json
├── effective_config.json
├── migrations_checked.json
├── tests_summary.json
├── data_quality.json
├── git_state.txt
└── decisions.md
```

### Phase E — Contraintes et compatibilité

La migration `0088_us_fact_instrument_constraints` n’est applicable que si le
backfill est complet. Elle ajoute :

- un index `instrument_id` avec la date métier lorsque disponible ;
- une FK vers `instruments` avec `ON DELETE RESTRICT` ;
- un trigger `BEFORE INSERT` et un trigger `BEFORE UPDATE` par table ;
- la résolution automatique d’un ancien producteur qui écrit seulement
  `symbol` ;
- le refus d’une paire `symbol/instrument_id` incohérente ;
- le refus d’un ticker réel US non résolu ;
- l’autorisation explicite des lignes agrégées et de la crypto legacy.

Le SQL autonome complet, y compris les triggers, est généré dans
`database/sql/migration_0088_us_fact_instrument_constraints.sql` par
`scripts/render_sprint5_constraint_sql.py`. Alembic demeure la voie canonique.

## 5. Contrat applicatif

### 5.1 Lecture

Les nouvelles lectures doivent recevoir `instrument_id`. Le pont temporaire
`InstrumentRepository.resolve_local_symbol(market_code, symbol)` permet aux
écrans et commandes historiques de résoudre d’abord l’identité, puis de lire
les faits par clé canonique.

`BarsRepository.load_bars` accepte donc :

```python
load_bars(instrument_id=123, start=..., end=...)
load_bars("AAPL", market_code="US_EQ", start=..., end=...)  # pont legacy
```

Dans le second cas, la requête finale porte quand même sur `instrument_id`.
Une ambiguïté entre deux places est bloquante : le code appelant doit fournir
le MIC ou l’identifiant.

### 5.2 Écriture

Pendant la transition :

```text
producteur moderne  → écrit instrument_id + symbol
producteur legacy   → écrit symbol → trigger résout instrument_id
incohérence         → transaction refusée
```

`symbol` est conservé comme dénormalisation lisible et pour comparer la
parité. Il ne doit plus servir de clé de jointure entre faits migrés.

Deux exceptions sont auditées et explicitement isolées : le bootstrap, qui
doit précisément convertir l’ancienne clé, et les tables brutes/versionnées de
Forward PIT qui ne sont pas encore des faits canoniques. Elles ne sont jamais
utilisées pour croiser deux marchés.

## 6. Cas particuliers

### Classes d’actions et suffixes

`BF.A`, `BRK-B` et les autres tickers ponctués sont acceptés comme identités
legacy. Les suffixes propres à EODHD, Alpaca ou Tushare appartiennent à
`instrument_provider_symbols`, jamais à la clé métier d’un fait.

### OTC et exchange inconnu

OTC est conservé sous MIC `OTCM`. Un exchange réellement inconnu produit une
identité `mapping_pending`; aucune place n’est inventée.

### Agrégats ML

Les lignes globales ou sectorielles ne sont pas rattachées artificiellement à
un titre. Leur `instrument_id` nullable est un choix de modèle, pas une lacune
de couverture.

### Crypto legacy

Le Sprint 5 couvre les actions US. Les lignes crypto historiques restent
compatibles mais ne sont pas transformées en instruments `US_EQ`.

## 7. Tests et non-régression

Les tests spécifiques couvrent :

- stabilité et portée des migrations ;
- classification ticker contre agrégat ;
- reprise par tranche ;
- résolution d’un symbole unique et refus d’une ambiguïté ;
- identité des DataFrames lus par ticker et par ID ;
- usage de la vraie colonne `date` dans les barres ;
- absence de jointure critique `symbol = symbol` ;
- requêtes diagnostics, sélection, liquidité, sentiment et rapports.

Le gate final exige aussi la suite complète du projet. Les tests unitaires ne
remplacent pas `parity_report.json`, qui constitue la preuve sur la base réelle.

## 8. Exploitation et retour arrière

Ne jamais supprimer immédiatement `symbol` ni ses anciennes clés. La période
de double écriture sert à détecter les producteurs oubliés.

Ordre de retour arrière sûr :

1. remettre les lectures legacy si nécessaire ;
2. retirer les triggers/FK/index via downgrade 0088 ;
3. conserver les colonnes et le backfill pour diagnostic ;
4. ne downgrader 0087 qu’après vérification qu’aucun code ne dépend plus de
   `instrument_id`.

Le backfill n’altère aucune valeur métier : il ajoute seulement une référence.
Les anciennes données restent donc récupérables pendant toute la transition.

## 9. Condition de passage au Sprint 6/7

Le `gate_result.json` du 21 septembre 2026 vaut `GO`. Le Sprint 6 peut donc
créer la base physique `alpha_trade_cn` et son staging Tushare. Le verrou
Sprint 5 sur le Sprint 7 est levé, sans autoriser pour autant une publication
CN prématurée : les contrôles de qualité, calendrier et PIT propres au staging
CN restent obligatoires avant toute promotion vers les tables canoniques.
