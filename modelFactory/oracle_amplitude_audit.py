"""E6-A research-only: audit direction-neutral de l'amplitude Oracle OOF.

L'expérience ne cherche jamais le sens du mouvement. Elle vérifie si le TOP20
du score Oracle, calculé hors échantillon, concentre davantage d'amplitude
future que les 80 % restants et que la tranche immédiatement inférieure.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_universe_bars
from modelFactory.labeling import _compute_atr
from modelFactory.shared_directional import DEFAULT_ARTIFACTS_ROOT, _semester_label

LOGGER = logging.getLogger(__name__)

SCORE_COL = "directional_oracle_extreme_pct"
ELIGIBLE_COL = "directional_oracle_eligible"
OOF_COL = "directional_oracle_oof_available"
GROUP_COL = "oracle_amplitude_group"
TOP20 = "TOP20"
NEXT20 = "NEXT20"
BOTTOM60 = "BOTTOM60"
REST80 = "REST80"


@dataclass(frozen=True, slots=True)
class AmplitudeAuditConfig:
    horizons: tuple[int, ...] = (3, 5, 10, 20)
    pool_pct: float = 0.20
    entry_delay_sessions: int = 1
    max_entry_gap_pct: float = 0.03
    atr_window: int = 14
    barrier_atr_mult: float = 3.0
    barrier_max_pct: float = 0.07
    min_atr_pct: float = 0.001
    max_path_price_ratio: float = 4.0
    min_daily_universe: int = 20
    min_relative_lift: float = 0.10
    min_positive_day_rate: float = 0.55
    min_daily_spearman: float = 0.03
    min_positive_semester_rate: float = 0.60

    def __post_init__(self) -> None:
        if not self.horizons or any(h < 1 for h in self.horizons):
            raise ValueError("Les horizons E6 doivent être des entiers positifs.")
        if len(set(self.horizons)) != len(self.horizons):
            raise ValueError("Les horizons E6 doivent être uniques.")
        if not 0 < self.pool_pct < 0.5:
            raise ValueError("pool_pct doit être dans ]0, 0.5[.")
        if self.entry_delay_sessions < 1:
            raise ValueError("E6 exige une entrée différée d'au moins une séance.")
        if not 0 <= self.max_entry_gap_pct < 1:
            raise ValueError("max_entry_gap_pct doit être dans [0,1[.")
        if self.atr_window < 2 or self.min_daily_universe < 2:
            raise ValueError("Fenêtre ATR ou univers quotidien E6 invalide.")
        if self.max_path_price_ratio <= 1:
            raise ValueError("max_path_price_ratio doit être supérieur à 1.")


def load_oof_gate(path: Path, config: AmplitudeAuditConfig) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Charge et valide le panel Oracle OOF complet, sans reconstruire le score."""
    if not path.exists():
        raise FileNotFoundError(f"Gate Oracle OOF introuvable: {path}")
    gate = pd.read_parquet(path)
    required = {"date", "symbol", SCORE_COL, ELIGIBLE_COL, OOF_COL}
    missing = sorted(required.difference(gate.columns))
    if missing:
        raise ValueError(f"Gate Oracle OOF incomplet: {missing}")
    gate = gate[list(required)].copy()
    gate["date"] = pd.to_datetime(gate["date"], errors="coerce").dt.normalize()
    gate["symbol"] = gate["symbol"].astype(str).str.upper().str.strip()
    gate[SCORE_COL] = pd.to_numeric(gate[SCORE_COL], errors="coerce")
    gate[ELIGIBLE_COL] = gate[ELIGIBLE_COL].fillna(False).astype(bool)
    gate[OOF_COL] = gate[OOF_COL].fillna(False).astype(bool)
    gate = gate.dropna(subset=["date", "symbol", SCORE_COL])
    gate = gate[gate[OOF_COL]].copy()
    if gate.empty:
        raise ValueError("Le gate ne contient aucune ligne Oracle OOF disponible.")
    if gate.duplicated(["date", "symbol"]).any():
        raise ValueError("Le gate Oracle OOF n'est pas unique par date/symbole.")
    if not gate[SCORE_COL].between(0, 1).all():
        raise ValueError("Le percentile Oracle doit rester dans [0,1].")
    threshold = 1.0 - config.pool_pct
    expected = gate[SCORE_COL].ge(threshold)
    mismatch = gate[ELIGIBLE_COL].ne(expected)
    # Les égalités au seuil peuvent être résolues par le rang canonique. Une
    # divergence massive indiquerait toutefois un mauvais contrat de gate.
    mismatch_rate = float(mismatch.mean())
    if mismatch_rate > 0.02:
        raise ValueError(
            f"Gate TOP20 incohérent avec son percentile ({mismatch_rate:.2%} de divergences)."
        )
    diagnostics = {
        "rows": int(len(gate)), "dates": int(gate["date"].nunique()),
        "symbols": int(gate["symbol"].nunique()),
        "first_date": str(gate["date"].min().date()),
        "last_date": str(gate["date"].max().date()),
        "eligible_share": float(gate[ELIGIBLE_COL].mean()),
        "percentile_eligibility_mismatch_rate": mismatch_rate,
    }
    return gate.sort_values(["symbol", "date"]).reset_index(drop=True), diagnostics


def build_amplitude_panel(bars: pd.DataFrame, config: AmplitudeAuditConfig) -> pd.DataFrame:
    """Calcule des métriques futures symétriques depuis l'open J+1.

    H désigne le nombre de séances détenues, séance d'entrée comprise. Le
    terminal est donc le close de la H-ième séance et les excursions utilisent
    les high/low de ces mêmes H séances. Toute fenêtre incomplète est censurée.
    """
    required = {"date", "symbol", "open", "high", "low", "close"}
    missing = sorted(required.difference(bars.columns))
    if missing:
        raise ValueError(f"Barres incomplètes pour E6: {missing}")
    outputs: list[pd.DataFrame] = []
    for symbol, raw in bars.groupby("symbol", sort=False):
        part = raw.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
        if len(part) <= config.atr_window + config.entry_delay_sessions:
            continue
        opens = pd.to_numeric(part["open"], errors="coerce").to_numpy(float)
        highs = pd.to_numeric(part["high"], errors="coerce").to_numpy(float)
        lows = pd.to_numeric(part["low"], errors="coerce").to_numpy(float)
        closes = pd.to_numeric(part["close"], errors="coerce").to_numpy(float)
        atr = _compute_atr(highs, lows, closes, config.atr_window)
        rows: list[dict[str, Any]] = []
        for signal_idx in range(len(part)):
            entry_idx = signal_idx + config.entry_delay_sessions
            row: dict[str, Any] = {
                "date": pd.Timestamp(part.loc[signal_idx, "date"]).normalize(),
                "symbol": str(symbol).upper(),
            }
            eligible = False
            entry = np.nan
            gap = np.nan
            barrier_pct = np.nan
            if entry_idx < len(part) and np.isfinite(closes[signal_idx]) and closes[signal_idx] > 0:
                entry = opens[entry_idx]
                gap = abs(entry / closes[signal_idx] - 1.0) if np.isfinite(entry) else np.nan
                atr_value = atr[signal_idx]
                eligible = bool(
                    np.isfinite(entry) and entry > 0 and np.isfinite(atr_value)
                    and (config.max_entry_gap_pct == 0 or gap <= config.max_entry_gap_pct)
                )
                if eligible:
                    barrier_pct = min(
                        config.barrier_atr_mult * max(float(atr_value) / entry, config.min_atr_pct),
                        config.barrier_max_pct,
                    )
            row.update({
                "amplitude_entry_eligible": eligible,
                "amplitude_entry_gap_abs": float(gap) if np.isfinite(gap) else np.nan,
                "amplitude_barrier_pct": float(barrier_pct) if np.isfinite(barrier_pct) else np.nan,
            })
            if eligible:
                for horizon in config.horizons:
                    last_exclusive = entry_idx + horizon
                    if last_exclusive > len(part):
                        continue
                    window_high = highs[entry_idx:last_exclusive]
                    window_low = lows[entry_idx:last_exclusive]
                    window_close = closes[entry_idx:last_exclusive]
                    previous_closes = np.concatenate(([entry], window_close[:-1]))
                    path_ratios = window_close / previous_closes
                    if (
                        len(window_close) != horizon
                        or not np.isfinite(window_high).all()
                        or not np.isfinite(window_low).all()
                        or not np.isfinite(window_close).all()
                        or (window_close <= 0).any()
                        or (path_ratios > config.max_path_price_ratio).any()
                        or (path_ratios < 1.0 / config.max_path_price_ratio).any()
                    ):
                        continue
                    upside = float(np.max(window_high) / entry - 1.0)
                    downside = float(1.0 - np.min(window_low) / entry)
                    terminal = float(window_close[-1] / entry - 1.0)
                    path = np.concatenate(([entry], window_close))
                    log_returns = np.diff(np.log(path))
                    prefix = f"h{horizon}_"
                    row.update({
                        prefix + "terminal_return": terminal,
                        prefix + "abs_terminal_return": abs(terminal),
                        prefix + "max_up_excursion": upside,
                        prefix + "max_down_excursion": downside,
                        prefix + "max_abs_excursion": max(upside, downside),
                        prefix + "max_abs_excursion_capped_100pct": min(
                            max(upside, downside), 1.0
                        ),
                        prefix + "realized_range": float((np.max(window_high) - np.min(window_low)) / entry),
                        prefix + "realized_vol": float(np.sqrt(np.sum(np.square(log_returns)))),
                        prefix + "barrier_hit": float(max(upside, downside) >= barrier_pct),
                    })
            rows.append(row)
        outputs.append(pd.DataFrame(rows))
    if not outputs:
        return pd.DataFrame()
    panel = pd.concat(outputs, ignore_index=True)
    if panel.duplicated(["date", "symbol"]).any():
        raise ValueError("Panel d'amplitude E6 non unique par date/symbole.")
    return panel


def attach_amplitude(gate: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    """Joint le futur au gate OOF sans changer la population Oracle."""
    if panel.empty:
        raise ValueError("Panel d'amplitude E6 vide.")
    return gate.merge(panel, on=["date", "symbol"], how="left", validate="one_to_one")


def assign_groups(events: pd.DataFrame, config: AmplitudeAuditConfig) -> pd.DataFrame:
    result = events.copy()
    threshold = 1.0 - config.pool_pct
    next_threshold = 1.0 - 2.0 * config.pool_pct
    result[GROUP_COL] = np.select(
        [result[SCORE_COL].ge(threshold), result[SCORE_COL].ge(next_threshold)],
        [TOP20, NEXT20], default=BOTTOM60,
    )
    return result


def _safe_mean(series: pd.Series) -> float | None:
    value = pd.to_numeric(series, errors="coerce").mean()
    return float(value) if np.isfinite(value) else None


def _safe_spearman(group: pd.DataFrame, metric: str) -> float | None:
    values = group[[SCORE_COL, metric]].dropna()
    if len(values) < 3 or values[SCORE_COL].nunique() < 2 or values[metric].nunique() < 2:
        return None
    value = values[SCORE_COL].corr(values[metric], method="spearman")
    return float(value) if np.isfinite(value) else None


def build_daily_comparisons(
    events: pd.DataFrame, metric: str, *, min_daily_universe: int
) -> pd.DataFrame:
    """Construit les écarts journaliers appariés TOP20 vs contrôles."""
    rows: list[dict[str, Any]] = []
    for date, group in events.groupby("date", sort=True):
        valid = group.dropna(subset=[metric])
        if len(valid) < min_daily_universe:
            continue
        top = valid[valid[GROUP_COL].eq(TOP20)][metric]
        next20 = valid[valid[GROUP_COL].eq(NEXT20)][metric]
        rest = valid[~valid[GROUP_COL].eq(TOP20)][metric]
        if top.empty or next20.empty or rest.empty:
            continue
        top_mean, rest_mean, next_mean = float(top.mean()), float(rest.mean()), float(next20.mean())
        rows.append({
            "date": pd.Timestamp(date).normalize(), "metric": metric,
            "universe_count": int(len(valid)), "top20_count": int(len(top)),
            "top20_mean": top_mean, "rest80_mean": rest_mean, "next20_mean": next_mean,
            "top20_median": float(top.median()),
            "rest80_median": float(rest.median()),
            "next20_median": float(next20.median()),
            "lift_vs_rest80": top_mean - rest_mean,
            "lift_vs_next20": top_mean - next_mean,
            "relative_lift_vs_rest80": (
                top_mean / rest_mean - 1.0 if rest_mean != 0 else np.nan
            ),
            "daily_spearman": _safe_spearman(valid, metric),
        })
    return pd.DataFrame(rows)


def summarize_daily_comparison(daily: pd.DataFrame) -> dict[str, Any]:
    if daily.empty:
        return {"dates": 0}
    lift = pd.to_numeric(daily["lift_vs_rest80"], errors="coerce").dropna()
    relative = pd.to_numeric(daily["relative_lift_vs_rest80"], errors="coerce").dropna()
    spearman = pd.to_numeric(daily["daily_spearman"], errors="coerce").dropna()
    std = float(lift.std(ddof=1)) if len(lift) > 1 else 0.0
    se = std / math.sqrt(len(lift)) if len(lift) else np.nan
    mean_lift = float(lift.mean()) if len(lift) else np.nan
    semesters = daily.assign(semester=daily["date"].map(_semester_label)).groupby("semester").agg(
        dates=("date", "size"), mean_lift=("lift_vs_rest80", "mean"),
        mean_relative_lift=("relative_lift_vs_rest80", "mean"),
        mean_spearman=("daily_spearman", "mean"),
    ).reset_index()
    return {
        "dates": int(len(daily)),
        "mean_top20": _safe_mean(daily["top20_mean"]),
        "mean_rest80": _safe_mean(daily["rest80_mean"]),
        "mean_next20": _safe_mean(daily["next20_mean"]),
        "mean_daily_top20_median": _safe_mean(daily["top20_median"]),
        "mean_daily_rest80_median": _safe_mean(daily["rest80_median"]),
        "mean_daily_next20_median": _safe_mean(daily["next20_median"]),
        "mean_lift_vs_rest80": mean_lift,
        "mean_lift_vs_next20": _safe_mean(daily["lift_vs_next20"]),
        "mean_relative_lift_vs_rest80": float(relative.mean()) if len(relative) else None,
        "median_relative_lift_vs_rest80": float(relative.median()) if len(relative) else None,
        "positive_day_rate": float(lift.gt(0).mean()) if len(lift) else None,
        "mean_daily_spearman": float(spearman.mean()) if len(spearman) else None,
        "positive_spearman_rate": float(spearman.gt(0).mean()) if len(spearman) else None,
        "mean_lift_normal_95pct_ci": [mean_lift - 1.96 * se, mean_lift + 1.96 * se],
        "semesters": semesters.to_dict(orient="records"),
        "positive_semester_rate": float(semesters["mean_lift"].gt(0).mean()),
    }


def decile_table(events: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    frame = events.copy()
    frame["oracle_decile"] = np.minimum(np.floor(frame[SCORE_COL] * 10).astype(int) + 1, 10)
    rows: list[dict[str, Any]] = []
    for (date, decile), group in frame.groupby(["date", "oracle_decile"], sort=True):
        row: dict[str, Any] = {"date": date, "oracle_decile": int(decile), "count": len(group)}
        row.update({metric: _safe_mean(group[metric]) for metric in metrics})
        rows.append(row)
    daily = pd.DataFrame(rows)
    aggregations: dict[str, tuple[str, str]] = {"dates": ("date", "nunique"), "mean_count": ("count", "mean")}
    aggregations.update({metric: (metric, "mean") for metric in metrics})
    return daily.groupby("oracle_decile").agg(**aggregations).reset_index()


def evaluate_amplitude(events: pd.DataFrame, config: AmplitudeAuditConfig) -> tuple[dict[str, Any], pd.DataFrame]:
    """Évalue l'amplitude avec des comparaisons cross-sectionnelles appariées."""
    events = assign_groups(events, config)
    metrics = [
        f"h{h}_{suffix}" for h in config.horizons for suffix in (
            "abs_terminal_return", "max_abs_excursion", "realized_range",
            "max_abs_excursion_capped_100pct", "realized_vol", "barrier_hit",
        )
    ]
    daily_frames: list[pd.DataFrame] = []
    summaries: dict[str, Any] = {}
    for metric in metrics:
        if metric not in events:
            continue
        daily = build_daily_comparisons(
            events, metric, min_daily_universe=config.min_daily_universe
        )
        summaries[metric] = summarize_daily_comparison(daily)
        if not daily.empty:
            daily_frames.append(daily)
    daily_all = pd.concat(daily_frames, ignore_index=True) if daily_frames else pd.DataFrame()
    primary_h = max(config.horizons)
    primary_name = f"h{primary_h}_max_abs_excursion_capped_100pct"
    secondary_name = f"h{primary_h}_barrier_hit"
    primary = summaries.get(primary_name, {})
    horizon_support = []
    for horizon in config.horizons:
        summary = summaries.get(f"h{horizon}_max_abs_excursion_capped_100pct", {})
        relative = summary.get("mean_relative_lift_vs_rest80")
        horizon_support.append(relative is not None and relative > 0)
    semester_rate = primary.get("positive_semester_rate")
    gates = {
        "primary_relative_lift_gte_min": (
            primary.get("mean_relative_lift_vs_rest80") is not None
            and primary["mean_relative_lift_vs_rest80"] >= config.min_relative_lift
        ),
        "primary_positive_day_rate_gte_min": (
            primary.get("positive_day_rate") is not None
            and primary["positive_day_rate"] >= config.min_positive_day_rate
        ),
        "primary_daily_spearman_gte_min": (
            primary.get("mean_daily_spearman") is not None
            and primary["mean_daily_spearman"] >= config.min_daily_spearman
        ),
        "primary_positive_semester_rate_gte_min": (
            semester_rate is not None and semester_rate >= config.min_positive_semester_rate
        ),
        "capped_max_excursion_lift_positive_all_horizons": all(horizon_support),
        "barrier_hit_lift_positive": (
            summaries.get(secondary_name, {}).get("mean_lift_vs_rest80") is not None
            and summaries[secondary_name]["mean_lift_vs_rest80"] > 0
        ),
    }
    return {
        "primary_metric": primary_name,
        "metric_summaries": summaries,
        "gates": {**gates, "passed": int(sum(gates.values())), "total": len(gates),
                  "all_passed": all(gates.values())},
        "deciles": decile_table(events, metrics).to_dict(orient="records"),
    }, daily_all


def run_amplitude_audit(
    engine: Any,
    oracle_batch_id: str,
    *,
    start_date: str,
    end_date: str,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    symbols_limit: int | None = None,
    config: AmplitudeAuditConfig | None = None,
) -> tuple[Path, dict[str, Any]]:
    audit = config or AmplitudeAuditConfig()
    gate_path = Path("artifacts/models") / oracle_batch_id / "_oracle_oof_gate.parquet"
    gate, gate_diagnostics = load_oof_gate(gate_path, audit)
    requested_start, requested_end = pd.Timestamp(start_date), pd.Timestamp(end_date)
    gate = gate[gate["date"].between(requested_start, requested_end)].copy()
    symbols = sorted(gate["symbol"].unique())
    if symbols_limit:
        symbols = symbols[:symbols_limit]
        gate = gate[gate["symbol"].isin(symbols)].copy()
    if gate.empty:
        raise ValueError("Aucune observation Oracle OOF dans la période E6 demandée.")
    warmup = (requested_start - pd.offsets.BDay(audit.atr_window + 5)).date()
    future = (requested_end + pd.offsets.BDay(max(audit.horizons) + 3)).date()
    LOGGER.info("E6 charge %d symboles de %s à %s", len(symbols), warmup, future)
    bars = load_universe_bars(engine, symbols, start_date=warmup, end_date=future)
    events = attach_amplitude(gate, build_amplitude_panel(bars, audit))
    primary_col = f"h{max(audit.horizons)}_max_abs_excursion_capped_100pct"
    population = {
        "gate_rows_in_period": int(len(gate)), "symbols": int(len(symbols)),
        "dates": int(gate["date"].nunique()), "bars": int(len(bars)),
        "entry_eligible_rows": int(events["amplitude_entry_eligible"].fillna(False).sum()),
        "primary_complete_rows": int(events[primary_col].notna().sum()),
        "primary_complete_share": float(events[primary_col].notna().mean()),
    }
    evaluation, daily = evaluate_amplitude(events, audit)
    run_id = f"oracle-amplitude-audit-{datetime.now(UTC):%Y%m%d%H%M%S}-{oracle_batch_id[-6:]}"
    output = artifacts_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    events = assign_groups(events, audit)
    events.to_parquet(output / "event_metrics.parquet", index=False)
    daily.to_parquet(output / "daily_metrics.parquet", index=False)
    pd.DataFrame(evaluation["deciles"]).to_csv(output / "decile_metrics.csv", index=False)
    report = {
        "schema_version": 1, "run_id": run_id,
        "experiment": "E6_A_oracle_direction_neutral_amplitude_audit_v1",
        "status": "completed", "research_only": True, "serving_ready": False,
        "source_oracle_batch_id": oracle_batch_id,
        "gate_path": str(gate_path), "gate_diagnostics": gate_diagnostics,
        "requested_period": {"start": start_date, "end": end_date},
        "measurement_contract": {
            "signal_time": "close J", "entry_time": "open J+1",
            "holding_horizon": "H sessions including entry session",
            "future_window_required_complete": True,
            "corporate_discontinuity_filter": (
                "censor horizon if an adjacent close ratio exceeds "
                f"{audit.max_path_price_ratio}:1 in either direction"
            ),
            "primary_metric_cap": "100% underlying excursion per event",
            "direction_used_for_selection": False,
            "comparison": "daily paired TOP20 vs REST80 and NEXT20",
            "oracle_score": SCORE_COL,
        },
        "config": asdict(audit), "population": population, "evaluation": evaluation,
        "decision": {
            "open_E6_B_options_research": evaluation["gates"]["all_passed"],
            "rule": "E6-B n'est ouverte que si les six gates d'amplitude préfixés passent.",
        },
        "artifact_paths": {
            "events": str(output / "event_metrics.parquet"),
            "daily": str(output / "daily_metrics.parquet"),
            "deciles": str(output / "decile_metrics.csv"),
        },
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return output, report


def _summary(path: Path, report: dict[str, Any]) -> str:
    evaluation = report["evaluation"]
    primary = evaluation["metric_summaries"][evaluation["primary_metric"]]
    barrier = evaluation["metric_summaries"][
        f"h{max(report['config']['horizons'])}_barrier_hit"
    ]
    return "\n".join([
        f"E6-A amplitude Oracle terminé: {path}",
        f"TOP20 max excursion H{max(report['config']['horizons'])}: "
        f"{primary['mean_top20']:.2%} vs REST80 {primary['mean_rest80']:.2%} "
        f"(lift relatif {primary['mean_relative_lift_vs_rest80']:+.1%})",
        f"Taux de barrière: {barrier['mean_top20']:.1%} vs {barrier['mean_rest80']:.1%}",
        f"Gates amplitude: {evaluation['gates']['passed']}/{evaluation['gates']['total']}",
        "E6-B options: " + ("OUVERTE" if report["decision"]["open_E6_B_options_research"] else "REJETÉE"),
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-batch-id", required=True)
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--horizons", default="3,5,10,20")
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    parser.add_argument("--symbols-limit", type=int, default=None)
    parser.add_argument("--pool-pct", type=float, default=0.20)
    parser.add_argument("--max-entry-gap-pct", type=float, default=0.03)
    parser.add_argument("--min-daily-universe", type=int, default=20)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    config = AmplitudeAuditConfig(
        horizons=tuple(int(value) for value in args.horizons.split(",")),
        pool_pct=args.pool_pct, max_entry_gap_pct=args.max_entry_gap_pct,
        min_daily_universe=args.min_daily_universe,
    )
    path, report = run_amplitude_audit(
        get_sqlalchemy_engine(), args.oracle_batch_id,
        start_date=args.start_date, end_date=args.end_date,
        artifacts_root=args.artifacts_root, symbols_limit=args.symbols_limit, config=config,
    )
    print(_summary(path, report))


if __name__ == "__main__":
    main()
