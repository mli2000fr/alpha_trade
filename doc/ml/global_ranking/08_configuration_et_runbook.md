# 8 — Configuration et runbook

## Paramètres structurants

| Paramètre | Effet |
|---|---|
| `global_model.enabled` | entraîne la phase globale |
| `stacking_enabled` | injecte les rangs OOF dans les modèles locaux |
| `challenger_enabled` | rend le global candidat dans la gouvernance élargie |
| `champion_enabled` | compare LightGBM, CatBoost et XGBoost par horizon |
| `model_name` | backend unique si championnat désactivé |
| `artifact_symbol` | identité globale, défaut `__GLOBAL__` |
| `use_cross_sectional_features` | active la famille cross-sectionnelle globale |
| `ranking_max_depth`, `ranking_num_leaves` | complexité des arbres |
| `ranking_sector_group` | `all`, `cyclical` ou `defensive` |
| paramètres CatBoost/XGBoost dédiés | itérations et learning rate globaux |
| `ranking_raw_target` | désactive lissage et neutralisations de target |
| `data.global_ranking_max_symbols` | plafond d’univers, 0 = sans plafond |
| `global_ranking_selection_stratified` | plafonnement stratifié ou par liquidité |

LightGBM et plusieurs régularisations utilisent encore `BaselineConfig`.
CatBoost ranking prend sa loss dans cette configuration baseline, mais ses
itérations et son learning rate globaux sont séparés. Conserver la configuration
effective complète, pas seulement le bloc `global_model`.

## Entraîner

Le chemin normal passe par l’orchestrateur de campagne. Il entraîne le Global
Ranking avant ses consommateurs, persiste tôt ses métriques et fusionne
éventuellement le cache OOF pour le stacking.

Checklist : univers et profondeur disponibles ; benchmark/secteurs accessibles ;
flags de features cohérents ; splits et seed enregistrés ; espace disque ; base
accessible ; contrat `ranking_raw_target` explicite.

## Vérifier un batch terminé

- statut du run et entrée globale ;
- cinq horizons présents ou fallbacks expliqués ;
- manifeste lisible ;
- modèle chargeable pour chaque horizon ;
- champions, IC, IR, splits positifs et spreads ;
- `best_horizon` et scores ;
- cache OOS et couverture ;
- cohérence artefacts, métadonnées DB et IHM.

## Produire l’historique PIT

Utiliser la prédiction historique avec l’univers as-of, ou le backfill seulement
si le parquet OOS appartient au batch. Après écriture, contrôler dates,
effectifs et colonnes dans `global_rank_history`. Ne jamais recopier les rangs
d’un batch sous un autre identifiant.

## Activer synthèse et cascade

Sélectionner le `best_horizon` du manifeste ou un horizon validé, le `top_pct`
et le contrat DIP. Vérifier que `reclaim_ratio` n’est pas attendu en live,
puisque ce chemin l’ignore. Contrôler comptes long/short/flat et provenance
`global_rank_synth`.

## Incidents fréquents

### Manifeste absent

La prédiction retourne `None`. Restaurer l’ensemble cohérent du batch plutôt que
reconstituer la seule liste de features.

### Modèle d’un horizon absent

Le rang devient `0.5`. Identifier erreur de sauvegarde, champion et extension
avant backfill ou serving.

### Trop de valeurs à 0,5

Mesurer features manquantes, symboles trop courts, modèles absents, dates non
couvertes et fusion stacking. Le percentile médian naturel existe aussi :
utiliser les flags de disponibilité.

### IC bon mais backtest faible

Vérifier target vol-scalée, turnover, population réellement tradée, coûts,
filtres, lifecycle et concentration. L’IC mesure l’ordre, pas la monétisation.

### Backtest et live divergent

Comparer batch, horizon, univers PIT, manifeste, benchmark, flags, neutralisation,
DIP et reclaim. Relancer la parité sur les mêmes dates.

## Promotion et rollback

Archiver le batch précédent, vérifier manifeste et chargement, tester des
prédictions, remplir l’historique nécessaire et tester le consommateur. Un batch
entraîné n’est pas automatiquement servi.

