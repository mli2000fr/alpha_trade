# Inventaire API — alembic

Extraction AST du 2026-10-10 ; aucune importation ni exécution métier.

Classes, fonctions de module et méthodes déclarées ; fonctions imbriquées exclues.
Les symboles `_...` sont internes. Signature présente ≠ API publique stable.

## `alembic/env.py`

Source SHA-256 : `cac2992f60f09d2500ad402808e959191a446537797e9abed8535ffce0f2a3d1`

- [run_migrations_offline](../../alembic/env.py) — ligne 25 : `def run_migrations_offline()`
- [run_migrations_online](../../alembic/env.py) — ligne 33 : `def run_migrations_online()`

## `alembic/versions/0001_initial.py`

Source SHA-256 : `785ea15266dae2ca62d6e4921697f96327667edd1b3d3e67d8aef90731ef3b6a`

- [upgrade](../../alembic/versions/0001_initial.py) — ligne 17 : `def upgrade()`
- [downgrade](../../alembic/versions/0001_initial.py) — ligne 20 : `def downgrade()`

## `alembic/versions/0002_add_account_id.py`

Source SHA-256 : `15e90dbabc696d91b9790b5a4d32f1ffe6b65aca0844f334d0fcd2761ef9691c`

- [upgrade](../../alembic/versions/0002_add_account_id.py) — ligne 24 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0002_add_account_id.py) — ligne 33 : `def downgrade() -> None`

## `alembic/versions/0003_news_checkpoint_per_symbol.py`

Source SHA-256 : `c69d4e59ee5b1b0189f0fb2d34444352e830e3937cadadf9df1afbd721bbbaa4`

- [upgrade](../../alembic/versions/0003_news_checkpoint_per_symbol.py) — ligne 19 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0003_news_checkpoint_per_symbol.py) — ligne 28 : `def downgrade() -> None`

## `alembic/versions/0004_add_selector_reference_data.py`

Source SHA-256 : `04e97ac206ed8ce970e762cf3632c5ddc822c2f5268db9999ba6b1cfcb8ef2b1`

- [upgrade](../../alembic/versions/0004_add_selector_reference_data.py) — ligne 16 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0004_add_selector_reference_data.py) — ligne 59 : `def downgrade() -> None`

## `alembic/versions/0005_add_model_predictions_audit_fields.py`

Source SHA-256 : `0bb7748999939d348285fd5a95e35b455bcc393746a6ddd58fd94057f3689342`

- [upgrade](../../alembic/versions/0005_add_model_predictions_audit_fields.py) — ligne 16 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0005_add_model_predictions_audit_fields.py) — ligne 24 : `def downgrade() -> None`

## `alembic/versions/0006_add_model_governance_table.py`

Source SHA-256 : `90cde285920700053ed1a245ee34e6b79b4be31b9386121c98a871baaf04e234`

- [upgrade](../../alembic/versions/0006_add_model_governance_table.py) — ligne 16 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0006_add_model_governance_table.py) — ligne 57 : `def downgrade() -> None`

## `alembic/versions/0007_add_run_business_summaries_table.py`

Source SHA-256 : `012455dc12c946dde81282ee37719d8f95668a067d8922bd1607fb92660e76d8`

- [upgrade](../../alembic/versions/0007_add_run_business_summaries_table.py) — ligne 11 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0007_add_run_business_summaries_table.py) — ligne 34 : `def downgrade() -> None`

## `alembic/versions/0008_add_execution_sprint1_foundations.py`

Source SHA-256 : `d9295974c2ec0b7997b54de8009611bd0e098a6aa191b4f88298d46e42646887`

- [upgrade](../../alembic/versions/0008_add_execution_sprint1_foundations.py) — ligne 15 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0008_add_execution_sprint1_foundations.py) — ligne 67 : `def downgrade() -> None`

## `alembic/versions/0009_add_execution_sprint2_persistence.py`

Source SHA-256 : `5552a71f62e50949dabe8c691acb7205ff46e1de48db79c13ac774522a3da27a`

- [upgrade](../../alembic/versions/0009_add_execution_sprint2_persistence.py) — ligne 15 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0009_add_execution_sprint2_persistence.py) — ligne 118 : `def downgrade() -> None`

## `alembic/versions/0010_add_execution_sprint4_positions.py`

Source SHA-256 : `690eb384fefae85443967641946796da559ec012042c50d0ac027e73258c9bae`

- [upgrade](../../alembic/versions/0010_add_execution_sprint4_positions.py) — ligne 15 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0010_add_execution_sprint4_positions.py) — ligne 64 : `def downgrade() -> None`

## `alembic/versions/0011_add_execution_sprint5_reconciliation.py`

Source SHA-256 : `f67f3a3e855db4a095111d1c4364d9395a4887986e2b5ba2080a691fc58dd2df`

- [upgrade](../../alembic/versions/0011_add_execution_sprint5_reconciliation.py) — ligne 15 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0011_add_execution_sprint5_reconciliation.py) — ligne 43 : `def downgrade() -> None`

## `alembic/versions/0012_market_data_provenance_and_check.py`

Source SHA-256 : `c395442c2215f86e5c179803cdb1447187f7059d4a8bd7ff5b2cfdd225f0bf1b`

- [_has_column](../../alembic/versions/0012_market_data_provenance_and_check.py) — ligne 28 : `def _has_column(bind, table: str, column: str) -> bool`
- [upgrade](../../alembic/versions/0012_market_data_provenance_and_check.py) — ligne 35 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0012_market_data_provenance_and_check.py) — ligne 121 : `def downgrade() -> None`

## `alembic/versions/0013_watcher_heartbeats.py`

Source SHA-256 : `3757ddaccf97d728e335bd39e3498850a39af7b11892ece561cf2e91c575e31d`

- [upgrade](../../alembic/versions/0013_watcher_heartbeats.py) — ligne 30 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0013_watcher_heartbeats.py) — ligne 50 : `def downgrade() -> None`

## `alembic/versions/0014_cleaning_audit_quotes_earnings_runs.py`

Source SHA-256 : `44709b4a513e7d71146dc0dfe4898b53a2f2b0df473fcb04ddbf2ad322f75cf3`

- [_create_audit_table](../../alembic/versions/0014_cleaning_audit_quotes_earnings_runs.py) — ligne 30 : `def _create_audit_table(table_name: str) -> None`
- [upgrade](../../alembic/versions/0014_cleaning_audit_quotes_earnings_runs.py) — ligne 73 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0014_cleaning_audit_quotes_earnings_runs.py) — ligne 78 : `def downgrade() -> None`

## `alembic/versions/0015_finbert_model_fingerprint.py`

Source SHA-256 : `bd0d2a2530a96829de092b2d6717a47dcddc83c83bf31cb2864490ea0f11937c`

- [upgrade](../../alembic/versions/0015_finbert_model_fingerprint.py) — ligne 24 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0015_finbert_model_fingerprint.py) — ligne 41 : `def downgrade() -> None`

## `alembic/versions/0016_model_metrics_full_blob.py`

Source SHA-256 : `0ada32f9816e82f2ce2b4fc37383dca6e93bdff285628458a8b70a40ea5d1d9f`

- [upgrade](../../alembic/versions/0016_model_metrics_full_blob.py) — ligne 25 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0016_model_metrics_full_blob.py) — ligne 50 : `def downgrade() -> None`

## `alembic/versions/0017_execution_kill_switch_runs.py`

Source SHA-256 : `dc199ab92efe49ac7b55a9860eb51c96b5e7132fd0a3585e77034afa65680fec`

- [upgrade](../../alembic/versions/0017_execution_kill_switch_runs.py) — ligne 23 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0017_execution_kill_switch_runs.py) — ligne 56 : `def downgrade() -> None`

## `alembic/versions/0018_corporate_actions_audit_runs.py`

Source SHA-256 : `9b8eef40034ace9dbf67e81602a12805d581eeed5b7b8b3d83e71df88df50fc6`

- [upgrade](../../alembic/versions/0018_corporate_actions_audit_runs.py) — ligne 23 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0018_corporate_actions_audit_runs.py) — ligne 77 : `def downgrade() -> None`

## `alembic/versions/0019_corporate_actions_account_idempotency.py`

Source SHA-256 : `a6a9e065602bc7330795ac01bcaff256ceda4fbd9ef3f02cc6124060541c5929`

- [upgrade](../../alembic/versions/0019_corporate_actions_account_idempotency.py) — ligne 30 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0019_corporate_actions_account_idempotency.py) — ligne 59 : `def downgrade() -> None`

## `alembic/versions/0020_weights_calibration_runs.py`

Source SHA-256 : `2673a505c14d6eeee31eafea37daea519bec62d041803b1b1f427f0632433296`

- [upgrade](../../alembic/versions/0020_weights_calibration_runs.py) — ligne 22 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0020_weights_calibration_runs.py) — ligne 45 : `def downgrade() -> None`

## `alembic/versions/0021_ml_drift_runs.py`

Source SHA-256 : `742bafe6a318ca9fe6b64a96870a512887eae56c1589a7c8d926ce3b9b4e2ab3`

- [upgrade](../../alembic/versions/0021_ml_drift_runs.py) — ligne 22 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0021_ml_drift_runs.py) — ligne 41 : `def downgrade() -> None`

## `alembic/versions/0022_shadow_drift_runs.py`

Source SHA-256 : `a4ad90cf97066bf801eb22950a50c76647a7a1efab662ef5f920a94cf226913f`

- [upgrade](../../alembic/versions/0022_shadow_drift_runs.py) — ligne 23 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0022_shadow_drift_runs.py) — ligne 41 : `def downgrade() -> None`

## `alembic/versions/0023_stock_scores_history_capital_preset.py`

Source SHA-256 : `de273a84a15fff8093bb5e49823526fdd29002105639022d178a623c2a1141bb`

- [_has_column](../../alembic/versions/0023_stock_scores_history_capital_preset.py) — ligne 21 : `def _has_column(bind, table: str, column: str) -> bool`
- [_has_index](../../alembic/versions/0023_stock_scores_history_capital_preset.py) — ligne 28 : `def _has_index(bind, table: str, index_name: str) -> bool`
- [_has_unique](../../alembic/versions/0023_stock_scores_history_capital_preset.py) — ligne 35 : `def _has_unique(bind, table: str, constraint_name: str) -> bool`
- [upgrade](../../alembic/versions/0023_stock_scores_history_capital_preset.py) — ligne 42 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0023_stock_scores_history_capital_preset.py) — ligne 84 : `def downgrade() -> None`

## `alembic/versions/0024_audit_chain.py`

Source SHA-256 : `ebdc103ea41e82a9cb92054db934a09faed2232ff655bb689f021fffb25aa7d3`

- [upgrade](../../alembic/versions/0024_audit_chain.py) — ligne 23 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0024_audit_chain.py) — ligne 73 : `def downgrade() -> None`

## `alembic/versions/0025_broker_statements.py`

Source SHA-256 : `a6b19c5e151265ac7592e6bcdccd238f0c39ff2d559bc1cbdda675d994889508`

- [upgrade](../../alembic/versions/0025_broker_statements.py) — ligne 19 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0025_broker_statements.py) — ligne 52 : `def downgrade() -> None`

## `alembic/versions/0026_champion_history.py`

Source SHA-256 : `ecf57f94a1bc77d460f7e6b66f69a3e30e052463fd8451b3469652d75217838e`

- [upgrade](../../alembic/versions/0026_champion_history.py) — ligne 20 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0026_champion_history.py) — ligne 61 : `def downgrade() -> None`

## `alembic/versions/0027_news_ticker_map_relevance.py`

Source SHA-256 : `d96ce889bdda9322b4e30153581302a3bdb5c72ee94e737c7182b1dffb28da5b`

- [upgrade](../../alembic/versions/0027_news_ticker_map_relevance.py) — ligne 31 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0027_news_ticker_map_relevance.py) — ligne 57 : `def downgrade() -> None`

## `alembic/versions/0028_news_ticker_sentiment.py`

Source SHA-256 : `b29f41e4bbd0084662cfa40ce754bf7fda8832b124ce0bfbc76604f8a1aa5d05`

- [upgrade](../../alembic/versions/0028_news_ticker_sentiment.py) — ligne 27 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0028_news_ticker_sentiment.py) — ligne 102 : `def downgrade() -> None`

## `alembic/versions/0029_selector_explainability_persistence.py`

Source SHA-256 : `ce584c8c4d56c086d4b272463028cc7bf8c9e1347c9edebce15a78eb87153ee0`

- [_has_table](../../alembic/versions/0029_selector_explainability_persistence.py) — ligne 38 : `def _has_table(bind, table: str) -> bool`
- [_has_column](../../alembic/versions/0029_selector_explainability_persistence.py) — ligne 42 : `def _has_column(bind, table: str, column: str) -> bool`
- [upgrade](../../alembic/versions/0029_selector_explainability_persistence.py) — ligne 49 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0029_selector_explainability_persistence.py) — ligne 59 : `def downgrade() -> None`

## `alembic/versions/0030_weights_calibration_runs_add_risk_scope.py`

Source SHA-256 : `5c72003d375db54adb49efb29e7ea86cfd9f34af5fb06952baa8f5f232e8c22b`

- [upgrade](../../alembic/versions/0030_weights_calibration_runs_add_risk_scope.py) — ligne 15 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0030_weights_calibration_runs_add_risk_scope.py) — ligne 24 : `def downgrade() -> None`

## `alembic/versions/0031_weights_calibration_runs_regime_segmentation.py`

Source SHA-256 : `bc46d8b392225cce1a3f6fe5b87322481bfe5f00580bec09af1003c9a73977fc`

- [upgrade](../../alembic/versions/0031_weights_calibration_runs_regime_segmentation.py) — ligne 16 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0031_weights_calibration_runs_regime_segmentation.py) — ligne 43 : `def downgrade() -> None`

## `alembic/versions/0032_weights_calibration_multi_segment_governance.py`

Source SHA-256 : `8821e4f6f891ef3eb68a453c687d88bdcd3f4a47313cb01a51242280c96dbec6`

- [upgrade](../../alembic/versions/0032_weights_calibration_multi_segment_governance.py) — ligne 17 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0032_weights_calibration_multi_segment_governance.py) — ligne 73 : `def downgrade() -> None`

## `alembic/versions/0033_news_checkpoint_stage_timestamps.py`

Source SHA-256 : `4964c080749c2b6b30c51163616bcaf5175dbc56b95647b906510264f2979022`

- [upgrade](../../alembic/versions/0033_news_checkpoint_stage_timestamps.py) — ligne 26 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0033_news_checkpoint_stage_timestamps.py) — ligne 32 : `def downgrade() -> None`

## `alembic/versions/0034_add_stock_macro_indicators_daily.py`

Source SHA-256 : `25190bf535357e7b21700fdd4ab7caa3a649b5bd1d332df72f29b2ecc1011b65`

- [upgrade](../../alembic/versions/0034_add_stock_macro_indicators_daily.py) — ligne 20 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0034_add_stock_macro_indicators_daily.py) — ligne 46 : `def downgrade() -> None`

## `alembic/versions/0035_drop_equity_simulated.py`

Source SHA-256 : `e5923accaa2be9037e0c47197702d8aae046d20d040a27fb7d0dadc7ed7356ef`

- [upgrade](../../alembic/versions/0035_drop_equity_simulated.py) — ligne 19 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0035_drop_equity_simulated.py) — ligne 23 : `def downgrade() -> None`

## `alembic/versions/0036_expand_sizing_method_column.py`

Source SHA-256 : `c00eb42bf04858fca91d40e0ad6b174ff3832040d5a309b498f40d2fbd639f3b`

- [upgrade](../../alembic/versions/0036_expand_sizing_method_column.py) — ligne 16 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0036_expand_sizing_method_column.py) — ligne 39 : `def downgrade() -> None`

## `alembic/versions/0037_add_fractionable_and_fractional_target_shares.py`

Source SHA-256 : `bf530b72dcd5a795ff7f871eb8355ec12ae4c3cbda3a79f543d3c08b50eec030`

- [_has_table](../../alembic/versions/0037_add_fractionable_and_fractional_target_shares.py) — ligne 19 : `def _has_table(table_name: str) -> bool`
- [_has_column](../../alembic/versions/0037_add_fractionable_and_fractional_target_shares.py) — ligne 25 : `def _has_column(table_name: str, column_name: str) -> bool`
- [upgrade](../../alembic/versions/0037_add_fractionable_and_fractional_target_shares.py) — ligne 31 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0037_add_fractionable_and_fractional_target_shares.py) — ligne 49 : `def downgrade() -> None`

## `alembic/versions/0038_add_model_predictions_ternary.py`

Source SHA-256 : `440f8e536b8214ef1f68b451b58812339cf66f431e8afacc3cf59048dfb4afbf`

- [_has_table](../../alembic/versions/0038_add_model_predictions_ternary.py) — ligne 19 : `def _has_table(table_name: str) -> bool`
- [_has_column](../../alembic/versions/0038_add_model_predictions_ternary.py) — ligne 25 : `def _has_column(table_name: str, column_name: str) -> bool`
- [upgrade](../../alembic/versions/0038_add_model_predictions_ternary.py) — ligne 31 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0038_add_model_predictions_ternary.py) — ligne 67 : `def downgrade() -> None`

## `alembic/versions/0039_add_model_metrics_ternary.py`

Source SHA-256 : `a21ba19288175a8a22867be4d83d416762597e9c9094ee6a442dfc02d91dac2b`

- [_has_table](../../alembic/versions/0039_add_model_metrics_ternary.py) — ligne 19 : `def _has_table(table_name: str) -> bool`
- [_has_column](../../alembic/versions/0039_add_model_metrics_ternary.py) — ligne 25 : `def _has_column(table_name: str, column_name: str) -> bool`
- [upgrade](../../alembic/versions/0039_add_model_metrics_ternary.py) — ligne 31 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0039_add_model_metrics_ternary.py) — ligne 53 : `def downgrade() -> None`

## `alembic/versions/0040_optimize_stock_bars_indexes.py`

Source SHA-256 : `f25d8373f2bc138a2bd5a7828bcfdbb565d7a4d0f017f0ba01d73a76452329c8`

- [_index_exists](../../alembic/versions/0040_optimize_stock_bars_indexes.py) — ligne 25 : `def _index_exists(bind, table: str, index: str) -> bool`
- [upgrade](../../alembic/versions/0040_optimize_stock_bars_indexes.py) — ligne 33 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0040_optimize_stock_bars_indexes.py) — ligne 52 : `def downgrade() -> None`

## `alembic/versions/0041_add_short_score_to_history.py`

Source SHA-256 : `9c84caaefc77d9f14cd651aa290280cf2c27a9b5a78410b39b7e7cd2b260c2ef`

- [_has_column](../../alembic/versions/0041_add_short_score_to_history.py) — ligne 19 : `def _has_column(bind, table: str, column: str) -> bool`
- [upgrade](../../alembic/versions/0041_add_short_score_to_history.py) — ligne 26 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0041_add_short_score_to_history.py) — ligne 44 : `def downgrade() -> None`

## `alembic/versions/0042_add_sma_to_history.py`

Source SHA-256 : `cf88dcbe8a20225e35752fb0681c8026987def69c8ce8be6c80637fd4fbf2a62`

- [_has_column](../../alembic/versions/0042_add_sma_to_history.py) — ligne 19 : `def _has_column(bind, table: str, column: str) -> bool`
- [upgrade](../../alembic/versions/0042_add_sma_to_history.py) — ligne 26 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0042_add_sma_to_history.py) — ligne 54 : `def downgrade() -> None`

## `alembic/versions/0043_add_vxn_vix3m_move_rvx.py`

Source SHA-256 : `12e2a3f55380bd08c4e3d490cd1de9247dab3fd5003729adb1b0c68ce399508b`

- [_has_column](../../alembic/versions/0043_add_vxn_vix3m_move_rvx.py) — ligne 29 : `def _has_column(bind, table: str, column: str) -> bool`
- [upgrade](../../alembic/versions/0043_add_vxn_vix3m_move_rvx.py) — ligne 36 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0043_add_vxn_vix3m_move_rvx.py) — ligne 58 : `def downgrade() -> None`

## `alembic/versions/0044_add_model_metrics_model_name.py`

Source SHA-256 : `674185f33f1be24d70433bd9b3c11ad29516b4d58a5f64f006a15e6edcfa2737`

- [_has_table](../../alembic/versions/0044_add_model_metrics_model_name.py) — ligne 19 : `def _has_table(table_name: str) -> bool`
- [_has_column](../../alembic/versions/0044_add_model_metrics_model_name.py) — ligne 25 : `def _has_column(table_name: str, column_name: str) -> bool`
- [_has_index](../../alembic/versions/0044_add_model_metrics_model_name.py) — ligne 31 : `def _has_index(table_name: str, index_name: str) -> bool`
- [upgrade](../../alembic/versions/0044_add_model_metrics_model_name.py) — ligne 37 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0044_add_model_metrics_model_name.py) — ligne 54 : `def downgrade() -> None`

## `alembic/versions/0045_add_model_training_run_data_dates.py`

Source SHA-256 : `66c51e8d288e0d1cb75415551032e5f0f28c1d67975f37aa572e0ee1eb743015`

- [_has_table](../../alembic/versions/0045_add_model_training_run_data_dates.py) — ligne 20 : `def _has_table(table_name: str) -> bool`
- [_has_column](../../alembic/versions/0045_add_model_training_run_data_dates.py) — ligne 26 : `def _has_column(table_name: str, column_name: str) -> bool`
- [upgrade](../../alembic/versions/0045_add_model_training_run_data_dates.py) — ligne 32 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0045_add_model_training_run_data_dates.py) — ligne 46 : `def downgrade() -> None`

## `alembic/versions/0046_add_tradable_universe_history.py`

Source SHA-256 : `1bfbc3dd3addd836af35b022926f7796daf530b9e97975e1d0080a384fbc2378`

- [upgrade](../../alembic/versions/0046_add_tradable_universe_history.py) — ligne 18 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0046_add_tradable_universe_history.py) — ligne 80 : `def downgrade() -> None`

## `alembic/versions/0047_add_selection_rank_to_risk_execution.py`

Source SHA-256 : `c089726b257b3c05e338c9d98a1d0707df7fdde0677dfbb278138cb34ae55ed9`

- [upgrade](../../alembic/versions/0047_add_selection_rank_to_risk_execution.py) — ligne 21 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0047_add_selection_rank_to_risk_execution.py) — ligne 41 : `def downgrade() -> None`

## `alembic/versions/0048_add_model_directional_oos_metrics.py`

Source SHA-256 : `e5341c84809215f79dee3dc8e286bb7a132708b3fac599de9a314435b7376027`

- [upgrade](../../alembic/versions/0048_add_model_directional_oos_metrics.py) — ligne 18 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0048_add_model_directional_oos_metrics.py) — ligne 50 : `def downgrade() -> None`

## `alembic/versions/0048_drop_candidate_columns_from_score_snapshots.py`

Source SHA-256 : `50c148d33c30c819b5428e9d0815a8e234702beb821ce27430a7fafa95af676c`

- [upgrade](../../alembic/versions/0048_drop_candidate_columns_from_score_snapshots.py) — ligne 21 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0048_drop_candidate_columns_from_score_snapshots.py) — ligne 68 : `def downgrade() -> None`

## `alembic/versions/0049_add_model_training_run_batch_id.py`

Source SHA-256 : `5caa5bef85d46fc809333c0a476a25e91e916e8481ec4603acc535d666d416c2`

- [upgrade](../../alembic/versions/0049_add_model_training_run_batch_id.py) — ligne 21 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0049_add_model_training_run_batch_id.py) — ligne 44 : `def downgrade() -> None`

## `alembic/versions/0050_add_model_training_batch.py`

Source SHA-256 : `c254a6f2d70c89ccf16923c04fb0399f6717473f930cb95dfc15c7cbc579800b`

- [upgrade](../../alembic/versions/0050_add_model_training_batch.py) — ligne 18 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0050_add_model_training_batch.py) — ligne 50 : `def downgrade() -> None`

## `alembic/versions/0051_add_comment_to_model_training_batch.py`

Source SHA-256 : `60846a8e219120ae44639ebef30063deb784423cc3a82ad49625958e5d473143`

- [upgrade](../../alembic/versions/0051_add_comment_to_model_training_batch.py) — ligne 18 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0051_add_comment_to_model_training_batch.py) — ligne 34 : `def downgrade() -> None`

## `alembic/versions/0052_add_model_metrics_pct_columns.py`

Source SHA-256 : `1f4c95e695eee3afcf849d78e5b90feb2919e51e8708869837bbcfdf21945641`

- [upgrade](../../alembic/versions/0052_add_model_metrics_pct_columns.py) — ligne 18 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0052_add_model_metrics_pct_columns.py) — ligne 43 : `def downgrade() -> None`

## `alembic/versions/0053_add_model_serving_batch.py`

Source SHA-256 : `6cc5024634dc2b3664b49274dcf9f0c4f8124fceb2c84e85e7abbe3e754698af`

- [upgrade](../../alembic/versions/0053_add_model_serving_batch.py) — ligne 18 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0053_add_model_serving_batch.py) — ligne 33 : `def downgrade() -> None`

## `alembic/versions/0054_add_model_batch_diagnostics.py`

Source SHA-256 : `5b565b7a51b19b58044bcb4ef945f01c758b2630d5d98ecf24335ca5627231c4`

- [upgrade](../../alembic/versions/0054_add_model_batch_diagnostics.py) — ligne 18 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0054_add_model_batch_diagnostics.py) — ligne 57 : `def downgrade() -> None`

## `alembic/versions/0055_add_stock_fundamentals_daily.py`

Source SHA-256 : `e91292508ad3c93f0005941d4c4cc20bbfa8579da07abd15762a2d77783c27dd`

- [upgrade](../../alembic/versions/0055_add_stock_fundamentals_daily.py) — ligne 18 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0055_add_stock_fundamentals_daily.py) — ligne 110 : `def downgrade() -> None`

## `alembic/versions/0056_add_ic_rank_to_training_batch.py`

Source SHA-256 : `d4aafe8dffe3bdd7a9d6e867f3a43b5d049ffafffc516e4ef825c44a4b7fc275`

- [upgrade](../../alembic/versions/0056_add_ic_rank_to_training_batch.py) — ligne 20 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0056_add_ic_rank_to_training_batch.py) — ligne 33 : `def downgrade() -> None`

## `alembic/versions/0057_add_decile_spreads_to_training_batch.py`

Source SHA-256 : `a8f80089f0f1557cc53daa9bc638786684f09ff08588f5086b28f79b197199c1`

- [upgrade](../../alembic/versions/0057_add_decile_spreads_to_training_batch.py) — ligne 18 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0057_add_decile_spreads_to_training_batch.py) — ligne 43 : `def downgrade() -> None`

## `alembic/versions/0058_add_global_rank_history.py`

Source SHA-256 : `0b4958d22000faac21c87bde1c5e0479bf56d541b7dd6011e0e19a3426c09bd5`

- [upgrade](../../alembic/versions/0058_add_global_rank_history.py) — ligne 23 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0058_add_global_rank_history.py) — ligne 53 : `def downgrade() -> None`

## `alembic/versions/0059_add_stacking_enabled_to_training_batch.py`

Source SHA-256 : `59c7f722eca9c71f7c9579acd3030a515436896bf789fc98fdd9deb1be258faf`

- [upgrade](../../alembic/versions/0059_add_stacking_enabled_to_training_batch.py) — ligne 23 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0059_add_stacking_enabled_to_training_batch.py) — ligne 37 : `def downgrade() -> None`

## `alembic/versions/0060_add_shares_outstanding_to_fundamentals.py`

Source SHA-256 : `0080c6b69fedf5f528dc4c59628e5973f41cb6ab4ff4741a366c12ae4842c65a`

- [upgrade](../../alembic/versions/0060_add_shares_outstanding_to_fundamentals.py) — ligne 18 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0060_add_shares_outstanding_to_fundamentals.py) — ligne 48 : `def downgrade() -> None`

## `alembic/versions/0061_widen_symbol_columns_for_sector_names.py`

Source SHA-256 : `e787d1e9c2c5f5fe8f5874794af4f82c0e084fcc096b0416d1cca4d5434f9def`

- [upgrade](../../alembic/versions/0061_widen_symbol_columns_for_sector_names.py) — ligne 28 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0061_widen_symbol_columns_for_sector_names.py) — ligne 35 : `def downgrade() -> None`

## `alembic/versions/0062_add_horizon_to_model_metrics.py`

Source SHA-256 : `71e87de680c4aee5e67047dd03437a6a3ba6d2b228b2b941a56f7d45996dc55b`

- [upgrade](../../alembic/versions/0062_add_horizon_to_model_metrics.py) — ligne 18 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0062_add_horizon_to_model_metrics.py) — ligne 40 : `def downgrade() -> None`

## `alembic/versions/0063_add_symbols_to_training_batch.py`

Source SHA-256 : `0d8a1c48646244c173b4d946beb67a8bf55b23f9ff91ff9082e110a662f5df3e`

- [upgrade](../../alembic/versions/0063_add_symbols_to_training_batch.py) — ligne 18 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0063_add_symbols_to_training_batch.py) — ligne 30 : `def downgrade() -> None`

## `alembic/versions/0064_add_global_oracle_labels.py`

Source SHA-256 : `103855062544f1b155a3a83c63ba1fb8ef6e757628d30cde064d1c508f8e2d76`

- [upgrade](../../alembic/versions/0064_add_global_oracle_labels.py) — ligne 26 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0064_add_global_oracle_labels.py) — ligne 64 : `def downgrade() -> None`

## `alembic/versions/0065_oracle_extreme_rename.py`

Source SHA-256 : `e6639677ef0140640f04d6d778b7d468034907f9b8b0749eca54821f23e74bb0`

- [_has_column](../../alembic/versions/0065_oracle_extreme_rename.py) — ligne 32 : `def _has_column(bind, table: str, column: str) -> bool`
- [upgrade](../../alembic/versions/0065_oracle_extreme_rename.py) — ligne 39 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0065_oracle_extreme_rename.py) — ligne 77 : `def downgrade() -> None`

## `alembic/versions/0066_add_model_predictions_run_id_index.py`

Source SHA-256 : `f23273c30260a52a0a5619a1d5c89689b63cd831aa2735c8eac058b49405e6ce`

- [_has_index](../../alembic/versions/0066_add_model_predictions_run_id_index.py) — ligne 28 : `def _has_index(bind, index: str) -> bool`
- [upgrade](../../alembic/versions/0066_add_model_predictions_run_id_index.py) — ligne 38 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0066_add_model_predictions_run_id_index.py) — ligne 51 : `def downgrade() -> None`

## `alembic/versions/0067_add_model_predictions_source.py`

Source SHA-256 : `23811ea3d18e77f9274526818b99901e4c2ccb24e8b4c02f8a7d633762a811d2`

- [_has_table](../../alembic/versions/0067_add_model_predictions_source.py) — ligne 37 : `def _has_table(bind, schema: str, table: str) -> bool`
- [_has_column](../../alembic/versions/0067_add_model_predictions_source.py) — ligne 44 : `def _has_column(bind, schema: str, table: str, column: str) -> bool`
- [_has_index](../../alembic/versions/0067_add_model_predictions_source.py) — ligne 53 : `def _has_index(bind, schema: str, table: str, index: str) -> bool`
- [upgrade](../../alembic/versions/0067_add_model_predictions_source.py) — ligne 62 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0067_add_model_predictions_source.py) — ligne 86 : `def downgrade() -> None`

## `alembic/versions/0068_analyst_snapshot_collection.py`

Source SHA-256 : `17f70f953cf5268ad9c8bffab6f816e934aeba30013c46e5655ae5314a95c13e`

- [_has_table](../../alembic/versions/0068_analyst_snapshot_collection.py) — ligne 45 : `def _has_table(bind, table: str) -> bool`
- [_create_estimate_history](../../alembic/versions/0068_analyst_snapshot_collection.py) — ligne 49 : `def _create_estimate_history(op_) -> None`
- [_create_target_history](../../alembic/versions/0068_analyst_snapshot_collection.py) — ligne 99 : `def _create_target_history(op_) -> None`
- [_create_recommendation_history](../../alembic/versions/0068_analyst_snapshot_collection.py) — ligne 133 : `def _create_recommendation_history(op_) -> None`
- [_create_collection_run](../../alembic/versions/0068_analyst_snapshot_collection.py) — ligne 167 : `def _create_collection_run(op_) -> None`
- [upgrade](../../alembic/versions/0068_analyst_snapshot_collection.py) — ligne 203 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0068_analyst_snapshot_collection.py) — ligne 215 : `def downgrade() -> None`

## `alembic/versions/0069_add_directional_bundle_prediction_lineage.py`

Source SHA-256 : `80e91dde115af5a9819d766dd11f0b1b4a34ccb4acd2d5b5d53b7abd502658cd`

- [_has_table](../../alembic/versions/0069_add_directional_bundle_prediction_lineage.py) — ligne 36 : `def _has_table(bind) -> bool`
- [_column_names](../../alembic/versions/0069_add_directional_bundle_prediction_lineage.py) — ligne 40 : `def _column_names(bind) -> set[str]`
- [_index_names](../../alembic/versions/0069_add_directional_bundle_prediction_lineage.py) — ligne 44 : `def _index_names(bind) -> set[str]`
- [upgrade](../../alembic/versions/0069_add_directional_bundle_prediction_lineage.py) — ligne 48 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0069_add_directional_bundle_prediction_lineage.py) — ligne 62 : `def downgrade() -> None`

## `alembic/versions/0070_add_model_training_run_role.py`

Source SHA-256 : `eae7c74efa06f545576c0e7562e2ec6c27bb861778e7e7559199cf34c2ac7162`

- [_has_table](../../alembic/versions/0070_add_model_training_run_role.py) — ligne 28 : `def _has_table(bind) -> bool`
- [upgrade](../../alembic/versions/0070_add_model_training_run_role.py) — ligne 32 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0070_add_model_training_run_role.py) — ligne 72 : `def downgrade() -> None`

## `alembic/versions/0071_widen_prediction_calibration_method.py`

Source SHA-256 : `1747fabb919bc29cd0db246a1b95eed63c7a426828305184fafaedd70d1897b2`

- [_has_column](../../alembic/versions/0071_widen_prediction_calibration_method.py) — ligne 26 : `def _has_column(bind) -> bool`
- [upgrade](../../alembic/versions/0071_widen_prediction_calibration_method.py) — ligne 36 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0071_widen_prediction_calibration_method.py) — ligne 51 : `def downgrade() -> None`

## `alembic/versions/0072_add_oracle_label_quality.py`

Source SHA-256 : `02414dbc66ee52e36db03132512801fbc51c77a46435f16103eaeb7d9ec89e3f`

- [_columns](../../alembic/versions/0072_add_oracle_label_quality.py) — ligne 20 : `def _columns(bind) -> set[str]`
- [upgrade](../../alembic/versions/0072_add_oracle_label_quality.py) — ligne 30 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0072_add_oracle_label_quality.py) — ligne 82 : `def downgrade() -> None`

## `alembic/versions/0073_fundamentals_multi_provider_identity.py`

Source SHA-256 : `d34df02a44914a2dcefa7ac88f55329ca1ba4e81ef3d0c0fbe03a03b9a9de68f`

- [_unique_names](../../alembic/versions/0073_fundamentals_multi_provider_identity.py) — ligne 23 : `def _unique_names(bind) -> set[str]`
- [upgrade](../../alembic/versions/0073_fundamentals_multi_provider_identity.py) — ligne 34 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0073_fundamentals_multi_provider_identity.py) — ligne 50 : `def downgrade() -> None`

## `alembic/versions/0074_fundamental_pit_contract.py`

Source SHA-256 : `48eade7b3d6dd3e3a00b62ce70145799f084c2a1eede4f782873ff363270cf5e`

- [_column_names](../../alembic/versions/0074_fundamental_pit_contract.py) — ligne 22 : `def _column_names(bind) -> set[str]`
- [upgrade](../../alembic/versions/0074_fundamental_pit_contract.py) — ligne 29 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0074_fundamental_pit_contract.py) — ligne 66 : `def downgrade() -> None`

## `alembic/versions/0075_forward_pit_collection_foundation.py`

Source SHA-256 : `49131608c08db53940e30ac06efe9652dfa9c600b8e792858941687781c00251`

- [_statements](../../alembic/versions/0075_forward_pit_collection_foundation.py) — ligne 26 : `def _statements() -> list[str]`
- [upgrade](../../alembic/versions/0075_forward_pit_collection_foundation.py) — ligne 35 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0075_forward_pit_collection_foundation.py) — ligne 40 : `def downgrade() -> None`

## `alembic/versions/0076_finra_short_volume_daily.py`

Source SHA-256 : `60579e8f04b087db2702fb1b7c9c6cbc3d6f66a09f606232350e8d9e4c74a2fc`

- [upgrade](../../alembic/versions/0076_finra_short_volume_daily.py) — ligne 16 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0076_finra_short_volume_daily.py) — ligne 40 : `def downgrade() -> None`

## `alembic/versions/0077_yahoo_analyst_trends_revisions.py`

Source SHA-256 : `a7b9468c08a543821b40081c7ef0f0adcf66d6f19ee93797fa2968a7994516f5`

- [_create_analysis_table](../../alembic/versions/0077_yahoo_analyst_trends_revisions.py) — ligne 20 : `def _create_analysis_table(name: str, value_columns: list[sa.Column]) -> None`
- [upgrade](../../alembic/versions/0077_yahoo_analyst_trends_revisions.py) — ligne 54 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0077_yahoo_analyst_trends_revisions.py) — ligne 89 : `def downgrade() -> None`

## `alembic/versions/0078_alpaca_opening_window_pit.py`

Source SHA-256 : `1ea21969f621117219e63c43db0cb9c1df707bdf152b6c29aac9649ec07747a4`

- [upgrade](../../alembic/versions/0078_alpaca_opening_window_pit.py) — ligne 20 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0078_alpaca_opening_window_pit.py) — ligne 99 : `def downgrade() -> None`

## `alembic/versions/0079_delayed_options_and_occ_adjustments.py`

Source SHA-256 : `e92869f5d54c59ac5c9d5cee91e335505d428e49a924ace6e3f497af4562f5ee`

- [upgrade](../../alembic/versions/0079_delayed_options_and_occ_adjustments.py) — ligne 18 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0079_delayed_options_and_occ_adjustments.py) — ligne 87 : `def downgrade() -> None`

## `alembic/versions/0080_widen_pit_collection_run_provider.py`

Source SHA-256 : `ea5c0fd632de3903c40ff9a7fc0124bb0dabcb3153a744226a1571ef9c097e87`

- [upgrade](../../alembic/versions/0080_widen_pit_collection_run_provider.py) — ligne 18 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0080_widen_pit_collection_run_provider.py) — ligne 29 : `def downgrade() -> None`

## `alembic/versions/0081_widen_forward_pit_providers.py`

Source SHA-256 : `702b61ea671b048735a6949cc6dd31c9fbe4193c8b325fe56abaf703a30d2e81`

- [upgrade](../../alembic/versions/0081_widen_forward_pit_providers.py) — ligne 38 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0081_widen_forward_pit_providers.py) — ligne 50 : `def downgrade() -> None`

## `alembic/versions/0082_sec_filing_documents.py`

Source SHA-256 : `0058554dd3274b24c2f0b0bdd7b72a67829ebf92912b5f8bf4fc0017a39a421b`

- [upgrade](../../alembic/versions/0082_sec_filing_documents.py) — ligne 19 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0082_sec_filing_documents.py) — ligne 63 : `def downgrade() -> None`

## `alembic/versions/0083_finra_fractional_short_volume.py`

Source SHA-256 : `c1a965d3b56ad08f7220a62265d23677dd22bcb6603a2d44379c033ef991c993`

- [upgrade](../../alembic/versions/0083_finra_fractional_short_volume.py) — ligne 19 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0083_finra_fractional_short_volume.py) — ligne 30 : `def downgrade() -> None`

## `alembic/versions/0084_market_instrument_foundation.py`

Source SHA-256 : `2620ad021ffe91d44386cf20d4263f3edf8b1c1fba3a42af01f292b2e5845be2`

- [_sql_root](../../alembic/versions/0084_market_instrument_foundation.py) — ligne 116 : `def _sql_root() -> Path`
- [_create_mysql_temporal_guards](../../alembic/versions/0084_market_instrument_foundation.py) — ligne 120 : `def _create_mysql_temporal_guards() -> None`
- [upgrade](../../alembic/versions/0084_market_instrument_foundation.py) — ligne 130 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0084_market_instrument_foundation.py) — ligne 140 : `def downgrade() -> None`

## `alembic/versions/0085_market_scope_parents.py`

Source SHA-256 : `550a9fd1f4831dee5927b5d247fb2329f5cb5a0df681c3e466f9fd2219a26c81`

- [upgrade](../../alembic/versions/0085_market_scope_parents.py) — ligne 23 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0085_market_scope_parents.py) — ligne 138 : `def downgrade() -> None`

## `alembic/versions/0086_market_calendar_pit.py`

Source SHA-256 : `8200c5ad981367708b0735156980713e96427895e474c9b412efc703343cdd70`

- [upgrade](../../alembic/versions/0086_market_calendar_pit.py) — ligne 21 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0086_market_calendar_pit.py) — ligne 25 : `def downgrade() -> None`

## `alembic/versions/0087_us_fact_instrument_columns.py`

Source SHA-256 : `b44247c39e6af9b1def25bb0a79eab01de51a32d841f2d9b1b1f9835b2abbdc1`

- [_existing_tables](../../alembic/versions/0087_us_fact_instrument_columns.py) — ligne 58 : `def _existing_tables() -> set[str]`
- [upgrade](../../alembic/versions/0087_us_fact_instrument_columns.py) — ligne 63 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0087_us_fact_instrument_columns.py) — ligne 70 : `def downgrade() -> None`

## `alembic/versions/0088_us_fact_instrument_constraints.py`

Source SHA-256 : `6156e9ad0f9a5b4ed578d0ab1f1ffbb6ecf8967537a6a5d2e7b7ccf4bcf1cd8d`

- [_existing_tables](../../alembic/versions/0088_us_fact_instrument_constraints.py) — ligne 61 : `def _existing_tables() -> set[str]`
- [_trigger_sql](../../alembic/versions/0088_us_fact_instrument_constraints.py) — ligne 65 : `def _trigger_sql(table: str, timing: str) -> str`
- [upgrade](../../alembic/versions/0088_us_fact_instrument_constraints.py) — ligne 117 : `def upgrade() -> None`
- [downgrade](../../alembic/versions/0088_us_fact_instrument_constraints.py) — ligne 171 : `def downgrade() -> None`

## `alembic/versions/0089_oracle_atr_market_regime_daily.py`

Source SHA-256 : `0727fabf6879dced1823985eeec0339044770ba8b2fd70feec35e151c1af7657`

- [upgrade](../../alembic/versions/0089_oracle_atr_market_regime_daily.py) — ligne 16 : `def upgrade()`
- [downgrade](../../alembic/versions/0089_oracle_atr_market_regime_daily.py) — ligne 23 : `def downgrade()`

## `alembic/versions/0090_oracle_atr_d10_d1_ratio.py`

Source SHA-256 : `138eaa7e288301dcdd4e79994940f59b5a8485fe2ce4b59cb6f17ee1fd46ef06`

- [upgrade](../../alembic/versions/0090_oracle_atr_d10_d1_ratio.py) — ligne 11 : `def upgrade()`
- [downgrade](../../alembic/versions/0090_oracle_atr_d10_d1_ratio.py) — ligne 25 : `def downgrade()`

## `alembic/versions/0091_oracle_atr_total_pct.py`

Source SHA-256 : `417888de8f9fb007e734652741de9818223deef6af49a9cc1c23d5abb093325c`

- [upgrade](../../alembic/versions/0091_oracle_atr_total_pct.py) — ligne 11 : `def upgrade()`
- [downgrade](../../alembic/versions/0091_oracle_atr_total_pct.py) — ligne 25 : `def downgrade()`

## `alembic/versions/0092_oracle_atr_movements.py`

Source SHA-256 : `23de1ce62b26d27dc5c0f1da4e1b0977a2931621d4ccffd05246af5fe667129c`

- [_existing](../../alembic/versions/0092_oracle_atr_movements.py) — ligne 14 : `def _existing()`
- [upgrade](../../alembic/versions/0092_oracle_atr_movements.py) — ligne 23 : `def upgrade()`
- [downgrade](../../alembic/versions/0092_oracle_atr_movements.py) — ligne 30 : `def downgrade()`

## `alembic/versions/0093_llm_directional.py`

Source SHA-256 : `df704ad923bdeb1c1e3ad0f45383b1137c6daf4cb4207fc7dc066cfa3ed2e87d`

- [_guard](../../alembic/versions/0093_llm_directional.py) — ligne 14 : `def _guard()`
- [upgrade](../../alembic/versions/0093_llm_directional.py) — ligne 19 : `def upgrade()`
- [downgrade](../../alembic/versions/0093_llm_directional.py) — ligne 29 : `def downgrade()`

## `alembic/versions/0094_oracle_atr_score_order.py`

Source SHA-256 : `63b701c00de91269e58342bdfb3713c3f429b562b9558278e3d7eacddbad304c`

- [_existing](../../alembic/versions/0094_oracle_atr_score_order.py) — ligne 13 : `def _existing()`
- [upgrade](../../alembic/versions/0094_oracle_atr_score_order.py) — ligne 22 : `def upgrade()`
- [downgrade](../../alembic/versions/0094_oracle_atr_score_order.py) — ligne 28 : `def downgrade()`

## `alembic/versions/0095_oracle_atr_partial_returns.py`

Source SHA-256 : `6343f2ff3435ea75f3e62fe493013931c51c7fb0116c0722376554e2c0db3168`

- [_existing](../../alembic/versions/0095_oracle_atr_partial_returns.py) — ligne 14 : `def _existing()`
- [upgrade](../../alembic/versions/0095_oracle_atr_partial_returns.py) — ligne 23 : `def upgrade()`
- [downgrade](../../alembic/versions/0095_oracle_atr_partial_returns.py) — ligne 30 : `def downgrade()`
