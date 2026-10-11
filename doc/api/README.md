# Inventaires API par package

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

Ces inventaires complètent les guides explicatifs. Ils sont régénérés depuis
l'AST du code le 10 octobre 2026, sans importer ni exécuter les modules métier.
Ils listent fonctions de module, classes et méthodes avec signatures, lignes
et empreintes SHA-256. Les fonctions imbriquées sont exclues ; ces listes ne
prouvent ni stabilité publique, ni couverture de tests, ni disponibilité runtime.

[Décompte exact par package](../reference/modules_generes.md) ·
[Configuration](../reference/configuration_generee.md) ·
[Migrations/DDL](../reference/schema_et_migrations_generes.md).

- [Core](core.md) et [Common](common.md)
- [Database](database.md), [Alembic US](alembic.md), [Alembic CN](alembic_cn.md), [Alembic FR](alembic_fr.md)
- [Data Integrity](dataIntegrityEngine.md)
- [Model Factory](modelFactory.md)
- [Risk Management](risk_management.md)
- [Execution Engine](execution_engine.md)
- [Backtesting](backtesting.md)
- [Event Sentiment](event_sentiment.md)
- [Analyst Research](analyst_research.md) : contrats de collecte/recherche, pas une autorisation d'activer une source bloquée.
- [Selector](selector.md)
- [Screener](screener.md)
- [Services](service.md)
- [IHM](ihm.md)
- [Corporate Actions](corporate_actions.md)
- [Flows](flows.md), [Lineage](lineage.md), [Reporting](reporting.md)
- [Formal](formal.md), [Tax](tax.md)
- [Scripts](scripts.md), [Points d'entrée racine](entrypoints.md)
- [Stabilité v1 et dépréciation](stabilite_v1_et_deprecation.md)

Un symbole privé `_...` est documenté uniquement pour faciliter la maintenance ; il ne constitue pas une API publique stable.

Regénération et garde-fous : [maintenance documentaire](../MAINTENANCE_DOCUMENTAIRE.md).
