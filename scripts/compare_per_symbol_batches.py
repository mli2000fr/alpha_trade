"""Compare en lecture seule deux batchs per-symbol sur leurs symboles communs."""

from __future__ import annotations

import argparse
import json

import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine


QUERY = text("""
SELECT r.batch_id, m.symbol, m.model_name, m.f1_macro, m.f1_short,
       m.f1_flat, m.f1_long, m.directional_accuracy
FROM model_metrics m
JOIN model_training_run r ON r.run_id = m.run_id
WHERE r.batch_id IN (:full_batch, :pilot_batch)
  AND r.status = 'completed'
  AND m.split_name = 'test'
  AND (
       (r.batch_id = :full_batch AND m.horizon = :full_horizon)
       OR (r.batch_id = :pilot_batch AND m.horizon IS NULL)
  )
""")

GOVERNANCE_QUERY = text("""
SELECT r.batch_id, g.symbol, g.model_name, g.test_f1_macro, g.val_f1_macro
FROM model_governance g
JOIN model_training_run r ON r.run_id = g.run_id
WHERE r.batch_id IN (:full_batch, :pilot_batch)
  AND r.status = 'completed'
  AND g.is_selected_model = 1
""")


def _finite(value: object) -> float | None:
    result = float(value)
    return round(result, 6) if pd.notna(result) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-batch", required=True)
    parser.add_argument("--pilot-batch", required=True)
    parser.add_argument("--full-horizon", type=int, default=20)
    args = parser.parse_args()

    with get_sqlalchemy_engine().connect() as connection:
        frame = pd.read_sql_query(
            QUERY,
            connection,
            params={
                "full_batch": args.full_batch,
                "pilot_batch": args.pilot_batch,
                "full_horizon": args.full_horizon,
            },
        )
        governance = pd.read_sql_query(
            GOVERNANCE_QUERY,
            connection,
            params={"full_batch": args.full_batch, "pilot_batch": args.pilot_batch},
        )

    full = frame[frame["batch_id"] == args.full_batch]
    pilot = frame[frame["batch_id"] == args.pilot_batch]
    common = sorted(set(full["symbol"]) & set(pilot["symbol"]))
    full = full[full["symbol"].isin(common)]
    pilot = pilot[pilot["symbol"].isin(common)]

    model_rows: list[dict[str, object]] = []
    for model in sorted(set(full["model_name"]) & set(pilot["model_name"])):
        left = full[full["model_name"] == model].set_index("symbol")
        right = pilot[pilot["model_name"] == model].set_index("symbol")
        paired = left[["f1_macro"]].join(
            right[["f1_macro"]], lsuffix="_full", rsuffix="_pilot", how="inner"
        ).dropna()
        delta = paired["f1_macro_full"] - paired["f1_macro_pilot"]
        model_rows.append({
            "model": model,
            "symbols": len(paired),
            "full_mean": _finite(paired["f1_macro_full"].mean()),
            "pilot_mean": _finite(paired["f1_macro_pilot"].mean()),
            "mean_delta": _finite(delta.mean()),
            "median_delta": _finite(delta.median()),
            "full_win_pct": _finite((delta > 0).mean() * 100),
            "correlation": _finite(paired["f1_macro_full"].corr(paired["f1_macro_pilot"])),
        })

    full_best = full.groupby("symbol")["f1_macro"].max()
    pilot_best = pilot.groupby("symbol")["f1_macro"].max()
    best = pd.concat({"full": full_best, "pilot": pilot_best}, axis=1).dropna()
    full_gov = governance[governance["batch_id"] == args.full_batch].set_index("symbol")
    pilot_gov = governance[governance["batch_id"] == args.pilot_batch].set_index("symbol")
    champions = full_gov.join(pilot_gov, lsuffix="_full", rsuffix="_pilot", how="inner")
    champion_f1 = champions[["test_f1_macro_full", "test_f1_macro_pilot"]].dropna()
    summary = {
        "common_symbols": len(common),
        "models": model_rows,
        "best_model_test_proxy": {
            "full_mean": _finite(best["full"].mean()),
            "pilot_mean": _finite(best["pilot"].mean()),
            "mean_delta": _finite((best["full"] - best["pilot"]).mean()),
            "correlation": _finite(best["full"].corr(best["pilot"])),
            "full_ge_033": int((best["full"] >= 0.33).sum()),
            "pilot_ge_033": int((best["pilot"] >= 0.33).sum()),
            "full_ge_040": int((best["full"] >= 0.40).sum()),
            "pilot_ge_040": int((best["pilot"] >= 0.40).sum()),
            "both_ge_040": int(((best["full"] >= 0.40) & (best["pilot"] >= 0.40)).sum()),
            "either_ge_040": int(((best["full"] >= 0.40) | (best["pilot"] >= 0.40)).sum()),
            "full_ge_040_caught_by_pilot_ge_033": int(
                ((best["full"] >= 0.40) & (best["pilot"] >= 0.33)).sum()
            ),
            "full_ge_040_caught_by_pilot_ge_030": int(
                ((best["full"] >= 0.40) & (best["pilot"] >= 0.30)).sum()
            ),
        },
        "selected_champions": {
            "symbols": len(champions),
            "same_model_pct": _finite(
                (champions["model_name_full"] == champions["model_name_pilot"]).mean() * 100
            ),
            "full_mean": _finite(champion_f1["test_f1_macro_full"].mean()),
            "pilot_mean": _finite(champion_f1["test_f1_macro_pilot"].mean()),
            "correlation": _finite(
                champion_f1["test_f1_macro_full"].corr(champion_f1["test_f1_macro_pilot"])
            ),
            "full_ge_040": int((champion_f1["test_f1_macro_full"] >= 0.40).sum()),
            "pilot_ge_040": int((champion_f1["test_f1_macro_pilot"] >= 0.40).sum()),
            "both_ge_040": int(
                ((champion_f1["test_f1_macro_full"] >= 0.40)
                 & (champion_f1["test_f1_macro_pilot"] >= 0.40)).sum()
            ),
            "full_ge_040_caught_by_pilot_ge_033": int(
                ((champion_f1["test_f1_macro_full"] >= 0.40)
                 & (champion_f1["test_f1_macro_pilot"] >= 0.33)).sum()
            ),
            "full_ge_040_caught_by_pilot_ge_030": int(
                ((champion_f1["test_f1_macro_full"] >= 0.40)
                 & (champion_f1["test_f1_macro_pilot"] >= 0.30)).sum()
            ),
        },
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
