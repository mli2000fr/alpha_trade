"""Labels Oracle CN_A avant ouverture : J open -> J+H close, sans entraînement."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sqlalchemy import Engine, text

from database.router import get_market_engine
from modelFactory.cn_feature_panel import ROOT
from service.market.cn_universe_pit import _fingerprint

DEFAULT_CONFIG = ROOT / "config" / "labels_cn.yaml"
DEFAULT_FEATURE_ROOT = ROOT / "artifacts" / "cn" / "features" / "cn_price_v1"
DEFAULT_OUTPUT_ROOT = ROOT / "artifacts" / "cn" / "labels"
FEATURE_COLUMNS = ("session_date", "instrument_id", "provider_symbol", "board_code",
                   "universe_run_id", "decision_at")
OUTPUT_COLUMNS = (
    "market_code", "session_date", "instrument_id", "provider_symbol", "board_code",
    "universe_run_id", "decision_at", "horizon", "exit_date", "available_date",
    "available_at_utc",
    "entry_open", "exit_close", "future_return", "future_return_raw",
    "target_quality_valid", "target_quality_reason", "rank_universe_count",
    "oracle_pct_rank", "oracle_decile", "oracle_extreme20",
    "path_limit_locked", "path_limit_unknown", "path_factor_event",
    "path_factor_unverified", "entry_limit_locked",
    "exit_limit_locked", "execution_data_eligible",
)


@dataclass(frozen=True)
class CNLabelPolicy:
    horizons: tuple[int, ...]
    min_rank_cross_section: int

    @classmethod
    def from_yaml(cls, path: Path) -> CNLabelPolicy:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        required = {
            "profile": "cn_oracle_labels_v1", "market_code": "CN_A",
            "database_alias": "cn_primary", "feature_profile": "cn_price_v1",
            "entry_price": "open_on_prediction_session",
            "exit_price": "close_at_plus_h_sessions",
            "available_date": "next_cn_session_after_exit",
            "quarantine_missing_session_bar": True,
            "quarantine_suspension_or_status_conflict": True,
            "quarantine_unverified_factor_event": True,
            "quarantine_late_source_revision": True,
            "price_limits_affect_label": False,
            "price_limits_affect_execution_flag": True,
        }
        if any(raw.get(key) != value for key, value in required.items()):
            raise ValueError("Contrat des labels CN modifié ou marché US introduit")
        horizons = tuple(int(value) for value in raw.get("horizons", ()))
        if horizons != (5, 10, 15, 20):
            raise ValueError("Horizons Oracle CN attendus : H5/H10/H15/H20")
        minimum = int(raw.get("min_rank_cross_section", 0))
        if minimum < 20:
            raise ValueError("Coupe transversale CN trop petite")
        return cls(horizons=horizons, min_rank_cross_section=minimum)


def _interval_count(prefix: np.ndarray, start: np.ndarray, end: np.ndarray) -> np.ndarray:
    before = np.where(start > 0, prefix[np.maximum(start - 1, 0)], 0)
    return prefix[end] - before


def _mark_reason(reasons: np.ndarray, condition: np.ndarray, label: str) -> None:
    reasons[(reasons == "") & condition] = label


def _symbol_labels(
    candidates: pd.DataFrame, bars: pd.DataFrame, calendar: pd.DataFrame,
    *, horizon: int,
) -> pd.DataFrame:
    """Calcul vectorisé par titre sur des positions du calendrier CN."""
    dates = pd.DatetimeIndex(calendar["session_date"])
    n = len(dates)
    entry = dates.get_indexer(pd.to_datetime(candidates["session_date"]))
    if (entry < 0).any():
        raise ValueError("Une décision CN ne correspond à aucune séance ouverte")
    exit_pos = entry + horizon
    avail_pos = exit_pos + 1
    safe_exit = np.minimum(exit_pos, n - 1)
    safe_avail = np.minimum(avail_pos, n - 1)
    indexed = bars.copy()
    indexed["date"] = pd.to_datetime(indexed["date"])
    positions = dates.get_indexer(indexed["date"])
    if (positions < 0).any():
        raise ValueError("Barre CN hors calendrier")

    def numeric(name: str) -> np.ndarray:
        values = np.full(n, np.nan, dtype=float)
        values[positions] = pd.to_numeric(indexed[name], errors="coerce").to_numpy(dtype=float)
        return values

    open_price, close_price = numeric("open"), numeric("close")
    pre_close = numeric("pre_close")
    factor_value, previous_factor_value = numeric("factor_value"), numeric("previous_factor_value")
    daily_return = numeric("daily_return")
    present = np.zeros(n, dtype=bool)
    present[positions] = True
    trade = np.zeros(n, dtype=bool)
    trade[positions] = (
        indexed["trading_status"].astype(str).str.startswith("TRADE").to_numpy()
        & pd.to_numeric(indexed["volume"], errors="coerce").gt(0).to_numpy()
    )
    factor = np.zeros(n, dtype=bool)
    factor[positions] = indexed["factor_event"].fillna(0).astype(bool).to_numpy()
    previous_traded_close = pd.Series(close_price).where(trade).ffill().shift(1).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        expected_pre_close = previous_traded_close * previous_factor_value / factor_value
    factor_verified = (
        factor & np.isfinite(expected_pre_close) & (expected_pre_close > 0)
        & np.isfinite(pre_close) & (pre_close > 0)
        & (np.abs(pre_close - expected_pre_close) <= np.maximum(0.02, expected_pre_close * 0.005))
    )
    factor_unverified = factor & ~factor_verified
    limit_unknown = np.ones(n, dtype=bool)
    limit_unknown[positions] = (
        indexed["limit_policy"].isna()
        | indexed["limit_policy"].eq("OBSERVED_OUTSIDE_DERIVED_LIMIT_V1")
    ).to_numpy()
    limit_locked = np.zeros(n, dtype=bool)
    limit_locked[positions] = (
        indexed["locked_up"].eq(1) | indexed["locked_down"].eq(1)
    ).to_numpy()
    available_ns = np.full(n, np.iinfo(np.int64).min, dtype=np.int64)
    available_ns[positions] = pd.to_datetime(indexed["available_at"]).astype("int64").to_numpy()
    factor_available_ns = pd.to_datetime(indexed["factor_available_at"]).astype("int64").to_numpy()
    available_ns[positions] = np.maximum(available_ns[positions], factor_available_ns)
    valid_step_return = np.isfinite(daily_return) & (daily_return > -1)
    log_steps = np.where(valid_step_return, np.log1p(np.where(valid_step_return, daily_return, 0)), 0)
    log_prefix = np.cumsum(log_steps)
    prefixes = {
        "missing": np.cumsum(~present),
        "suspended": np.cumsum(present & ~trade),
        "factor": np.cumsum(factor),
        "factor_unverified": np.cumsum(factor_unverified),
        "invalid_return": np.cumsum(~valid_step_return),
        "locked": np.cumsum(limit_locked),
        "unknown_limit": np.cumsum(limit_unknown),
    }
    missing = _interval_count(prefixes["missing"], entry, safe_exit) > 0
    suspended = _interval_count(prefixes["suspended"], entry, safe_exit) > 0
    factors = _interval_count(prefixes["factor"], entry, safe_exit) > 0
    unverified_factors = _interval_count(prefixes["factor_unverified"], entry, safe_exit) > 0
    invalid_steps = (
        prefixes["invalid_return"][safe_exit] - prefixes["invalid_return"][entry]
    ) > 0
    path_locked = _interval_count(prefixes["locked"], entry, safe_exit) > 0
    path_unknown = _interval_count(prefixes["unknown_limit"], entry, safe_exit) > 0
    path_max_source = np.maximum.reduce([
        available_ns[np.minimum(entry + offset, n - 1)] for offset in range(horizon + 1)
    ])
    available_cutoff = pd.to_datetime(calendar["open_at_utc"]).astype("int64").to_numpy()[safe_avail]
    late_source = path_max_source > available_cutoff
    begin, finish = open_price[entry], close_price[safe_exit]
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        raw_return = finish / begin - 1
        adjusted_return = np.expm1(
            np.log(close_price[entry] / begin) + log_prefix[safe_exit] - log_prefix[entry]
        )
    reasons = np.full(len(entry), "", dtype=object)
    _mark_reason(reasons, exit_pos >= n, "FUTURE_HORIZON_UNAVAILABLE")
    _mark_reason(reasons, avail_pos >= n, "AVAILABILITY_SESSION_UNAVAILABLE")
    _mark_reason(reasons, missing, "MISSING_PATH_BAR")
    _mark_reason(reasons, suspended, "SUSPENDED_OR_STATUS_CONFLICT")
    _mark_reason(reasons, unverified_factors, "UNVERIFIED_FACTOR_ADJUSTMENT")
    _mark_reason(reasons, invalid_steps, "MISSING_OR_INVALID_DAILY_RETURN")
    _mark_reason(reasons, ~np.isfinite(begin) | (begin <= 0), "INVALID_ENTRY_OPEN")
    _mark_reason(reasons, ~np.isfinite(finish) | (finish <= 0), "INVALID_EXIT_CLOSE")
    _mark_reason(reasons, late_source, "SOURCE_AFTER_LABEL_AVAILABILITY")
    _mark_reason(reasons, ~np.isfinite(adjusted_return), "NONFINITE_FUTURE_RETURN")
    valid = reasons == ""
    result = candidates[list(FEATURE_COLUMNS)].copy().reset_index(drop=True)
    result["market_code"] = "CN_A"
    result["horizon"] = horizon
    result["exit_date"] = pd.Series(dates[safe_exit]).where(exit_pos < n).to_numpy()
    result["available_date"] = pd.Series(dates[safe_avail]).where(avail_pos < n).to_numpy()
    result["available_at_utc"] = pd.Series(pd.to_datetime(calendar["open_at_utc"]).to_numpy()[safe_avail]).where(
        avail_pos < n
    ).to_numpy()
    result["entry_open"] = begin
    result["exit_close"] = np.where(exit_pos < n, finish, np.nan)
    result["future_return"] = np.where(valid, adjusted_return, np.nan)
    result["future_return_raw"] = np.where((exit_pos < n) & np.isfinite(raw_return), raw_return, np.nan)
    result["target_quality_valid"] = valid
    result["target_quality_reason"] = np.where(valid, "OK", reasons)
    result["path_limit_locked"] = path_locked
    result["path_limit_unknown"] = path_unknown
    result["path_factor_event"] = factors
    result["path_factor_unverified"] = unverified_factors
    result["entry_limit_locked"] = limit_locked[entry]
    result["exit_limit_locked"] = limit_locked[safe_exit]
    result["execution_data_eligible"] = (
        valid & ~limit_locked[entry] & ~limit_locked[safe_exit]
        & ~limit_unknown[entry] & ~limit_unknown[safe_exit]
    )
    return result


def compute_horizon_labels(
    candidates: pd.DataFrame, bars: pd.DataFrame, calendar: pd.DataFrame,
    *, horizon: int, min_rank_cross_section: int = 20,
) -> pd.DataFrame:
    if horizon <= 0 or candidates.empty:
        raise ValueError("Horizon positif et candidats CN requis")
    if candidates.duplicated(["session_date", "instrument_id"]).any():
        raise ValueError("Candidats CN dupliqués")
    cal = calendar.copy()
    cal["session_date"] = pd.to_datetime(cal["session_date"])
    cal["open_at_utc"] = pd.to_datetime(cal["open_at_utc"])
    cal = cal.sort_values("session_date").reset_index(drop=True)
    if cal["session_date"].duplicated().any() or cal["open_at_utc"].isna().any():
        raise ValueError("Calendrier CN invalide")
    bar_groups = dict(iter(bars.groupby("instrument_id", sort=False)))
    empty_bars = bars.iloc[0:0]
    parts: list[pd.DataFrame] = []
    for instrument_id, group in candidates.groupby("instrument_id", sort=False):
        source = bar_groups.get(instrument_id, empty_bars)
        parts.append(_symbol_labels(group, source, cal, horizon=horizon))
    result = pd.concat(parts, ignore_index=True)
    good = result["target_quality_valid"]
    result["rank_universe_count"] = result["session_date"].map(
        result.loc[good].groupby("session_date")["instrument_id"].size()
    ).fillna(0).astype(int)
    too_small = good & result["rank_universe_count"].lt(min_rank_cross_section)
    result.loc[too_small, ["future_return", "target_quality_valid"]] = [np.nan, False]
    result.loc[too_small, "target_quality_reason"] = "INSUFFICIENT_RANK_UNIVERSE"
    valid = result["target_quality_valid"]
    ranks = result.loc[valid].groupby("session_date")["future_return"].rank(
        method="average", pct=True
    )
    result["oracle_pct_rank"] = np.nan
    result.loc[valid, "oracle_pct_rank"] = ranks
    decile = np.ceil(result["oracle_pct_rank"] * 10).clip(1, 10)
    result["oracle_decile"] = decile.astype("Int8")
    result["oracle_extreme20"] = result["oracle_decile"].isin([1, 10]).where(valid).astype("boolean")
    result["session_date"] = pd.to_datetime(result["session_date"])
    result["decision_at"] = pd.to_datetime(result["decision_at"])
    if (result.loc[valid, "available_date"] <= result.loc[valid, "session_date"]).any():
        raise ValueError("Date de disponibilité du label non future")
    return result[list(OUTPUT_COLUMNS)].sort_values(["session_date", "instrument_id"]).reset_index(drop=True)


def _resolve_feature_panel(year: int, feature_root: Path) -> tuple[Path, dict[str, Any]]:
    from modelFactory.cn_feature_panel import ROOT as CODE_ROOT

    implementation_sha = hashlib.sha256((CODE_ROOT / "modelFactory" / "cn_feature_panel.py").read_bytes()).hexdigest()
    matches = []
    for path in feature_root.glob(f"cn-feature-{year}0101-{year}1231-*/report.json"):
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("implementation_sha256") == implementation_sha:
            matches.append((path, report))
    if len(matches) != 1:
        raise ValueError(f"{year}: {len(matches)} panels CN du moteur courant (attendu 1)")
    report_path, report = matches[0]
    panel_path = report_path.parent / "panel.parquet"
    if hashlib.sha256(panel_path.read_bytes()).hexdigest() != report["panel_sha256"]:
        raise ValueError("SHA du panel CN source différent")
    return panel_path, report


def _load_data(
    engine: Engine, *, start: date, end: date, candidate_ids: set[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if engine.url.database != "alpha_trade_cn":
        raise RuntimeError("Labels CN refusés hors alpha_trade_cn")
    search_end = end + timedelta(days=120)
    with engine.connect() as conn:
        history = conn.execute(text(
            "SELECT session_date FROM market_sessions WHERE market_code='CN_A' "
            "AND session_status='open' AND session_date<:start "
            "ORDER BY session_date DESC LIMIT 10"
        ), {"start": start}).scalars().all()
        history_start = history[-1] if history else start
        calendar = pd.read_sql(text(
            "SELECT session_date,open_at_utc FROM market_sessions "
            "WHERE market_code='CN_A' AND session_status='open' "
            "AND session_date BETWEEN :start AND :end ORDER BY session_date"
        ), conn, params={"start": history_start, "end": search_end})
        bars = pd.read_sql(text(
            "SELECT b.instrument_id,b.date,CAST(b.open AS DOUBLE) open,"
            "CAST(b.close AS DOUBLE) close,CAST(b.pre_close AS DOUBLE) pre_close,"
            "CAST(b.volume AS DOUBLE) volume,"
            "CAST(b.daily_return AS DOUBLE) daily_return,b.trading_status,b.available_at,"
            "l.policy_code limit_policy,l.locked_up,l.locked_down,"
            "CASE WHEN ca.instrument_id IS NULL THEN 0 ELSE 1 END factor_event,"
            "CAST(ca.factor_value AS DOUBLE) factor_value,"
            "CAST(ca.previous_factor_value AS DOUBLE) previous_factor_value,"
            "ca.factor_available_at "
            "FROM stock_bars_daily b LEFT JOIN cn_daily_price_limits l "
            "ON l.instrument_id=b.instrument_id AND l.session_date=b.date "
            "LEFT JOIN (SELECT instrument_id,ex_date,MAX(factor_value) factor_value,"
            "MAX(previous_factor_value) previous_factor_value,"
            "MAX(available_at) factor_available_at "
            "FROM cn_corporate_actions WHERE classification_status='UNCLASSIFIED_FACTOR_EVENT' "
            "GROUP BY instrument_id,ex_date) ca "
            "ON ca.instrument_id=b.instrument_id AND ca.ex_date=b.date "
            "WHERE b.market_code='CN_A' AND b.date BETWEEN :start AND :end "
            "ORDER BY b.instrument_id,b.date"
        ), conn, params={"start": history_start, "end": search_end})
    if calendar.empty or bars.empty:
        raise ValueError("Calendrier ou barres CN absents")
    bars = bars.loc[bars["instrument_id"].isin(candidate_ids)].copy()
    return bars, calendar


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_year(
    *, year: int, config_path: Path = DEFAULT_CONFIG,
    feature_root: Path = DEFAULT_FEATURE_ROOT, output_root: Path = DEFAULT_OUTPUT_ROOT,
    start_date: date | None = None, end_date: date | None = None,
) -> dict[str, Any]:
    if year < 2018 or year > 2025:
        raise ValueError("Sprint 10-A borné aux données CN 2018–2025")
    policy = CNLabelPolicy.from_yaml(config_path)
    panel_path, panel_report = _resolve_feature_panel(year, feature_root)
    candidates = pd.read_parquet(panel_path, columns=list(FEATURE_COLUMNS))
    candidates["session_date"] = pd.to_datetime(candidates["session_date"])
    candidates["decision_at"] = pd.to_datetime(candidates["decision_at"])
    start, end = start_date or date(year, 1, 1), end_date or date(year, 12, 31)
    if start.year != year or end.year != year or end < start:
        raise ValueError("Période CN hors année demandée")
    candidates = candidates.loc[candidates["session_date"].between(pd.Timestamp(start), pd.Timestamp(end))].copy()
    if candidates.empty or candidates.duplicated(["session_date", "instrument_id"]).any():
        raise ValueError("Panel candidat CN vide ou dupliqué")
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    bars, calendar = _load_data(
        engine, start=start, end=end,
        candidate_ids=set(candidates["instrument_id"].astype(int)),
    )
    implementation_sha = _file_sha(Path(__file__))
    identity = _fingerprint({
        "year": year, "start": start, "end": end,
        "policy": policy.__dict__, "config_sha": _file_sha(config_path),
        "feature_panel_sha": panel_report["panel_sha256"],
        "implementation_sha": implementation_sha,
    })
    directory = output_root / "cn_oracle_labels_v1" / f"cn-labels-{start:%Y%m%d}-{end:%Y%m%d}-{identity[:12]}"
    directory.mkdir(parents=True, exist_ok=True)
    horizon_reports = {}
    for horizon in policy.horizons:
        labels = compute_horizon_labels(
            candidates, bars, calendar, horizon=horizon,
            min_rank_cross_section=policy.min_rank_cross_section,
        )
        temp = directory / f"h{horizon}.tmp.parquet"
        final = directory / f"h{horizon}.parquet"
        labels.to_parquet(temp, index=False)
        new_sha = _file_sha(temp)
        if final.exists():
            temp.unlink()
            if _file_sha(final) != new_sha:
                raise RuntimeError(f"Labels CN H{horizon} existants divergents ; écrasement refusé")
        else:
            temp.replace(final)
        valid = labels["target_quality_valid"]
        matured = ~labels["target_quality_reason"].isin([
            "FUTURE_HORIZON_UNAVAILABLE", "AVAILABILITY_SESSION_UNAVAILABLE",
        ])
        adjusted_gap = (labels["future_return"] - labels["future_return_raw"]).abs()
        factor_rows = valid & labels["path_factor_event"]
        horizon_reports[str(horizon)] = {
            "rows": len(labels), "valid": int(valid.sum()), "valid_fraction": round(float(valid.mean()), 6),
            "matured_rows": int(matured.sum()),
            "valid_fraction_among_matured": round(float(valid.sum() / matured.sum()), 6) if matured.any() else None,
            "quality_reasons": labels["target_quality_reason"].value_counts().to_dict(),
            "verified_factor_path_rows": int(factor_rows.sum()),
            "unverified_factor_path_rows": int(labels["path_factor_unverified"].sum()),
            "median_adjusted_raw_gap_on_factor_paths": (
                round(float(adjusted_gap[factor_rows].median()), 6) if factor_rows.any() else None
            ),
            "deciles": {str(key): int(value) for key, value in labels["oracle_decile"].value_counts().sort_index().items()},
            "extreme20_fraction": round(float(labels.loc[valid, "oracle_extreme20"].mean()), 6) if valid.any() else None,
            "execution_data_eligible_fraction": round(float(labels["execution_data_eligible"].mean()), 6),
            "panel_sha256": new_sha, "path": str(final),
        }
    report = {
        "profile": "cn_oracle_labels_v1", "market_code": "CN_A", "year": year,
        "start": start.isoformat(), "end": end.isoformat(),
        "feature_panel_sha256": panel_report["panel_sha256"],
        "implementation_sha256": implementation_sha, "input_fingerprint": identity,
        "candidate_rows": len(candidates), "horizons": horizon_reports,
        "limit_policy": "flags_only_not_removed_from_ranking",
    }
    (directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
