# Références ML

1. [Orchestration train/predict](orchestration_train_predict.md)
2. [Features et labels](features_et_labels.md)
3. [Global Ranking](global_ranking_reference.md)
   - [Dossier Global Ranking complet](global_ranking/README.md)
4. [Oracle Extreme](oracle_extreme_reference.md)
5. [Oracle Extreme — dossier complet](oracle/README.md)
6. [Validation et gouvernance](validation_et_gouvernance.md)
7. [Features et contrat de dataset](features_et_dataset.md)
8. [Ordre d'exécution et dépendances](ordre_execution_et_dependances.md)
9. [Entraînement, serving et gouvernance](entrainement_serving_et_gouvernance.md)
10. [Qualité, couverture et fallbacks](qualite_couverture_et_fallbacks.md)
11. [Cascade et fallbacks](cascade_et_fallbacks.md)
12. [Modèles global, per-sector et per-symbol](modeles_per_symbol_et_per_sector.md)
    - [Dossier per-symbol complet](per_symbol/README.md)
    - [Dossier per-sector complet](per_sector/README.md)
13. [Recalibration et promotion](recalibration_et_promotion.md)
14. [Ranker conditionnel au TOP20 Oracle](conditional_oracle_ranker.md)
15. [Filtre screener PIT après Oracle](screener_post_oracle.md)
16. [Panel screener PIT dense sur la population Oracle](panel_screener_dense.md)
17. [POC Eroya — nouvelles informations directionnelles](eroya_directional_poc.md)
18. [Capitalisation PIT — SEC EDGAR ou EODHD](market_cap_sec_edgar.md)
    - collecte gratuite des actions SEC ;
    - calcul quotidien, TTL, switch fournisseur et contrat fail-closed.
19. [E16 — reconstruction PIT de l’univers tradable](oracle_tradable_pit_reconstruction_e16.md)
    - audit des grades `full`/`degraded` et du statut canonique ;
    - reconstruction bar-PIT sans imputation ;
    - réplication E12/E15 et verdict lifecycle.
20. [E17 — bibliothèque d’alphas directionnels price-only](directional_alpha_book_e17.md)
    - signaux autonomes, sans Oracle, à H60/H120 ;
    - portefeuille top/bottom 20 % et gates pré-enregistrés ;
    - distinction entre classement relatif et direction absolue.
21. [E17-B — confirmation prospective du momentum résiduel H120](directional_alpha_book_confirmation_e17b.md)
    - candidat long-only figé et indépendant de l’Oracle ;
    - empreinte du protocole, preuve minimale et gates non modifiables ;
    - bloqué tant que les barres ne dépassent pas le début prospectif.
22. [E17-C — robustesse historique du momentum résiduel H120](directional_alpha_book_robustness_e17c.md)
    - blocs temporels, hash folds, calendriers, secteurs et concentration ;
    - avantage robuste contre l’univers mais pas contre SPY ;
    - verdict `NOT_ROBUST`, sans revendication OOS.
23. [E18-A — attribution bêta, secteurs et régimes](directional_alpha_attribution_e18a.md)
    - bêta PIT, portefeuille sector-neutral et couverture SPY ;
    - attribution de la rupture 2021–2022 et de la reprise récente ;
    - verdict `MARKET_OR_SECTOR_EXPOSURE`, sans filtre de régime.
24. [E19-A — audit PIT des fondamentaux](fundamental_pit_availability_e19a.md)
    - couverture SEC quotidienne reconstruite avec disponibilité J+1 ;
    - audit des features, sources, versions et valeurs manquantes ;
    - verdict `PARTIAL_CONTRACT_BLOCKED` avant tout alpha fondamental.
25. [E19-A2 — correction du contrat PIT fondamental](fundamental_pit_contract_e19a2.md)
    - disponibilité J+1, priorité fournisseur et prédécesseur de fenêtre ;
    - lineage SEC, masques de valeurs absentes et corrections sémantiques ;
    - schéma et rafraîchissement SEC validés ; audit `DATA_READY`, E19-B autorisée.
26. [E19-B — bibliothèque d’alphas fondamentaux PIT](fundamental_alpha_book_e19b.md)
    - qualité, valeur, croissance, levier et amélioration ;
    - validation Walk-Forward H20/H60/H120, neutralisation secteur/taille ;
    - composite `NO_GO` après attribution au marché ; valeur seule candidate à
      une confirmation E19-C verrouillée, aucun serving modifié.
27. [E19-C — confirmation verrouillée du facteur valeur PIT](fundamental_value_confirmation_e19c.md)
    - holdouts 2018–2020 et 2025H2, attribution SPY/univers et cinq partitions hash ;
    - verdict `NO_GO` : inversion ancienne malgré un holdout récent positif.
28. [Données manquantes et priorités fournisseurs](data_gaps_and_provider_priorities.md)
29. [Sources gratuites pour le Forward PIT Collector](data_gaps_and_provider_priorities_source_free.md)
30. [Plan des batchs Forward PIT — P0 à P4](forward_pit_batch_plan.md)

Retour : [vue d'ensemble ML](../06_ml_vue_ensemble.md).
