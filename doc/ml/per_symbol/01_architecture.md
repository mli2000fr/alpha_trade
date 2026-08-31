# 1 — Architecture et responsabilités per-symbol

`train_symbol` crée un `run_id` unique, enregistre le run si la base est
disponible, dérive une seed du symbole et refuse un historique inférieur à
`min_history_days`. Une panne du registre DB est journalisée puis l’entraînement
peut continuer sans persistance DB ; l’artefact disque reste donc à rapprocher
du registre.

## Challengers réels

- `lstm_attention` : séquences temporelles de longueur configurée, PyTorch
  Lightning, checkpoint au meilleur `val_loss`, early stopping ;
- `lightgbm` : baseline tabulaire, classification ou régression selon la target ;
- `catboost` : baseline tabulaire avec le même contrat de features/target.

Le modèle global peut apparaître comme challenger dans la gouvernance élargie
si sa route existe, mais il reste une famille distincte. Le modèle per-symbol
n’est donc pas synonyme de LSTM : la route servie peut être tabulaire.

## Étapes

1. optimisation optionnelle de target sur train/validation admissibles ;
2. préparation du `SymbolDataModule` ;
3. validation walk-forward LSTM ;
4. fit final LSTM et évaluation val/test ;
5. entraînement des horizons LSTM supplémentaires ;
6. entraînement et WF LightGBM/CatBoost ;
7. construction des challengers et routes ;
8. sélection du champion sans lire le holdout final ;
9. sauvegarde config, métriques, calibrateurs, signatures et registre.

## Multi-horizons

L’horizon primaire garde les artefacts LSTM à la racine du dossier symbole pour
compatibilité. Les horizons supplémentaires utilisent `h{N}/`. Les tabulaires
bouclent également sur `forecast_horizons`. Le consommateur doit lire la route
et la configuration, pas deviner un fichier à partir du seul ticker.

