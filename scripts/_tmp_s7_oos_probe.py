"""Probe S7-C : valide le chargement du frame OOS + scaler + modèles pour un symbole."""
from __future__ import annotations

import json
import pickle
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory import predictor
from modelFactory.features import get_feature_columns

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "artifacts" / "models_s7_dc"
BATCH = "model-factory-20260818161944-1c73e8"
SYM = "ACI"
OOS_END = date(2026, 5, 31)

eng = get_sqlalchemy_engine()
cfg = json.load(open(RUN_DIR / BATCH / SYM / "config.json", encoding="utf-8"))
data_cfg = predictor._load_data_cfg_from_payload(cfg)
print("arch selected:", cfg.get("architecture_selected"))
print("data_cfg feature_set:", data_cfg.feature_set, "| wl enabled:", data_cfg.feature_whitelist_enabled, "| n wl:", len(data_cfg.feature_whitelist))
print("feature_columns (persisted):", len(cfg.get("feature_columns", [])))

df = predictor._prepare_prediction_frame(
    SYM, data_cfg=data_cfg, engine=eng, cutoff_date=OOS_END, include_global_stacking=False,
)
print("\nframe shape:", None if df is None else df.shape)
if df is not None:
    print("frame date range:", df["date"].min(), "->", df["date"].max())
    print("columns:", list(df.columns)[:20], "... total", len(df.columns))
    has_close = "close" in df.columns
    print("has close:", has_close)

    # scaler
    scaler_path = RUN_DIR / BATCH / SYM / "scaler.pkl"
    with open(scaler_path, "rb") as fh:
        scaler = pickle.load(fh)
    print("\nscaler type:", type(scaler).__name__)
    print("scaler feature_names:", len(getattr(scaler, "feature_names", []) or []))
    try:
        X = scaler.transform(df.tail(2))
        print("scaler.transform ok, shape:", X.shape)
    except Exception as exc:
        print("scaler.transform FAIL:", type(exc).__name__, str(exc)[:200])

    # LightGBM
    try:
        import lightgbm as lgb
        model = lgb.Booster(model_file=str(RUN_DIR / BATCH / SYM / "h20" / "lightgbm" / "lightgbm_model.txt"))
        cols = [c for c in cfg.get("feature_columns", []) if c in df.columns]
        P = model.predict(df[cols].tail(2).values)
        print("\nlightgbm predict ok:", P[:3], "dtype:", P.dtype)
    except Exception as exc:
        print("\nlightgbm FAIL:", type(exc).__name__, str(exc)[:200])

    # CatBoost — tester CatBoostClassifier vs CatBoost()
    try:
        from catboost import CatBoostClassifier, CatBoost
        for cls, name in [(CatBoostClassifier, "CatBoostClassifier"), (CatBoost, "CatBoost")]:
            try:
                m = cls()
                m.load_model(str(RUN_DIR / BATCH / SYM / "h20" / "catboost" / "catboost_model.cbm"))
                P = m.predict(df[cols].tail(2).values)
                print(f"\ncatboost as {name}: predict ok -> {P} dtype={getattr(P, 'dtype', None)}")
            except Exception as exc:
                print(f"\ncatboost as {name} FAIL:", type(exc).__name__, str(exc)[:160])
    except Exception as exc:
        print("\ncatboost import FAIL:", type(exc).__name__, str(exc)[:160])
