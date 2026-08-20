"""Campagne Per-Symbol Directional v2 — OOS 2025/2026 (F0/F1/F2/F3a/F3b).

Pour chaque run × 39 symboles communs, génère les prédictions OOS
(2025-01-01 -> 2026-05-31) pour chaque architecture (LSTM, LightGBM, CatBoost)
et le champion sélectionné, en réutilisant le pipeline de s7_oos_predict.py.

Aucun réentraînement, aucun tuning. Sortie : artifacts/per_symbol_v2/predictions_oos.parquet
"""
from __future__ import annotations

import json
import os
import pickle
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from database.connection import get_sqlalchemy_engine
from modelFactory import predictor
from modelFactory.dataset import FeatureScaler

ROOT = Path(__file__).resolve().parents[1]
RUNS = {
    "f0": ("artifacts/models_s7_bl", "model-factory-20260818161922-d7d984", "F0 legacy (18, WL off)"),
    "f1": ("artifacts/psv2_f1", "model-factory-20260818193414-b43139", "F1 Trend/Vol (7)"),
    "f2": ("artifacts/psv2_f2", "model-factory-20260818200840-c1f256", "F2 Momentum/Structure (17)"),
    "f3a": ("artifacts/psv2_f3a", "model-factory-20260818200855-db8b99", "F3a Relative Strength (6)"),
    "f3b": ("artifacts/psv2_f3b", "model-factory-20260818200911-541e15", "F3b Volume (4)"),
}
ARCHS = ["lstm_attention", "lightgbm", "catboost"]
SYMBOLS_40 = [
    "ACI","ACIW","AGNC","AN","ARQT","AXS","BAH","BJ","BKD","CAKE","CMC","CNM",
    "COMP","CPRI","CRBG","ENS","FLO","FLR","FTV","GEN","INVH","IOT","LEA","LNC",
    "MGY","MKC","MWA","NE","PLNT","RHI","RVLV","RVTY","SHOO","TDC","VIPS","VOYA",
    "VRNS","VTRS","WMG","YETI",
]
EXCLUDE = {"CRBG"}
SYMBOLS = [s for s in SYMBOLS_40 if s not in EXCLUDE]
OOS_START = date(2025, 1, 1)
OOS_END = date(2026, 5, 31)

_TEST_RUNS = os.environ.get("PSV2_RUNS", "").strip()
_TEST_LIMIT = int(os.environ.get("PSV2_LIMIT", "0") or 0)


def _load_scaler(scaler_path: Path) -> FeatureScaler:
    with open(scaler_path, "rb") as fh:
        state = pickle.load(fh)
    return FeatureScaler.from_state_dict(state)


def _predict_lstm_scores(model, scaler: FeatureScaler, df: pd.DataFrame, seq_len: int, device, batch: int = 128) -> np.ndarray:
    X = scaler.transform(df)
    scores = np.full(len(df), np.nan, dtype=np.float64)
    model.eval()
    with torch.no_grad():
        idxs = list(range(seq_len - 1, len(df)))
        for start in range(0, len(idxs), batch):
            chunk = idxs[start : start + batch]
            xs = np.stack([X[i - seq_len + 1 : i + 1] for i in chunk])
            xt = torch.from_numpy(xs.astype(np.float32)).to(device)
            out, _ = model(xt)
            out = out.squeeze(-1).cpu().numpy()
            for k, i in enumerate(chunk):
                scores[i] = out[k]
    return scores


def _predict_tabular_scores(model, scaler: FeatureScaler, df: pd.DataFrame) -> np.ndarray:
    cols = [c for c in scaler.feature_names if c in df.columns]
    X = scaler.transform(df[cols].copy())
    return np.asarray(model.predict(X), dtype=np.float64)


def main() -> None:
    eng = get_sqlalchemy_engine()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out_dir = ROOT / "artifacts" / "per_symbol_v2"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for run, (run_dir, batch, _label) in RUNS.items():
        if _TEST_RUNS and run not in _TEST_RUNS.split(","):
            continue
        base = ROOT / run_dir / batch
        print(f"[{run}] start", flush=True)
        _symbols = SYMBOLS[: _TEST_LIMIT] if _TEST_LIMIT else SYMBOLS
        for sym in _symbols:
            cfg_path = base / sym / "config.json"
            if not cfg_path.exists():
                continue
            cfg = json.load(open(cfg_path, encoding="utf-8"))
            data_cfg = predictor._load_data_cfg_from_payload(cfg)
            horizon = int(cfg.get("selected_forecast_horizon") or 20)
            seq_len = int(cfg.get("data", {}).get("sequence_length") or 40)
            champion = cfg.get("architecture_selected")

            df = predictor._prepare_prediction_frame(
                sym, data_cfg=data_cfg, engine=eng, cutoff_date=OOS_END, include_global_stacking=False,
            )
            if df is None or df.empty or "close" not in df.columns:
                continue
            df = df.sort_values("date").reset_index(drop=True)
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df["future_return"] = df["close"].shift(-horizon) / df["close"] - 1.0

            scaler_path = base / sym / "scaler.pkl"
            if not scaler_path.exists():
                continue
            scaler = _load_scaler(scaler_path)

            scores = {}
            # LSTM
            try:
                ckpt = base / sym / "best.ckpt"
                if ckpt.exists():
                    model = predictor.load_lstm_module_cached(ckpt, device)
                    scores["lstm_attention"] = _predict_lstm_scores(model, scaler, df, seq_len, device)
            except Exception as exc:
                print(f"  [{run} {sym}] lstm FAIL {type(exc).__name__} {str(exc)[:120]}", flush=True)
            # LightGBM
            try:
                import lightgbm as lgb
                mp = base / sym / "h20" / "lightgbm" / "lightgbm_model.txt"
                if mp.exists():
                    model = lgb.Booster(model_file=str(mp))
                    scores["lightgbm"] = _predict_tabular_scores(model, scaler, df)
            except Exception as exc:
                print(f"  [{run} {sym}] lightgbm FAIL {type(exc).__name__} {str(exc)[:120]}", flush=True)
            # CatBoost (sauvegardé en pickle avec extension .cbm)
            try:
                mp = base / sym / "h20" / "catboost" / "catboost_model.cbm"
                if mp.exists():
                    with open(mp, "rb") as fh:
                        model = pickle.load(fh)
                    scores["catboost"] = _predict_tabular_scores(model, scaler, df)
            except Exception as exc:
                print(f"  [{run} {sym}] catboost FAIL {type(exc).__name__} {str(exc)[:120]}", flush=True)

            # Restreindre à OOS
            mask = (df["date"] >= OOS_START) & (df["date"] <= OOS_END)
            sub = df[mask].copy()
            for arch in ARCHS:
                if arch in scores:
                    for idx, d, fr in zip(sub.index, sub["date"], sub["future_return"]):
                        rows.append({
                            "run": run, "symbol": sym, "arch": arch, "date": d,
                            "score": scores[arch][idx], "future_return": fr,
                        })
            if champion in scores:
                for idx, d, fr in zip(sub.index, sub["date"], sub["future_return"]):
                    rows.append({
                        "run": run, "symbol": sym, "arch": "champion", "date": d,
                        "score": scores[champion][idx], "future_return": fr,
                    })
        print(f"[{run}] done, cumul {len(rows)} rows", flush=True)

    df_all = pd.DataFrame(rows)
    if df_all.empty:
        print("AUCUN résultat")
        return
    df_all.to_parquet(out_dir / "predictions_oos.parquet")
    print("saved:", out_dir / "predictions_oos.parquet", "| rows:", len(df_all))


if __name__ == "__main__":
    main()
