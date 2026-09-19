# Sprint 0 — Baseline US, ADR et remédiation

> Date : 19 septembre 2026  
> Commit de départ : 324c626a8a8e4578c9547473f0a5fd5994c13603  
> Branche : develop_cn  
> État final : **GO**  
> Sprint 1 est débloqué.

## 1. Résultat exécutif

Le Sprint 0 et sa remédiation sont terminés. Les décisions d’architecture sont documentées, la baseline US est reproductible, la suite globale est verte et le ledger Alembic correspond désormais au schéma physique.

Résultats finaux :

- suite ciblée marché/parité : **151 réussis sur 151** ;
- suite complète : **5 771 tests collectés**, **5 737 réussis**, **0 échec**, **34 ignorés** ;
- couverture : **70,96 %**, seuil conservé à **70 %** ;
- base US : **95 tables** lors de l’inventaire initial ;
- tables avec symbol : **58** ;
- tables avec market_code : **0** ;
- tables avec instrument_id : **0** ;
- tables dont une clé symbol-only doit être auditée : **39** ;
- version Alembic base après réconciliation : **0083_finra_fractional_short_volume** ;
- tête du dépôt : **0083_finra_fractional_short_volume**.

La remédiation n’a modifié aucune donnée métier. Elle a élargi à VARCHAR(255) les 17 colonnes provider prévues par la migration 0081, puis a aligné le pointeur Alembic après vérification physique complète.

## 2. ADR produits

- [ADR-0001 — MarketContext explicite](../architecture/adr_0001_market_context.md)
- [ADR-0002 — Identité canonique des instruments](../architecture/adr_0002_instrument_identity.md)
- [ADR-0003 — Isolation physique US/CN](../architecture/adr_0003_market_data_partitioning.md)
- [ADR-0004 — Règles d’exécution chinoises](../architecture/adr_0004_cn_execution_rules.md)

Décisions principales : alpha_trade pour US_EQ, alpha_trade_cn pour CN_A/CN_BJ, code et migrations logiques partagés, MarketContext et database_alias obligatoires, instrument_id interne et instrument_uid exportable, config_cn.yaml et batch_cn.yaml réservés à la Chine.

## 3. Baseline de tests

### 3.1 Suite ciblée

Les 151 tests concernant la parité backtest/live, le calendrier, PIT, Oracle, les univers et le schéma des prédictions passent sans échec ni skip.

### 3.2 Suite complète après remédiation

| Famille | Cause | Remédiation |
|---|---|---|
| Repository risque | 19 doubles de test utilisaient l’ancienne signature | stubs alignés sur batch_id et sources |
| API Alpaca | trois modules importaient des helpers privés | façade publique ajoutée et consommateurs migrés |
| Scanner de secrets | chemin artifact interprété comme base64 | clés de chemins explicitement autorisées, détection des credentials inchangée |
| Administration DB | tables Forward PIT/SEC/Oracle non classées | registre fonctionnel complété ; aucune table SQL non classée |
| IHM | aides absentes et attentes anciennes | tooltips ajoutés ; défaut WF=15 et commande univers testés |
| Backfill parallèle | test dépendant de l’ordre de terminaison | vérification par ensemble de dates, sans désactiver le parallélisme |
| Couverture | scripts d’expériences ponctuelles comptés comme runtime | périmètre explicite dans .coveragerc ; seuil 70 % inchangé |
| Migration 0082 | création non idempotente | contrôle table/index avant création + test de non-régression |

La couverture exclut uniquement les campagnes de recherche ponctuelles identifiées par leur emplacement ou leur suffixe : DIP research, directional data research, P-MATH, POC, audits, ablations, backfills et expériences E17 à E23. Ces scripts produisent leurs propres rapports et ne font pas partie du runtime livré.

Dette non bloquante observée : plusieurs ResourceWarning signalent des connexions SQLite de tests non fermées. Ils n’altèrent pas le résultat fonctionnel mais doivent être traités dans un chantier de propreté séparé.

## 4. Inventaire de données

Le fichier schema_inventory.json contient pour chaque table : colonnes, clé primaire, contraintes uniques, présence de symbol, market_code et instrument_id, volumétrie estimée et risque de clé symbol-only.

Les familles P0 à migrer en premier restent :

1. stock_metadata, stock_bars et stock_bars_daily ;
2. tradable_universe_runs/history ;
3. model_training_batch/run et model_predictions ;
4. global_oracle_labels, oracle_extreme_predictions et global_rank_history ;
5. positions, cibles, décisions risque et réconciliation ;
6. corporate actions, fondamentaux, analystes, sentiment et Forward PIT.

## 5. Réconciliation Alembic

L’audit physique des révisions 0069 à 0083 a montré :

- 14 contrats sur 15 déjà présents malgré un pointeur resté à 0068 ;
- migration 0081 seule partiellement absente : 17 colonnes provider restées en VARCHAR(16/32) ;
- migrations 0082 et 0083 déjà matérialisées en base.

Actions réalisées :

1. contrôle des valeurs NULL avant modification ;
2. élargissement non destructif des 17 colonnes provider à VARCHAR(255) ;
3. nouvel audit physique : **15 contrats sur 15 présents** ;
4. alignement du pointeur Alembic sur 0083 ;
5. migration 0082 rendue idempotente pour les bases déjà partiellement provisionnées.

Un upgrade aveugle depuis 0068 n’a pas été exécuté.

## 6. Gate de sortie

| Contrôle | Résultat |
|---|---:|
| ADR requis | PASS |
| inventaire SQL | PASS |
| suite ciblée | PASS — 151/151 |
| suite complète | PASS — 5 737 réussis, 0 échec |
| couverture ≥ 70 % | PASS — 70,96 % |
| migrations physiques 0069–0083 | PASS — 15/15 |
| version DB = head dépôt | PASS — 0083 |
| régression US introduite | aucune détectée |

**Décision : GO Sprint 1 — MarketContext.**

## 7. Preuves

Dossier : artifacts/audits/market_integration/sprint_00/

- effective_config.json ;
- git_state.txt ;
- schema_inventory.json ;
- table_contract_inventory.csv ;
- migrations_checked.json ;
- alembic_reconciliation.md ;
- pytest_targeted.xml ;
- pytest_full.xml ;
- tests_targeted_summary.json ;
- tests_summary.json ;
- parity_report.json ;
- data_quality.json ;
- decisions.md ;
- gate_result.json.