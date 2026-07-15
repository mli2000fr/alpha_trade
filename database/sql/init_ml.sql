START TRANSACTION;

-- Enfants directs des runs d'entrainement.
DELETE FROM alpha_trade.model_directional_oos_metrics;
DELETE FROM alpha_trade.model_metrics_full;
DELETE FROM alpha_trade.model_metrics;
DELETE FROM alpha_trade.model_governance;

-- Predictions produites par les anciens modeles.
DELETE FROM alpha_trade.model_predictions;

-- Historique ML operationnel.
DELETE FROM alpha_trade.champion_history;
DELETE FROM alpha_trade.ml_drift_runs;

-- Runs puis registre des modeles.
DELETE FROM alpha_trade.model_training_run;
DELETE FROM alpha_trade.model_registry;

-- Repartir avec des identifiants numeriques propres.
ALTER TABLE alpha_trade.model_metrics AUTO_INCREMENT = 1;
ALTER TABLE alpha_trade.model_governance AUTO_INCREMENT = 1;
ALTER TABLE alpha_trade.model_registry AUTO_INCREMENT = 1;
ALTER TABLE alpha_trade.champion_history AUTO_INCREMENT = 1;

COMMIT;


/**
Remove-Item -LiteralPath "f:\projets\artifacts\models" -Recurse -Force
Remove-Item -LiteralPath "f:\projets\artifacts\benchmarks" -Recurse -Force
Remove-Item -LiteralPath "f:\projets\artifacts\global_benchmark" -Recurse -Force
Remove-Item -LiteralPath "f:\projets\catboost_info" -Recurse -Force
**/