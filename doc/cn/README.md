# Documentation — Intégration du marché chinois

Ordre de lecture recommandé :

1. [Audit du code et roadmap](./roadmap_integration_marche_chinois_audit_code.md)
2. [Sprint planning détaillé](./sprint_planning_integration_marche_chinois.md)
3. [Architecture des bases, batchs et configurations](./architecture_bases_batchs_configuration_cn.md)
4. [Sprint 0 — baseline US et ADR](./sprint_0_baseline_us_et_adr.md)
5. [Sprint 1 - MarketContext et registre](./sprint_1_market_context.md)
6. [Comparaison des données fournisseurs](./comparaison_data_fournisseur.md)
7. [Actualisation des fournisseurs](./actualisation_fournisseurs_chine.md)
8. [Étude d’opportunité historique](./Étude%20d’opportunité%20—%20Extension%20d’α-Trade%20au%20marché%20actions%20chinois.md)

Les trois premiers documents définissent la cible technique actuelle. L’étude d’opportunité historique fournit le contexte et a été harmonisée avec les décisions finales.

## Décisions normatives

- données US dans `alpha_trade` ;
- données Chine dans `alpha_trade_cn` ;
- code, contrats logiques, repositories, ML et backtest partagés ;
- `market_code` et `database_alias` obligatoires malgré l’isolation physique ;
- `config.yaml` et `batch.yaml` réservés au chemin US/legacy ;
- `config_cn.yaml` et `batch_cn.yaml` réservés au chemin Chine ;
- suffixe `_cn` pour tout autre fichier de configuration, profil de features, univers ou manifeste propre à la Chine ;
- `config/databases.yaml` reste transversal, car il porte précisément le routage entre les deux bases.

En cas d’ambiguïté, [architecture_bases_batchs_configuration_cn.md](./architecture_bases_batchs_configuration_cn.md) prévaut pour la base, les batchs et les configurations ; la roadmap prévaut pour les impacts code ; le sprint planning prévaut pour l’ordre de réalisation.

