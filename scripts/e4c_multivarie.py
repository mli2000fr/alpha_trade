"""E4-C v2 — Test multivarié final des sources PIT (pool Oracle Extreme 400).

Même méthodologie que E4-C v1, moteur optimisé :
  - HistGradientBoosting (sklearn, parallélisé) au lieu de GradientBoosting séquentiel.
  - 30 répliques de permutation (au lieu de 60) — distribution null suffisante.
  - Logging de progression par phase et par réplique.

Compare PRICE-only vs ORTHOGONAL-only vs ALL dans EXACTEMENT le même WF causal
(folds annuels identiques à l'Oracle : fold_start 2022..2026, test = année du
fold, train = tout le passé). AUCUNE optimisation P&L, AUCUN tuning : hyperparams
par défaut fixes pour les 3 configs.

Target = UP/DOWN ABSOLU H20 (future_return > 0 vs < 0) dans le pool Oracle
Extreme OOS restreint aux 400 symboles.

Gates FIXÉES avant entraînement :
  G1. AUC ALL >= 0.55
  G2. AUC > 0.52 sur >= 4/5 périodes annuelles
  G3. pas d'effondrement 2025/2026 (AUC 2025 >= 0.52 et AUC 2026 >= 0.52)
  G4. amélioration significative vs permutation null (p_perm < 0.05)

Feature sets :
  PRICE      : 179 features OHLCV/régime du e2_feature_dataset (PIT)
  ORTHOGONAL : short volume (B2A) + short interest (B2B) + news (B2C) + fundamentals (B2D)
  ALL        : PRICE + ORTHOGONAL
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.ensemble import HistGradientBoostingClassifier

DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
OOS = Path("artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet")
TICKET = Path("config/ticket_recherche.txt")
OUT = Path("artifacts/models/oracle/e4c_multivarie_diag.md")

A = Path("artifacts/models/oracle/e4b2a_short_volume_features.parquet")
B = Path("artifacts/models/oracle/e4b2b_short_interest_features.parquet")
C = Path("artifacts/models/oracle/e4b2c_news_features.parquet")
D = Path("artifacts/models/oracle/e4b2d_fundamentals_features.parquet")

META = {"date", "symbol", "oracle_extreme10", "oracle_pct_rank", "oracle_decile",
        "future_return", "daily_return", "global_rank_20", "oracle_available_date"}

PERIODS = ["2023", "2024", "2025", "2026"]  # 2022 = warmup (pas de train antérieur)
N_PERM = 30
RNG = np.random.default_rng(7)

MODEL = dict(max_iter=120, learning_rate=0.1, max_leaf_nodes=15,
             min_samples_leaf=40, l2_regularization=1.0, random_state=42)


def _auc(y, s):
    m = np.isfinite(s) & np.isfinite(y)
    y, s = y[m], s[m]
    if len(y) < 20 or len(np.unique(y)) < 2 or np.all(s == s[0]):
        return float("nan")
    try:
        u, _ = mannwhitneyu(s[y == 1], s[y == 0], alternative="two-sided")
        return float(u / (np.sum(y == 1) * np.sum(y == 0)))
    except ValueError:
        return float("nan")


def run_wf(feats, pool, permute=False, log=False, tag=""):
    results = {}
    for per in PERIODS:
        test_start = pd.Timestamp(f"{per}-01-01")
        train = pool[pool["date"] < test_start]
        test = pool[pool["date"] >= test_start]
        if len(train) < 2000 or len(test) < 1000:
            continue
        Xtr = train[feats].fillna(0.0)
        ytr = train["up"].to_numpy()
        Xte = test[feats].fillna(0.0)
        yte = test["up"].to_numpy()
        if permute:
            ytr = RNG.permutation(ytr)
        clf = HistGradientBoostingClassifier(**MODEL)
        clf.fit(Xtr, ytr)
        proba = clf.predict_proba(Xte)[:, 1]
        results[per] = _auc(yte, proba)
    if log:
        print(f"  [done] {tag} permute={permute}: " +
              " ".join(f"{p}={results.get(p, float('nan')):.3f}" for p in PERIODS), flush=True)
    return results


def main() -> None:
    t0 = time.time()
    ticket = sorted({s.strip().upper() for s in TICKET.read_text(encoding="utf-8").split(",") if s.strip()})

    # --- features PRICE ---
    e2 = pd.read_parquet(DATA)
    e2["date"] = pd.to_datetime(e2["date"]).dt.normalize()
    e2["symbol"] = e2["symbol"].astype(str).str.upper()
    price_feats = [c for c in e2.columns if c not in META and e2[c].dtype in ("float64", "float32", "int64")]
    print(f"PRICE features: {len(price_feats)}")

    # --- features ORTHOGONALES (avec préfixe a_/b_/c_/d_ pour éviter collisions) ---
    a = pd.read_parquet(A); b = pd.read_parquet(B); c = pd.read_parquet(C); d = pd.read_parquet(D)
    for df in (a, b, c, d):
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        df["symbol"] = df["symbol"].astype(str).str.upper()
    base = e2[["date", "symbol"]]
    tags = {"a": a, "b": b, "c": c, "d": d}
    ortho_feats = []
    for t, df in tags.items():
        cols = [f for f in df.columns if f not in ("date", "symbol")]
        base = base.merge(df[["date", "symbol"] + cols].rename(columns={f: f"{t}_{f}" for f in cols}),
                          on=["date", "symbol"], how="left")
        ortho_feats += [f"{t}_{f}" for f in cols]
    print(f"ORTHOGONAL features: {len(ortho_feats)}", flush=True)

    # --- pool OOS + labels ---
    oos = pd.read_parquet(OOS)
    oos["date"] = pd.to_datetime(oos["date"]).dt.normalize()
    oos["symbol"] = oos["symbol"].astype(str).str.upper()
    m = e2[["date", "symbol", "future_return", "oracle_extreme10"]].merge(
        oos[["date", "symbol", "fold_start"]], on=["date", "symbol"], how="inner")
    m = m[(m["oracle_extreme10"] == 1) & m["symbol"].isin(set(ticket))].copy()
    m["up"] = (m["future_return"] > 0).astype(int)
    m = m[m["future_return"] != 0].copy()
    print(f"pool Extreme 400: {len(m):,} | UP={int((m['up']==1).sum()):,} DOWN={int((m['up']==0).sum()):,}", flush=True)

    # fusion des features price + orthogonales
    m = m.merge(e2[["date", "symbol"] + price_feats], on=["date", "symbol"], how="left")
    m = m.merge(base[["date", "symbol"] + ortho_feats], on=["date", "symbol"], how="left")

    configs = {"PRICE": price_feats, "ORTHOGONAL": ortho_feats, "ALL": price_feats + ortho_feats}

    md: list[str] = [
        "# E4-C — Test multivarié final des sources PIT (pool Oracle Extreme 400)",
        "",
        f"Population : pool Oracle Extreme restreint aux {len(ticket)} symboles. N={len(m):,} "
        f"(UP {int((m['up']==1).sum()):,} / DOWN {int((m['up']==0).sum()):,}).",
        "WF causal IDENTIQUE à l'Oracle (folds annuels, train = tout le passé, test = année du fold).",
        "2022 = warmup (pas de train antérieur) -> périodes testables 2023..2026.",
        "Modèle : HistGradientBoosting FIXE (max_iter=120, lr=0.1, max_leaf_nodes=15, min_leaf=40, l2=1.0).",
        "v2 optimisée : 30 répliques de permutation (vs 60), moteur parallélisé.",
        "AUCUNE optimisation P&L, AUCUN tuning. Target = UP/DOWN absolu H20.",
        "",
        f"PRICE features ({len(price_feats)}).",
        f"ORTHOGONAL features ({len(ortho_feats)}).",
        "",
        "## Gates (fixées AVANT entraînement)",
        "",
        "| gate | critère |",
        "|---|---|",
        "| G1 | AUC ALL >= 0.55 |",
        "| G2 | AUC > 0.52 sur >= 4/5 périodes annuelles |",
        "| G3 | pas d'effondrement 2025/2026 (AUC 2025>=0.52 ET AUC 2026>=0.52) |",
        "| G4 | amélioration significative vs permutation null (p_perm < 0.05) |",
        "",
    ]

    # --- WF réel par config ---
    print("== WF réel ==", flush=True)
    md.append("## Walk-forward OOS (AUC par année)")
    md.append("")
    md.append("| config | " + " | ".join(PERIODS) + " | ALL |")
    md.append("|---|" + "---|" * len(PERIODS) + "---|")
    wf_results = {}
    for name, feats in configs.items():
        res = run_wf(feats, m, log=True, tag=name)
        wf_results[name] = res
        vals = [res[p] for p in PERIODS if p in res and np.isfinite(res[p])]
        all_auc = float(np.mean(vals)) if vals else float("nan")
        row = " | ".join(f"{res.get(p, float('nan')):.3f}" for p in PERIODS)
        md.append(f"| {name} | {row} | {all_auc:.3f} |")
    md.append("")

    # --- permutation null par config ---
    print("== Permutation null (30 répliques) ==", flush=True)
    md.append("## Permutation null (30 répliques, labels permutés, même WF)")
    md.append("")
    md.append("| config | AUC ALL obs | mean null | p95 null | p99 null | p_perm |")
    md.append("|---|---|---|---|---|---|")
    perm_results = {}
    for name, feats in configs.items():
        nulls = []
        for rep in range(N_PERM):
            r = run_wf(feats, m, permute=True)
            vals = [r[p] for p in PERIODS if p in r and np.isfinite(r[p])]
            if vals:
                nulls.append(float(np.mean(vals)))
            if (rep + 1) % 10 == 0:
                print(f"  {name} perm {rep+1}/{N_PERM}", flush=True)
        nulls = np.array(nulls)
        obs_vals = [wf_results[name][p] for p in PERIODS if p in wf_results[name] and np.isfinite(wf_results[name][p])]
        obs = float(np.mean(obs_vals)) if obs_vals else float("nan")
        p_perm = float(np.mean(nulls >= obs)) if len(nulls) else float("nan")
        perm_results[name] = p_perm
        md.append(f"| {name} | {obs:.3f} | {nulls.mean():.3f} | {np.percentile(nulls,95):.3f} | "
                  f"{np.percentile(nulls,99):.3f} | {p_perm:.3f} |")
    md.append("")

    # --- gates ---
    print("== Verdict ==", flush=True)
    md.append("## Verdict E4-C")
    md.append("")
    for name in configs:
        res = wf_results[name]
        all_obs = [res[p] for p in PERIODS if p in res and np.isfinite(res[p])]
        all_auc = float(np.mean(all_obs)) if all_obs else float("nan")
        g1 = all_auc >= 0.55
        g2 = sum(1 for p in PERIODS if p in res and res[p] > 0.52) >= 4
        g3 = ("2025" in res and res["2025"] >= 0.52) and ("2026" in res and res["2026"] >= 0.52)
        g4 = perm_results.get(name, 1.0) < 0.05
        md.append(f"### {name}")
        md.append("")
        md.append(f"| gate | résultat |")
        md.append("|---|---|")
        md.append(f"| G1 (ALL>=0.55) | ALL={all_auc:.3f} -> {'OK' if g1 else 'FAIL'} |")
        md.append(f"| G2 (>=4/5 per.>0.52) | " + ", ".join(f"{p}={res[p]:.3f}" for p in PERIODS if p in res) + f" -> {'OK' if g2 else 'FAIL'} |")
        md.append(f"| G3 (2025/2026 pas d'effondrement) | 2025={res.get('2025', float('nan')):.3f} 2026={res.get('2026', float('nan')):.3f} -> {'OK' if g3 else 'FAIL'} |")
        md.append(f"| G4 (p_perm<0.05) | p_perm={perm_results.get(name, float('nan')):.3f} -> {'OK' if g4 else 'FAIL'} |")
        md.append(f"| **VERDICT** | **{'PASS' if (g1 and g2 and g3 and g4) else 'FAIL'}** |")
        md.append("")

    md.append("### Décision")
    md.append("")
    all_pass = all((np.mean([wf_results[n][p] for p in PERIODS if p in wf_results[n] and np.isfinite(wf_results[n][p])]) >= 0.55)
                   and (sum(1 for p in PERIODS if p in wf_results[n] and wf_results[n][p] > 0.52) >= 4)
                   and (wf_results[n].get("2025", 0) >= 0.52 and wf_results[n].get("2026", 0) >= 0.52)
                   and perm_results.get(n, 1.0) < 0.05 for n in configs)
    if all_pass:
        md.append("**PASS : les sources orthogonales améliorent significativement la direction UP/DOWN dans le pool Extreme.**")
        md.append("On peut envisager d'intégrer ces sources (avec prudence) dans un pipeline directionnel, puis éventuellement les options (E4-B3).")
    else:
        md.append("**FAIL : AUCUNE config ne passe les gates fixées. Les sources gratuites testées (price, short volume, short interest, news, fundamentals) ne permettent pas de prédire le signe UP/DOWN dans le pool Extreme.**")
        md.append("Conforme au plan : fermer les sources gratuites et passer à une information réellement orthogonale — Options/IV/skew en priorité (E4-B3).")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"\nrapport: {OUT} | durée {(time.time()-t0)/60:.1f} min", flush=True)
    for name, res in wf_results.items():
        vals = [res[p] for p in PERIODS if p in res and np.isfinite(res[p])]
        print(f"  {name}: " + " ".join(f"{p}={res[p]:.3f}" for p in PERIODS if p in res) +
              f" | ALL={np.mean(vals):.3f} | p_perm={perm_results[name]:.3f}", flush=True)


if __name__ == "__main__":
    main()
