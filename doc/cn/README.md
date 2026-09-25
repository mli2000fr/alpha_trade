# Documentation — Intégration du marché chinois

Ordre de lecture recommandé :

1. [Audit du code et roadmap](./roadmap_integration_marche_chinois_audit_code.md)
2. [Sprint planning détaillé](./sprint_planning_integration_marche_chinois.md)
3. [Architecture des bases, batchs et configurations](./architecture_bases_batchs_configuration_cn.md)
4. [Sprint 0 — baseline US et ADR](./sprint_0_baseline_us_et_adr.md)
5. [Sprint 1 - MarketContext et registre](./sprint_1_market_context.md)
6. [Sprint 2 — Référentiel instruments](./sprint_2_referentiel_instruments.md)
7. [Sprint 6 — sources gratuites BaoStock](./sprint_6_sources_gratuites_baostock.md)
8. [Comparaison des données fournisseurs](./comparaison_data_fournisseur.md)
9. [Actualisation des fournisseurs](./actualisation_fournisseurs_chine.md)
10. [Étude d’opportunité historique](./Étude%20d’opportunité%20—%20Extension%20d’α-Trade%20au%20marché%20actions%20chinois.md)

Les trois premiers documents définissent la cible technique actuelle. L’étude d’opportunité historique fournit le contexte ; ses choix initiaux de fournisseurs sont remplacés par la décision gratuite actuelle.

## Décisions normatives

- données US dans `alpha_trade` ;
- données Chine dans `alpha_trade_cn` ;
- code, contrats logiques, repositories, ML et backtest partagés ;
- `market_code` et `database_alias` obligatoires malgré l’isolation physique ;
- `config.yaml` et `batch.yaml` réservés au chemin US/legacy ;
- `config_cn.yaml` et `batch_cn.yaml` réservés au chemin Chine ;
- suffixe `_cn` pour tout autre fichier de configuration, profil de features, univers ou manifeste propre à la Chine ;
- BaoStock est le fournisseur primaire gratuit du Sprint 6 ; AKShare est complémentaire et non bloquant ; RQData/Tushare restent optionnels ;
- `config/databases.yaml` reste transversal, car il porte précisément le routage entre les deux bases.

En cas d’ambiguïté, [architecture_bases_batchs_configuration_cn.md](./architecture_bases_batchs_configuration_cn.md) prévaut pour la base, les batchs et les configurations ; la roadmap prévaut pour les impacts code ; le sprint planning prévaut pour l’ordre de réalisation.
- [Sprint 3 — contexte marché sur les runs, batches et univers](./sprint_3_contexte_marche_runs.md) — contrat parent, serving par marché, backfill US et garde cross-market.

- [Sprint 4 — calendrier et PIT multi-marchés](./sprint_4_calendrier_pit_multi_marches.md) — séances US/CN, segments, cutoffs dataset et compatibilité NYSE.

- [Sprint 5 — migration canonique US vers `instrument_id`](./sprint_5_migration_canonique_us.md) — backfill reprenable, double écriture, parité US et gate avant données CN canoniques.

- [Sprint 6 — sources gratuites BaoStock](./sprint_6_sources_gratuites_baostock.md) — base `alpha_trade_cn`, staging multi-fournisseurs, smoke réel et chemin Oracle amplitude.
- [Archive Sprint 6 Tushare](./sprint_6_connecteur_tushare_staging.md) — connecteur conservé mais non requis.
- [Sprint 7-B — canonicalisation historique](./sprint_7b_canonicalisation_complete.md) — 5 405 actions, backfill 2018–2025 et contrat des limites dérivées.
- [Audit et remédiation Sprint 7-B](./sprint_7b_audit_final_2026_09_24.md) — couverture, exceptions de radiation, suspensions contradictoires et correctif des limites ST.
- [Contrat d'univers tradable PIT](./contrat_univers_tradable_pit.md) — convention de radiation inclusive, exclusions des statuts contradictoires et limites inconnues, sans fuite temporelle.
- [Sprint 8 — Univers quotidien Point-in-Time](./sprint_8_univers_pit.md) — politique V1, snapshots avant séance, audit après clôture, migration CN et gate de validation.
- [Validation finale du Sprint 8](./sprint_8_validation_finale_2026_09_25.md) — 1 942 séances, contrôle complet PIT et traitement des exceptions.
- [Sprint 9 — Features CN price-only](./sprint_9_features_cn_price_v1.md) — panel PIT `cn_price_v1`, benchmark CSI 300, rangs transversaux et limites documentées.
- [Validation Sprint 9, 2018–2025](./sprint_9_validation_2018_2025.md) — 8,28 M lignes, audit global et limites sectorielles/ajustements.
- [Sprint 10-A — Labels Oracle CN](./sprint_10a_labels_oracle_cn.md) — H5/H10/H15/H20, disponibilité future, facteurs vérifiés et déciles D1–D10.
- [Sprint 10-A — Validation 2018–2025](./sprint_10a_validation_2018_2025.md) — audit des 32 artefacts, couvertures et quarantaine avant entraînement.
- [Sprint 10-B — Oracle amplitude Walk-Forward](./sprint_10b_oracle_walk_forward.md) — protocole pré-enregistré, folds OOS CN, baseline ATR et gate de recherche.
- [Sprint 10-C — Global ranking signé CN](./sprint_10c_global_ranking.md) — classement D1–D10 sur l'univers PIT et dans le TOP20 Oracle OOS.
