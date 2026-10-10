# DDL et graphe des migrations présents dans le dépôt

Inventaire statique au 2026-10-10, **pas un schéma déployé**. Aucun SQL exécuté.
Les tables peuvent être définies à plusieurs endroits ou migrées depuis un DDL initial.
Le graphe des révisions et les ALTER ultérieurs priment sur un CREATE isolé.
Les migrations US ne s'appliquent pas automatiquement aux bases CN/FR.
[Contrat migrations](../database/migrations_et_transactions.md).

## Révisions Alembic

| Fichier | revision | down_revision |
| --- | --- | --- |
| [alembic/versions/0001_initial.py](../../alembic/versions/0001_initial.py) | `0001_initial` | `None` |
| [alembic/versions/0002_add_account_id.py](../../alembic/versions/0002_add_account_id.py) | `0002_add_account_id` | `0001_initial` |
| [alembic/versions/0003_news_checkpoint_per_symbol.py](../../alembic/versions/0003_news_checkpoint_per_symbol.py) | `0003_news_checkpoint_per_symbol` | `0002_add_account_id` |
| [alembic/versions/0004_add_selector_reference_data.py](../../alembic/versions/0004_add_selector_reference_data.py) | `0004_add_selector_reference_data` | `0003_news_checkpoint_per_symbol` |
| [alembic/versions/0005_add_model_predictions_audit_fields.py](../../alembic/versions/0005_add_model_predictions_audit_fields.py) | `0005_add_model_predictions_audit_fields` | `0004_add_selector_reference_data` |
| [alembic/versions/0006_add_model_governance_table.py](../../alembic/versions/0006_add_model_governance_table.py) | `0006_add_model_governance_table` | `0005_add_model_predictions_audit_fields` |
| [alembic/versions/0007_add_run_business_summaries_table.py](../../alembic/versions/0007_add_run_business_summaries_table.py) | `0007_add_run_business_summaries_table` | `0006_add_model_governance_table` |
| [alembic/versions/0008_add_execution_sprint1_foundations.py](../../alembic/versions/0008_add_execution_sprint1_foundations.py) | `0008_add_execution_sprint1_foundations` | `0007_add_run_business_summaries_table` |
| [alembic/versions/0009_add_execution_sprint2_persistence.py](../../alembic/versions/0009_add_execution_sprint2_persistence.py) | `0009_add_execution_sprint2_persistence` | `0008_add_execution_sprint1_foundations` |
| [alembic/versions/0010_add_execution_sprint4_positions.py](../../alembic/versions/0010_add_execution_sprint4_positions.py) | `0010_add_execution_sprint4_positions` | `0009_add_execution_sprint2_persistence` |
| [alembic/versions/0011_add_execution_sprint5_reconciliation.py](../../alembic/versions/0011_add_execution_sprint5_reconciliation.py) | `0011_add_execution_sprint5_reconciliation` | `0010_add_execution_sprint4_positions` |
| [alembic/versions/0012_market_data_provenance_and_check.py](../../alembic/versions/0012_market_data_provenance_and_check.py) | `0012_market_data_provenance_and_check` | `0011_add_execution_sprint5_reconciliation` |
| [alembic/versions/0013_watcher_heartbeats.py](../../alembic/versions/0013_watcher_heartbeats.py) | `0013_watcher_heartbeats` | `0012_market_data_provenance_and_check` |
| [alembic/versions/0014_cleaning_audit_quotes_earnings_runs.py](../../alembic/versions/0014_cleaning_audit_quotes_earnings_runs.py) | `0014_cleaning_audit_quotes_earnings_runs` | `0013_watcher_heartbeats` |
| [alembic/versions/0015_finbert_model_fingerprint.py](../../alembic/versions/0015_finbert_model_fingerprint.py) | `0015_finbert_model_fingerprint` | `0014_cleaning_audit_quotes_earnings_runs` |
| [alembic/versions/0016_model_metrics_full_blob.py](../../alembic/versions/0016_model_metrics_full_blob.py) | `0016_model_metrics_full_blob` | `0015_finbert_model_fingerprint` |
| [alembic/versions/0017_execution_kill_switch_runs.py](../../alembic/versions/0017_execution_kill_switch_runs.py) | `0017_execution_kill_switch_runs` | `0016_model_metrics_full_blob` |
| [alembic/versions/0018_corporate_actions_audit_runs.py](../../alembic/versions/0018_corporate_actions_audit_runs.py) | `0018_corporate_actions_audit_runs` | `0017_execution_kill_switch_runs` |
| [alembic/versions/0019_corporate_actions_account_idempotency.py](../../alembic/versions/0019_corporate_actions_account_idempotency.py) | `0019_corporate_actions_account_idempotency` | `0018_corporate_actions_audit_runs` |
| [alembic/versions/0020_weights_calibration_runs.py](../../alembic/versions/0020_weights_calibration_runs.py) | `0020_weights_calibration_runs` | `0019_corporate_actions_account_idempotency` |
| [alembic/versions/0021_ml_drift_runs.py](../../alembic/versions/0021_ml_drift_runs.py) | `0021_ml_drift_runs` | `0020_weights_calibration_runs` |
| [alembic/versions/0022_shadow_drift_runs.py](../../alembic/versions/0022_shadow_drift_runs.py) | `0022_shadow_drift_runs` | `0021_ml_drift_runs` |
| [alembic/versions/0023_stock_scores_history_capital_preset.py](../../alembic/versions/0023_stock_scores_history_capital_preset.py) | `0023_stock_scores_history_capital_preset` | `0022_shadow_drift_runs` |
| [alembic/versions/0024_audit_chain.py](../../alembic/versions/0024_audit_chain.py) | `0024_audit_chain` | `0023_stock_scores_history_capital_preset` |
| [alembic/versions/0025_broker_statements.py](../../alembic/versions/0025_broker_statements.py) | `0025_broker_statements` | `0024_audit_chain` |
| [alembic/versions/0026_champion_history.py](../../alembic/versions/0026_champion_history.py) | `0026_champion_history` | `0025_broker_statements` |
| [alembic/versions/0027_news_ticker_map_relevance.py](../../alembic/versions/0027_news_ticker_map_relevance.py) | `0027_news_ticker_map_relevance` | `0026_champion_history` |
| [alembic/versions/0028_news_ticker_sentiment.py](../../alembic/versions/0028_news_ticker_sentiment.py) | `0028_news_ticker_sentiment` | `0027_news_ticker_map_relevance` |
| [alembic/versions/0029_selector_explainability_persistence.py](../../alembic/versions/0029_selector_explainability_persistence.py) | `0029_selector_explainability_persistence` | `0028_news_ticker_sentiment` |
| [alembic/versions/0030_weights_calibration_runs_add_risk_scope.py](../../alembic/versions/0030_weights_calibration_runs_add_risk_scope.py) | `0030_weights_calibration_runs_add_risk_scope` | `0029_selector_explainability_persistence` |
| [alembic/versions/0031_weights_calibration_runs_regime_segmentation.py](../../alembic/versions/0031_weights_calibration_runs_regime_segmentation.py) | `0031_weights_calibration_runs_regime_segmentation` | `0030_weights_calibration_runs_add_risk_scope` |
| [alembic/versions/0032_weights_calibration_multi_segment_governance.py](../../alembic/versions/0032_weights_calibration_multi_segment_governance.py) | `0032_weights_calibration_multi_segment_governance` | `0031_weights_calibration_runs_regime_segmentation` |
| [alembic/versions/0033_news_checkpoint_stage_timestamps.py](../../alembic/versions/0033_news_checkpoint_stage_timestamps.py) | `0033_news_checkpoint_stage_timestamps` | `0032_weights_calibration_multi_segment_governance` |
| [alembic/versions/0034_add_stock_macro_indicators_daily.py](../../alembic/versions/0034_add_stock_macro_indicators_daily.py) | `0034_add_stock_macro_indicators_daily` | `0033_news_checkpoint_stage_timestamps` |
| [alembic/versions/0035_drop_equity_simulated.py](../../alembic/versions/0035_drop_equity_simulated.py) | `0035_drop_equity_simulated` | `0034_add_stock_macro_indicators_daily` |
| [alembic/versions/0036_expand_sizing_method_column.py](../../alembic/versions/0036_expand_sizing_method_column.py) | `0036_expand_sizing_method_column` | `0035_drop_equity_simulated` |
| [alembic/versions/0037_add_fractionable_and_fractional_target_shares.py](../../alembic/versions/0037_add_fractionable_and_fractional_target_shares.py) | `0037_add_fractionable_and_fractional_target_shares` | `0036_expand_sizing_method_column` |
| [alembic/versions/0038_add_model_predictions_ternary.py](../../alembic/versions/0038_add_model_predictions_ternary.py) | `0038_add_model_predictions_ternary` | `0037_add_fractionable_and_fractional_target_shares` |
| [alembic/versions/0039_add_model_metrics_ternary.py](../../alembic/versions/0039_add_model_metrics_ternary.py) | `0039_add_model_metrics_ternary` | `0038_add_model_predictions_ternary` |
| [alembic/versions/0040_optimize_stock_bars_indexes.py](../../alembic/versions/0040_optimize_stock_bars_indexes.py) | `0040_optimize_stock_bars_indexes` | `0039_add_model_metrics_ternary` |
| [alembic/versions/0041_add_short_score_to_history.py](../../alembic/versions/0041_add_short_score_to_history.py) | `0041_add_short_score_to_history` | `0040_optimize_stock_bars_indexes` |
| [alembic/versions/0042_add_sma_to_history.py](../../alembic/versions/0042_add_sma_to_history.py) | `0042_add_sma_to_history` | `0041_add_short_score_to_history` |
| [alembic/versions/0043_add_vxn_vix3m_move_rvx.py](../../alembic/versions/0043_add_vxn_vix3m_move_rvx.py) | `0043_add_vxn_vix3m_move_rvx` | `0042_add_sma_to_history` |
| [alembic/versions/0044_add_model_metrics_model_name.py](../../alembic/versions/0044_add_model_metrics_model_name.py) | `0044_add_model_metrics_model_name` | `0043_add_vxn_vix3m_move_rvx` |
| [alembic/versions/0045_add_model_training_run_data_dates.py](../../alembic/versions/0045_add_model_training_run_data_dates.py) | `0045_add_model_training_run_data_dates` | `0044_add_model_metrics_model_name` |
| [alembic/versions/0046_add_tradable_universe_history.py](../../alembic/versions/0046_add_tradable_universe_history.py) | `0046_add_tradable_universe_history` | `0045_add_model_training_run_data_dates` |
| [alembic/versions/0047_add_selection_rank_to_risk_execution.py](../../alembic/versions/0047_add_selection_rank_to_risk_execution.py) | `0047_add_selection_rank_to_risk_execution` | `0046_add_tradable_universe_history` |
| [alembic/versions/0048_add_model_directional_oos_metrics.py](../../alembic/versions/0048_add_model_directional_oos_metrics.py) | `0048_add_model_directional_oos_metrics` | `0047_add_selection_rank_to_risk_execution` |
| [alembic/versions/0048_drop_candidate_columns_from_score_snapshots.py](../../alembic/versions/0048_drop_candidate_columns_from_score_snapshots.py) | `0048_drop_candidate_columns_from_score_snapshots` | `0047_add_selection_rank_to_risk_execution` |
| [alembic/versions/0049_add_model_training_run_batch_id.py](../../alembic/versions/0049_add_model_training_run_batch_id.py) | `0049_add_model_training_run_batch_id` | `('0048_add_model_directional_oos_metrics', '0048_drop_candidate_columns_from_score_snapshots')` |
| [alembic/versions/0050_add_model_training_batch.py](../../alembic/versions/0050_add_model_training_batch.py) | `0050_add_model_training_batch` | `0049_add_model_training_run_batch_id` |
| [alembic/versions/0051_add_comment_to_model_training_batch.py](../../alembic/versions/0051_add_comment_to_model_training_batch.py) | `0051_add_comment_to_model_training_batch` | `0050_add_model_training_batch` |
| [alembic/versions/0052_add_model_metrics_pct_columns.py](../../alembic/versions/0052_add_model_metrics_pct_columns.py) | `0052_add_model_metrics_pct_columns` | `0051_add_comment_to_model_training_batch` |
| [alembic/versions/0053_add_model_serving_batch.py](../../alembic/versions/0053_add_model_serving_batch.py) | `0053_add_model_serving_batch` | `0052_add_model_metrics_pct_columns` |
| [alembic/versions/0054_add_model_batch_diagnostics.py](../../alembic/versions/0054_add_model_batch_diagnostics.py) | `0054_add_model_batch_diagnostics` | `0053_add_model_serving_batch` |
| [alembic/versions/0055_add_stock_fundamentals_daily.py](../../alembic/versions/0055_add_stock_fundamentals_daily.py) | `0055_add_stock_fundamentals_daily` | `0054_add_model_batch_diagnostics` |
| [alembic/versions/0056_add_ic_rank_to_training_batch.py](../../alembic/versions/0056_add_ic_rank_to_training_batch.py) | `0056_add_ic_rank_to_training_batch` | `0055_add_stock_fundamentals_daily` |
| [alembic/versions/0057_add_decile_spreads_to_training_batch.py](../../alembic/versions/0057_add_decile_spreads_to_training_batch.py) | `0057` | `0056_add_ic_rank_to_training_batch` |
| [alembic/versions/0058_add_global_rank_history.py](../../alembic/versions/0058_add_global_rank_history.py) | `0058` | `0057` |
| [alembic/versions/0059_add_stacking_enabled_to_training_batch.py](../../alembic/versions/0059_add_stacking_enabled_to_training_batch.py) | `0059` | `0058` |
| [alembic/versions/0060_add_shares_outstanding_to_fundamentals.py](../../alembic/versions/0060_add_shares_outstanding_to_fundamentals.py) | `0060_add_shares_outstanding_to_fundamentals` | `0059` |
| [alembic/versions/0061_widen_symbol_columns_for_sector_names.py](../../alembic/versions/0061_widen_symbol_columns_for_sector_names.py) | `0061_widen_symbol_columns_for_sector_names` | `0060_add_shares_outstanding_to_fundamentals` |
| [alembic/versions/0062_add_horizon_to_model_metrics.py](../../alembic/versions/0062_add_horizon_to_model_metrics.py) | `0062_add_horizon_to_model_metrics` | `0061_widen_symbol_columns_for_sector_names` |
| [alembic/versions/0063_add_symbols_to_training_batch.py](../../alembic/versions/0063_add_symbols_to_training_batch.py) | `0063_add_symbols_to_training_batch` | `0062_add_horizon_to_model_metrics` |
| [alembic/versions/0064_add_global_oracle_labels.py](../../alembic/versions/0064_add_global_oracle_labels.py) | `0064_add_global_oracle_labels` | `0063_add_symbols_to_training_batch` |
| [alembic/versions/0065_oracle_extreme_rename.py](../../alembic/versions/0065_oracle_extreme_rename.py) | `0065_oracle_extreme_rename` | `0064_add_global_oracle_labels` |
| [alembic/versions/0066_add_model_predictions_run_id_index.py](../../alembic/versions/0066_add_model_predictions_run_id_index.py) | `0066_add_model_predictions_run_id_index` | `0065_oracle_extreme_rename` |
| [alembic/versions/0067_add_model_predictions_source.py](../../alembic/versions/0067_add_model_predictions_source.py) | `0067_add_model_predictions_source` | `0066_add_model_predictions_run_id_index` |
| [alembic/versions/0068_analyst_snapshot_collection.py](../../alembic/versions/0068_analyst_snapshot_collection.py) | `0068_analyst_snapshot_collection` | `0067_add_model_predictions_source` |
| [alembic/versions/0069_add_directional_bundle_prediction_lineage.py](../../alembic/versions/0069_add_directional_bundle_prediction_lineage.py) | `0069_directional_bundle_lineage` | `0068_analyst_snapshot_collection` |
| [alembic/versions/0070_add_model_training_run_role.py](../../alembic/versions/0070_add_model_training_run_role.py) | `0070_training_run_role` | `0069_directional_bundle_lineage` |
| [alembic/versions/0071_widen_prediction_calibration_method.py](../../alembic/versions/0071_widen_prediction_calibration_method.py) | `0071_widen_prediction_calibration` | `0070_training_run_role` |
| [alembic/versions/0072_add_oracle_label_quality.py](../../alembic/versions/0072_add_oracle_label_quality.py) | `0072_oracle_label_quality` | `0071_widen_prediction_calibration` |
| [alembic/versions/0073_fundamentals_multi_provider_identity.py](../../alembic/versions/0073_fundamentals_multi_provider_identity.py) | `0073_fundamentals_multi_provider` | `0072_oracle_label_quality` |
| [alembic/versions/0074_fundamental_pit_contract.py](../../alembic/versions/0074_fundamental_pit_contract.py) | `0074_fundamental_pit_contract` | `0073_fundamentals_multi_provider` |
| [alembic/versions/0075_forward_pit_collection_foundation.py](../../alembic/versions/0075_forward_pit_collection_foundation.py) | `0075_forward_pit_collection` | `0074_fundamental_pit_contract` |
| [alembic/versions/0076_finra_short_volume_daily.py](../../alembic/versions/0076_finra_short_volume_daily.py) | `0076_finra_short_volume` | `0075_forward_pit_collection` |
| [alembic/versions/0077_yahoo_analyst_trends_revisions.py](../../alembic/versions/0077_yahoo_analyst_trends_revisions.py) | `0077_yahoo_analyst_trends` | `0076_finra_short_volume` |
| [alembic/versions/0078_alpaca_opening_window_pit.py](../../alembic/versions/0078_alpaca_opening_window_pit.py) | `0078_alpaca_opening_window_pit` | `0077_yahoo_analyst_trends` |
| [alembic/versions/0079_delayed_options_and_occ_adjustments.py](../../alembic/versions/0079_delayed_options_and_occ_adjustments.py) | `0079_delayed_options_occ` | `0078_alpaca_opening_window_pit` |
| [alembic/versions/0080_widen_pit_collection_run_provider.py](../../alembic/versions/0080_widen_pit_collection_run_provider.py) | `0080_widen_pit_run_provider` | `0079_delayed_options_occ` |
| [alembic/versions/0081_widen_forward_pit_providers.py](../../alembic/versions/0081_widen_forward_pit_providers.py) | `0081_widen_forward_pit_providers` | `0080_widen_pit_run_provider` |
| [alembic/versions/0082_sec_filing_documents.py](../../alembic/versions/0082_sec_filing_documents.py) | `0082_sec_filing_documents` | `0081_widen_forward_pit_providers` |
| [alembic/versions/0083_finra_fractional_short_volume.py](../../alembic/versions/0083_finra_fractional_short_volume.py) | `0083_finra_fractional_short_volume` | `0082_sec_filing_documents` |
| [alembic/versions/0084_market_instrument_foundation.py](../../alembic/versions/0084_market_instrument_foundation.py) | `0084_market_instrument_foundation` | `0083_finra_fractional_short_volume` |
| [alembic/versions/0085_market_scope_parents.py](../../alembic/versions/0085_market_scope_parents.py) | `0085_market_scope_parents` | `0084_market_instrument_foundation` |
| [alembic/versions/0086_market_calendar_pit.py](../../alembic/versions/0086_market_calendar_pit.py) | `0086_market_calendar_pit` | `0085_market_scope_parents` |
| [alembic/versions/0087_us_fact_instrument_columns.py](../../alembic/versions/0087_us_fact_instrument_columns.py) | `0087_us_fact_instrument_columns` | `0086_market_calendar_pit` |
| [alembic/versions/0088_us_fact_instrument_constraints.py](../../alembic/versions/0088_us_fact_instrument_constraints.py) | `0088_us_fact_instrument_constraints` | `0087_us_fact_instrument_columns` |
| [alembic/versions/0089_oracle_atr_market_regime_daily.py](../../alembic/versions/0089_oracle_atr_market_regime_daily.py) | `0089_oracle_atr_regime` | `0088_us_fact_instrument_constraints` |
| [alembic/versions/0090_oracle_atr_d10_d1_ratio.py](../../alembic/versions/0090_oracle_atr_d10_d1_ratio.py) | `0090_oracle_atr_d10_d1_ratio` | `0089_oracle_atr_regime` |
| [alembic/versions/0091_oracle_atr_total_pct.py](../../alembic/versions/0091_oracle_atr_total_pct.py) | `0091_oracle_atr_total_pct` | `0090_oracle_atr_d10_d1_ratio` |
| [alembic/versions/0092_oracle_atr_movements.py](../../alembic/versions/0092_oracle_atr_movements.py) | `0092_oracle_atr_movements` | `0091_oracle_atr_total_pct` |
| [alembic/versions/0093_llm_directional.py](../../alembic/versions/0093_llm_directional.py) | `0093_llm_directional` | `0092_oracle_atr_movements` |
| [alembic/versions/0094_oracle_atr_score_order.py](../../alembic/versions/0094_oracle_atr_score_order.py) | `0094_oracle_atr_score_order` | `0093_llm_directional` |
| [alembic/versions/0095_oracle_atr_partial_returns.py](../../alembic/versions/0095_oracle_atr_partial_returns.py) | `0095_oracle_atr_partial_returns` | `0094_oracle_atr_score_order` |
| [alembic_cn/versions/0001_tushare_raw_staging.py](../../alembic_cn/versions/0001_tushare_raw_staging.py) | `0001_tushare_raw_staging` | `None` |
| [alembic_cn/versions/0002_tushare_raw_run_lineage.py](../../alembic_cn/versions/0002_tushare_raw_run_lineage.py) | `0002_tushare_raw_run_lineage` | `0001_tushare_raw_staging` |
| [alembic_cn/versions/0003_provider_neutral_staging.py](../../alembic_cn/versions/0003_provider_neutral_staging.py) | `0003_provider_neutral_staging` | `0002_tushare_raw_run_lineage` |
| [alembic_cn/versions/0004_canonical_market_pilot.py](../../alembic_cn/versions/0004_canonical_market_pilot.py) | `0004_canonical_market_pilot` | `0003_provider_neutral_staging` |
| [alembic_cn/versions/0005_canonical_full_coverage.py](../../alembic_cn/versions/0005_canonical_full_coverage.py) | `0005_canonical_full_coverage` | `0004_canonical_market_pilot` |
| [alembic_cn/versions/0006_universe_pit.py](../../alembic_cn/versions/0006_universe_pit.py) | `0006_universe_pit` | `0005_canonical_full_coverage` |
| [alembic_cn/versions/0007_universe_audit_indexes.py](../../alembic_cn/versions/0007_universe_audit_indexes.py) | `0007_universe_audit_indexes` | `0006_universe_pit` |
| [alembic_fr/versions/0001_fr_reference.py](../../alembic_fr/versions/0001_fr_reference.py) | `0001_fr_reference` | `None` |
| [alembic_fr/versions/0002_fr_prices.py](../../alembic_fr/versions/0002_fr_prices.py) | `0002_fr_prices` | `0001_fr_reference` |
| [alembic_fr/versions/0003_fr_split_volume.py](../../alembic_fr/versions/0003_fr_split_volume.py) | `0003_fr_split_volume` | `0002_fr_prices` |
| [alembic_fr/versions/0004_fr_provider_staging.py](../../alembic_fr/versions/0004_fr_provider_staging.py) | `0004_fr_provider_staging` | `0003_fr_split_volume` |
| [alembic_fr/versions/0005_fr_staging_quality_version.py](../../alembic_fr/versions/0005_fr_staging_quality_version.py) | `0005_fr_staging_quality_version` | `0004_fr_provider_staging` |
| [alembic_fr/versions/0006_fr_universe_contract.py](../../alembic_fr/versions/0006_fr_universe_contract.py) | `0006_fr_universe_contract` | `0005_fr_staging_quality_version` |
| [alembic_fr/versions/0007_fr_liquidity_research.py](../../alembic_fr/versions/0007_fr_liquidity_research.py) | `0007_fr_liquidity_research` | `0006_fr_universe_contract` |
| [alembic_fr/versions/0008_fr_reference_research.py](../../alembic_fr/versions/0008_fr_reference_research.py) | `0008_fr_reference_research` | `0007_fr_liquidity_research` |

## Tables nommées dans les DDL SQL

| Table | DDL présent |
| --- | --- |
| `account_risk_snapshots` | [database/sql/risk/account_risk_snapshots.sql](../../database/sql/risk/account_risk_snapshots.sql) |
| `alpha_trade.audit_chain_events` | [database/sql/audit_chain_events.sql](../../database/sql/audit_chain_events.sql) |
| `alpha_trade.broker_statements` | [database/sql/broker_statements.sql](../../database/sql/broker_statements.sql) |
| `alpha_trade.champion_history` | [database/sql/champion_history.sql](../../database/sql/champion_history.sql) |
| `alpha_trade.cleaning_audit_earnings_runs` | [database/sql/stock/cleaning_audit_earnings_runs.sql](../../database/sql/stock/cleaning_audit_earnings_runs.sql) |
| `alpha_trade.cleaning_audit_latest` | [database/sql/stock/cleaning_audit_latest.sql](../../database/sql/stock/cleaning_audit_latest.sql) |
| `alpha_trade.cleaning_audit_quotes_runs` | [database/sql/stock/cleaning_audit_quotes_runs.sql](../../database/sql/stock/cleaning_audit_quotes_runs.sql) |
| `alpha_trade.cleaning_audit_runs` | [database/sql/stock/cleaning_audit_runs.sql](../../database/sql/stock/cleaning_audit_runs.sql) |
| `alpha_trade.corporate_action_source_events` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.corporate_actions_applications` | [database/sql/corporate_actions/corporate_actions_applications.sql](../../database/sql/corporate_actions/corporate_actions_applications.sql) |
| `alpha_trade.corporate_actions_audit_runs` | [database/sql/corporate_actions/corporate_actions_audit_runs.sql](../../database/sql/corporate_actions/corporate_actions_audit_runs.sql) |
| `alpha_trade.corporate_actions_events` | [database/sql/corporate_actions/corporate_actions_events.sql](../../database/sql/corporate_actions/corporate_actions_events.sql) |
| `alpha_trade.execution_kill_switch_runs` | [database/sql/execution/execution_kill_switch_runs.sql](../../database/sql/execution/execution_kill_switch_runs.sql) |
| `alpha_trade.global_oracle_labels` | [database/sql/ml/global_oracle_labels.sql](../../database/sql/ml/global_oracle_labels.sql) |
| `alpha_trade.global_rank_history` | [database/sql/ml/global_rank_history.sql](../../database/sql/ml/global_rank_history.sql) |
| `alpha_trade.macro_event_audit` | [database/sql/news/init_event_sentiment.sql](../../database/sql/news/init_event_sentiment.sql), [database/sql/news/macro_event_audit.sql](../../database/sql/news/macro_event_audit.sql) |
| `alpha_trade.macro_vintage_observations` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.ml_drift_runs` | [database/sql/ml/ml_drift_runs.sql](../../database/sql/ml/ml_drift_runs.sql) |
| `alpha_trade.model_batch_diagnostics` | [database/sql/ml/model_batch_diagnostics.sql](../../database/sql/ml/model_batch_diagnostics.sql) |
| `alpha_trade.model_governance` | [database/sql/ml/model_governance.sql](../../database/sql/ml/model_governance.sql) |
| `alpha_trade.model_metrics` | [database/sql/ml/model_metrics.sql](../../database/sql/ml/model_metrics.sql) |
| `alpha_trade.model_metrics_full` | [database/sql/ml/model_metrics_full.sql](../../database/sql/ml/model_metrics_full.sql) |
| `alpha_trade.model_predictions` | [database/sql/ml/model_predictions.sql](../../database/sql/ml/model_predictions.sql) |
| `alpha_trade.model_registry` | [database/sql/ml/model_registry.sql](../../database/sql/ml/model_registry.sql) |
| `alpha_trade.model_training_batch` | [database/sql/ml/model_training_batch.sql](../../database/sql/ml/model_training_batch.sql) |
| `alpha_trade.model_training_run` | [database/sql/ml/model_training_run.sql](../../database/sql/ml/model_training_run.sql) |
| `alpha_trade.news_ingestion_checkpoint` | [database/sql/news/init_event_sentiment.sql](../../database/sql/news/init_event_sentiment.sql), [database/sql/news/news_ingestion_checkpoint.sql](../../database/sql/news/news_ingestion_checkpoint.sql) |
| `alpha_trade.news_raw` | [database/sql/news/init_event_sentiment.sql](../../database/sql/news/init_event_sentiment.sql), [database/sql/news/news_raw.sql](../../database/sql/news/news_raw.sql) |
| `alpha_trade.news_sentiment` | [database/sql/news/init_event_sentiment.sql](../../database/sql/news/init_event_sentiment.sql), [database/sql/news/news_sentiment.sql](../../database/sql/news/news_sentiment.sql) |
| `alpha_trade.news_ticker_map` | [database/sql/news/init_event_sentiment.sql](../../database/sql/news/init_event_sentiment.sql), [database/sql/news/news_ticker_map.sql](../../database/sql/news/news_ticker_map.sql) |
| `alpha_trade.news_ticker_sentiment` | [database/sql/news/init_event_sentiment.sql](../../database/sql/news/init_event_sentiment.sql), [database/sql/news/news_ticker_sentiment.sql](../../database/sql/news/news_ticker_sentiment.sql) |
| `alpha_trade.option_contract_adjustments` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql), [database/sql/migration_0079_delayed_options_and_occ_adjustments.sql](../../database/sql/migration_0079_delayed_options_and_occ_adjustments.sql) |
| `alpha_trade.oracle_atr_market_regime_daily` | [database/sql/ml/oracle_atr_market_regime_daily.sql](../../database/sql/ml/oracle_atr_market_regime_daily.sql) |
| `alpha_trade.oracle_extreme_predictions` | [database/sql/oracle/oracle_extreme_predictions.sql](../../database/sql/oracle/oracle_extreme_predictions.sql) |
| `alpha_trade.pit_collection_runs` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.pit_data_quality_issues` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.pit_data_quality_metrics` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.pit_raw_payloads` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.portfolio_cash_ledger` | [database/sql/corporate_actions/portfolio_cash_ledger.sql](../../database/sql/corporate_actions/portfolio_cash_ledger.sql) |
| `alpha_trade.sec_corporate_events` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.sec_filing_documents` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql), [database/sql/migration_0082_sec_filing_documents.sql](../../database/sql/migration_0082_sec_filing_documents.sql) |
| `alpha_trade.sec_filing_raw` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.sec_ownership_snapshots` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.sector_daily_sentiment_features` | [database/sql/news/init_event_sentiment.sql](../../database/sql/news/init_event_sentiment.sql), [database/sql/news/sector_daily_sentiment_features.sql](../../database/sql/news/sector_daily_sentiment_features.sql) |
| `alpha_trade.security_master_changes` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.security_master_snapshots` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.shadow_drift_runs` | [database/sql/risk/shadow_drift_runs.sql](../../database/sql/risk/shadow_drift_runs.sql) |
| `alpha_trade.stock_analyst_consensus_snapshots` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.stock_bars` | [database/sql/stock/stock_bars.sql](../../database/sql/stock/stock_bars.sql) |
| `alpha_trade.stock_bars_daily` | [database/sql/stock/stock_bars_daily.sql](../../database/sql/stock/stock_bars_daily.sql) |
| `alpha_trade.stock_bars_daily_versions` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.stock_borrow_status_snapshots` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.stock_earnings_calendar` | [database/sql/stock/stock_earnings_calendar.sql](../../database/sql/stock/stock_earnings_calendar.sql) |
| `alpha_trade.stock_fundamentals_daily` | [database/sql/stock/stock_fundamentals_daily.sql](../../database/sql/stock/stock_fundamentals_daily.sql) |
| `alpha_trade.stock_macro_indicators_daily` | [database/sql/stock/stock_macro_indicators_daily.sql](../../database/sql/stock/stock_macro_indicators_daily.sql) |
| `alpha_trade.stock_metadata` | [database/sql/stock/stock_metadata.sql](../../database/sql/stock/stock_metadata.sql) |
| `alpha_trade.stock_opening_window_bar_versions` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql), [database/sql/migration_0078_alpaca_opening_window_pit.sql](../../database/sql/migration_0078_alpaca_opening_window_pit.sql) |
| `alpha_trade.stock_opening_window_bars` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.stock_option_bars_delayed` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql), [database/sql/migration_0079_delayed_options_and_occ_adjustments.sql](../../database/sql/migration_0079_delayed_options_and_occ_adjustments.sql) |
| `alpha_trade.stock_option_contract_versions` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql), [database/sql/migration_0079_delayed_options_and_occ_adjustments.sql](../../database/sql/migration_0079_delayed_options_and_occ_adjustments.sql) |
| `alpha_trade.stock_option_snapshots` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.stock_quote_snapshots` | [database/sql/stock/stock_quote_snapshots.sql](../../database/sql/stock/stock_quote_snapshots.sql) |
| `alpha_trade.stock_scores` | [database/sql/stock/stock_scores.sql](../../database/sql/stock/stock_scores.sql) |
| `alpha_trade.stock_scores_history` | [database/sql/stock/stock_scores_history.sql](../../database/sql/stock/stock_scores_history.sql) |
| `alpha_trade.stock_short_volume_daily` | [database/sql/forward_pit/forward_pit_tables.sql](../../database/sql/forward_pit/forward_pit_tables.sql) |
| `alpha_trade.ticker_daily_sentiment_features` | [database/sql/news/init_event_sentiment.sql](../../database/sql/news/init_event_sentiment.sql), [database/sql/news/ticker_daily_sentiment_features.sql](../../database/sql/news/ticker_daily_sentiment_features.sql) |
| `alpha_trade.tradable_universe_history` | [database/sql/stock/tradable_universe_history.sql](../../database/sql/stock/tradable_universe_history.sql) |
| `alpha_trade.tradable_universe_runs` | [database/sql/stock/tradable_universe_history.sql](../../database/sql/stock/tradable_universe_history.sql) |
| `alpha_trade.weights_calibration_runs` | [database/sql/ml/weights_calibration_runs.sql](../../database/sql/ml/weights_calibration_runs.sql) |
| `alpha_trade.weights_calibration_segment_drifts` | [database/sql/ml/weights_calibration_runs_upgrade.sql](../../database/sql/ml/weights_calibration_runs_upgrade.sql), [database/sql/ml/weights_calibration_segment_drifts.sql](../../database/sql/ml/weights_calibration_segment_drifts.sql) |
| `analyst_snapshot_collection_run` | [database/sql/stock/analyst_snapshot_collection_run.sql](../../database/sql/stock/analyst_snapshot_collection_run.sql) |
| `broker_account_snapshots` | [database/sql/execution/broker_account_snapshots.sql](../../database/sql/execution/broker_account_snapshots.sql) |
| `broker_positions_snapshots` | [database/sql/execution/broker_positions_snapshots.sql](../../database/sql/execution/broker_positions_snapshots.sql) |
| `cn_canonical_coverage_metrics` | [database/sql/cn/migration_cn_0005_canonical_full_coverage.sql](../../database/sql/cn/migration_cn_0005_canonical_full_coverage.sql) |
| `cn_canonicalization_runs` | [database/sql/cn/migration_cn_0004_canonical_market_pilot.sql](../../database/sql/cn/migration_cn_0004_canonical_market_pilot.sql) |
| `cn_corporate_actions` | [database/sql/cn/migration_cn_0005_canonical_full_coverage.sql](../../database/sql/cn/migration_cn_0005_canonical_full_coverage.sql) |
| `cn_daily_price_limits` | [database/sql/cn/migration_cn_0005_canonical_full_coverage.sql](../../database/sql/cn/migration_cn_0005_canonical_full_coverage.sql) |
| `cn_execution_cost_profiles` | [database/sql/cn/migration_cn_0008_execution_contract.sql](../../database/sql/cn/migration_cn_0008_execution_contract.sql) |
| `cn_ingestion_runs` | [database/sql/cn/migration_cn_0001_tushare_raw_staging.sql](../../database/sql/cn/migration_cn_0001_tushare_raw_staging.sql) |
| `cn_staging_quality_metrics` | [database/sql/cn/migration_cn_0001_tushare_raw_staging.sql](../../database/sql/cn/migration_cn_0001_tushare_raw_staging.sql) |
| `cn_universe_decisions` | [database/sql/cn/migration_cn_0006_universe_pit.sql](../../database/sql/cn/migration_cn_0006_universe_pit.sql) |
| `cn_universe_execution_audit` | [database/sql/cn/migration_cn_0006_universe_pit.sql](../../database/sql/cn/migration_cn_0006_universe_pit.sql) |
| `cn_universe_runs` | [database/sql/cn/migration_cn_0006_universe_pit.sql](../../database/sql/cn/migration_cn_0006_universe_pit.sql) |
| `execution_broker_fills` | [database/sql/execution/execution_broker_fills.sql](../../database/sql/execution/execution_broker_fills.sql) |
| `execution_broker_orders` | [database/sql/execution/execution_broker_orders.sql](../../database/sql/execution/execution_broker_orders.sql) |
| `execution_events` | [database/sql/execution/execution_events.sql](../../database/sql/execution/execution_events.sql) |
| `execution_locks` | [database/sql/execution/execution_locks.sql](../../database/sql/execution/execution_locks.sql) |
| `execution_order_requests` | [database/sql/execution/execution_order_requests.sql](../../database/sql/execution/execution_order_requests.sql) |
| `execution_position_lots` | [database/sql/execution/execution_position_lots.sql](../../database/sql/execution/execution_position_lots.sql) |
| `execution_positions` | [database/sql/execution/execution_positions.sql](../../database/sql/execution/execution_positions.sql) |
| `execution_reconciliation_results` | [database/sql/execution/execution_reconciliation_results.sql](../../database/sql/execution/execution_reconciliation_results.sql) |
| `execution_runs` | [database/sql/execution/execution_runs.sql](../../database/sql/execution/execution_runs.sql) |
| `execution_targets_snapshot` | [database/sql/execution/execution_targets_snapshot.sql](../../database/sql/execution/execution_targets_snapshot.sql) |
| `fr_canonicalization_runs` | [database/sql/fr/migration_fr_0002_prices.sql](../../database/sql/fr/migration_fr_0002_prices.sql) |
| `fr_corporate_actions` | [database/sql/fr/migration_fr_0002_prices.sql](../../database/sql/fr/migration_fr_0002_prices.sql) |
| `fr_data_anomalies` | [database/sql/fr/migration_fr_0002_prices.sql](../../database/sql/fr/migration_fr_0002_prices.sql) |
| `fr_ingestion_runs` | [database/sql/fr/migration_fr_0001_reference.sql](../../database/sql/fr/migration_fr_0001_reference.sql) |
| `fr_liquidity_runs` | [database/sql/fr/migration_fr_0007_liquidity_research.sql](../../database/sql/fr/migration_fr_0007_liquidity_research.sql) |
| `fr_liquidity_snapshots` | [database/sql/fr/migration_fr_0007_liquidity_research.sql](../../database/sql/fr/migration_fr_0007_liquidity_research.sql) |
| `fr_provider_actions_staging` | [database/sql/fr/migration_fr_0004_provider_staging.sql](../../database/sql/fr/migration_fr_0004_provider_staging.sql) |
| `fr_provider_bars_daily` | [database/sql/fr/migration_fr_0002_prices.sql](../../database/sql/fr/migration_fr_0002_prices.sql) |
| `fr_provider_bars_staging` | [database/sql/fr/migration_fr_0004_provider_staging.sql](../../database/sql/fr/migration_fr_0004_provider_staging.sql) |
| `fr_provider_universe_staging` | [database/sql/fr/migration_fr_0004_provider_staging.sql](../../database/sql/fr/migration_fr_0004_provider_staging.sql) |
| `fr_raw_payloads` | [database/sql/fr/migration_fr_0002_prices.sql](../../database/sql/fr/migration_fr_0002_prices.sql) |
| `fr_reference_runs` | [database/sql/fr/migration_fr_0008_reference_research.sql](../../database/sql/fr/migration_fr_0008_reference_research.sql) |
| `fr_research_benchmark_constituents` | [database/sql/fr/migration_fr_0008_reference_research.sql](../../database/sql/fr/migration_fr_0008_reference_research.sql) |
| `fr_research_benchmark_daily` | [database/sql/fr/migration_fr_0008_reference_research.sql](../../database/sql/fr/migration_fr_0008_reference_research.sql) |
| `fr_research_identities` | [database/sql/fr/migration_fr_0008_reference_research.sql](../../database/sql/fr/migration_fr_0008_reference_research.sql) |
| `fr_research_sector_memberships` | [database/sql/fr/migration_fr_0008_reference_research.sql](../../database/sql/fr/migration_fr_0008_reference_research.sql) |
| `fr_source_versions` | [database/sql/fr/migration_fr_0002_prices.sql](../../database/sql/fr/migration_fr_0002_prices.sql) |
| `fr_staging_progress` | [database/sql/fr/migration_fr_0004_provider_staging.sql](../../database/sql/fr/migration_fr_0004_provider_staging.sql) |
| `fr_universe_decisions` | [database/sql/fr/migration_fr_0006_universe_contract.sql](../../database/sql/fr/migration_fr_0006_universe_contract.sql) |
| `fr_universe_runs` | [database/sql/fr/migration_fr_0006_universe_contract.sql](../../database/sql/fr/migration_fr_0006_universe_contract.sql) |
| `instrument_adjustment_factors` | [database/sql/cn/migration_cn_0004_canonical_market_pilot.sql](../../database/sql/cn/migration_cn_0004_canonical_market_pilot.sql) |
| `instrument_listings` | [database/sql/fr/migration_fr_0001_reference.sql](../../database/sql/fr/migration_fr_0001_reference.sql) |
| `instrument_provider_symbols` | [database/sql/cn/migration_cn_0004_canonical_market_pilot.sql](../../database/sql/cn/migration_cn_0004_canonical_market_pilot.sql), [database/sql/fr/migration_fr_0001_reference.sql](../../database/sql/fr/migration_fr_0001_reference.sql), [database/sql/market/instrument_provider_symbols.sql](../../database/sql/market/instrument_provider_symbols.sql) |
| `instrument_status_history` | [database/sql/cn/migration_cn_0004_canonical_market_pilot.sql](../../database/sql/cn/migration_cn_0004_canonical_market_pilot.sql), [database/sql/fr/migration_fr_0001_reference.sql](../../database/sql/fr/migration_fr_0001_reference.sql), [database/sql/market/instrument_status_history.sql](../../database/sql/market/instrument_status_history.sql) |
| `instruments` | [database/sql/cn/migration_cn_0004_canonical_market_pilot.sql](../../database/sql/cn/migration_cn_0004_canonical_market_pilot.sql), [database/sql/fr/migration_fr_0001_reference.sql](../../database/sql/fr/migration_fr_0001_reference.sql), [database/sql/market/instruments.sql](../../database/sql/market/instruments.sql) |
| `llm_directional_assessments` | [database/sql/ml/llm_directional_filter.sql](../../database/sql/ml/llm_directional_filter.sql) |
| `llm_directional_evaluations` | [database/sql/ml/llm_directional_filter.sql](../../database/sql/ml/llm_directional_filter.sql) |
| `llm_directional_runs` | [database/sql/ml/llm_directional_filter.sql](../../database/sql/ml/llm_directional_filter.sql) |
| `market_execution_rules` | [database/sql/cn/migration_cn_0008_execution_contract.sql](../../database/sql/cn/migration_cn_0008_execution_contract.sql), [database/sql/market/market_execution_rules.sql](../../database/sql/market/market_execution_rules.sql) |
| `market_sessions` | [database/sql/cn/migration_cn_0004_canonical_market_pilot.sql](../../database/sql/cn/migration_cn_0004_canonical_market_pilot.sql), [database/sql/fr/migration_fr_0001_reference.sql](../../database/sql/fr/migration_fr_0001_reference.sql), [database/sql/market/market_sessions.sql](../../database/sql/market/market_sessions.sql) |
| `markets` | [database/sql/cn/migration_cn_0004_canonical_market_pilot.sql](../../database/sql/cn/migration_cn_0004_canonical_market_pilot.sql), [database/sql/fr/migration_fr_0001_reference.sql](../../database/sql/fr/migration_fr_0001_reference.sql), [database/sql/market/markets.sql](../../database/sql/market/markets.sql) |
| `model_directional_oos_metrics` | [database/sql/ml/model_directional_oos_metrics.sql](../../database/sql/ml/model_directional_oos_metrics.sql) |
| `model_serving_batch` | [database/sql/ml/model_serving_batch.sql](../../database/sql/ml/model_serving_batch.sql) |
| `portfolio_targets` | [database/sql/risk/portfolio_targets.sql](../../database/sql/risk/portfolio_targets.sql) |
| `risk_decisions` | [database/sql/risk/risk_decisions.sql](../../database/sql/risk/risk_decisions.sql) |
| `run_business_summaries` | [database/sql/run_business_summaries.sql](../../database/sql/run_business_summaries.sql) |
| `run_summaries` | [database/sql/run_summaries.sql](../../database/sql/run_summaries.sql) |
| `stock_analyst_eps_revision_history` | [database/sql/stock/stock_analyst_eps_revision_history.sql](../../database/sql/stock/stock_analyst_eps_revision_history.sql) |
| `stock_analyst_eps_trend_history` | [database/sql/stock/stock_analyst_eps_trend_history.sql](../../database/sql/stock/stock_analyst_eps_trend_history.sql) |
| `stock_analyst_estimate_history` | [database/sql/stock/stock_analyst_estimate_history.sql](../../database/sql/stock/stock_analyst_estimate_history.sql) |
| `stock_analyst_recommendation_history` | [database/sql/stock/stock_analyst_recommendation_history.sql](../../database/sql/stock/stock_analyst_recommendation_history.sql) |
| `stock_analyst_target_history` | [database/sql/stock/stock_analyst_target_history.sql](../../database/sql/stock/stock_analyst_target_history.sql) |
| `stock_bars_daily` | [database/sql/cn/migration_cn_0004_canonical_market_pilot.sql](../../database/sql/cn/migration_cn_0004_canonical_market_pilot.sql), [database/sql/fr/migration_fr_0002_prices.sql](../../database/sql/fr/migration_fr_0002_prices.sql) |
| `tushare_raw_payloads` | [database/sql/cn/migration_cn_0001_tushare_raw_staging.sql](../../database/sql/cn/migration_cn_0001_tushare_raw_staging.sql) |
| `tushare_staging_rows` | [database/sql/cn/migration_cn_0001_tushare_raw_staging.sql](../../database/sql/cn/migration_cn_0001_tushare_raw_staging.sql) |
| `watcher_heartbeats` | [database/sql/execution/watcher_heartbeats.sql](../../database/sql/execution/watcher_heartbeats.sql) |
