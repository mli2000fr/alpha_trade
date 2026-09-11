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

Retour : [vue d'ensemble ML](../06_ml_vue_ensemble.md).
