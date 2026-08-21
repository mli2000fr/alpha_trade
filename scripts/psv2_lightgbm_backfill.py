"""Backfill LightGBM h20 — runs campagne F1/F2/F3a/F3b (LightGBM absent).

Les 4 runs campagne ont été lancés SANS --compare-lightgbm → baseline.enabled=False
→ aucun modèle LightGBM persisté (seuls LSTM + CatBoost existent).

Ce script ré-entraîne UNIQUEMENT le modèle LightGBM h20 de chaque symbole, en
réutilisant EXACTEMENT le pipeline d'entraînement (mêmes splits, winsorize,
standardization, sample weights, seed) :
  - reconstruction du TrainingConfig depuis le config.json persisté ;
  - chargement des données comme l'orchestrateur (_train_worker) ;
  - SymbolDataModule → prepared_df (features + target) ;
  - run_tabular_baseline(model_name="lightgbm", forecast_horizon_override=20)
    → h20/lightgbm/lightgbm_model.txt.

Idempotent : un modèle déjà présent est conservé. Env de test :
PSV2_BF_RUNS='f1,f3a' PSV2_BF_LIMIT=1
"""
from __future__ import annotations

import dataclasses
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.config import (
    BaselineConfig,
    CalibrationConfig,
    DataConfig,
    ModelConfig,
    ReproducibilityConfig,
    TrainingConfig,
    WalkForwardConfig,
)
from modelFactory.cross_sectional import build_cross_sectional_features_from_db
from modelFactory.data_loader import (
    load_benchmark_bars,
    load_symbol_bars,
    load_symbol_latest_bar_date,
    load_symbol_selector_context,
    resolve_training_start_date,
)
from modelFactory.dataset import SymbolDataModule
from modelFactory.reproducibility import derive_seed
from modelFactory.tabular_baseline import run_tabular_baseline

ROOT = Path(__file__).resolve().parents[1]
RUNS = {
    "f1": ("artifacts/psv2_f1", "model-factory-20260818193414-b43139"),
    "f2": ("artifacts/psv2_f2", "model-factory-20260818200840-c1f256"),
    "f3a": ("artifacts/psv2_f3a", "model-factory-20260818200855-db8b99"),
    "f3b": ("artifacts/psv2_f3b", "model-factory-20260818200911-541e15"),
}
SYMBOLS = [
    "ACI","ACIW","AGNC","AN","ARQT","AXS","BAH","BJ","BKD","CAKE","CMC","CNM",
    "COMP","CPRI","ENS","FLO","FLR","FTV","GEN","INVH","IOT","LEA","LNC",
    "MGY","MKC","MWA","NE","PLNT","RHI","RVLV","RVTY","SHOO","TDC","VIPS","VOYA",
    "VRNS","VTRS","WMG","YETI",
]

_TEST_RUNS = os.environ.get("PSV2_BF_RUNS", "").strip()
_TEST_LIMIT = int(os.environ.get("PSV2_BF_LIMIT", "0") or 0)


# ── Reconstruction des configs depuis le config.json persisté ──────────────
def _conv(value, kind):
    if value is None:
        return None
    if kind == "date":
        return datetime.strptime(value, "%Y-%m-%d").date()
    if kind == "tuple_int":
        return tuple(int(x) for x in value)
    if kind == "tuple_str":
        return tuple(str(x) for x in value)
    return value


def _build(cls, section: dict, special: dict | None = None) -> object:
    special = special or {}
    kwargs = {}
    for f in dataclasses.fields(cls):
        if f.name in section:
            kwargs[f.name] = _conv(section[f.name], special.get(f.name))
    return cls(**kwargs)


def _training_cfg(payload: dict) -> TrainingConfig:
    data = payload.get("data", {})
    model = payload.get("model", {})
    calib = payload.get("calibration", {})
    wf = payload.get("walk_forward", {})
    baseline = payload.get("baseline", {})
    data_cfg = _build(
        DataConfig, data,
        {"forecast_horizons": "tuple_int", "feature_whitelist": "tuple_str",
         "training_start_date": "date", "training_end_date": "date"},
    )
    model_cfg = _build(ModelConfig, model)
    calib_cfg = _build(CalibrationConfig, calib)
    wf_cfg = _build(WalkForwardConfig, wf)
    baseline_cfg = _build(BaselineConfig, baseline)
    # Campaign runs : seed 42, deterministic, pas de stacking.
    return TrainingConfig(
        data=data_cfg,
        model=model_cfg,
        calibration=calib_cfg,
        walk_forward=wf_cfg,
        baseline=baseline_cfg,
        reproducibility=ReproducibilityConfig(seed=42, deterministic=True),
    )


# ── Chargement des données (réplique orchestrator._train_worker) ───────────
def _load_symbol_data(sym: str, cfg: TrainingConfig, engine) -> dict:
    history_end = load_symbol_latest_bar_date(engine, sym, end_date=cfg.data.training_end_date)
    history_start = resolve_training_start_date(history_end, cfg.data.training_start_date)
    bars = load_symbol_bars(engine, sym, end_date=history_end, start_date=history_start)
    benchmark_df = None
    if cfg.data.feature_set == "expert" or cfg.data.enable_cross_sectional_features:
        benchmark_df = load_benchmark_bars(engine, cfg.data.benchmark_symbol, end_date=history_end, start_date=history_start)
    selector_df = None
    if cfg.data.include_screener_scores or cfg.data.include_short_score_features:
        selector_df = load_symbol_selector_context(engine, sym, end_date=history_end, start_date=history_start)
    cross_sectional_df = None
    if cfg.data.enable_cross_sectional_features:
        cross_sectional_df, _ = build_cross_sectional_features_from_db(
            engine, list(SYMBOLS), benchmark_df=benchmark_df,
            min_universe_size=cfg.data.cross_sectional_min_universe,
            start_date=history_start, end_date=history_end,
        )
    return {"bars": bars, "benchmark_df": benchmark_df, "selector_df": selector_df,
            "cross_sectional_df": cross_sectional_df, "history_start": history_start,
            "history_end": history_end}


def _backfill_symbol(run: str, sym: str, base: Path, cfg: TrainingConfig, engine) -> str:
    sym_dir = base / sym
    out = sym_dir / "h20" / "lightgbm" / "lightgbm_model.txt"
    if out.exists():
        return f"skip(exists) {sym}"
    data = _load_symbol_data(sym, cfg, engine)
    bars = data["bars"]
    if bars is None or len(bars) < cfg.data.min_history_days:
        return f"skip(history {len(bars) if bars is not None else 0}) {sym}"

    symbol_seed = derive_seed(cfg.reproducibility.seed, "train_symbol", sym)
    dm = SymbolDataModule(
        bars,
        cfg.data,
        cfg.model,
        sentiment_df=None,
        benchmark_df=data["benchmark_df"],
        selector_df=data["selector_df"],
        cross_sectional_df=data["cross_sectional_df"],
        reproducibility_seed=derive_seed(symbol_seed, "symbol_datamodule"),
        include_global_stacking=False,
    )
    dm.setup()
    prepared_df = getattr(dm, "prepared_df", None)
    if prepared_df is None or prepared_df.empty:
        return f"skip(no_prepared) {sym}"

    # Multi-horizon → extraire l'horizon h20
    _df = prepared_df.copy()
    if "target_h20" in _df.columns and "future_return_h20" in _df.columns:
        _df["target"] = _df["target_h20"]
        _df["future_return"] = _df["future_return_h20"]

    def _lgbm_builder(seed):
        import lightgbm as lgb
        return lgb.LGBMRegressor(
            objective="regression",
            max_depth=cfg.baseline.max_depth,
            num_leaves=cfg.baseline.lgbm_num_leaves,
            n_estimators=cfg.baseline.n_estimators,
            learning_rate=cfg.baseline.learning_rate,
            random_state=seed, verbosity=-1,
            reg_alpha=cfg.baseline.lgbm_reg_alpha,
            reg_lambda=cfg.baseline.lgbm_reg_lambda,
            min_child_samples=cfg.baseline.lgbm_min_child_samples,
            subsample=cfg.baseline.lgbm_subsample,
            colsample_bytree=cfg.baseline.lgbm_colsample_bytree,
        )

    res = run_tabular_baseline(
        _df, cfg,
        model_name="lightgbm",
        model_builder=_lgbm_builder,
        artifact_dir=sym_dir / "h20" / "lightgbm",
        save_callback=lambda model, path: model.booster_.save_model(str(path)),
        model_extension=".txt",
        by_dates=False,
        symbol_tag=f"{sym}_h20",
        forecast_horizon_override=20,
    )
    if out.exists():
        return f"ok {sym} status={res.get('status')}"
    return f"FAILED {sym} status={res.get('status')} reason={str(res.get('reason'))[:80]}"


def main() -> None:
    engine = get_sqlalchemy_engine()
    for run, (run_dir, batch) in RUNS.items():
        if _TEST_RUNS and run not in _TEST_RUNS.split(","):
            continue
        base = ROOT / run_dir / batch
        _symbols = SYMBOLS[: _TEST_LIMIT] if _TEST_LIMIT else SYMBOLS
        print(f"[{run}] start", flush=True)
        done = 0
        for sym in _symbols:
            cfg_path = base / sym / "config.json"
            if not cfg_path.exists():
                print(f"  [{run} {sym}] no config", flush=True)
                continue
            cfg = _training_cfg(json.load(open(cfg_path, encoding="utf-8")))
            try:
                msg = _backfill_symbol(run, sym, base, cfg, engine)
            except Exception as exc:
                msg = f"ERROR {sym}: {type(exc).__name__} {str(exc)[:120]}"
            print(f"  [{run}] {msg}", flush=True)
            if msg.startswith("ok"):
                done += 1
        print(f"[{run}] done, lightgbm h20 ok={done}/{len(_symbols)}", flush=True)


if __name__ == "__main__":
    main()
