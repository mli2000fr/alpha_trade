# Sprint 2 — Référentiel instruments et mappings fournisseurs

> Date de clôture : 19 septembre 2026  
> Branche : develop_cn  
> État : **GO**  
> Migration appliquée sur la base US : 0084_market_instrument_foundation  
> Données métier migrées : aucune ; le backfill US reste volontairement à blanc.

## 1. Résultat exécutif

Le Sprint 2 crée l’identité canonique qui remplacera progressivement symbol. Six tables neuves ont été ajoutées sans modifier fonctionnellement les tables historiques :

1. markets ;
2. instruments ;
3. instrument_provider_symbols ;
4. instrument_status_history ;
5. market_sessions ;
6. market_execution_rules.

La base US est passée de la révision Alembic 0083 à 0084. Les six tables, cinq clés étrangères et deux triggers temporels ont été vérifiés physiquement. Les contextes CN_A et CN_BJ existent dans markets mais restent disabled et live_disabled.

Aucune ligne stock_metadata n’a été copiée dans instruments. Le mapping US a été simulé en lecture seule afin de mesurer la qualité de l’identité avant tout dual-write.

## 2. Modèle de données

### 2.1 markets

Cette table matérialise les contrats du MarketRegistry en base :

- market_code ;
- database_alias ;
- country_code et currency ;
- timezone et calendar_id ;
- benchmark_symbol ;
- sector_taxonomy ;
- enabled et live_enabled ;
- context_fingerprint.

Les trois marchés sont initialisés de façon idempotente par la migration. US_EQ est actif. CN_A et CN_BJ sont désactivés.

### 2.2 instruments

instruments porte l’identité économique canonique :

- instrument_id : clé technique locale BIGINT ;
- instrument_uid : UUID stable exportable entre bases ;
- market_code : rattachement obligatoire au marché ;
- exchange_mic et local_symbol : identité de cotation ;
- display_name et instrument_type ;
- currency ;
- listing_date et delisting_date ;
- mapping_status : mapped, mapping_pending ou retired ;
- is_active.

Contraintes structurantes :

- instrument_uid unique ;
- couple exchange_mic/local_symbol unique ;
- devise ISO sur trois caractères ;
- delisting_date postérieure ou égale à listing_date ;
- exchange_mic obligatoire lorsqu’un instrument est déclaré mapped ;
- marché existant obligatoire par clé étrangère.

instrument_uid est généré par UUID v5 à partir d’une identité d’onboarding contrôlée. Un changement ultérieur de ticker ne doit jamais recalculer cet UID.

### 2.3 instrument_provider_symbols

Cette table dissocie l’instrument des conventions des fournisseurs :

- provider ;
- provider_symbol ;
- provider_exchange ;
- valid_from et valid_to ;
- is_primary ;
- instrument_id.

Deux protections sont appliquées dans le repository et, sur MySQL/MariaDB, par deux triggers :

1. le même provider_symbol d’un fournisseur ne peut pas désigner deux instruments sur des périodes qui se chevauchent ;
2. un instrument ne peut pas avoir deux mappings primaires simultanés chez le même fournisseur.

Les périodes sont inclusives. Un changement de ticker se représente donc par une ancienne période clôturée puis une nouvelle période commençant le jour suivant.

### 2.4 instrument_status_history

Cette table représente l’état temporel d’un titre :

- période de validité ;
- listing_status ;
- trading_status ;
- is_tradable ;
- is_special_treatment ;
- board_code ;
- source ;
- observed_at et available_at.

Elle prépare les suspensions, delistings, statuts ST chinois et restrictions par board sans écraser l’histoire.

### 2.5 market_sessions

Cette table porte les séances datées d’un marché :

- session_date et session_status ;
- ouverture et clôture UTC ;
- date de règlement ;
- source et timestamps PIT.

Elle reste vide au Sprint 2. Le calendrier CN sera alimenté dans le sprint dédié au temps de marché.

### 2.6 market_execution_rules

Cette table versionne les règles par marché, MIC, board et période :

- devise ;
- cycle de règlement ;
- lots achat/vente ;
- tick size ;
- limite quotidienne de variation ;
- vente à découvert ;
- revente le jour même ;
- métadonnées JSON.

Elle reste vide au Sprint 2. Les règles ne sont donc pas encore consommées par le backtest ni le live.

## 3. Relations

Flux d’identité cible :

    markets
       |
       +-- instruments
             |
             +-- instrument_provider_symbols
             |
             +-- instrument_status_history

    markets
       |
       +-- market_sessions
       |
       +-- market_execution_rules

Le symbole affiché n’est plus destiné à être une clé universelle. Les jointures futures utiliseront instrument_id à l’intérieur d’une base et instrument_uid plus market_code lors d’un échange entre bases.

## 4. Repository

InstrumentRepository fournit les opérations prévues par le planning :

- resolve_instrument(market_code, mic, local_symbol) ;
- resolve_provider_symbol(provider, provider_symbol, as_of) ;
- list_instruments(market_code, as_of, filters) ;
- load_status_asof(instrument_id, as_of).

Il fournit également les écritures contrôlées nécessaires aux tests et au futur onboarding :

- create_instrument ;
- add_provider_symbol.

Garanties :

- marché et MIC cohérents ;
- devise cohérente avec le MarketContext ;
- CN impossible en écriture tant que son contexte reste disabled ;
- paramètres SQL liés, filtres sur liste blanche ;
- résolution ambiguë transformée en erreur ;
- dates ISO contrôlées ;
- transaction sur chaque écriture ;
- verrouillage FOR UPDATE sur MySQL pour les contrôles de chevauchement.

Les MIC actuellement autorisés sont volontairement limités aux places démontrées :

| Marché | MIC |
|---|---|
| US_EQ | XNAS, XNYS, XASE, ARCX, BATS |
| CN_A | XSHG, XSHE |
| CN_BJ | BJSE |

BJSE est le MIC ISO 10383 de Beijing Stock Exchange. Les OTC américains ne reçoivent pas de MIC inventé dans le dry-run.

## 5. Backfill US à blanc

Commande reproductible :

    python -m scripts.audit_us_instrument_mapping

Sortie :

    artifacts/audits/market_integration/sprint_02/us_mapping_dry_run.json

Résultat sur stock_metadata :

| Mesure | Valeur |
|---|---:|
| Lignes analysées | 33 633 |
| Mappables avec MIC démontrable | 15 949 |
| mapping_pending | 17 684 |
| Taux global strict | 47,42 % |
| OTC placés en attente | 17 611 |
| CRYPTO/places inconnues placées en attente | 73 |
| Symboles ponctués/classes signalés | 955 |
| ADR/ADS potentiels signalés | 2 627 |

Répartition des 15 949 titres mappables :

| MIC | Nombre |
|---|---:|
| XNAS | 6 951 |
| XNYS | 3 781 |
| ARCX | 3 150 |
| BATS | 1 678 |
| XASE | 389 |

Lecture importante : le taux global de 47,42 % n’indique pas un défaut de mapping sur les places principales. Les 17 684 lignes non mappées sont exactement les 17 611 OTC et les 73 CRYPTO. La couverture des lignes restantes dont la place est démontrable est donc de 100 %.

Les symboles avec point, tiret ou slash et les ADR sont signalés pour revue, mais ne sont pas automatiquement rejetés si leur place est connue. Aucun instrument_uid n’a été créé et aucune donnée métier n’a été écrite.

## 6. Politique des ambiguïtés avant Sprint 5

Les cas suivants restent en mapping_pending :

- exchange absent ;
- exchange inconnu ;
- OTC sans référentiel MIC détaillé validé ;
- lignes CRYPTO présentes dans stock_metadata ;
- toute future collision non résolue entre classe, ticker local et symbole fournisseur.

Avant le dual-write, il faudra :

1. limiter le backfill aux equities réellement retenues ;
2. rapprocher les identifiants Alpaca, EODHD et autres fournisseurs ;
3. distinguer actions ordinaires, ADR, ETF, fonds, warrants et preferred shares ;
4. définir la politique OTC ou les exclure explicitement ;
5. confirmer chaque classe de titre ponctuée ;
6. produire un fichier d’exceptions revu et versionné.

## 7. Migration et SQL de référence

Migration :

- alembic/versions/0084_market_instrument_foundation.py.

SQL canoniques :

- database/sql/market/markets.sql ;
- database/sql/market/instruments.sql ;
- database/sql/market/instrument_provider_symbols.sql ;
- database/sql/market/instrument_status_history.sql ;
- database/sql/market/market_sessions.sql ;
- database/sql/market/market_execution_rules.sql.

Les CREATE TABLE utilisent IF NOT EXISTS. L’initialisation des marchés utilise INSERT IGNORE. Les triggers sont recréés après DROP TRIGGER IF EXISTS. Le contrat est donc réexécutable après une installation partielle.

Le downgrade supprime uniquement les objets créés par 0084, dans l’ordre inverse des dépendances.

## 8. Administration IHM

Les six tables apparaissent dans le groupe Marché / Référentiel titres.

Elles sont protégées contre la purge depuis l’IHM, au même titre que stock_metadata et les tables de marché fondamentales. Cette protection évite une suppression partielle du référentiel laissant des données métier orphelines.

Aucun nouveau sélecteur de marché n’est ajouté à l’IHM pendant ce sprint.

## 9. Validation

Tests dédiés Sprint 2 : **14 réussis**.

Ils couvrent :

- même symbole local sur deux MIC ;
- changement de ticker et résolution as-of ;
- mappings Alpaca, EODHD et Tushare distincts ;
- rejet d’une période fournisseur chevauchante ;
- rejet de deux mappings primaires actifs ;
- alias fournisseur secondaire ;
- statut as-of ;
- liste filtrée et protégée contre les filtres arbitraires ;
- cohérence marché/MIC/devise ;
- contexte CN désactivé ;
- stabilité de instrument_uid ;
- dry-run sans MIC inventé ;
- statistiques du dry-run ;
- présence des six SQL et idempotence contractuelle de la migration.

Campagne ciblée : **84 réussis, 1 ignoré, 0 échec**.

Suite complète :

- **5 805 tests collectés** ;
- **5 771 réussis** ;
- **34 ignorés** ;
- **0 échec** ;
- couverture : **71,04 %**, seuil de 70 % respecté.

Dette préexistante : les ResourceWarning SQLite déjà documentés restent non bloquants.

## 10. État physique vérifié

Après migration :

- alembic_version = 0084_market_instrument_foundation ;
- six tables présentes ;
- trois marchés initialisés ;
- CN_A et CN_BJ désactivés ;
- cinq clés étrangères présentes ;
- deux triggers instrument_provider_symbols présents ;
- zéro table historique modifiée par la migration ;
- zéro instrument historique backfillé.

## 11. Hors périmètre volontaire

Le Sprint 2 ne réalise pas encore :

- le backfill réel de stock_metadata ;
- l’ajout de instrument_id aux tables existantes ;
- le dual-write ;
- le routage alpha_trade / alpha_trade_cn ;
- les calendriers chinois ;
- les règles d’exécution chinoises ;
- l’adaptation ML, Oracle, ranking, risque ou backtest ;
- l’activation IHM ou live CN.

Ces travaux suivent l’ordre du planning. Le Sprint 3 doit d’abord porter le marché dans les parents de runs et batches.

## 12. Décision de gate

**GO Sprint 3.**

Le schéma est installé, aucune table métier historique n’a changé de comportement, le mapping US est mesuré et les ambiguïtés sont documentées avant le futur dual-write.