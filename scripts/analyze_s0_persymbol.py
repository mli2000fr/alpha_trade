# -*- coding: utf-8 -*-
"""Analyse per-symbol du batch S0 (model-factory-20260814165502-f62322) — final.

Notes schema:
- `walk_forward` top-level = walkforward du LSTM (default champion), PAS du champion selectionne.
- `challengers[m]['walk_forward']['mean']` = vraies metriques WF par modele.
- LSTM: mean/std sans ic/mse -> on reagrege depuis les splits.
"""
import json, glob, os, math
import numpy as np
import pandas as pd

BATCH = r"artifacts\models\model-factory-20260814165502-f62322"
files = glob.glob(os.path.join(BATCH, "*", "metrics.json"))
MODELS = ("catboost", "lightgbm", "lstm_attention")
print(f"nb symboles: {len(files)}")

rows = []
for f in files:
    sym = os.path.basename(os.path.dirname(f))
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception as e:
        print("ERR", sym, e); continue
    champ = (d.get("champion") or {}).get("model_name")
    chal = d.get("challengers", {})
    r = {"symbol": sym, "champion": champ}
    for m in MODELS:
        cm = chal.get(m) if isinstance(chal.get(m), dict) else {}
        wf = cm.get("walk_forward", {}) if isinstance(cm, dict) else {}
        wm = wf.get("mean", {}) if isinstance(wf, dict) else {}
        r[f"{m}_f1"] = wm.get("f1_macro")
        r[f"{m}_ic"] = wm.get("ic")
        r[f"{m}_mse"] = wm.get("mse")
        r[f"{m}_dir"] = wm.get("directional_accuracy")
        r[f"{m}_sel"] = cm.get("selection_score")
        # LSTM: reagreger ic/mse depuis les splits si absents du mean
        if r[f"{m}_ic"] is None or (isinstance(r[f"{m}_ic"], float) and math.isnan(r[f"{m}_ic"])):
            splits = wf.get("splits", []) if isinstance(wf, dict) else []
            ics = [s["ic"] for s in splits if isinstance(s.get("ic"), (int, float))]
            mses = [s["mse"] for s in splits if isinstance(s.get("mse"), (int, float))]
            if ics:
                r[f"{m}_ic"] = float(np.mean(ics))
                r[f"{m}_ic_std"] = float(np.std(ics))
                r[f"{m}_ic_neg"] = sum(1 for x in ics if x < 0)
                r[f"{m}_ic_n"] = len(ics)
            if mses:
                r[f"{m}_mse"] = float(np.mean(mses))
    # metriques du champion (depuis challengers)
    if champ in MODELS:
        r["champ_f1"] = r[f"{champ}_f1"]
        r["champ_ic"] = r[f"{champ}_ic"]
        r["champ_mse"] = r[f"{champ}_mse"]
        r["champ_dir"] = r[f"{champ}_dir"]
        r["champ_sel"] = r[f"{champ}_sel"]
        r["champ_ic_std"] = r.get(f"{champ}_ic_std")
        r["champ_ic_neg"] = r.get(f"{champ}_ic_neg")
        r["champ_ic_n"] = r.get(f"{champ}_ic_n")
    rows.append(r)

df = pd.DataFrame(rows)

print("\n========== 1. CHAMPIONS : distribution et qualite WF reelle ==========")
g = df.groupby("champion").agg(n=("symbol", "size"),
    f1=("champ_f1", "mean"), f1_med=("champ_f1", "median"),
    ic=("champ_ic", "mean"), ic_med=("champ_ic", "median"),
    dir=("champ_dir", "mean"), mse=("champ_mse", "mean"),
    sel=("champ_sel", "mean")).round(4)
print(g.to_string())

print("\n========== 2. PAR MODELE (tous symboles, WF) ==========")
for m in MODELS:
    ok = df[f"{m}_f1"].notna()
    ic = df.loc[ok, f"{m}_ic"]
    mse = df.loc[ok, f"{m}_mse"]
    print(f"{m:14s} n={ok.sum():3d} f1={df.loc[ok,f'{m}_f1'].mean():.4f}  "
          f"ic={ic.mean():.4f}  mse_med={mse.median():.3f} mse_max={mse.max():.2f}  "
          f"dir={df.loc[ok,f'{m}_dir'].mean():.4f}")

print("\n========== 3. CHAMPION vs MEILLEUR MODELE DISPONIBLE ==========")
def best_by(row, col):
    vals = {m: row.get(f"{m}_{col}") for m in MODELS
            if isinstance(row.get(f"{m}_{col}"), (int, float)) and not math.isnan(row[f"{m}_{col}"])}
    if not vals: return None
    return max(vals, key=vals.get)
df["best_ic_model"] = df.apply(lambda r: best_by(r, "ic"), axis=1)
df["best_f1_model"] = df.apply(lambda r: best_by(r, "f1"), axis=1)
print("champion == meilleur F1 WF :", (df["champion"] == df["best_f1_model"]).sum(), "/",
      df["best_f1_model"].notna().sum())
print("champion == meilleur IC WF :", (df["champion"] == df["best_ic_model"]).sum(), "/",
      df["best_ic_model"].notna().sum())
print("\nMeilleur IC par symbole :"); print(df.groupby("best_ic_model").size().to_string())
print("\nMeilleur F1 par symbole :"); print(df.groupby("best_f1_model").size().to_string())
ic_champ = df["champ_ic"]
ic_best = df.apply(lambda r: r.get(f"{r['best_ic_model']}_ic") if r["best_ic_model"] else np.nan, axis=1)
print(f"\nIC moyen champion: {ic_champ.mean():.4f}  | IC moyen meilleur dispo: {ic_best.mean():.4f}  "
      f"| regret: {(ic_best - ic_champ).mean():.4f}")

print("\n========== 4. LSTM : OU ET POURQUOI IL GAGNE ==========")
df["lstm_is_champ"] = df["champion"] == "lstm_attention"
print("LSTM champion sur:", df["lstm_is_champ"].sum(), "symboles")
print("\nProfils moyens (symboles LSTM-champion vs arbres-champion):")
prof = df.groupby("lstm_is_champ").agg(
    n=("symbol", "size"), f1_arbre_best=("champ_f1", "mean"),
    lstm_f1=("lstm_attention_f1", "mean"), lstm_ic=("lstm_attention_ic", "mean"),
    lstm_mse=("lstm_attention_mse", "mean"), lstm_dir=("lstm_attention_dir", "mean"),
    cb_ic=("catboost_ic", "mean"), lb_ic=("lightgbm_ic", "mean")).round(4)
print(prof.to_string())
print("\nLSTM mse WF: median=%.3f  p90=%.3f  max=%.1f" % (
    df["lstm_attention_mse"].median(), df["lstm_attention_mse"].quantile(0.9),
    df["lstm_attention_mse"].max()))
print("symboles LSTM mse > 10 :", (df["lstm_attention_mse"] > 10).sum(), "/", df["lstm_attention_mse"].notna().sum())
print("symboles LSTM ic < 0   :", (df["lstm_attention_ic"] < 0).sum(), "/", df["lstm_attention_ic"].notna().sum())

print("\n========== 5. STABILITE IC DU CHAMPION ==========")
st = df[df["champ_ic_neg"].notna()].copy()
print(f"symboles >=1 split IC<0     : {(st['champ_ic_neg']>0).sum()} / {len(st)}")
print(f"symboles >=50%% splits IC<0  : {(st['champ_ic_neg']>=st['champ_ic_n']/2).sum()}")
print(f"symboles IC>0 sur tous les splits : {(st['champ_ic_neg']==0).sum()}")
print("\nTop 15 IC champion :")
print(st.nlargest(15, "champ_ic")[["symbol", "champion", "champ_ic", "champ_ic_std", "champ_f1", "champ_dir"]].round(4).to_string(index=False))
print("\nBottom 15 IC champion :")
print(st.nsmallest(15, "champ_ic")[["symbol", "champion", "champ_ic", "champ_ic_std", "champ_f1", "champ_dir"]].round(4).to_string(index=False))

print("\n========== 6. SELECTION SCORE vs REALITE ==========")
print("corr(sel, f1 WF)   =", df["champ_sel"].corr(df["champ_f1"]).round(3))
print("corr(sel, ic WF)   =", df["champ_sel"].corr(df["champ_ic"]).round(3))
print("corr(f1 WF, ic WF) =", df["champ_f1"].corr(df["champ_ic"]).round(3))
print("corr(ic, dir)      =", df["champ_ic"].corr(df["champ_dir"]).round(3))
print("\nPar modele, corr(sel, f1_wf):")
for m in MODELS:
    s = pd.to_numeric(df[f"{m}_sel"], errors="coerce")
    f1 = pd.to_numeric(df[f"{m}_f1"], errors="coerce")
    print(f"  {m:14s} {s.corr(f1):.3f}")

print("\n========== 7. QUALITE vs CONSISTANCE ==========")
q = pd.qcut(df["champ_ic"].rank(method="first"), 4, labels=["Q1 pire", "Q2", "Q3", "Q4 meilleur"])
print(df.groupby(q, observed=True).agg(n=("symbol", "size"), ic=("champ_ic", "mean"),
      f1=("champ_f1", "mean"), ic_std=("champ_ic_std", "mean"),
      dir=("champ_dir", "mean"), lstm_pct=("lstm_is_champ", "mean")).round(4).to_string())

print("\n========== 8. DISTRIBUTION IC CHAMPION ==========")
ic = df["champ_ic"].dropna()
print(ic.describe().round(4).to_string())
print(f"IC>0.05 : {(ic>0.05).sum()} | 0<IC<=0.05 : {((ic>0)&(ic<=0.05)).sum()} | IC<0 : {(ic<0).sum()}")

print("\n========== 9. LISTES UTILES ==========")
print("\nTop 15 F1 champion (vraies WF):")
print(df.nlargest(15, "champ_f1")[["symbol", "champion", "champ_f1", "champ_ic", "champ_dir"]].round(4).to_string(index=False))
print("\nTop 15 IC champion avec F1 correcte:")
print(df.nlargest(15, "champ_ic")[["symbol", "champion", "champ_f1", "champ_ic", "champ_dir"]].round(4).to_string(index=False))

df.to_csv(os.path.join(BATCH, "_per_symbol_analysis.csv"), index=False)
print("\nCSV:", os.path.join(BATCH, "_per_symbol_analysis.csv"))
