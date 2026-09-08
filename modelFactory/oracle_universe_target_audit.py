"""P0c: compare des cibles Oracle sur le meme panel dynamique P0b.

L'audit est research-only et ne modifie ni tables, ni batchs, ni profils ML.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine


def _rank(frame: pd.DataFrame, score: str, groups: list[str]) -> pd.Series:
    return frame.groupby(groups, observed=True)[score].rank(method="max", pct=True)


def _top_share(counts: pd.Series, fraction: float = 0.20) -> float:
    values = pd.to_numeric(counts, errors="coerce").fillna(0).sort_values(ascending=False)
    n = max(1, math.ceil(len(values) * fraction))
    return float(values.head(n).sum() / values.sum()) if values.sum() else 0.0


def _variant_metrics(frame: pd.DataFrame, prefix: str, raw_extreme: pd.Series) -> dict[str, Any]:
    valid = frame[f"{prefix}_pct_rank"].notna()
    selected = frame[f"{prefix}_extreme"].astype("boolean").fillna(False).astype(bool) & valid
    rest = ~selected & valid
    symbol_counts = frame.loc[selected].groupby("symbol").size()
    all_counts = symbol_counts.reindex(sorted(frame.loc[valid, "symbol"].unique()), fill_value=0)
    raw_abs = frame["future_return"].abs()
    per_symbol = frame.loc[valid, ["symbol", "vol20"]].copy()
    per_symbol["selected"] = selected.loc[valid].to_numpy()
    rates = per_symbol.groupby("symbol").agg(
        tail_frequency=("selected", "mean"), median_vol20=("vol20", "median")
    ).dropna()
    yearly = frame.loc[valid, ["date", "future_return"]].copy()
    yearly["selected"] = selected.loc[valid].to_numpy()
    yearly["year"] = yearly["date"].dt.year
    yearly_metrics = []
    for year, part in yearly.groupby("year"):
        tail = part.loc[part["selected"], "future_return"].abs()
        other = part.loc[~part["selected"], "future_return"].abs()
        yearly_metrics.append({
            "year": int(year), "tail_abs_mean": float(tail.mean()),
            "rest_abs_mean": float(other.mean()),
            "lift": float(tail.mean() - other.mean()),
        })
    raw_selected = raw_extreme & valid
    union = selected | raw_selected
    return {
        "rows": int(valid.sum()),
        "coverage": float(valid.mean()),
        "symbols": int(frame.loc[valid, "symbol"].nunique()),
        "tail_rows": int(selected.sum()),
        "tail_rate": float(selected.loc[valid].mean()),
        "tail_abs_return_mean": float(raw_abs.loc[selected].mean()),
        "tail_abs_return_median": float(raw_abs.loc[selected].median()),
        "rest_abs_return_mean": float(raw_abs.loc[rest].mean()),
        "amplitude_lift": float(raw_abs.loc[selected].mean() - raw_abs.loc[rest].mean()),
        "amplitude_lift_ratio": float(raw_abs.loc[selected].mean() / raw_abs.loc[rest].mean()),
        "top20_symbol_tail_share": _top_share(all_counts),
        "tail_frequency_vs_vol20_spearman": float(rates.corr(method="spearman").iloc[0, 1]),
        "raw_tail_jaccard": float((selected & raw_selected).sum() / union.sum()) if union.sum() else None,
        "positive_lift_years": int(sum(row["lift"] > 0 for row in yearly_metrics)),
        "evaluated_years": len(yearly_metrics),
        "yearly": yearly_metrics,
    }


def run(labels_path: Path, output_root: Path, min_sector_members: int = 20) -> Path:
    labels = pd.read_parquet(labels_path)
    required = {"date", "symbol", "future_return", "oracle_pct_rank", "oracle_decile", "oracle_extreme10"}
    missing = required.difference(labels.columns)
    if missing:
        raise ValueError(f"Labels P0b incomplets: {sorted(missing)}")
    labels["date"] = pd.to_datetime(labels["date"], errors="coerce").dt.normalize()
    labels["symbol"] = labels["symbol"].astype(str).str.upper().str.strip()
    labels["future_return"] = pd.to_numeric(labels["future_return"], errors="coerce")
    symbols = sorted(labels["symbol"].unique())
    load_start = labels["date"].min() - pd.Timedelta(days=60)
    load_end = labels["date"].max()
    engine = get_sqlalchemy_engine()
    query = text(
        "SELECT symbol,`date`,CAST(COALESCE(adj_close,close) AS DOUBLE) close,"
        "COALESCE(is_filled,0) is_filled FROM stock_bars_daily "
        "WHERE symbol IN :symbols AND `date` BETWEEN :start AND :end ORDER BY symbol,`date`"
    ).bindparams(bindparam("symbols", expanding=True))
    bars = pd.read_sql(query, engine, params={
        "symbols": symbols, "start": load_start.date(), "end": load_end.date()
    }, parse_dates=["date"])
    bars = bars.sort_values(["symbol", "date"])
    bars["close"] = pd.to_numeric(bars["close"], errors="coerce")
    bars["log_return"] = bars.groupby("symbol")["close"].transform(
        lambda x: np.log(x).diff()
    )
    bars["vol20"] = bars.groupby("symbol")["log_return"].transform(
        lambda x: x.rolling(20, min_periods=20).std()
    )
    bars.loc[pd.to_numeric(bars["is_filled"], errors="coerce").eq(1), "vol20"] = np.nan
    labels = labels.merge(bars[["date", "symbol", "vol20"]], on=["date", "symbol"], how="left")
    metadata_query = text(
        "SELECT symbol,COALESCE(provider_sector,sector) sector FROM stock_metadata WHERE symbol IN :symbols"
    ).bindparams(bindparam("symbols", expanding=True))
    metadata = pd.read_sql(metadata_query, engine, params={"symbols": symbols})
    metadata["symbol"] = metadata["symbol"].astype(str).str.upper()
    labels = labels.merge(metadata, on="symbol", how="left")
    labels["sector"] = labels["sector"].fillna("Unknown")

    labels["raw_pct_rank"] = pd.to_numeric(labels["oracle_pct_rank"], errors="coerce")
    labels["vol_scaled_score"] = labels["future_return"] / labels["vol20"].clip(lower=0.0025)
    labels["vol_scaled_pct_rank"] = _rank(labels, "vol_scaled_score", ["date"])
    labels["vol_percentile"] = _rank(labels, "vol20", ["date"])
    labels["vol_quintile"] = np.ceil(labels["vol_percentile"] * 5).clip(1, 5).astype("Int8")
    labels["vol_strata_pct_rank"] = _rank(labels, "future_return", ["date", "vol_quintile"])
    sector_size = labels.groupby(["date", "sector"], observed=True)["symbol"].transform("size")
    labels["sector_eligible"] = sector_size.ge(min_sector_members) & labels["sector"].ne("Unknown")
    labels["sector_pct_rank"] = _rank(
        labels.where(labels["sector_eligible"]), "future_return", ["date", "sector"]
    )
    for prefix in ("raw", "vol_scaled", "vol_strata", "sector"):
        rank = labels[f"{prefix}_pct_rank"]
        labels[f"{prefix}_decile"] = np.ceil(rank * 10).clip(1, 10).astype("Int8")
        labels[f"{prefix}_extreme"] = ((rank <= 0.10) | (rank >= 0.90)).where(rank.notna())

    raw_extreme = labels["raw_extreme"].astype("boolean").fillna(False).astype(bool)
    variants = {
        name: _variant_metrics(labels, name, raw_extreme)
        for name in ("raw", "vol_scaled", "vol_strata", "sector")
    }
    raw = variants["raw"]
    gates = {}
    for name, metrics in variants.items():
        gates[name] = {
            "coverage_ge_95pct": metrics["coverage"] >= 0.95,
            "concentration_reduction_ge_15pct": metrics["top20_symbol_tail_share"] <= raw["top20_symbol_tail_share"] * 0.85,
            "raw_amplitude_retention_ge_90pct": metrics["tail_abs_return_mean"] >= raw["tail_abs_return_mean"] * 0.90,
            "positive_lift_years_ge_8": metrics["positive_lift_years"] >= 8,
            "current_sector_metadata_is_pit": False if name == "sector" else None,
        }
        gates[name]["promotable"] = all(
            value for key, value in gates[name].items()
            if value is not None and key != "current_sector_metadata_is_pit"
        ) and name != "sector"
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": str(labels_path),
        "contract": {
            "horizon": 20, "volatility": "20_session_log_return_std_known_at_J",
            "vol_floor": 0.0025, "vol_strata": 5, "min_sector_members": min_sector_members,
            "sector_warning": "stock_metadata sector is current, not certified PIT",
        },
        "variants": variants,
        "gates": gates,
    }
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    output = output_root / f"p0c-{stamp}"
    output.mkdir(parents=True, exist_ok=False)
    keep = ["date", "symbol", "future_return", "vol20", "vol_quintile", "sector"]
    for prefix in ("raw", "vol_scaled", "vol_strata", "sector"):
        keep += [f"{prefix}_pct_rank", f"{prefix}_decile", f"{prefix}_extreme"]
    labels[keep].to_parquet(output / "target_assignments.parquet", index=False)
    rows = []
    for name, metrics in variants.items():
        rows.append({key: value for key, value in {"variant": name, **metrics}.items() if key != "yearly"})
    pd.DataFrame(rows).to_csv(output / "variant_summary.csv", index=False)
    year_rows = [{"variant": name, **row} for name, metrics in variants.items() for row in metrics["yearly"]]
    pd.DataFrame(year_rows).to_csv(output / "yearly_summary.csv", index=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = ["# P0c — comparaison des cibles Oracle", "", "| Variante | Couverture | Top20 symboles → tails | Abs. tail moyen | Lift tail/rest | Jaccard brut | Années lift+ | Promouvable |", "|---|---:|---:|---:|---:|---:|---:|---|"]
    for name, metrics in variants.items():
        lines.append(
            f"| {name} | {metrics['coverage']:.1%} | {metrics['top20_symbol_tail_share']:.1%} | "
            f"{metrics['tail_abs_return_mean']:.2%} | {metrics['amplitude_lift_ratio']:.2f}x | "
            f"{metrics['raw_tail_jaccard']:.1%} | {metrics['positive_lift_years']}/{metrics['evaluated_years']} | "
            f"{gates[name]['promotable']} |"
        )
    lines += ["", "Le rang sectoriel est diagnostique uniquement : le secteur courant n'est pas une donnée PIT historique certifiée."]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit P0c des cibles Oracle")
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/research/oracle_universe_target_audit"))
    parser.add_argument("--min-sector-members", type=int, default=20)
    args = parser.parse_args()
    run(args.labels, args.output_root, args.min_sector_members)


if __name__ == "__main__":
    main()
