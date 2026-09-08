"""Audit P0 reproductible d'un univers statique utilise par l'Oracle.

La base est consultee en lecture seule. Les resultats sont ecrits sous
``artifacts/research/oracle_universe_audit``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from common.universe_files import load_universe_file_symbols
from database.connection import get_sqlalchemy_engine

OUTPUT_ROOT = Path("artifacts/research/oracle_universe_audit")


def parse_symbols(raw: str | None) -> list[str]:
    return sorted({value.strip().upper() for value in str(raw or "").split(",") if value.strip()})


def source_path(source: str) -> Path | None:
    prefix = "universe-file:"
    return Path("config/univers") / source[len(prefix):] if source.startswith(prefix) else None


def _read_symbols(engine: Any, sql: str, symbols: list[str], **params: Any) -> pd.DataFrame:
    query = text(sql).bindparams(bindparam("symbols", expanding=True))
    return pd.read_sql(query, engine, params={"symbols": symbols, **params})


def _concentration(values: pd.Series) -> dict[str, float | int]:
    counts = pd.to_numeric(values, errors="coerce").fillna(0).sort_values(ascending=False)
    total = float(counts.sum())
    result: dict[str, float | int] = {"events": int(total), "symbols": int(len(counts))}
    for pct in (10, 20, 30):
        n = max(1, math.ceil(len(counts) * pct / 100)) if len(counts) else 0
        result[f"top_{pct}pct_symbols"] = n
        result[f"top_{pct}pct_event_share"] = float(counts.iloc[:n].sum() / total) if total else 0.0
    result["hhi"] = float(np.square(counts / total).sum()) if total else 0.0
    return result


def _safe(value: Any) -> Any:
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    return value


def _pct(value: Any) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{float(value):.1%}"


def run(batch_id: str, output_root: Path = OUTPUT_ROOT) -> Path:
    engine = get_sqlalchemy_engine()
    batch_query = text(
        "SELECT batch_id,status,symbol_source,universe_date,training_start_date,"
        "training_end_date,started_at,finished_at,comment,symbols "
        "FROM model_training_batch WHERE batch_id=:batch_id"
    )
    with engine.connect() as connection:
        batch_row = connection.execute(batch_query, {"batch_id": batch_id}).mappings().first()
    if batch_row is None:
        raise ValueError(f"Batch introuvable: {batch_id}")
    batch = dict(batch_row)
    persisted = parse_symbols(batch.get("symbols"))
    path = source_path(str(batch.get("symbol_source") or ""))
    current = load_universe_file_symbols(str(batch["symbol_source"])) if path and path.exists() else []
    symbols = persisted or sorted(set(current))
    if not symbols:
        raise ValueError("Le batch ne contient aucune liste de symboles auditable.")
    start, end = batch["training_start_date"], batch["training_end_date"]

    coverage = _read_symbols(
        engine,
        "SELECT symbol,MIN(`date`) first_bar,MAX(`date`) last_bar,COUNT(*) all_sessions,"
        "SUM(COALESCE(is_filled,0)=1) filled_sessions FROM stock_bars_daily "
        "WHERE symbol IN :symbols GROUP BY symbol",
        symbols,
    )
    bars = _read_symbols(
        engine,
        "SELECT symbol,`date`,COALESCE(adj_close,close) close,high,low,volume,daily_return,is_filled "
        "FROM stock_bars_daily WHERE symbol IN :symbols AND `date` BETWEEN :start AND :end "
        "ORDER BY symbol,`date`",
        sorted(set(symbols) | {"SPY"}), start=start, end=end,
    )
    metadata = _read_symbols(
        engine,
        "SELECT symbol,company_name,exchange,asset_class,status,tradable,bars_available,"
        "history_status,COALESCE(provider_sector,sector) sector,market_cap,data_source,"
        "market_cap_refreshed_at,metadata_synced_at FROM stock_metadata WHERE symbol IN :symbols",
        symbols,
    )
    labels = _read_symbols(
        engine,
        "SELECT prediction_date,symbol,horizon,oracle_decile,oracle_extreme10,target_quality_valid "
        "FROM global_oracle_labels WHERE batch_id=:batch_id AND symbol IN :symbols "
        "AND prediction_date BETWEEN :start AND :end",
        symbols, batch_id=batch_id, start=start, end=end,
    )
    pit_query = text(
        "SELECT r.snapshot_date AS `date`,h.symbol,h.data_quality_grade FROM tradable_universe_runs r "
        "JOIN tradable_universe_history h ON h.universe_run_id=r.universe_run_id "
        "WHERE r.snapshot_date BETWEEN :start AND :end AND r.status='completed' "
        "AND r.is_canonical=1 AND r.rows_written=r.rows_expected AND h.is_tradable=1"
    )
    pit = pd.read_sql(pit_query, engine, params={"start": start, "end": end})

    bars["date"] = pd.to_datetime(bars["date"], errors="coerce").dt.normalize()
    for column in ("close", "high", "low", "volume", "daily_return"):
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    bars["computed_return"] = bars.groupby("symbol")["close"].pct_change(fill_method=None)
    bars["return_used"] = bars["daily_return"].where(bars["daily_return"].notna(), bars["computed_return"])
    bars["range_pct"] = (bars["high"] - bars["low"]) / bars["close"].replace(0, np.nan)
    bars["dollar_volume"] = bars["close"] * bars["volume"]
    spy = bars[bars["symbol"].eq("SPY")][["date", "return_used"]].rename(columns={"return_used": "spy_return"})
    actual = bars[bars["symbol"].isin(symbols)].copy()
    benchmark_sessions = int(spy["date"].nunique())
    bar_metrics = actual.groupby("symbol").agg(
        training_sessions=("date", "nunique"),
        realized_vol_annual=("return_used", lambda x: float(x.std() * math.sqrt(252))),
        median_range_pct=("range_pct", "median"),
        median_dollar_volume=("dollar_volume", "median"),
        filled_training_sessions=("is_filled", lambda x: int(pd.to_numeric(x, errors="coerce").fillna(0).eq(1).sum())),
    ).reset_index()
    bar_metrics["training_coverage_ratio"] = bar_metrics["training_sessions"] / max(benchmark_sessions, 1)
    pairs = actual[["symbol", "date", "return_used"]].merge(spy, on="date", how="inner").dropna()
    beta_rows = []
    for symbol, part in pairs.groupby("symbol"):
        variance = float(part["spy_return"].var())
        beta_rows.append({
            "symbol": symbol,
            "beta_vs_spy": float(part[["return_used", "spy_return"]].cov().iloc[0, 1] / variance) if variance else np.nan,
            "beta_sessions": int(len(part)),
        })
    valid = labels[pd.to_numeric(labels["target_quality_valid"], errors="coerce").fillna(1).eq(1)].copy()
    label_metrics = valid.groupby("symbol").agg(
        valid_labels=("oracle_decile", "count"),
        d1_count=("oracle_decile", lambda x: int(pd.to_numeric(x, errors="coerce").eq(1).sum())),
        d10_count=("oracle_decile", lambda x: int(pd.to_numeric(x, errors="coerce").eq(10).sum())),
        extreme_count=("oracle_extreme10", lambda x: int(pd.to_numeric(x, errors="coerce").eq(1).sum())),
    ).reset_index()
    for name in ("d1", "d10", "extreme"):
        label_metrics[f"{name}_frequency"] = label_metrics[f"{name}_count"] / label_metrics["valid_labels"].replace(0, np.nan)

    audit = pd.DataFrame({"symbol": symbols})
    for frame in (coverage, bar_metrics, pd.DataFrame(beta_rows), metadata, label_metrics):
        audit = audit.merge(frame, on="symbol", how="left")
    audit["first_bar"] = pd.to_datetime(audit["first_bar"], errors="coerce")
    audit["last_bar"] = pd.to_datetime(audit["last_bar"], errors="coerce")
    audit["active_at_training_start_proxy"] = audit["first_bar"].le(pd.Timestamp(start))
    audit["first_bar_after_training_start"] = audit["first_bar"].gt(pd.Timestamp(start))
    audit["first_bar_after_2020"] = audit["first_bar"].ge(pd.Timestamp("2020-01-01"))
    audit["first_bar_after_2022"] = audit["first_bar"].ge(pd.Timestamp("2022-01-01"))
    audit["market_cap_band_current"] = pd.cut(
        pd.to_numeric(audit["market_cap"], errors="coerce"),
        [-np.inf, 500e6, 2e9, 10e9, np.inf],
        labels=["mini_<500M", "small_500M_2B", "mid_2B_10B", "large_>=10B"],
    ).astype("string")

    tail: dict[str, Any] = {
        "extreme": _concentration(audit["extreme_count"]),
        "d1": _concentration(audit["d1_count"]),
        "d10": _concentration(audit["d10_count"]),
        "correlations": {},
    }
    for feature in ("realized_vol_annual", "median_range_pct", "beta_vs_spy", "median_dollar_volume"):
        pair = audit[["extreme_frequency", feature]].replace([np.inf, -np.inf], np.nan).dropna()
        tail["correlations"][f"extreme_frequency_vs_{feature}_spearman"] = (
            float(pair.corr(method="spearman").iloc[0, 1]) if len(pair) >= 3 else None
        )

    valid["date"] = pd.to_datetime(valid["prediction_date"], errors="coerce").dt.normalize()
    pit["date"] = pd.to_datetime(pit["date"], errors="coerce").dt.normalize()
    static_sets = valid.groupby("date")["symbol"].agg(lambda x: set(map(str, x)))
    pit_sets = pit.groupby("date")["symbol"].agg(lambda x: set(map(str, x)))
    pit_grades = pit.groupby("date")["data_quality_grade"].agg(lambda x: ",".join(sorted(set(map(str, x)))))
    overlap_rows = []
    static_set = set(symbols)
    for date_value in sorted(set(static_sets.index) & set(pit_sets.index)):
        left, right = static_sets[date_value], pit_sets[date_value]
        overlap_rows.append({
            "date": date_value,
            "static_label_universe": len(left),
            "pit_tradable_universe": len(right),
            "intersection": len(left & right),
            "static_not_pit": len(left - right),
            "pit_not_static": len(right - static_set),
            "jaccard": len(left & right) / len(left | right) if left | right else np.nan,
            "static_covered_by_pit": len(left & right) / len(left) if left else np.nan,
            "pit_quality": pit_grades.get(date_value),
        })
    overlap = pd.DataFrame(overlap_rows)
    coverage_summary = {
        "symbols": len(symbols),
        "symbols_with_bars": int(audit["first_bar"].notna().sum()),
        "active_at_training_start_proxy": int(audit["active_at_training_start_proxy"].fillna(False).sum()),
        "first_bar_after_training_start": int(audit["first_bar_after_training_start"].fillna(False).sum()),
        "first_bar_after_2020": int(audit["first_bar_after_2020"].fillna(False).sum()),
        "first_bar_after_2022": int(audit["first_bar_after_2022"].fillna(False).sum()),
        "coverage_ge_95pct": int(audit["training_coverage_ratio"].ge(0.95).sum()),
        "current_mini_cap": int(audit["market_cap_band_current"].eq("mini_<500M").sum()),
        "current_small_cap": int(audit["market_cap_band_current"].eq("small_500M_2B").sum()),
        "metadata_missing": int(audit["company_name"].isna().sum()),
        "benchmark_sessions": benchmark_sessions,
    }
    pit_summary = {
        "comparison_dates": int(len(overlap)),
        "pit_distinct_symbols": int(pit["symbol"].nunique()),
        "pit_symbols_outside_static": int(len(set(pit["symbol"]) - static_set)),
        "median_static_label_universe": float(overlap["static_label_universe"].median()) if len(overlap) else None,
        "median_pit_tradable_universe": float(overlap["pit_tradable_universe"].median()) if len(overlap) else None,
        "median_jaccard": float(overlap["jaccard"].median()) if len(overlap) else None,
        "median_static_covered_by_pit": float(overlap["static_covered_by_pit"].median()) if len(overlap) else None,
        "degraded_date_share": float(overlap["pit_quality"].fillna("").str.contains("degraded").mean()) if len(overlap) else None,
    }
    batch_summary = {key: _safe(value) for key, value in batch.items() if key != "symbols"}
    batch_summary.update({
        "persisted_symbol_count": len(persisted),
        "current_source_symbol_count": len(current),
        "source_file": str(path) if path else None,
        "source_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path and path.exists() else None,
        "source_file_matches_persisted": bool(current and set(current) == set(persisted)),
    })
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "batch": batch_summary,
        "coverage": coverage_summary,
        "tail": tail,
        "pit": pit_summary,
        "label_rows": int(len(labels)),
        "label_horizons": sorted(pd.to_numeric(labels["horizon"], errors="coerce").dropna().astype(int).unique().tolist()),
        "limitations": [
            "first_bar est un proxy de disponibilite dans la base, pas une date IPO officielle",
            "stock_metadata est courant et non PIT",
            "pays et type detaille d'instrument ne sont pas disponibles dans stock_metadata",
            "les snapshots PIT marques degraded ne sont pas une verite certifiee",
        ],
    }
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    output = output_root / f"audit-{stamp}-{batch_id.rsplit('-', 1)[-1]}"
    output.mkdir(parents=True, exist_ok=False)
    audit.sort_values(["first_bar", "symbol"], na_position="last").to_csv(output / "symbol_audit.csv", index=False)
    overlap.to_csv(output / "pit_overlap_daily.csv", index=False)
    sectors = audit.assign(sector=audit["sector"].fillna("Unknown")).groupby("sector", dropna=False).agg(
        symbols=("symbol", "nunique"), valid_labels=("valid_labels", "sum"), extremes=("extreme_count", "sum")
    ).reset_index().sort_values("symbols", ascending=False)
    sectors.to_csv(output / "sector_summary.csv", index=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=_safe), encoding="utf-8")

    recent = audit[audit["first_bar_after_2020"].fillna(False)].sort_values("first_bar")
    recent_lines = "\n".join(f"- `{r.symbol}` : {r.first_bar.date()}" for r in recent.itertuples()) or "- Aucun"
    report = f"""# Audit P0 — univers Oracle de 400 symboles

Batch : `{batch_id}`

Période : {start} → {end}

Source : `{batch['symbol_source']}`

## Verdict

Le batch utilise une liste statique de {len(symbols)} symboles. Les rangs Oracle sont recalculés chaque jour sur les rendements valides, mais la composition de départ a été choisie a posteriori. Il existe donc un **biais de sélection de l'univers**, sans injection de barres avant cotation.

- Présents dès le début selon la première barre disponible : {coverage_summary['active_at_training_start_proxy']}/{len(symbols)}
- Première barre postérieure au début : {coverage_summary['first_bar_after_training_start']}
- Première barre en 2020 ou après : {coverage_summary['first_bar_after_2020']}
- Couverture d'au moins 95 % des séances SPY : {coverage_summary['coverage_ge_95pct']}
- Mini caps courantes (<500 M$) : {coverage_summary['current_mini_cap']}
- Small caps courantes (500 M$–2 Md$) : {coverage_summary['current_small_cap']}

## Concentration des tails

- Part des extrêmes produite par les 20 % de symboles les plus contributeurs : {_pct(tail['extreme']['top_20pct_event_share'])}
- D1 : {_pct(tail['d1']['top_20pct_event_share'])}
- D10 : {_pct(tail['d10']['top_20pct_event_share'])}
- Spearman fréquence extrême / volatilité réalisée : {_pct(tail['correlations']['extreme_frequency_vs_realized_vol_annual_spearman'])}
- Spearman fréquence extrême / range médian : {_pct(tail['correlations']['extreme_frequency_vs_median_range_pct_spearman'])}

## Comparaison aux snapshots PIT existants

- Dates comparables : {pit_summary['comparison_dates']}
- Univers statique médian avec label : {pit_summary['median_static_label_universe']}
- Univers PIT tradable médian : {pit_summary['median_pit_tradable_universe']}
- Jaccard médian : {_pct(pit_summary['median_jaccard'])}
- Couverture médiane du statique par le PIT : {_pct(pit_summary['median_static_covered_by_pit'])}
- Symboles PIT distincts hors liste statique : {pit_summary['pit_symbols_outside_static']}
- Dates PIT marquées `degraded` : {_pct(pit_summary['degraded_date_share'])}

Les snapshots dégradés prouvent un écart de composition, mais ne constituent pas encore une référence historique certifiée.

## Premières barres disponibles en 2020 ou après

La date est un proxy de disponibilité en base, pas une date d'IPO officielle.

{recent_lines}

## Limites

`stock_metadata` ne contient ni pays ni type détaillé d'instrument et représente l'état courant. L'identification certaine des ADR, REIT, BDC, MLP et des titres disparus nécessite une source historique supplémentaire.
"""
    (output / "report.md").write_text(report, encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit P0 de l'univers Oracle")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    print(run(args.batch_id, args.output_root))


if __name__ == "__main__":
    main()
