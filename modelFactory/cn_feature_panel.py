"""Profil price-only CN_A, sans facteurs US ni secteur historique inventé."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sqlalchemy import Engine, text

from database.router import get_market_engine
from service.market.cn_universe_pit import CNUniversePolicy, _fingerprint

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "config" / "features_cn" / "cn_price_v1.yaml"
DEFAULT_UNIVERSE_POLICY = ROOT / "config" / "universe_cn.yaml"

RETURN_HORIZONS = (1, 3, 5, 10, 20, 60)
NUMERIC_FEATURES = (
    *(f"return_{h}" for h in RETURN_HORIZONS),
    "sma20_distance", "sma50_distance", "sma200_distance", "atr20_pct",
    "realized_vol20", "range20_position", "volume_ratio20", "amount_mean20_cny",
    "overnight_gap", "position_52w", "benchmark_return_20", "benchmark_vol20",
    "relative_return_20", "cn_return20_rank", "cn_vol20_rank",
    "cn_breadth_1", "cn_dispersion_1", "sector_return20_rank",
)


@dataclass(frozen=True)
class CNFeatureProfile:
    benchmark_provider_symbol: str
    sector_taxonomy: str
    sector_membership_mode: str
    price_adjustment_mode: str
    warmup_sessions: int
    min_cross_section: int

    @classmethod
    def from_yaml(cls, path: Path) -> CNFeatureProfile:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if raw.get("profile") != "cn_price_v1" or raw.get("market_code") != "CN_A" or raw.get("database_alias") != "cn_primary":
            raise ValueError("Le profil doit cibler exclusivement cn_price_v1/CN_A/cn_primary")
        if tuple(raw.get("return_horizons", ())) != RETURN_HORIZONS:
            raise ValueError("Horizons CN non conformes au contrat cn_price_v1")
        if raw.get("sector_membership_mode") != "missing_until_pit_source":
            raise ValueError("Secteur CN PIT indisponible : ne pas injecter de classification actuelle")
        if raw.get("price_adjustment_mode") != "raw_with_factor_event_masks":
            raise ValueError("Mode de prix CN inconnu")
        profile = cls(**{key: raw[key] for key in (
            "benchmark_provider_symbol", "sector_taxonomy", "sector_membership_mode",
            "price_adjustment_mode", "warmup_sessions", "min_cross_section",
        )})
        if profile.benchmark_provider_symbol != "sh.000300" or profile.warmup_sessions < 252 or profile.min_cross_section < 2:
            raise ValueError("Benchmark ou fenêtre CN invalide")
        return profile


def _rolling_return(values: pd.Series, periods: int) -> pd.Series:
    safe = values.where(values > -1)
    return np.expm1(np.log1p(safe).rolling(periods, min_periods=periods).sum())


def compute_symbol_features(bars: pd.DataFrame, factor_events: pd.DataFrame | None = None) -> pd.DataFrame:
    """Calcule uniquement à partir de la barre courante et du passé du titre."""
    if bars.empty:
        return bars.copy()
    required = {"instrument_id", "date", "open", "high", "low", "close", "pre_close", "volume",
                "amount", "daily_return", "trading_status", "is_special_treatment", "available_at"}
    if missing := required - set(bars):
        raise ValueError(f"Barres CN incomplètes : {sorted(missing)}")
    frame = bars.copy().sort_values(["instrument_id", "date"], kind="stable").reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["available_at"] = pd.to_datetime(frame["available_at"])
    for name in ("open", "high", "low", "close", "pre_close", "volume", "amount", "daily_return"):
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
    if factor_events is not None and not factor_events.empty:
        events = factor_events[["instrument_id", "date", "available_at"]].drop_duplicates(
            ["instrument_id", "date"]
        ).rename(columns={"available_at": "event_available_at"}).copy()
        events["date"] = pd.to_datetime(events["date"])
        events["event_available_at"] = pd.to_datetime(events["event_available_at"])
        frame = frame.merge(events, on=["instrument_id", "date"], how="left", validate="one_to_one")
        frame["factor_event"] = (
            frame["event_available_at"].notna()
            & frame["event_available_at"].le(frame["date"] + pd.Timedelta(days=1))
        ).astype("int8")
    else:
        frame["factor_event"] = np.int8(0)
    pieces: list[pd.DataFrame] = []
    for _, group in frame.groupby("instrument_id", sort=False):
        group = group.copy().reset_index(drop=True)
        group["max_input_available_at"] = group["available_at"].cummax()
        valid = group["trading_status"].astype(str).str.startswith("TRADE") & group["close"].gt(0)
        close = group["close"].where(valid)
        high = group["high"].where(valid)
        low = group["low"].where(valid)
        returns = group["daily_return"].where(valid & group["daily_return"].gt(-1))
        for horizon in RETURN_HORIZONS:
            group[f"return_{horizon}"] = _rolling_return(returns, horizon)
        for window in (20, 50, 200):
            mean = close.rolling(window, min_periods=window).mean()
            contaminated = group["factor_event"].rolling(window, min_periods=1).max().gt(0)
            group[f"sma{window}_distance"] = (close / mean - 1).where(~contaminated)
        prev = group["pre_close"].where(group["pre_close"].gt(0))
        true_range = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
        group["atr20_pct"] = (true_range.rolling(20, min_periods=20).mean() / close).where(close.gt(0))
        group["realized_vol20"] = returns.rolling(20, min_periods=20).std() * np.sqrt(252)
        low20, high20 = low.rolling(20, min_periods=20).min(), high.rolling(20, min_periods=20).max()
        group["range20_position"] = ((close - low20) / (high20 - low20).replace(0, np.nan)).where(
            ~group["factor_event"].rolling(20, min_periods=1).max().gt(0)
        )
        mean_volume = group["volume"].where(valid).rolling(20, min_periods=20).mean()
        group["volume_ratio20"] = group["volume"].where(valid) / mean_volume.replace(0, np.nan)
        group["amount_mean20_cny"] = group["amount"].where(valid).rolling(20, min_periods=20).mean()
        group["overnight_gap"] = (group["open"] / prev - 1).where(valid)
        low252, high252 = low.rolling(252, min_periods=252).min(), high.rolling(252, min_periods=252).max()
        group["position_52w"] = ((close - low252) / (high252 - low252).replace(0, np.nan)).where(
            ~group["factor_event"].rolling(252, min_periods=1).max().gt(0)
        )
        group["factor_event_recent20"] = group["factor_event"].rolling(20, min_periods=1).max().astype("int8")
        group["factor_event_recent252"] = group["factor_event"].rolling(252, min_periods=1).max().astype("int8")
        group["prior_suspended"] = (~valid).astype("int8")
        group["prior_st"] = group["is_special_treatment"].fillna(False).astype("int8")
        pieces.append(group)
    return pd.concat(pieces, ignore_index=True)


def assemble_candidate_panel(
    candidates: pd.DataFrame, features: pd.DataFrame, benchmark: pd.DataFrame,
    limits: pd.DataFrame, *, profile: CNFeatureProfile,
) -> pd.DataFrame:
    """Joint le dernier close connu à la décision J ; jamais la barre J."""
    if candidates.empty:
        return candidates.copy()
    panel = candidates.copy()
    panel["session_date"] = pd.to_datetime(panel["session_date"])
    panel["asof_date"] = pd.to_datetime(panel["asof_date"])
    panel["decision_at"] = pd.to_datetime(panel["decision_at"])
    panel["source_available_at"] = pd.to_datetime(panel["source_available_at"])
    if not (panel["asof_date"] < panel["session_date"]).all() or not (panel["source_available_at"] <= panel["decision_at"]).all():
        raise ValueError("Fuite PIT dans les décisions d'univers CN")
    source = features.rename(columns={"date": "asof_date", "available_at": "bar_available_at"})
    panel = panel.merge(source, on=["instrument_id", "asof_date"], how="left", validate="many_to_one")
    if (panel["bar_available_at"].isna().any()
            or (panel["bar_available_at"] > panel["decision_at"]).any()
            or (panel["max_input_available_at"] > panel["decision_at"]).any()):
        raise ValueError("Barre source CN absente ou publiée après la décision")
    bench = benchmark.rename(columns={"date": "asof_date", "available_at": "benchmark_available_at",
                                      "max_input_available_at": "benchmark_max_input_available_at",
                                      "return_20": "benchmark_return_20", "realized_vol20": "benchmark_vol20"})
    panel = panel.merge(bench[["asof_date", "benchmark_available_at", "benchmark_max_input_available_at",
                               "benchmark_return_20", "benchmark_vol20"]],
                        on="asof_date", how="left", validate="many_to_one")
    if (panel["benchmark_available_at"].isna().any()
            or (panel["benchmark_available_at"] > panel["decision_at"]).any()
            or (panel["benchmark_max_input_available_at"] > panel["decision_at"]).any()):
        raise ValueError("Benchmark CN absent ou publié après la décision")
    panel["relative_return_20"] = panel["return_20"] - panel["benchmark_return_20"]
    if not limits.empty:
        selected_limits = limits.rename(columns={"session_date": "asof_date"}).copy()
        selected_limits["asof_date"] = pd.to_datetime(selected_limits["asof_date"])
        selected_limits["limit_available_at"] = pd.to_datetime(selected_limits["limit_available_at"])
        panel = panel.merge(selected_limits, on=["instrument_id", "asof_date"], how="left", validate="many_to_one")
        late = panel["limit_available_at"] > panel["decision_at"]
        for name in ("limit_policy", "limit_locked_up", "limit_locked_down"):
            panel.loc[late, name] = np.nan
    else:
        for name in ("limit_policy", "limit_locked_up", "limit_locked_down", "limit_available_at"):
            panel[name] = np.nan
    panel["prior_limit_unknown"] = panel["limit_policy"].isna() | panel["limit_policy"].eq("OBSERVED_OUTSIDE_DERIVED_LIMIT_V1")
    panel["prior_limit_locked"] = panel[["limit_locked_up", "limit_locked_down"]].eq(1).any(axis=1)
    code = panel["provider_symbol"].str.split(".", regex=False).str[-1]
    panel["board_code"] = np.select(
        [code.str.startswith("688"), code.str.startswith(("300", "301")), panel["provider_symbol"].str.startswith("sh.")],
        ["STAR", "CHINEXT", "SH_MAIN"], default="SZ_MAIN",
    )
    for board in ("SH_MAIN", "SZ_MAIN", "STAR", "CHINEXT"):
        panel[f"board_{board.lower()}"] = panel["board_code"].eq(board).astype("int8")
    panel["sector_taxonomy"] = profile.sector_taxonomy
    panel["sector_code"] = pd.Series(pd.NA, index=panel.index, dtype="string")
    panel["sector_membership_available"] = np.int8(0)
    panel["sector_return20_rank"] = np.nan
    grouped = panel.groupby("session_date", sort=False)
    panel["cn_return20_rank"] = grouped["return_20"].rank(pct=True)
    panel["cn_vol20_rank"] = grouped["realized_vol20"].rank(pct=True)
    panel["cn_breadth_1"] = grouped["return_1"].transform(lambda series: (series.dropna() > 0).mean() if series.notna().any() else np.nan)
    panel["cn_dispersion_1"] = grouped["return_1"].transform("std")
    panel["cross_section_count"] = grouped["instrument_id"].transform("size")
    insufficient = panel["cross_section_count"] < profile.min_cross_section
    for name in ("cn_return20_rank", "cn_vol20_rank", "cn_breadth_1", "cn_dispersion_1"):
        panel.loc[insufficient, name] = np.nan
    panel["mask_price20"] = panel[["return_20", "atr20_pct", "realized_vol20"]].notna().all(axis=1).astype("int8")
    panel["mask_benchmark"] = panel[["benchmark_return_20", "benchmark_vol20"]].notna().all(axis=1).astype("int8")
    panel["mask_sector"] = np.int8(0)
    panel["market_code"] = "CN_A"
    if panel["market_code"].nunique() != 1 or panel["market_code"].iloc[0] != "CN_A":
        raise ValueError("Panel multi-marché interdit")
    return panel


def _load_frames(engine: Engine, *, start: date, end: date, profile: CNFeatureProfile, universe_policy: CNUniversePolicy) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if engine.url.database != "alpha_trade_cn":
        raise RuntimeError("Features CN refusées hors alpha_trade_cn")
    policy_hash = _fingerprint(universe_policy.__dict__)
    with engine.connect() as conn:
        candidates = pd.read_sql(text(
            "SELECT r.universe_run_id,r.session_date,r.decision_at,d.instrument_id,d.provider_symbol,"
            "d.last_bar_date as asof_date,d.source_available_at "
            "FROM cn_universe_runs r JOIN cn_universe_decisions d ON d.universe_run_id=r.universe_run_id "
            "WHERE r.market_code='CN_A' AND r.policy_fingerprint=:policy AND r.status='COMPLETED' "
            "AND r.session_date BETWEEN :start AND :end AND d.decision_state='CANDIDATE' "
            "ORDER BY r.session_date,d.instrument_id"
        ), conn, params={"policy": policy_hash, "start": start, "end": end})
        if candidates.empty:
            raise ValueError("Aucun candidat CN PIT pour la période")
        sessions = pd.read_sql(text(
            "SELECT session_date FROM market_sessions WHERE market_code='CN_A' AND session_status='open' "
            "AND session_date<:start ORDER BY session_date DESC LIMIT :warmup"
        ), conn, params={"start": start, "warmup": profile.warmup_sessions})
        history_start = sessions["session_date"].iloc[-1] if not sessions.empty else start
        bars = pd.read_sql(text(
            "SELECT b.instrument_id,b.date,CAST(b.open AS DOUBLE) open,CAST(b.high AS DOUBLE) high,"
            "CAST(b.low AS DOUBLE) low,CAST(b.close AS DOUBLE) close,CAST(b.pre_close AS DOUBLE) pre_close,"
            "CAST(b.volume AS DOUBLE) volume,CAST(b.amount AS DOUBLE) amount,"
            "CAST(b.daily_return AS DOUBLE) daily_return,b.trading_status,b.is_special_treatment,b.available_at "
            "FROM stock_bars_daily b JOIN instruments i ON i.instrument_id=b.instrument_id "
            "WHERE b.market_code='CN_A' AND i.instrument_type='equity' AND b.date BETWEEN :start AND :end "
            "ORDER BY b.instrument_id,b.date"
        ), conn, params={"start": history_start, "end": end})
        benchmark = pd.read_sql(text(
            "SELECT date,CAST(open AS DOUBLE) open,CAST(high AS DOUBLE) high,CAST(low AS DOUBLE) low,"
            "CAST(close AS DOUBLE) close,CAST(pre_close AS DOUBLE) pre_close,CAST(volume AS DOUBLE) volume,"
            "CAST(amount AS DOUBLE) amount,CAST(daily_return AS DOUBLE) daily_return,"
            "trading_status,is_special_treatment,available_at "
            "FROM stock_bars_daily WHERE market_code='CN_A' AND symbol=:symbol "
            "AND date BETWEEN :start AND :end ORDER BY date"
        ), conn, params={"symbol": profile.benchmark_provider_symbol, "start": history_start, "end": end})
        if benchmark.empty:
            raise RuntimeError("Benchmark CSI 300 absent")
        benchmark["instrument_id"] = -1
        factors = pd.read_sql(text(
            "SELECT instrument_id,ex_date date,available_at FROM cn_corporate_actions "
            "WHERE ex_date BETWEEN :start AND :end AND classification_status='UNCLASSIFIED_FACTOR_EVENT'"
        ), conn, params={"start": history_start, "end": end})
        limits = pd.read_sql(text(
            "SELECT instrument_id,session_date,policy_code limit_policy,locked_up limit_locked_up,"
            "locked_down limit_locked_down,available_at limit_available_at "
            "FROM cn_daily_price_limits WHERE session_date BETWEEN :start AND :end"
        ), conn, params={"start": history_start, "end": end})
    return candidates, bars, benchmark, factors, limits


def build_panel(*, start: date, end: date, profile_path: Path = DEFAULT_PROFILE,
                universe_policy_path: Path = DEFAULT_UNIVERSE_POLICY,
                output_root: Path | None = None) -> dict[str, Any]:
    """Publie un panel Parquet reproductible ; une année par run est recommandée."""
    if end < start:
        raise ValueError("Période CN invalide")
    profile = CNFeatureProfile.from_yaml(profile_path)
    universe_policy = CNUniversePolicy.from_yaml(universe_policy_path)
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    candidates, bars, benchmark, factors, limits = _load_frames(
        engine, start=start, end=end, profile=profile, universe_policy=universe_policy,
    )
    features = compute_symbol_features(bars, factors)
    benchmark_features = compute_symbol_features(benchmark)
    panel = assemble_candidate_panel(candidates, features, benchmark_features, limits, profile=profile)
    selected = ["market_code", "universe_run_id", "session_date", "decision_at", "asof_date",
                "source_available_at", "bar_available_at", "max_input_available_at",
                "benchmark_available_at", "benchmark_max_input_available_at",
                "instrument_id", "provider_symbol", "board_code", "sector_code", "sector_taxonomy",
                "sector_membership_available", "cross_section_count", "factor_event_recent20",
                "factor_event_recent252", "prior_suspended", "prior_st", "prior_limit_unknown",
                "prior_limit_locked", "limit_policy", "limit_available_at",
                "mask_price20", "mask_benchmark", "mask_sector",
                *(f"board_{name}" for name in ("sh_main", "sz_main", "star", "chinext")), *NUMERIC_FEATURES]
    panel = panel[selected].sort_values(["session_date", "instrument_id"]).reset_index(drop=True)
    duplicate_keys = int(panel.duplicated(["session_date", "instrument_id"]).sum())
    if duplicate_keys:
        raise ValueError(f"Panel CN non unique : {duplicate_keys} clés")
    availability_columns = ("source_available_at", "bar_available_at", "benchmark_available_at")
    if any((panel[name] > panel["decision_at"]).any() for name in availability_columns):
        raise ValueError("Panel CN contient des données après la décision")
    implementation_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    identity = _fingerprint({"profile": profile.__dict__, "universe_policy": universe_policy.__dict__,
                             "profile_file_sha": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
                             "policy_file_sha": hashlib.sha256(universe_policy_path.read_bytes()).hexdigest(),
                             "implementation_sha": implementation_sha, "start": start, "end": end,
                             "universe_runs": sorted(candidates["universe_run_id"].unique().tolist())})
    destination = (output_root or ROOT / "artifacts" / "cn" / "features") / "cn_price_v1" / f"cn-feature-{start:%Y%m%d}-{end:%Y%m%d}-{identity[:12]}"
    destination.mkdir(parents=True, exist_ok=True)
    temp = destination / "panel.tmp.parquet"
    panel.to_parquet(temp, index=False)
    def file_sha(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    panel_sha = file_sha(temp)
    final_panel = destination / "panel.parquet"
    if final_panel.exists():
        temp.unlink()
        if file_sha(final_panel) != panel_sha:
            raise RuntimeError("Artefact CN existant différent : révision des données source ; ne pas écraser")
    else:
        temp.replace(final_panel)
    missing = {name: round(float(panel[name].isna().mean()), 6) for name in NUMERIC_FEATURES}
    constants = [name for name in NUMERIC_FEATURES if panel[name].nunique(dropna=True) <= 1]
    board_quality = {
        str(board): {
            "rows": int(len(group)),
            "price20_coverage": round(float(group["mask_price20"].mean()), 6),
            "benchmark_coverage": round(float(group["mask_benchmark"].mean()), 6),
            "position_52w_coverage": round(float(group["position_52w"].notna().mean()), 6),
        }
        for board, group in panel.groupby("board_code", sort=True)
    }
    daily_coverage = panel.groupby("session_date")["mask_price20"].mean()
    candidate_features = [name for name in NUMERIC_FEATURES
                          if name not in {"sector_return20_rank", "cn_breadth_1", "cn_dispersion_1"}]
    correlations = panel[candidate_features].corr(min_periods=min(100, len(panel)))
    high_correlation_pairs = [
        {"left": left, "right": right, "correlation": round(float(correlations.loc[left, right]), 6)}
        for offset, left in enumerate(candidate_features)
        for right in candidate_features[offset + 1:]
        if pd.notna(correlations.loc[left, right]) and abs(correlations.loc[left, right]) >= 0.995
    ]
    report = {"profile": "cn_price_v1", "market_code": "CN_A", "start": start.isoformat(),
              "end": end.isoformat(), "rows": len(panel), "sessions": int(panel["session_date"].nunique()),
              "instruments": int(panel["instrument_id"].nunique()), "benchmark": profile.benchmark_provider_symbol,
              "sector_membership_coverage": 0.0, "missing_fraction": missing,
              "quality": {"duplicate_keys": duplicate_keys, "late_source_rows": 0,
                          "price20_coverage": round(float(panel["mask_price20"].mean()), 6),
                          "benchmark_coverage": round(float(panel["mask_benchmark"].mean()), 6),
                          "factor_event_recent252_fraction": round(float(panel["factor_event_recent252"].mean()), 6),
                          "daily_price20_coverage_min": round(float(daily_coverage.min()), 6),
                          "daily_price20_coverage_median": round(float(daily_coverage.median()), 6),
                          "board_quality": board_quality,
                          "high_correlation_pairs": high_correlation_pairs,
                          "instrument_id_used_as_feature": False,
                          "constant_or_all_missing_numeric_features": constants,
                          "research_ready_price_only": bool(
                              panel["mask_price20"].mean() >= 0.95
                              and panel["mask_benchmark"].mean() >= 0.99)},
              "board_counts": panel["board_code"].value_counts().to_dict(),
              "feature_schema_fingerprint": _fingerprint(selected), "input_fingerprint": identity,
              "implementation_sha256": implementation_sha,
              "panel_sha256": panel_sha, "output": str(final_panel)}
    (destination / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
