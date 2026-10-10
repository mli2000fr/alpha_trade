# ADR FR-0001 — Marché France et isolation physique

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

- Date : 2 octobre 2026
- Statut : accepté pour les Sprints 0–1 ; ingestion, ML, backtest et live FR non activés
- Décision du propriétaire : une base séparée `alpha_trade_fr`, déjà créée

## Décision

Mise à jour au Sprint 6-C (3 octobre 2026) : le calendrier XPAR a été validé au Sprint 4. Le benchmark de recherche devient `FR_RESEARCH_EW_PRICE_V1` et la taxonomie déclarée `FR_SECTOR_UNKNOWN_V1`, selon le [contrat 6-C](sprint_6c_identite_benchmark_secteurs.md). Le benchmark est synthétique et limité au sous-ensemble de recherche ; les secteurs historiques restent inconnus. Les mentions `PENDING` et calendrier non implémenté ci-dessous décrivent l'état initial des Sprints 0–1. Coûts, promotion canonique et exécution restent bloqués.

Conserver un seul dépôt et les contrats transversaux (`MarketContext`, `DatabaseRouter`, `RunMarketScope`), avec trois bases distinctes :

```text
US_EQ          → us_primary → alpha_trade
CN_A / CN_BJ  → cn_primary → alpha_trade_cn
FR_EQ          → fr_primary → alpha_trade_fr
```

`FR_EQ` désigne ici la première portée de recherche des actions cotées à Paris : pays FR, devise de base EUR, timezone Europe/Paris, calendrier XPAR et MIC initial XPAR. Le MIC décrit **la ligne de cotation** et ne se déduit pas du seul ISIN ; les autres segments/venues français restent hors de la portée initiale tant que leur contrat n'est pas validé. Les documents fournisseurs `.PA` ne constituent pas un MIC. Le benchmark, la taxonomie sectorielle et les coûts portent des valeurs `PENDING` intentionnelles dans `market_fr.yaml` : ils ne sont ni une source de données, ni une autorisation d'entraînement.

`config_fr.yaml` ne permet aucune écriture canonique. `market_fr.yaml` est désactivé ; `live_enabled` et `short_execution_enabled` sont faux. La liste des capacités ne déclare pas `paper_execution` ou `live_execution`. Le `BrokerRouter` existant refuse tout marché non US, donc FR ne peut pas atteindre le client Alpaca. L'IHM n'affiche pas encore FR : c'est le Sprint 14. Le calendrier XPAR et les cutoffs FR ne sont pas encore implémentés : ils doivent échouer fermement jusqu'au Sprint 4.

## Barrières contre une mauvaise base

La route FR est figée à `alpha_trade_fr` dans `config/databases.yaml` et confirmée par le routeur. `DB_NAME_FR` n'est pas utilisé. Une configuration alternative pointant `fr_primary` sur `alpha_trade` est rejetée. L'override de base vers US/CN est rejeté ; un `url` explicite doit être `mysql+pymysql` sur `alpha_trade_fr` **et sur l'hôte configuré** ; la vérification de `SELECT DATABASE()` ne peut pas être désactivée pour FR. L'alias doit correspondre au marché avant l'ouverture de connexion.

Les secrets FR sont `LOGIN_DB_FR` et `PASSWORD_DB_FR`, sans fallback silencieux sur les variables US. `DB_HOST_FR` est optionnel (par défaut `localhost`). Le compte FR devrait être restreint à `alpha_trade_fr` ; cette séparation des permissions est un contrôle opérationnel complémentaire, pas une hypothèse déjà prouvée. La vérification initiale de la base a été faite en **lecture seule** avec les identifiants déjà disponibles ; elle ne remplace pas l'installation ultérieure des secrets FR dédiés.

## Données et déploiement

Les données métier et migrations FR vivront uniquement dans `alpha_trade_fr`. Les futures configurations, batchs, artefacts, modèles et sauvegardes FR devront porter explicitement `FR_EQ/fr_primary/EUR/XPAR`. Aucun schéma France n'est créé aux Sprints 0–1 ; le premier jeu de tables et `alembic_fr` relèvent du Sprint 2. Les mêmes frontières s'appliquent aux environnements de test.

## Rejeté et différé

- Rejeté : mélanger les tables FR dans `alpha_trade`, utiliser une branche Git permanente ou router FR vers Alpaca.
- Différé : Euronext Growth Paris, univers PIT, benchmark concret, source OHLCV canonique, calendrier validé, modèles, backtest économique, courtier et short live.
- Compatibilité : US demeure le marché par défaut pour les anciens appels sans `market_code`, avec le warning existant ; ce fallback ne doit jamais être utilisé pour une commande FR.

## Critère de révision

Réviser cet ADR avant d'activer FR ou d'ajouter un autre MIC/segment. Les changements de routage physique nécessitent des tests de refus inter-marchés et une procédure de migration/retour arrière distincte.
