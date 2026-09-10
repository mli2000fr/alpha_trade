"""Construit un univers Oracle de 400 symboles équilibre et reproductible."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine

CAP_TARGETS = {"small": 40, "mid": 260, "large": 100}
VOL_TARGETS = {1: 60, 2: 80, 3: 100, 4: 100, 5: 60}
BETA_TARGETS = {1: 80, 2: 80, 3: 80, 4: 80, 5: 80}


def is_excluded_security_name(names: pd.Series) -> pd.Series:
    """Détecte les instruments non ordinaires sans exclure un émetteur par son nom."""
    value = names.fillna("").astype(str)
    return value.str.contains(
        r"\bETF\b|Exchange Traded Fund|\bETN\b|\bExchange Traded Notes?\b|"
        r"\bWarrants?\b|\bSubscription Rights?\b|\bAcquisition Rights?\b|"
        r"\bPreferred (?:Stock|Shares?)\b|\bDepositary Shares?.*\bPreferred\b|"
        r"\bUnits? consisting of\b|\bAcquisition Corp\.? Units?\b",
        case=False,
        regex=True,
    )


def git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def read_symbols(path: Path) -> list[str]:
    values: list[str] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.lstrip().startswith("#"):
            continue
        values.extend(part.strip().upper() for part in line.split(",") if part.strip())
    return sorted(set(values))


def allocation_matrix() -> dict[tuple[str, int], int]:
    """Produit les quotas cap x volatilité avec sommes marginales exactes."""
    result: dict[tuple[str, int], int] = {}
    vol_shares = {key: value / 400 for key, value in VOL_TARGETS.items()}
    for cap, cap_total in CAP_TARGETS.items():
        raw = {q: cap_total * share for q, share in vol_shares.items()}
        allocated = {q: math.floor(value) for q, value in raw.items()}
        remaining = cap_total - sum(allocated.values())
        order = sorted(raw, key=lambda q: (raw[q] - allocated[q], -q), reverse=True)
        for q in order[:remaining]:
            allocated[q] += 1
        for q, count in allocated.items():
            result[(cap, q)] = count
    return result


def select_balanced(
    candidates: pd.DataFrame,
    *,
    seed: int,
    sector_cap: int = 40,
    foreign_proxy_cap: int = 60,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Sélection déterministe par cellule cap/vol, avec équilibrage sectoriel."""
    rng = np.random.default_rng(seed)
    work = candidates.copy().reset_index(drop=True)
    work["tie_break"] = rng.random(len(work))
    selected: list[int] = []
    selected_set: set[int] = set()
    sector_counts: dict[str, int] = {}
    beta_counts = dict.fromkeys(BETA_TARGETS, 0)
    foreign_count = 0
    diagnostics: list[dict[str, Any]] = []

    def choose(pool: pd.DataFrame, requested: int) -> int:
        nonlocal foreign_count
        added = 0
        while added < requested:
            available = pool.loc[~pool.index.isin(selected_set)].copy()
            available = available[
                available["sector"].map(lambda value: sector_counts.get(str(value), 0) < sector_cap)
            ]
            if foreign_count >= foreign_proxy_cap:
                available = available[~available["foreign_listing_proxy"]]
            if available.empty:
                break
            available["sector_used"] = available["sector"].map(lambda value: sector_counts.get(str(value), 0))
            available["beta_fill_ratio"] = available["beta_quintile"].map(
                lambda value: beta_counts.get(int(value), 0) / BETA_TARGETS.get(int(value), 80)
            )
            row = available.sort_values(
                ["beta_fill_ratio", "sector_used", "cap_age_days", "history_sessions", "tie_break"],
                ascending=[True, True, True, False, True],
            ).iloc[0]
            idx = int(row.name)
            selected.append(idx)
            selected_set.add(idx)
            sector = str(row["sector"])
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
            beta_quintile = int(row["beta_quintile"])
            beta_counts[beta_quintile] = beta_counts.get(beta_quintile, 0) + 1
            foreign_count += int(bool(row["foreign_listing_proxy"]))
            added += 1
        return added

    matrix = allocation_matrix()
    for (cap, quintile), requested in matrix.items():
        pool = work[work["cap_bucket"].eq(cap) & work["vol_quintile"].eq(quintile)]
        added = choose(pool, requested)
        diagnostics.append({
            "cap_bucket": cap, "vol_quintile": quintile,
            "requested": requested, "available": int(len(pool)), "selected": added,
        })
    if len(selected) < 400:
        added = choose(work, 400 - len(selected))
        diagnostics.append({
            "cap_bucket": "redistributed", "vol_quintile": 0,
            "requested": 400 - len(selected) + added, "available": len(work) - len(selected) + added,
            "selected": added,
        })
    result = work.loc[selected].drop(columns=["tie_break"]).copy()
    if len(result) != 400:
        raise RuntimeError(f"Sélection incomplète: {len(result)}/400")
    return result.sort_values("symbol").reset_index(drop=True), diagnostics


def run(source: Path, cutoff: str, seed: int, output_file: Path, output_root: Path) -> Path:
    symbols = read_symbols(source)
    cutoff_ts = pd.Timestamp(cutoff).normalize()
    lookback = cutoff_ts - pd.Timedelta(days=800)
    engine = get_sqlalchemy_engine()
    bars_query = text(
        "SELECT symbol,`date`,CAST(COALESCE(adj_close,close) AS DOUBLE) close,"
        "CAST(volume AS DOUBLE) volume,COALESCE(is_filled,0) is_filled "
        "FROM stock_bars_daily WHERE symbol IN :symbols AND `date`<=:cutoff "
        "AND `date`>=:lookback ORDER BY symbol,`date`"
    ).bindparams(bindparam("symbols", expanding=True))
    bars = pd.read_sql(bars_query, engine, params={
        "symbols": sorted(set(symbols) | {"SPY"}), "cutoff": cutoff_ts.date(), "lookback": lookback.date()
    }, parse_dates=["date"])
    history_query = text(
        "SELECT symbol,COUNT(*) history_sessions,MIN(`date`) first_bar,MAX(`date`) last_bar "
        "FROM stock_bars_daily WHERE symbol IN :symbols AND `date`<=:cutoff GROUP BY symbol"
    ).bindparams(bindparam("symbols", expanding=True))
    history = pd.read_sql(history_query, engine, params={"symbols": symbols, "cutoff": cutoff_ts.date()})
    cap_query = text(
        "SELECT symbol,trade_date cap_date,market_cap,source cap_source FROM ("
        "SELECT symbol,trade_date,market_cap,source,id,ROW_NUMBER() OVER "
        "(PARTITION BY symbol ORDER BY trade_date DESC,id DESC) rn "
        "FROM stock_fundamentals_daily WHERE symbol IN :symbols AND trade_date<=:cutoff "
        "AND market_cap IS NOT NULL) ranked WHERE rn=1"
    ).bindparams(bindparam("symbols", expanding=True))
    caps = pd.read_sql(cap_query, engine, params={"symbols": symbols, "cutoff": cutoff_ts.date()}, parse_dates=["cap_date"])
    meta_query = text(
        "SELECT symbol,company_name,exchange,asset_class,status,tradable,bars_available,"
        "COALESCE(provider_sector,sector) sector FROM stock_metadata WHERE symbol IN :symbols"
    ).bindparams(bindparam("symbols", expanding=True))
    meta = pd.read_sql(meta_query, engine, params={"symbols": symbols})

    bars = bars.sort_values(["symbol", "date"])
    bars["return"] = bars.groupby("symbol")["close"].transform(lambda x: np.log(x).diff())
    tail = bars.groupby("symbol").tail(252).copy()
    metrics = tail.groupby("symbol").agg(
        last_date=("date", "max"), last_close=("close", "last"),
        avg_volume20=("volume", lambda x: float(x.tail(20).mean())),
        adv20=("close", lambda x: 0.0),
        vol20=("return", lambda x: float(x.tail(20).std())),
        filled252=("is_filled", lambda x: float(pd.to_numeric(x, errors="coerce").fillna(0).eq(1).mean())),
    ).reset_index()
    dollar = tail.assign(dollar_volume=tail["close"] * tail["volume"])
    adv = dollar.groupby("symbol")["dollar_volume"].apply(lambda x: float(x.tail(20).mean())).rename("adv20")
    metrics = metrics.drop(columns="adv20").merge(adv, on="symbol", how="left")
    spy = bars[bars["symbol"].eq("SPY")][["date", "return"]].rename(columns={"return": "spy_return"})
    pair = tail[tail["symbol"].isin(symbols)][["symbol", "date", "return"]].merge(spy, on="date", how="left").dropna()
    beta_rows = []
    for symbol, part in pair.groupby("symbol"):
        var = float(part.tail(126)["spy_return"].var())
        cov = float(part.tail(126)[["return", "spy_return"]].cov().iloc[0, 1])
        beta_rows.append({"symbol": symbol, "beta126": cov / var if var else np.nan})

    audit = pd.DataFrame({"symbol": symbols})
    for frame in (history, metrics, pd.DataFrame(beta_rows), caps, meta):
        audit = audit.merge(frame, on="symbol", how="left")
    audit["cap_age_days"] = (cutoff_ts - audit["cap_date"]).dt.days
    audit["sector"] = audit["sector"].fillna("Unknown")
    names = audit["company_name"].fillna("")
    audit["foreign_listing_proxy"] = names.str.contains(
        r"American Depositar|American Depositor|Ordinary Shares|\bplc\b", case=False, regex=True
    )
    audit["excluded_security_proxy"] = is_excluded_security_name(names)
    spy_dates = sorted(bars.loc[bars["symbol"].eq("SPY"), "date"].dropna().unique())
    recent_bar_floor = pd.Timestamp(spy_dates[-5]) if len(spy_dates) >= 5 else cutoff_ts - pd.Timedelta(days=7)
    checks = {
        "history_lt_504": audit["history_sessions"].lt(504) | audit["history_sessions"].isna(),
        "stale_last_bar": audit["last_date"].lt(recent_bar_floor) | audit["last_date"].isna(),
        "price_below_10": audit["last_close"].lt(10) | audit["last_close"].isna(),
        "avg_volume20_below_100k": audit["avg_volume20"].lt(100_000) | audit["avg_volume20"].isna(),
        "adv20_below_10m": audit["adv20"].lt(10_000_000) | audit["adv20"].isna(),
        "filled252_above_2pct": audit["filled252"].gt(0.02) | audit["filled252"].isna(),
        "beta126_missing": audit["beta126"].isna(),
        "market_cap_missing_or_below_500m": audit["market_cap"].lt(500_000_000) | audit["market_cap"].isna(),
        "market_cap_older_than_365d": audit["cap_age_days"].gt(365) | audit["cap_age_days"].isna(),
        "metadata_not_active": ~audit["status"].eq("active"),
        "not_tradable": ~audit["tradable"].eq(1),
        "bars_not_available": ~audit["bars_available"].eq(1),
        "asset_class_not_us_equity": ~audit["asset_class"].eq("us_equity"),
        "excluded_security_type_proxy": audit["excluded_security_proxy"],
    }
    failures = pd.DataFrame(checks, index=audit.index).fillna(True).astype(bool)
    audit["exclusion_reasons"] = failures.apply(
        lambda row: ",".join(row.index[row.to_numpy()]), axis=1
    )
    audit["eligible"] = ~failures.any(axis=1)
    eligible = audit[audit["eligible"]].copy()
    eligible["cap_bucket"] = pd.cut(
        eligible["market_cap"], [500e6, 2e9, 10e9, np.inf], labels=["small", "mid", "large"], include_lowest=True
    ).astype(str)
    eligible["vol_quintile"] = np.ceil(eligible["vol20"].rank(method="first", pct=True) * 5).clip(1, 5).astype(int)
    eligible["beta_quintile"] = np.ceil(eligible["beta126"].rank(method="first", pct=True) * 5).clip(1, 5).astype("Int8")
    selected, allocation = select_balanced(eligible, seed=seed)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(",".join(selected["symbol"]) + "\n", encoding="utf-8")
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    output = output_root / f"p0d-{stamp}"
    output.mkdir(parents=True, exist_ok=False)
    audit.to_csv(output / "symbol_audit.csv", index=False)
    audit[~audit["eligible"]].to_csv(output / "exclusions.csv", index=False)
    selected.to_csv(output / "selected_400.csv", index=False)
    pd.DataFrame(allocation).to_csv(output / "allocation.csv", index=False)
    strata = selected.groupby(["cap_bucket", "vol_quintile"], observed=True).size().rename("symbols").reset_index()
    strata.to_csv(output / "strata_summary.csv", index=False)
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(), "selection_cutoff": cutoff,
        "source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "seed": seed, "candidate_symbols": len(symbols), "eligible_symbols": len(eligible),
        "selected_symbols": len(selected), "output_file": str(output_file),
        "output_sha256": hashlib.sha256(output_file.read_bytes()).hexdigest(),
        "git_commit": git_commit(),
        "targets": {
            "capitalization": CAP_TARGETS,
            "volatility": VOL_TARGETS,
            "beta": BETA_TARGETS,
            "sector_cap": 40,
            "foreign_listing_proxy_cap": 60,
        },
        "thresholds": {
            "history_sessions_min": 504,
            "price_min": 10,
            "average_volume20_min": 100_000,
            "adv20_min": 10_000_000,
            "filled252_max": 0.02,
            "market_cap_min": 500_000_000,
            "market_cap_age_days_max": 365,
        },
        "exclusion_counts_non_exclusive": {
            column: int(failures[column].sum()) for column in failures.columns
        },
        "selected_distributions": {
            "capitalization": {str(k): int(v) for k, v in selected["cap_bucket"].value_counts().items()},
            "volatility_quintile": {
                str(k): int(v) for k, v in selected["vol_quintile"].value_counts().sort_index().items()
            },
            "beta_quintile": {
                str(k): int(v) for k, v in selected["beta_quintile"].value_counts().sort_index().items()
            },
            "sector_max": int(selected["sector"].value_counts().max()),
            "sector_count": int(selected["sector"].nunique()),
            "foreign_listing_proxy": int(selected["foreign_listing_proxy"].sum()),
        },
        "recent_bar_floor": recent_bar_floor.date().isoformat(),
        "pit_grade": "RECONSTRUCTED_GRADE_B",
        "warnings": [
            "SEC market caps are historically dated but were back-collected in 2026",
            "sector and security type proxies come from current stock_metadata",
            "not an honest universe for 2026H1 confirmation",
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report = [
        "# P0d — Oracle Balanced 400", "", f"Cutoff: {cutoff}", f"Seed: {seed}",
        f"Candidats: {len(symbols)}", f"Éligibles: {len(eligible)}", "Sélectionnés: 400", "",
        "## Capitalisation", "", selected["cap_bucket"].value_counts().to_string(), "",
        "## Volatilité", "", selected["vol_quintile"].value_counts().sort_index().to_string(), "",
        "## Bêta", "", selected["beta_quintile"].value_counts().sort_index().to_string(), "",
        "## Secteurs", "", f"Secteurs distincts: {selected['sector'].nunique()}",
        f"Maximum dans un secteur: {selected['sector'].value_counts().max()}", "",
        "## Avertissement PIT", "",
        "Univers grade B reconstruit. Les capitalisations SEC sont datées historiquement mais collectées en 2026 ; le secteur est courant. Ne pas présenter un test 2026H1 comme une confirmation OOS indépendante.",
    ]
    (output / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Sélection Oracle Balanced 400")
    parser.add_argument("--source", type=Path, default=Path("config/univers/univers_filtred.txt"))
    parser.add_argument("--cutoff", default="2025-12-31")
    parser.add_argument("--seed", type=int, default=20251231)
    parser.add_argument("--output-file", type=Path, default=Path("config/univers/oracle_balanced_400_202512.txt"))
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/research/universe_selection"))
    args = parser.parse_args()
    run(args.source, args.cutoff, args.seed, args.output_file, args.output_root)


if __name__ == "__main__":
    main()
