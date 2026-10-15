# Références ML

> 13 octobre 2026 : les modèles US et leurs données ML dérivées ont été supprimés
> à la demande de l'utilisateur. Trois nouvelles campagnes TP20/SL10 fournies ensuite
> ont terminé leur évaluation annuelle hors ligne : neuf cas audités,
> résultats contrastés ; aucune promotion live.
> Les sources et les marchés CN/FR sont conservés.
> [Périmètre et contrôles de la remise à zéro](remise_a_zero_us_20261013.md).
> [Protocole des trois modèles annuels 2024–2026](oracle_modeles_annuels_20261013.md).

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Guide courant : lire aussi les contrats transverses actualisés. Les inventaires générés localisent le code ; ils ne prouvent ni état en base ni réussite opérationnelle. [Référence actuelle](../ETAT_ACTUEL_IMPLEMENTATION.md).
<!-- doc-status:end -->

## Contrats opérationnels actuels — 10 octobre 2026

- [Confiance GPT : gains/pertes par tranche LONG/SHORT et nouveau LONG >=0,90 TP20/SL10](news_gpt_confiance_tranches_2024_2026.md).
- [Vente à découvert des seuls 734 avis GPT baissiers : régimes natifs/variante recherche, emprunt hypothétique](news_gpt_baissiers_short_backtest_2024_2026.md).
- [Achat des seuls 913 avis GPT haussiers : backtests annuels 2024–2026, TP20/SL5 et témoin Oracle](news_gpt_haussiers_backtest_2024_2026.md).
- [GPT sur TOP20 Oracle parcours, 2024–septembre 2026 : modèles annuels, cache SQL et plafond de 8 USD](news_gpt_top20_historique_2024_2026.md).
- [État de l'implémentation US/CN/FR](../ETAT_ACTUEL_IMPLEMENTATION.md).
- [Oracle TOP20 tradable, backtest et live](oracle_tradable_top20_backtest_live.md).
- [Gate d'amplitude Oracle × ATR](oracle_atr_amplitude_gate.md).
- [Étude quotidienne : rendements réalisés et mode partiel](oracle_atr_market_regime_daily.md).
- [Oracle → GPT/Web → risque → PAPER LONG/SHORT](oracle_llm_directional_filter.md).
- [Registre daté des expériences](experiences_done.md) : pas une liste de branches promues.
- [Oracle Extreme parcours H20 : entraînement séparé depuis l'IHM](oracle_path_training.md).
- [Diagnostic ML adapté au parcours H20 : périodes SQL/OOF, amplitude TOP10/20/50 et filiation](diagnostic_oracle_parcours_h20.md).
- [Oracle parcours : comparaison LightGBM/CatBoost, sélection sur validation, pas de LSTM initial](oracle_path_comparaison_20261013.md).
- [Oracle parcours : confirmation 2024–2026 avec modèles figés et couverture TOP-K](oracle_path_confirmation_2024_2026.md).
- [Oracle parcours : challenger LSTM global, séquences causales et copies tabulaires appariées](oracle_path_lstm_comparaison_20261013.md).
- [Oracle parcours LightGBM : backtest économique TOP10/20/50, TP20/SL10 sans trailing](oracle_path_backtest_economique_20261013.md).
- [Oracle parcours LightGBM : audit des pertes, trajectoires, coûts, régimes et réentrées](oracle_path_audit_pertes_20261013.md).
- [Oracle parcours : qualification univariée d'un filtre d'entrée TP20 avant SL10](oracle_path_filtre_entree_separabilite_20261014.md).
- [Audit des anciens signaux directionnels faibles et de leur réutilisation](signaux_directionnels_faibles_audit_20261014.md).
- [News très positives J/J−1/J−2 : hausse pendant H0…H20, pas seulement à H20](news_positives_parcours_h20_20261014.md).
- [News après entrée : confirmation et sorties au prochain open, TP20/SL10 maintenus](news_post_entree_sortie_20261014.md).
- [Oracle parcours TOP5 : grille SL/trailing/TP avec levier ×2, portefeuille et réserves](oracle_path_top5_levier_grid_20261014.md).
- [Oracle parcours TOP5 : règle figée de protections à l'entrée selon régime, VIX, breadth et force relative](oracle_path_protections_dynamiques_20261014.md).
- [Oracle parcours TOP5 : comparaison économique appariée des poids LightGBM/CatBoost](oracle_path_comparaison_economique_backends_20261014.md).
- [Oracle parcours TOP5 : faisabilité de protections personnalisées, plafond rétrospectif sans apprentissage](oracle_path_protections_apprentissage_faisabilite_20261014.md).
- [Protections personnalisées : dataset OOF et variables à J qualifiés, trois nouveaux modèles annuels enregistrés](oracle_path_protections_dataset_oof_20261014.md).
- [Sélecteur des trois profils entraîné et douze portefeuilles annuels : NO_GO, choix LARGE constant](oracle_path_selecteur_protections_20261014.md).
- [TOP5 Oracle parcours : stops SL5, récupération ultérieure et distance ATR — diagnostic terminé, pas preuve de gain](oracle_path_stop_recovery_resultats_20261014.md).
- [TOP5 Oracle parcours : SL5 contre ATR20 borné à risque constant — six portefeuilles, avantage non stable](oracle_path_atr_stop_resultats_20261014.md).
- [TOP5 Oracle parcours : une entrée par épisode de signal — six portefeuilles, veto non favorable](oracle_path_signal_episodes_resultats_20261014.md).
- [News factuelles nouvelles : audit des textes terminé, test historique bloqué par la disponibilité des versions](news_materiality_feasibility_20261014.md).
- [Archive prospective des textes et associations : collecte existante raccordée, disponibilité confirmée après commit](../signals/news_version_archive.md).
- [Cache SQL des analyses GPT de news : 221 réponses importées, réutilisation lot/article et reprise sans nouvel appel](../signals/news_analysis_cache.md).
- [Pilote GPT sur les cinq premières séances de septembre 2026 : huit appels, aucun veto, aucun gain additionnel démontré](news_gpt_septembre_pilote_20261014.md).
- [TOP10 + GPT, janvier–mars 2025 : préparation, reproduction et limites PIT](news_gpt_top10_t1_2025_preparation_20261014.md).
- [TOP10 + GPT, T1 2025 terminé : −12,25 % contre −6,20 %, 213 appels / 0,089 USD, avantage rétrospectif non validé](news_gpt_top10_t1_2025_resultats_20261014.md).
- Oracle parcours : défaut d'entraînement depuis le 13 octobre ; raccordement
  ML Predict/backtest/live avec lineage, sans direction apprise ni promotion automatique.
- [Oracle TP avant SL : amplitude + direction LONG/SHORT, TP 20 % configurable](oracle_barrier_training.md).
- [Oracle TP avant SL : premier audit TOP10 réel et limites du choix LONG/SHORT](oracle_barrier_top10_audit_20261012.md).
- [Comparaison Oracle terminal / TP avant SL sur TOP10, TOP20 et TOP50](oracle_barrier_comparison_top10_20_50_20261012.md).
- [Rejeu 2026 AVB : conversion livrée, fractions et features encore réservées](oracle_merger_replay_2026_20261012.md).
- [2026 débloqué : grille des cinq couples TP/SL terminée, 72 cas](oracle_tp_sl_grid_20261012.md).
- [Trailing Oracle TP20/SL10 : 35 cas vérifiés, bénéfice non confirmé, un blocage LBRDK](oracle_trailing_grid_20261012.md).
- [Sorties des replays Oracle configurées : TP 20 % / SL 10 %, sans trailing](oracle_backtest_exit_policy.md).
- [Oracle SHORT forcé : protocole exploratoire TP20/SL10 et limites d'emprunt](oracle_short_tp20_sl10_20261012.md).
- [Nouveau modèle TP20/SL10 : baseline 2024–2026 terminée](oracle_tp20_sl10_new_baseline_and_challengers_20261012.md).
- [Trois challengers terminés : entrée, sortie quotidienne, TP/SL personnalisés — avantage non robuste](oracle_challengers_20261013.md).
- [Comparaison des trois nouveaux modèles Oracle : TOP50, exécution commune TP20/SL10](comparaison_trois_oracles_top50_20261012.md).
- [Garde progressive Oracle TOP50 : trois années auditées, NO-GO intégration](oracle_exposure_guard_20261013.md).

Les références de recherche ci-dessous conservent leurs verdicts et réserves.
Une source proposée dans un ancien plan ne devient pas une collecte autorisée
actuellement ; vérifier [le catalogue](../operations/catalogue_batchs_actuel.md).

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
30. [E20-A — disponibilité PIT Opening Window après Oracle](oracle_opening_window_availability_e20a.md)
31. [E20-B — confirmation Opening Window price-only](oracle_opening_price_confirmation_e20b.md)
32. [Plan des batchs Forward PIT — P0 à P4](forward_pit_batch_plan.md)

Retour : [vue d'ensemble ML](../06_ml_vue_ensemble.md).
