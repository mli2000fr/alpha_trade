# Architecture Chine — Bases, batchs et configurations `_cn`

> Complément obligatoire à la roadmap et au sprint planning d’intégration du marché chinois.  
> Date : 19 septembre 2026.  
> Décision : code et contrats communs, isolation physique des données par marché et fichiers de configuration CN explicitement suffixés `_cn`.

## 0. Convention documentaire normative

Ce document fixe la convention retenue pour toute l’intégration chinoise :

- `alpha_trade` reste la base physique US historique ;
- `alpha_trade_cn` devient la base physique Chine ;
- `config.yaml` et `batch.yaml` restent les entrées US/legacy ;
- `config_cn.yaml` et `batch_cn.yaml` deviennent les entrées Chine ;
- tout fichier de configuration propre au marché chinois porte le suffixe `_cn` avant son extension ;
- les registres réellement transversaux, par exemple le routeur de bases, restent uniques et sans suffixe marché ;
- le code, les contrats, les migrations paramétrables et les moteurs restent partagés.

Cette convention remplace toute proposition antérieure consistant à ajouter les sections Chine directement dans `batch.yaml` ou à utiliser des fichiers ambigus comme `cn_a.yaml` sans suffixe `_cn`.

## 1. Décision sur la base de données

### 1.1 Recommandation

Il est plus sûr de créer une base indépendante pour la Chine :

```text
MySQL
├── alpha_trade                  marché US existant, alias US_EQ
├── alpha_trade_cn               marchés CN_A puis CN_BJ
└── alpha_trade_control          optionnel à terme, coordination globale
```

Cette décision répond à un risque réel. Une colonne `market_code` protège une requête correctement écrite, mais ne protège pas suffisamment contre :

- un `TRUNCATE` ;
- un `DELETE` sans filtre ;
- un script de nettoyage historique US ;
- une restauration complète de la base US ;
- une migration reconstruisant une table ;
- une erreur manuelle dans un client SQL ;
- une politique de rétention différente ;
- un incident de volumétrie sur un marché.

La base `alpha_trade` actuelle peut rester physiquement la base US. Il n’est pas nécessaire de la renommer immédiatement, ce qui évite une migration dangereuse de toutes les configurations actuelles.

### 1.2 Ce qui n’est pas dupliqué

L’isolation des bases ne doit pas créer deux applications.

Restent partagés :

- le code Python ;
- les repositories ;
- les définitions SQL canoniques ;
- les migrations Alembic paramétrables ;
- le feature engine ;
- Oracle, global ranking et modèles directionnels ;
- le moteur de backtest ;
- l’IHM ;
- les contrats PIT ;
- la télémétrie des batchs.

Une évolution métier est implémentée une seule fois puis testée pour chaque marché.

### 1.3 `market_code` reste obligatoire

Une base indépendante ne remplace pas l’identité marché. Les éléments suivants doivent toujours porter `market_code` :

- batches et runs ;
- manifests ML ;
- univers ;
- artefacts disque ;
- exports ;
- backtests ;
- sauvegardes ;
- notifications ;
- futures opérations de portefeuille consolidé.

Cela protège contre une mauvaise connexion, un export déplacé ou un artefact chargé depuis le mauvais répertoire.

### 1.4 Routage des connexions

Introduire à terme un `DatabaseRouter` :

```text
MarketContext(US_EQ)
  → database_alias=us_primary
  → schema=alpha_trade

MarketContext(CN_A)
  → database_alias=cn_primary
  → schema=alpha_trade_cn
```

Règles :

- alias déclarés dans une allowlist ;
- aucune concaténation libre de nom de schéma ;
- un batch CN ne peut pas écrire via `us_primary` ;
- l’alias et le schéma effectifs sont persistés dans le run ;
- les pipelines ML/backtest n’exécutent pas de jointures cross-schema ;
- les vues consolidées sont en lecture seule et isolées dans un module dédié ;
- absence de route = erreur bloquante, jamais fallback US.

### 1.5 Identité instrument entre bases

Un BIGINT local peut avoir la même valeur dans deux bases. Prévoir :

```text
instrument_uid   UUID global public
instrument_id    BIGINT local performant
market_code      code obligatoire
```

Les tables volumineuses utilisent `instrument_id`. Les manifests, exports et échanges entre bases utilisent `instrument_uid` avec `market_code`.

### 1.6 Coordination globale

`alpha_trade_control` peut attendre. Il devient utile pour :

- registre des marchés et connexions ;
- inventaire global des batches ;
- comptes multi-marchés ;
- consolidation portefeuille/FX ;
- orchestration globale ;
- audit des sauvegardes.

Pour les premières études CN, l’IHM peut agréger en lecture les listes de `alpha_trade` et `alpha_trade_cn` via le routeur.

## 2. Sauvegarde, restauration et nettoyage

### 2.1 Batchs séparés

```text
db_us_backup       → alpha_trade
db_cn_backup       → alpha_trade_cn
db_control_backup  → alpha_trade_control, lorsqu’elle existera
```

Les fichiers doivent être stockés dans des répertoires distincts :

```text
backups/db/us/
backups/db/cn/
backups/db/control/
```

### 2.2 Nettoyage sécurisé

Toute commande destructive doit exiger :

```text
database_alias
market_code
scope/table allowlist
before_date ou run_id
dry_run préalable
confirmation_token
```

Garde-fous :

- aucune valeur `all` implicite ;
- refus si marché et alias divergent ;
- affichage du schéma résolu avant action ;
- compte des lignes avant suppression ;
- sauvegarde récente vérifiée ;
- journal d’audit ;
- tests de restauration distincts ;
- aucun script US historique autorisé sur `cn_primary`.

### 2.3 Artefacts ML

Séparer aussi les racines :

```text
artifacts/models/us_eq/
artifacts/models/cn_a/
artifacts/backtests/us_eq/
artifacts/backtests/cn_a/
backups/ml/us_eq/
backups/ml/cn_a/
```

Le chemin seul n’est pas une preuve : le manifest doit aussi porter le marché.

## 3. Batchs Chine nécessaires

### 3.1 Contrat commun

Chaque section de `batch_cn.yaml` doit contenir :

```yaml
market_code: CN_A
database_alias: cn_primary
provider: tushare
timezone: Asia/Shanghai
scheduler_timezone: Europe/Paris
calendar_id: CN_A_CANONICAL
enabled: false
```

Les batchs CN utilisent le launcher, les notifications, les compteurs et la page Workflow & Orchestration existants, mais ont des handlers et états distincts.

Ne pas simplement ajouter `market_code=CN` aux batchs US existants : leurs fournisseurs, endpoints, schémas de réponse et règles de disponibilité sont différents.

## 4. Batchs P0 — indispensables

### 4.1 `cn_security_master_sync`

Collecte :

- codes et places ;
- noms chinois/anglais ;
- type de titre ;
- board ;
- dates de listing/delisting ;
- statut ST/*ST et changements de nom ;
- statut actif/inactif ;
- symboles fournisseur.

Alimente : staging master, `instruments`, `instrument_provider_symbols`, `instrument_status_history`.

Fréquence : quotidienne après mise à jour fournisseur, plus backfill historique initial.

### 4.2 `cn_trade_calendar_sync`

Collecte les séances Shanghai/Shenzhen/Beijing, jours ouverts/fermés et exceptions.

Alimente `market_sessions`.

Fréquence : hebdomadaire et rafraîchissement annuel, avec contrôle quotidien de la séance attendue.

### 4.3 `cn_daily_bars_sync`

Collecte OHLCV brut et montant échangé, sans mélanger prix ajusté et prix exécutable.

Alimente staging bars puis barres canoniques de `alpha_trade_cn`.

Fréquence : après clôture et publication fournisseur ; fenêtre J−7/J idempotente si l’API le permet.

### 4.4 `cn_adjustment_factor_sync`

Collecte les facteurs d’ajustement et leur révision.

Alimente une table dédiée. Les prix ajustés destinés aux features sont reconstruits selon une convention documentée.

### 4.5 `cn_suspension_sync`

Collecte suspensions/reprises et disponibilité temporelle.

Interdit qu’une barre forward-fillée devienne tradable.

### 4.6 `cn_daily_price_limits_sync`

Collecte prix limite haut/bas et état de séance si fourni.

Nécessaire aux non-fills conservateurs du backtest.

### 4.7 `cn_corporate_actions_sync`

Collecte dividendes, splits, droits et autres actions affectant prix, quantité ou cash.

### 4.8 `cn_index_bars_sync`

Collecte les benchmarks utilisés par les features, le régime et les comparaisons.

### 4.9 `cn_sector_membership_sync`

Collecte et historise la taxonomie et l’appartenance sectorielle.

### 4.10 `cn_universe_publish`

Produit l’univers quotidien PIT depuis les tables canoniques : listing, delisting, historique, liquidité, suspension, limites, statut et board.

### 4.11 `cn_pit_data_quality_daily`

Contrôle uniquement :

- session attendue ;
- couverture ;
- fraîcheur ;
- instruments non mappés ;
- anomalies OHLCV ;
- limites/suspensions ;
- disponibilité PIT ;
- runs échoués.

Il ne collecte aucune donnée et doit être exécuté séparément du contrôle US.

## 5. Batchs P1 — recherche directionnelle

### 5.1 `cn_money_flow_sync`

Flux par tailles d’ordres, achats/ventes, flux nets et montant total. Les définitions exactes du fournisseur sont persistées avec leur version.

### 5.2 `cn_margin_lending_sync`

Financement sur marge, remboursements, soldes de prêt et changements. Ne pas confondre signal baissier et short réellement exécutable.

### 5.3 `cn_forecast_revision_sync`

Anciennes/nouvelles estimations, période fiscale, métrique, nombre d’analystes, dispersion, publication et disponibilité.

### 5.4 `cn_research_report_sync`

Rapports, recommandations et objectifs avec timestamp PIT et identité auteur/institution si disponible.

### 5.5 `cn_top_list_sync`

Dragon/Tiger list, motif, montants et participants publiés.

### 5.6 `cn_financials_pit_sync`

Fondamentaux bruts, période fiscale, unité, annonce et révisions. Aucune valeur n’est utilisable avant `available_at`.

### 5.7 `cn_institutional_holdings_sync`

Holdings et variations avec date de publication, en acceptant que la fréquence puisse être faible.

### 5.8 `cn_events_sync`

Guidance, forecasts officiels, annonces structurées et événements d’entreprise.

## 6. Cartographie des batchs actuels

### 6.1 Transversaux réutilisables

| Batch actuel | Décision |
|---|---|
| `ml_artifacts_backup` | moteur commun, destinations US/CN séparées |
| `db_core_backup` | dupliquer l’exécution par base, pas le code |
| `db_news_raw_backup` | conserver US ; créer CN seulement si une table news CN existe |
| `pit_data_quality_daily` | moteur réutilisable, run CN séparé |

### 6.2 Génériques de nom mais US dans le code actuel

| Batch | Décision CN |
|---|---|
| `market_cap_sync` | ne pas réutiliser directement ; utiliser données Tushare CN |
| `earnings_calendar_sync` | handler CN distinct |
| `analyst_snapshot_collection` | handler CN distinct |
| `latest_quotes_sync` | inutile au premier POC historique ; provider CN plus tard |
| `daily_bars_sync` | code orchestration réutilisable, handler Tushare distinct |
| `security_master_snapshot` | sources Nasdaq/Business Quant US ; batch CN séparé |
| `corporate_actions_sync` | canonicaliseur partageable, source CN distincte |
| `borrow_status_snapshot` | source et règles CN distinctes |

### 6.3 Exclusivement US

- `sec_edgar_incremental` ;
- `sec_corporate_events_normalize` ;
- `sec_institutional_ownership_normalize` ;
- `fred_alfred_vintage_sync` comme macro US ;
- `finra_short_volume_sync` ;
- `business_quant_analyst_snapshot` ;
- `oracle_options_indicative_snapshot` ;
- `options_delayed_bars_sync` ;
- `option_contract_adjustment_sync` OCC ;
- `oracle_opening_window_sync` Alpaca ;
- `auction_imbalance_sync` US ;
- `securities_lending_sync` dans sa forme actuelle ;
- `official_options_nbbo_sync` OPRA.

Ils peuvent éventuellement produire des facteurs externes pour une étude CN, mais ne deviennent pas des collecteurs Chine.

## 7. Planification et horaires

Le scheduler Windows reste en `Europe/Paris`. Le calcul de la séance métier utilise `Asia/Shanghai`.

Chaque batch doit distinguer :

```text
scheduler_timezone   heure de déclenchement opérateur
market_timezone      détermination de la séance
provider_timezone    interprétation des timestamps source
storage_timezone     UTC pour les timestamps canoniques
```

Les horaires exacts seront définis après mesure de la publication Tushare. Ne pas supposer que la donnée est complète immédiatement à la clôture.

Quand possible : fenêtre J−7/J avec upsert idempotent. Sinon : passage principal et rattrapage conditionnel vérifiant la réussite récente dans la base CN.

Les notifications doivent inclure : marché, base, passage principal/rattrapage, session, demandés, reçus, persistés, échecs, alertes et quota restant.

## 8. Fichiers de configuration

### 8.0 Règle de nommage

Le suffixe `_cn` est obligatoire pour un fichier dont le contenu est propre à la Chine. Il est placé immédiatement avant l’extension :

```text
config_cn.yaml
batch_cn.yaml
market_cn.yaml
costs_cn.yaml
execution_rules_cn.yaml
sectors_cn.yaml
oracle_cn.json
long_cn.json
short_cn.json
univers_research_cn.txt
univers_tradable_cn.txt
univers_research_cn.manifest.json
```

Ne sont pas dupliqués : les schémas de validation communs, le registre `config/databases.yaml`, la configuration de notifications sans règle marché et les paramètres techniques réellement partagés.

Une configuration CN ne doit jamais hériter silencieusement d’une valeur US. La configuration finale résolue est persistée dans chaque run.

### 8.1 Organisation cible

```text
config.yaml                         entrée US/legacy
config_cn.yaml                      entrée Chine
batch.yaml                          batchs US/legacy
batch_cn.yaml                       batchs Chine
config/
├── markets/
│   ├── market_us.yaml
│   ├── market_cn.yaml
│   └── market_cn_bj.yaml
├── univers/
│   ├── <univers_us_existant>.txt
│   ├── univers_research_cn.txt
│   ├── univers_tradable_cn.txt
│   └── univers_research_cn.manifest.json
├── features/
│   ├── legacy_us/
│   └── markets/
│       ├── us_eq/
│       │   ├── oracle/
│       │   ├── long/
│       │   └── short/
│       └── cn_a/
│           ├── oracle/
│           ├── long/
│           └── short/
├── costs/
│   ├── costs_us.yaml
│   └── costs_cn.yaml
├── execution_rules/
│   ├── execution_rules_us.yaml
│   └── execution_rules_cn.yaml
├── sectors/
│   ├── sectors_us.yaml
│   └── sectors_cn.yaml
└── databases.yaml
```

Les dossiers actuels ne doivent pas être déplacés brutalement. Ils deviennent le chemin legacy US pendant une période de compatibilité.

### 8.2 `databases.yaml`

Exemple conceptuel :

```yaml
databases:
  aliases:
    us_primary:
      schema: alpha_trade
      url_env: ALPHA_TRADE_US_DATABASE_URL
      allowed_markets: [US_EQ]
    cn_primary:
      schema: alpha_trade_cn
      url_env: ALPHA_TRADE_CN_DATABASE_URL
      allowed_markets: [CN_A, CN_BJ]
  market_routes:
    US_EQ: us_primary
    CN_A: cn_primary
    CN_BJ: cn_primary
```

Les secrets restent dans les variables d’environnement ou le vault.

### 8.3 `config_cn.yaml` et `config/markets/market_cn.yaml`

`config_cn.yaml` est le point d’entrée applicatif. Il référence les profils spécialisés sans répéter leurs contenus. `market_cn.yaml` décrit CN_A ; un futur `market_cn_bj.yaml` surcharge Beijing.

Doit couvrir :

```yaml
market_code: CN_A
country_code: CN
currency: CNY
timezone: Asia/Shanghai
calendar_id: CN_A_CANONICAL
database_alias: cn_primary
benchmark: <instrument canonique à valider>
sector_taxonomy: <taxonomie/version>
feature_profile_root: config/features/markets/cn_a
cost_profile: config/costs/costs_cn.yaml
execution_rules_profile: config/execution_rules/execution_rules_cn.yaml
live_enabled: false
short_execution_enabled: false
```

### 8.4 `batch_cn.yaml`

Ajouter les sections CN progressivement dans `batch_cn.yaml`, désactivées jusqu’à leur sprint. `batch.yaml` reste le fichier US/legacy. La page Batch devra charger les deux fichiers, afficher leur marché et ne jamais mélanger leurs compteurs ou états.

### 8.5 Univers

Chaque univers CN possède un manifeste :

```json
{
  "market_code": "CN_A",
  "database_alias": "cn_primary",
  "universe_id": "cn_a_liquid_research_v1",
  "symbols_file": "univers_research_cn.txt",
  "as_of_date": "2026-09-19",
  "currency": "CNY",
  "policy_version": "cn_a_universe_v1"
}
```

### 8.6 Features ML

Profils séparés :

```text
config/features/markets/cn_a/oracle/oracle_cn.json
config/features/markets/cn_a/long/long_cn.json
config/features/markets/cn_a/short/short_cn.json
```

Les profils US existants restent inchangés pendant la migration.

### 8.7 Coûts et règles

Les fichiers décrivent les politiques, tandis que les périodes historiques effectives peuvent être stockées en base. Aucun taux réglementaire ne doit être une constante éternelle.

### 8.8 Garde-fous de configuration

- aucun fallback CN vers US ;
- `market_code` compatible avec `database_alias` ;
- univers compatible avec le marché ;
- profil features compatible avec le batch ;
- devise, calendrier, coûts et règles cohérents ;
- config effective copiée dans chaque run ;
- fingerprint différent à chaque changement matériel ;
- live CN impossible tant que `live_enabled=false`.

## 9. Impacts sur le sprint planning

Les sprints de fondation doivent intégrer la séparation physique :

- Sprint 0 : ADR de routage et sauvegarde par base ;
- Sprint 1 : `MarketContext` contient `database_alias` ;
- Sprint 2 : identité globale compatible multi-base ;
- Sprint 3 : batches/runs stockent base et marché effectifs ;
- Sprint 5 : parité US dans `alpha_trade`, sans donnée CN ;
- Sprint 6 : création `alpha_trade_cn` et staging Tushare ;
- Sprint 7 : canonicalisation uniquement dans `cn_primary` ;
- Sprint 14 : IHM agrège les deux bases en lecture ;
- Sprint 17 : backups, contrôles et nettoyages séparés ;
- Sprint 18 : risque/exécution consolidés via couche de coordination, jamais par mélange implicite.

## 10. Verdict

La meilleure architecture pour ce projet est :

> **une base physique par marché pour l’isolation opérationnelle, un seul code et un seul contrat canonique pour éviter la divergence fonctionnelle.**

Cette approche permet de nettoyer, sauvegarder, restaurer ou reconstruire le marché chinois sans toucher aux données US. Elle coûte un routeur de connexions et une agrégation IHM, mais réduit fortement le risque d’erreur irréversible.

La création de `alpha_trade_cn` ne dispense pas des migrations `instrument_id`, `market_code`, calendrier et PIT. Elle constitue une deuxième barrière de sécurité, pas un substitut à l’architecture market-aware.

