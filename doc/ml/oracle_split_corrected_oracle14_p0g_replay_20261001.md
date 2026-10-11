# Oracle O0 réentraîné après correction des splits — 14 folds OOF, puis P0g

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](experiences_done.md).
<!-- doc-status:end -->

## Résultat

Le réentraînement hors base de l'Oracle d'amplitude O0 est terminé sur les **14 folds OOF gelés** du batch `model-factory-20260909051302-323684`. Les prix NVIDIA antérieurs aux splits 2021 et 2024 et les cibles Oracle recalculées ont été appliqués en mémoire. Les 168 features du profil `oracle.json`, les 2 908 295 observations de test, les dates des folds, la purge H20 et la garde `oracle_available_date` restent celles du protocole P0f.

| Mesure Oracle OOF | Ancien P0f publié | Réentraînement corrigé |
|---|---:|---:|
| AUC amplitude extrême | 0,7582 | **0,758141** |
| Précision TOP10 | 50,41 % | **50,435 %** |
| Prévalence | ≈ 20 % | **20,006 %** |
| Prédictions OOF | 2 908 295 | **2 908 295** |
| TOP20 quotidien | 582 700 | **582 700** |

L'amplitude demeure prédictive et ses métriques globales sont pratiquement inchangées. La composition du TOP20 change néanmoins : **9 041 sorties et 9 041 entrées**, sur **1 005 dates** ; 573 659 événements sont communs aux deux sélections.

Le rejeu P0g sur le **nouveau gate Oracle** a reconstruit les 84 features et leurs rangs transversaux sur l'univers de barres complet, avant le filtre TOP20. Il conserve exactement les **neuf fenêtres de test gelées**, de janvier 2021 à juillet 2025. Les prix et labels corrigés sont les mêmes que dans le rejeu antérieur à gate fixe.

| Mesure P0g OOS D1 contre D10 | Gate Oracle initial, prix/labels corrigés | Oracle réentraîné, prix/labels corrigés |
|---|---:|---:|
| Observations extrêmes scorées | 179 612 | **179 475** |
| AUC | 0,488211 | **0,481115** |
| IC directionnel quotidien moyen | −0,021189 | **−0,029740** |

La comparaison AUC sur les **176 598 mêmes événements OOS**, dont les labels et indices de fold concordent, donne **0,488053** avec l'ancien gate et **0,480660** avec le nouvel Oracle, soit **−0,007392**. Ce rapprochement contrôle le changement de population de test, mais les modèles P0g ont chacun été entraînés sur leur propre TOP20. Trois des neuf folds du nouveau rejeu dépassent 0,50 en AUC.

**Verdict : `ORACLE_O0_REFIT_COMPLETE / P0G_NO_GO_DIRECTION`.** Corriger les splits et réentraîner l'Oracle d'amplitude ne fait pas apparaître de séparation D1/D10. Aucun modèle n'est promu en serving ni utilisé pour un backtest de trading sur cette seule base.

## Reproductibilité et limites

- Jeu Oracle corrigé : `work/guidance_pit_followup_20260930/oracle_split_corrected_o0_dataset.parquet`, SHA-256 `af6c508e3bea1efecb971d21b7ea73d61bbe064c506e446a6b0503a1923b8b97`.
- Modèles des 14 folds, prédictions OOF, gate TOP20 et métriques : `work/guidance_pit_followup_20260930/oracle_split_corrected_o0_14fold_retrain/summary.json`. SHA-256 OOF `51d3488c27d15fead2064c2efb7b5f2e1c82893748334e61a71544c9a10bf5de` ; gate `497a69122b802133a9cad109be14b8722abf304e297310afab04fbef37ab8bf3`.
- Jeu P0g, prédictions et comparaison appariée : `work/guidance_pit_followup_20260930/p0g_split_corrected_new_gate_dataset_manifest.json`, `p0g_split_corrected_new_gate_replay_result.json`, `p0g_split_corrected_new_gate_comparison.json`.
- Scripts de reconstruction et de rejeu dans le même dossier `work/guidance_pit_followup_20260930/`. Ces artefacts sont des fichiers locaux de recherche ignorés par Git ; le rapport présent porte les résultats durables. Aucune écriture dans les tables canoniques.

La comparaison avec le P0f historique publié est indicative : l'environnement logiciel d'origine n'a pas été figé bit à bit. Le contraste P0g à gate fixe versus gate réentraîné utilise en revanche le même runtime local et les mêmes prix/cibles corrigés. Les corrections sont **rétrospectives** ; elles ne valident pas encore la disponibilité PIT des données d'entreprise en production. Les trois événements Oracle de split non ajusté et les exclusions indéterminées sont détaillés dans [l'audit des splits](oracle_split_label_audit_20260930.md).
