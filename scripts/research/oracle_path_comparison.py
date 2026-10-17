"""Historical path-Oracle comparison; read-only SQL, isolated research artifacts.

Run with -m. Uses the Pipeline's default feature/booster/WF settings, not a
browser session's transient values. No account, predictions or model journal writes.
"""
import argparse
from dataclasses import asdict
from datetime import date
import json
import logging
import os
from pathlib import Path

from common.universe_files import load_universe_file_symbols, resolve_universe_file_path
from modelFactory.config import TrainingConfig, DataConfig, BaselineConfig, WalkForwardConfig
from modelFactory.oracle_path.train import atomic_json, digest, train_oracle_path


def comparison_config(output, start, end):
    from ihm.services.pipeline_runner import PipelineLaunchOptions
    o = PipelineLaunchOptions()
    data = DataConfig(oracle_path_model_only=True, feature_set=o.ml_feature_set,
        force_v1_lstm=False, training_start_date=date.fromisoformat(start),
        training_end_date=date.fromisoformat(end), sequence_length=o.ml_sequence_length,
        benchmark_symbol=o.ml_benchmark_symbol, include_sentiment_features=o.ml_include_sentiment,
        include_screener_scores=o.ml_include_screener_scores,
        include_short_score_features=o.ml_include_short_score,
        include_macro_vix_features=o.ml_include_macro_vix, include_macro_vxn_features=o.ml_include_macro_vxn,
        include_macro_vix3m_features=o.ml_include_macro_vix3m, include_macro_move_features=o.ml_include_macro_move,
        include_fundamentals_features=o.ml_include_fundamentals, include_factors_features=o.ml_include_factors,
        include_macro_regime_features=o.ml_include_macro_regime, include_score_components=o.ml_include_score_components,
        include_volume_features=o.ml_include_volume_features)
    baseline = BaselineConfig(enable_catboost=True, max_depth=o.ml_lgbm_max_depth,
        n_estimators=o.ml_lgbm_n_estimators, learning_rate=o.ml_lgbm_learning_rate,
        catboost_depth=o.ml_catboost_depth, catboost_iterations=o.ml_catboost_iterations,
        catboost_learning_rate=o.ml_catboost_learning_rate)
    from dataclasses import replace
    if o.ml_lgbm_tuning_enabled:
        baseline = replace(baseline, lgbm_reg_alpha=o.ml_lgbm_reg_alpha, lgbm_reg_lambda=o.ml_lgbm_reg_lambda,
            lgbm_min_child_samples=o.ml_lgbm_min_child_samples, lgbm_subsample=o.ml_lgbm_subsample,
            lgbm_colsample_bytree=o.ml_lgbm_colsample_bytree)
    if o.ml_catboost_tuning_enabled:
        baseline = replace(baseline, catboost_l2_leaf_reg=o.ml_catboost_l2_leaf_reg,
            catboost_border_count=o.ml_catboost_border_count, catboost_random_strength=o.ml_catboost_random_strength,
            catboost_bagging_temperature=o.ml_catboost_bagging_temperature, catboost_od_type=o.ml_catboost_od_type,
            catboost_od_wait=o.ml_catboost_od_wait)
    return TrainingConfig(data=data, baseline=baseline, oracle_horizon=20,
        walk_forward=WalkForwardConfig(enabled=True, min_train_size=o.ml_wf_min_train_size,
            val_size=o.ml_wf_val_size, test_size=o.ml_wf_test_size,
            step_size=o.ml_wf_step_size, max_splits=o.ml_wf_max_splits),
        artifacts_dir=Path(output)/"models"/"oracle-path-comparison", max_workers=o.ml_max_workers)


def run(output, symbol_source, start, end):
    from database.connection import get_sqlalchemy_engine
    from sqlalchemy import text
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    cfg = comparison_config(output, start, end)
    source = resolve_universe_file_path(symbol_source)
    symbols = load_universe_file_symbols(symbol_source)
    frozen = dict(schema_version=1, symbol_source=symbol_source, universe_file_sha256=digest(source),
        symbols=symbols, training_config=asdict(cfg), selection="validation_auc; exact_tie_lightgbm",
        source_hashes={name: digest(name) for name in (
            "modelFactory/oracle_path/train.py", "modelFactory/oracle_path/labels.py",
            "modelFactory/oracle_path/predict.py", "modelFactory/oracle/walk_forward.py",
            "scripts/research/oracle_path_comparison.py")},
        no_sql_writes=True, no_orders=True, lstm=False)
    # Compare JSON-normalised types so paths/dates do not invalidate a resume.
    frozen = json.loads(json.dumps(frozen, default=str))
    plan = output/"plan.json"
    if plan.exists() and json.loads(plan.read_text(encoding="utf-8")) != frozen:
        raise ValueError("Comparison plan changed; new output directory required")
    atomic_json(plan, frozen)
    atomic_json(output/"run.json", dict(status="RUNNING", pid=os.getpid(), symbols=len(symbols), start=start, end=end))
    engine = get_sqlalchemy_engine()
    try:
        if engine.url.database != "alpha_trade":
            raise ValueError("US comparison requires alpha_trade")
        # MySQL session-level read-only transactions; no global DB setting changes.
        from sqlalchemy import event
        @event.listens_for(engine, "connect")
        def read_only(dbapi_conn, connection_record):
            with dbapi_conn.cursor() as cursor:
                cursor.execute("SET SESSION TRANSACTION READ ONLY")
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logging.info("Comparison start symbols=%d dates=%s..%s; SQL read-only", len(symbols), start, end)
        report = train_oracle_path(cfg, engine, "oracle-path-comparison", symbols)
        atomic_json(output/"report.json", report)
        atomic_json(output/"run.json", dict(status="COMPLETED", pid=os.getpid(), n_folds=report["n_folds"]))
        logging.info("Comparison completed: %s", output/"report.json")
        return report
    except Exception as exc:
        atomic_json(output/"run.json", dict(status="FAILED", pid=os.getpid(), error=str(exc)))
        raise
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--symbol-source", default="universe-file:univers_filtred_tradable.txt")
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default="2023-12-31")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(args.output, args.symbol_source, args.start, args.end)


if __name__ == "__main__":
    main()
