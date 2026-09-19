# Sprint 1 — MarketContext et registre de marchés

> Date de clôture : 19 septembre 2026  
> Branche : develop_cn  
> État : **GO**  
> Périmètre : fondation multi-marchés, sans activation fonctionnelle CN.

## 1. Résultat exécutif

Le Sprint 1 introduit un contrat de marché explicite, immuable et vérifiable. Le comportement historique reste US_EQ lorsque l’appelant ne transmet pas encore de marché. Ce fallback émet volontairement un FutureWarning et un log afin de rendre visible la dette de migration sans casser les commandes existantes.

Trois contextes sont déclarés :

| Code | Base logique | Devise | Timezone | Calendrier | Benchmark | État |
|---|---|---|---|---|---|---|
| US_EQ | us_primary | USD | America/New_York | NYSE | SPY | actif, paper/live autorisés |
| CN_A | cn_primary | CNY | Asia/Shanghai | CN_A | 000300.SH | désactivé |
| CN_BJ | cn_primary | CNY | Asia/Shanghai | CN_BJ | 899050.BJ | désactivé |

Aucune donnée chinoise n’est chargée, aucune table n’est migrée, aucun routeur de base n’est activé et aucune page IHM ne change. Ces éléments relèvent des sprints suivants.

## 2. Contrat livré

Le module common/market_context.py expose quatre types publics :

- MarketCode : codes canoniques US_EQ, CN_A et CN_BJ ;
- MarketContext : description figée d’un marché et de ses capacités ;
- MarketRegistry : registre immuable chargé depuis les fichiers YAML ;
- MarketCompatibilityError : erreur bloquante en cas de marché inconnu ou incohérent.

Un MarketContext contient :

- identité : market_code, database_alias, country_code ;
- conventions : currency, timezone, calendar_id ;
- référentiels : benchmark_instrument, sector_taxonomy ;
- politiques : cost_profile, execution_rules_profile ;
- chemin de features : feature_profile_root ;
- activation : enabled, live_enabled, short_execution_enabled ;
- capacités explicites : research, training, prediction, backtest, paper, live et short selon le marché.

Le contexte et le registre sont des dataclasses gelées. Les capacités deviennent un frozenset et la table interne du registre est protégée par MappingProxyType. Il n’existe donc aucun « marché courant » global mutable susceptible de fuir entre deux threads ou deux runs.

## 3. Chargement et résolution

common/config_loader.py fournit désormais :

- resolve_markets_config_dir : répertoire par défaut config/markets, surchargeable par ALPHA_TRADE_MARKETS_CONFIG_DIR ;
- load_market_registry : charge tous les fichiers market_*.yaml ;
- resolve_market_context : résout un contexte et conserve temporairement la compatibilité legacy.

Règles de résolution :

1. code explicite connu : retourne le contexte correspondant ;
2. code explicite inconnu : erreur bloquante ;
3. code absent : US_EQ, FutureWarning et log warning ;
4. require_enabled=true sur CN : erreur bloquante ;
5. répertoire vide, absent ou sans US_EQ : erreur bloquante.

L’override du répertoire sert aux tests, aux environnements empaquetés et aux futures configurations séparées. Il ne modifie pas config.yaml ni batch.yaml.

## 4. Validation de configuration

Chaque fichier marché porte schema_version: 1. Le chargeur refuse une autre version.

Les contrôles bloquants couvrent :

- market_code connu ;
- textes obligatoires non vides ;
- booléens YAML réels, afin que la chaîne "false" ne soit jamais interprétée comme vraie ;
- liste de capacités sans valeur vide ni doublon ;
- alias de base autorisé par marché ;
- pays, devise, timezone et calendrier cohérents avec le code ;
- timezone IANA réellement chargeable ;
- live interdit sur un marché désactivé ;
- short_execution_enabled interdit sans capacité short_execution ;
- présence obligatoire du contexte US_EQ dans tout registre.

La matrice d’alias du Sprint 1 est volontairement restrictive :

| Marché | Alias autorisé |
|---|---|
| US_EQ | us_primary |
| CN_A | cn_primary |
| CN_BJ | cn_primary |

Elle prépare l’isolation alpha_trade / alpha_trade_cn sans router encore les connexions.

## 5. Fingerprint et manifests

Chaque contexte produit un manifeste JSON sérialisable. Les capacités sont triées avant sérialisation, les clés le sont également, puis un SHA-256 est calculé.

Le fingerprint change si une convention structurante change : calendrier, devise, benchmark, règles d’exécution, coûts, capacité ou activation. Il pourra être persisté dans les manifests ML, backtests et batchs à partir des sprints où ces objets porteront le marché.

Le fingerprint ne se calcule pas sur lui-même ; il est ajouté après calcul au manifeste exposé. Deux chargements du même YAML produisent donc exactement la même empreinte.

## 6. Compatibilité US garantie

Le Sprint 1 ne branche MarketContext dans aucun moteur métier. Cela garantit que :

- les commandes historiques sans option marché gardent leurs paramètres et résultats ;
- les calendriers existants continuent d’utiliser les constantes US historiques ;
- le backtest et le live ne changent pas de route de base ;
- SPY reste le benchmark historique ;
- GICS reste la taxonomie sectorielle US ;
- l’IHM ne présente pas encore de sélecteur CN ;
- aucun modèle, rang ou label ne peut consommer CN puisque les contextes CN sont désactivés et non raccordés.

La compatibilité legacy n’est pas silencieuse : le warning signale les appelants à migrer, sans imposer cette migration dans le même sprint.

## 7. Tests et gate

Tests propres au contrat marché : **20 réussis**.

Ils couvrent :

- chargement des trois contextes ;
- fallback US avec warning ;
- CN visible mais désactivé ;
- immutabilité du contexte et du registre ;
- sérialisation et fingerprint ;
- version de schéma ;
- rejet des booléens textuels ;
- rejet des incohérences alias/pays/devise/timezone/calendrier ;
- cohérence live/short ;
- rejet des doublons et marchés inconnus ;
- contrôle d’alias de base ;
- résolution parallèle sans état global ;
- override du répertoire ;
- constantes historiques US.

Campagne ciblée US : **92 réussis, 4 ignorés, 0 échec**.

Suite complète :

- **5 791 tests collectés** ;
- **5 757 réussis** ;
- **34 ignorés** ;
- **0 échec** ;
- couverture globale : **71,00 %**, seuil obligatoire 70 % respecté.

Les ResourceWarning SQLite déjà signalés au Sprint 0 restent une dette non bloquante et ne sont pas introduits par MarketContext.

## 8. Ce qui est volontairement hors Sprint 1

Ne sont pas encore réalisés :

- tables markets/instruments et mappings fournisseurs ;
- migrations market_code/instrument_id ;
- routeur de connexions alpha_trade / alpha_trade_cn ;
- calendrier de séances CN ;
- ingestion Tushare/RQData ;
- propagation du marché dans les batchs et artefacts ;
- adaptation Oracle, ranking, features et backtest ;
- sélecteur IHM ;
- paper/live Chine.

Ces travaux commencent au Sprint 2. Une utilisation directe des contextes CN dans le runtime avant ces fondations serait prématurée.

## 9. Fichiers livrés

- common/market_context.py
- common/config_loader.py
- config/markets/market_us.yaml
- config/markets/market_cn.yaml
- config/markets/market_cn_bj.yaml
- config/markets/README.md
- tests/test_market_context.py
- artifacts/audits/market_integration/sprint_01/gate_summary.json

## 10. Décision de gate

**GO Sprint 2.**

Les critères sont satisfaits : US reste inchangé, CN est déclaratif et désactivé, le contrat est immuable et versionné, les incompatibilités sont bloquantes, les tests ciblés et globaux sont verts.