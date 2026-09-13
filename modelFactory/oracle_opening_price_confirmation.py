"""E20-B — confirmation directionnelle price-only après Oracle TOP20.

Recherche uniquement : OHLC Alpaca SIP, sans volume/trades/VWAP, sans modèle,
sans modification du serving, des prédictions ou du backtest.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.dataset import load_oracle_targets
from modelFactory.oracle_opening_window_availability_audit import (
    E20AConfig,
    attach_next_oracle_session,
    load_opening_rows,
    load_oracle_events,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class E20BConfig:
    checkpoints_minutes: tuple[int, ...] = (5, 15, 30, 60)
    thresholds: tuple[float, ...] = (0.0, 0.0025, 0.005, 0.01)
    primary_checkpoint_minutes: int = 30
    primary_threshold: float = 0.005
    maximum_open_delay_minutes: int = 5
    maximum_checkpoint_staleness_minutes: int = 3
    minimum_dates: int = 126
    minimum_events: int = 5_000
    minimum_selected_events: int = 1_000
    minimum_tail_events: int = 500
    minimum_selection_rate: float = 0.15
    minimum_coverage: float = 0.60
    minimum_direction_accuracy: float = 0.52
    minimum_tail_accuracy: float = 0.55
    minimum_positive_fold_ratio: float = 0.60
    minimum_positive_semester_ratio: float = 0.60
    bootstrap_samples: int = 2_000
    bootstrap_block_sessions: int = 21
    bootstrap_seed: int = 20260914

    def __post_init__(self) -> None:
        if self.primary_checkpoint_minutes not in self.checkpoints_minutes:
            raise ValueError("Checkpoint primaire absent des checkpoints.")
        if self.primary_threshold not in self.thresholds:
            raise ValueError("Seuil primaire absent des seuils pré-enregistrés.")
        if min(self.checkpoints_minutes) <= 0 or min(self.thresholds) < 0:
            raise ValueError("Checkpoints/seuils invalides.")


def build_price_only_features(rows: pd.DataFrame, config: E20BConfig) -> pd.DataFrame:
    """Construit chaque checkpoint avec les seules barres déjà terminées."""
    base_columns = ["session_date", "symbol", "opening_price", "opening_delay_minutes"]
    feature_columns = [
        item
        for checkpoint in config.checkpoints_minutes
        for item in (
            f"price_{checkpoint}m", f"checkpoint_staleness_{checkpoint}m",
            f"return_{checkpoint}m", f"range_{checkpoint}m",
            f"max_up_{checkpoint}m", f"max_down_{checkpoint}m",
            f"close_location_{checkpoint}m", f"eligible_{checkpoint}m",
        )
    ]
    if rows.empty:
        return pd.DataFrame(columns=base_columns + feature_columns)
    required = {"session_date", "symbol", "minute_of_day", "bar_timestamp",
                "open", "high", "low", "close"}
    missing = required - set(rows.columns)
    if missing:
        raise ValueError(f"Barres Opening Window incomplètes: {sorted(missing)}")
    work = rows.copy()
    for column in ("minute_of_day", "open", "high", "low", "close"):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work["session_date"] = pd.to_datetime(work["session_date"], errors="coerce").dt.normalize()
    work["symbol"] = work["symbol"].astype(str).str.strip().str.upper()
    work = work.dropna(subset=list(required)).sort_values(
        ["session_date", "symbol", "minute_of_day", "bar_timestamp"]
    )
    output: list[dict[str, Any]] = []
    for (session_date, symbol), group in work.groupby(["session_date", "symbol"], sort=False):
        regular = group[group["minute_of_day"].between(570, 630, inclusive="both")]
        if regular.empty:
            continue
        first = regular.iloc[0]
        opening_price = float(first["open"])
        open_delay = int(first["minute_of_day"] - 570)
        row: dict[str, Any] = {
            "session_date": session_date, "symbol": symbol,
            "opening_price": opening_price, "opening_delay_minutes": open_delay,
        }
        valid_open = opening_price > 0 and open_delay <= config.maximum_open_delay_minutes
        for checkpoint in config.checkpoints_minutes:
            endpoint = 570 + checkpoint - 1
            path = regular[regular["minute_of_day"].between(570, endpoint, inclusive="both")]
            eligible = False
            close = high = low = staleness = np.nan
            if valid_open and not path.empty:
                last = path.iloc[-1]
                close = float(last["close"])
                high, low = float(path["high"].max()), float(path["low"].min())
                staleness = int(endpoint - last["minute_of_day"])
                eligible = (
                    staleness <= config.maximum_checkpoint_staleness_minutes
                    and close > 0 and low > 0
                    and high >= max(opening_price, close)
                    and low <= min(opening_price, close)
                )
            spread = high - low if eligible else np.nan
            row.update({
                f"price_{checkpoint}m": close if eligible else np.nan,
                f"checkpoint_staleness_{checkpoint}m": staleness,
                f"return_{checkpoint}m": close / opening_price - 1 if eligible else np.nan,
                f"range_{checkpoint}m": high / low - 1 if eligible else np.nan,
                f"max_up_{checkpoint}m": high / opening_price - 1 if eligible else np.nan,
                f"max_down_{checkpoint}m": low / opening_price - 1 if eligible else np.nan,
                f"close_location_{checkpoint}m": (
                    (close - low) / spread if eligible and spread > 0
                    else 0.5 if eligible else np.nan
                ),
                f"eligible_{checkpoint}m": bool(eligible),
            })
        output.append(row)
    return pd.DataFrame(output, columns=base_columns + feature_columns)


def attach_price_only_features(events: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "symbol", "future_return", "oracle_decile"}
    missing = required - set(events.columns)
    if missing:
        raise ValueError(f"Événements Oracle incomplets: {sorted(missing)}")
    mapped = attach_next_oracle_session(events)
    joined = mapped.merge(
        features, left_on=["target_session", "symbol"],
        right_on=["session_date", "symbol"], how="left", validate="one_to_one",
    )
    dates = pd.to_datetime(joined["date"])
    joined["semester"] = dates.dt.year.astype(str) + "H" + np.where(dates.dt.month.le(6), "1", "2")
    return joined


def _moving_block_ci(values: pd.Series, config: E20BConfig) -> tuple[float | None, float | None]:
    clean = pd.to_numeric(values, errors="coerce").dropna().to_numpy(float)
    if len(clean) < 2:
        return None, None
    block = min(config.bootstrap_block_sessions, len(clean))
    count = int(np.ceil(len(clean) / block))
    rng = np.random.default_rng(config.bootstrap_seed)
    means = np.empty(config.bootstrap_samples)
    for index in range(config.bootstrap_samples):
        starts = rng.integers(0, len(clean), size=count)
        sample = np.concatenate([
            clean[np.arange(start, start + block) % len(clean)] for start in starts
        ])[:len(clean)]
        means[index] = sample.mean()
    return tuple(float(value) for value in np.quantile(means, [0.025, 0.975]))


def evaluate_rules(
    joined: pd.DataFrame, config: E20BConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Évalue une grille pré-enregistrée ; seule la politique primaire décide."""
    summaries: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []
    semester_rows: list[dict[str, Any]] = []
    fold_column = (
        "directional_oracle_fold_start"
        if "directional_oracle_fold_start" in joined else "date"
    )
    for checkpoint in config.checkpoints_minutes:
        score_column = f"return_{checkpoint}m"
        for threshold in config.thresholds:
            observed = joined.dropna(
                subset=[score_column, "future_return", "oracle_decile"]
            ).copy()
            observed["decision"] = np.select(
                [observed[score_column].gt(threshold), observed[score_column].lt(-threshold)],
                [1, -1], default=0,
            )
            selected = observed[observed["decision"].ne(0)].copy()
            selected["correct_direction"] = (
                np.sign(selected["future_return"]) == selected["decision"]
            )
            selected["signed_target_return"] = (
                selected["decision"] * selected["future_return"]
            )
            tails = selected[pd.to_numeric(
                selected["oracle_decile"], errors="coerce"
            ).isin([1, 10])]
            tail_accuracy = np.nan
            if len(tails):
                expected = np.where(tails["oracle_decile"].eq(10), 1, -1)
                tail_accuracy = float((tails["decision"].to_numpy() == expected).mean())
            daily = selected.groupby("date")["signed_target_return"].mean().sort_index()
            ci_low, ci_high = _moving_block_ci(daily, config)
            folds = selected.groupby(fold_column)["signed_target_return"].mean()
            semesters = selected.groupby("semester")["signed_target_return"].mean()
            policy = f"price_path_{checkpoint}m_abs_{threshold:.4f}"
            summaries.append({
                "policy": policy, "checkpoint_minutes": checkpoint,
                "threshold": threshold, "oracle_events": len(joined),
                "observed_events": len(observed), "selected_events": len(selected),
                "observed_dates": int(observed["date"].nunique()),
                "price_coverage": len(observed) / len(joined) if len(joined) else 0,
                "selection_rate": len(selected) / len(observed) if len(observed) else 0,
                "long_share": float(selected["decision"].eq(1).mean()) if len(selected) else np.nan,
                "direction_accuracy": float(selected["correct_direction"].mean()) if len(selected) else np.nan,
                "tail_events": len(tails), "tail_direction_accuracy": tail_accuracy,
                "mean_signed_target_return": float(selected["signed_target_return"].mean()) if len(selected) else np.nan,
                "daily_mean_signed_target_return": float(daily.mean()) if len(daily) else np.nan,
                "daily_mean_ci95_low": ci_low, "daily_mean_ci95_high": ci_high,
                "positive_fold_ratio": float(folds.gt(0).mean()) if len(folds) else 0,
                "positive_semester_ratio": float(semesters.gt(0).mean()) if len(semesters) else 0,
            })
            for fold, group in selected.groupby(fold_column):
                fold_rows.append({
                    "policy": policy, "fold": fold, "events": len(group),
                    "direction_accuracy": group["correct_direction"].mean(),
                    "mean_signed_target_return": group["signed_target_return"].mean(),
                })
            for semester, group in selected.groupby("semester"):
                semester_rows.append({
                    "policy": policy, "semester": semester, "events": len(group),
                    "direction_accuracy": group["correct_direction"].mean(),
                    "mean_signed_target_return": group["signed_target_return"].mean(),
                })
    return pd.DataFrame(summaries), pd.DataFrame(fold_rows), pd.DataFrame(semester_rows)


def decide(summary: pd.DataFrame, config: E20BConfig) -> dict[str, Any]:
    primary = summary[
        summary["checkpoint_minutes"].eq(config.primary_checkpoint_minutes)
        & np.isclose(summary["threshold"], config.primary_threshold)
    ]
    if primary.empty:
        raise ValueError("Politique primaire E20-B absente.")
    row = primary.iloc[0].to_dict()
    gates = {
        "minimum_dates": bool(row["observed_dates"] >= config.minimum_dates),
        "minimum_events": bool(row["observed_events"] >= config.minimum_events),
        "minimum_coverage": bool(row["price_coverage"] >= config.minimum_coverage),
        "minimum_selected_events": bool(
            row["selected_events"] >= config.minimum_selected_events
        ),
        "minimum_tail_events": bool(row["tail_events"] >= config.minimum_tail_events),
        "minimum_selection_rate": bool(
            row["selection_rate"] >= config.minimum_selection_rate
        ),
        "direction_accuracy": bool(
            np.isfinite(row["direction_accuracy"])
            and row["direction_accuracy"] >= config.minimum_direction_accuracy
        ),
        "tail_direction_accuracy": bool(
            np.isfinite(row["tail_direction_accuracy"])
            and row["tail_direction_accuracy"] >= config.minimum_tail_accuracy
        ),
        "signed_target_ci95_positive": bool(
            row["daily_mean_ci95_low"] is not None and row["daily_mean_ci95_low"] > 0
        ),
        "positive_fold_ratio": bool(
            row["positive_fold_ratio"] >= config.minimum_positive_fold_ratio
        ),
        "positive_semester_ratio": bool(
            row["positive_semester_ratio"] >= config.minimum_positive_semester_ratio
        ),
    }
    data_gates = ("minimum_dates", "minimum_events", "minimum_coverage")
    verdict = (
        "BLOCKED_INSUFFICIENT_DATA" if not all(gates[name] for name in data_gates)
        else "GO_RESEARCH_VOLUME_ABLATION" if all(gates.values())
        else "NO_GO_PRICE_ONLY"
    )
    return {
        "verdict": verdict, "primary_policy": row["policy"],
        "primary_metrics": row, "gates": gates, "promotion_authorized": False,
    }


def _load_labeled_events(
    engine: Any, *, batch_id: str, horizon: int, oracle_path: Path,
    start_date: str | None, end_date: str | None,
) -> pd.DataFrame:
    oracle = load_oracle_events(oracle_path)
    labels = load_oracle_targets(engine, batch_id, horizon).rename(
        columns={"prediction_date": "date"}
    )
    keep = ["date", "symbol", "future_return", "oracle_decile", "target_quality_valid"]
    events = oracle.merge(labels[keep], on=["date", "symbol"], how="inner", validate="one_to_one")
    if start_date:
        events = events[events["date"].ge(pd.Timestamp(start_date))]
    if end_date:
        events = events[events["date"].le(pd.Timestamp(end_date))]
    return events.sort_values(["date", "symbol"]).reset_index(drop=True)


def load_price_features(path: Path) -> pd.DataFrame:
    """Charge le consolidé ou, après interruption, les partitions disponibles."""
    if path.is_file():
        return pd.read_parquet(path)
    consolidated = path / "price_only_features.parquet"
    if consolidated.is_file():
        return pd.read_parquet(consolidated)
    partitions = sorted((path / "session_features").glob("*.parquet"))
    if not partitions:
        raise ValueError(f"Aucune feature price-only dans {path}.")
    return pd.concat((pd.read_parquet(item) for item in partitions), ignore_index=True)


def run(
    *, batch_id: str, horizon: int, oracle_path: Path, output_root: Path,
    config: E20BConfig, start_date: str | None = None,
    end_date: str | None = None, features_path: Path | None = None,
) -> Path:
    engine = get_sqlalchemy_engine()
    events = _load_labeled_events(
        engine, batch_id=batch_id, horizon=horizon, oracle_path=oracle_path,
        start_date=start_date, end_date=end_date,
    )
    if events.empty:
        raise ValueError("Aucun événement Oracle TOP20 avec label de qualité valide.")
    if features_path is None:
        mapped = attach_next_oracle_session(events)
        rows = load_opening_rows(
            engine, start_session=mapped["target_session"].min(),
            end_session=mapped["target_session"].max(), config=E20AConfig(),
        )
        features = build_price_only_features(rows, config)
        feature_source = "stock_opening_window_bars"
    else:
        features = load_price_features(features_path)
        feature_source = str(features_path)
    joined = attach_price_only_features(events, features)
    summary, folds, semesters = evaluate_rules(joined, config)
    decision = decide(summary, config)
    run_id = f"e20b-opening-price-only-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    features.to_parquet(output / "price_only_features.parquet", index=False)
    joined.to_parquet(output / "oracle_price_only_events.parquet", index=False)
    summary.to_csv(output / "policy_summary.csv", index=False)
    folds.to_csv(output / "policy_by_fold.csv", index=False)
    semesters.to_csv(output / "policy_by_semester.csv", index=False)
    report = {
        "schema_version": 1, "experiment": "E20_B_OPENING_PRICE_ONLY",
        "status": "complete", "research_only": True,
        "model_trained": False, "production_change": False,
        "generated_at": datetime.now(UTC).isoformat(), "run_id": run_id,
        "source": {
            "batch_id": batch_id, "horizon": horizon,
            "oracle_path": str(oracle_path), "provider": "alpaca",
            "feed": "sip", "adjustment": "raw",
            "price_features": feature_source,
        },
        "feature_contract": {
            "price_columns_used": ["open", "high", "low", "close"],
            "forbidden_columns": [
                "minute_volume", "cumulative_volume", "trade_count", "vwap",
            ],
            "volume_required": False,
            "entry_warning": (
                "Le rendement signé emploie le target H Oracle et n'est pas "
                "un PnL d'entrée retardée. Un replay économique séparé est requis."
            ),
        },
        "config": asdict(config),
        "population": {
            "oracle_events": len(events), "joined_events": len(joined),
            "price_feature_rows": len(features),
        },
        **decision,
        "next_action": (
            "pré-enregistrer E20-C volume incrémental sur la même population"
            if decision["verdict"] == "GO_RESEARCH_VOLUME_ABLATION" else
            "poursuivre la collecte prospective puis relancer E20-A/E20-B"
            if decision["verdict"] == "BLOCKED_INSUFFICIENT_DATA" else
            "fermer la confirmation price-only; ne pas ajouter le volume sans nouvelle hypothèse"
        ),
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E20-B terminé: %s verdict=%s", output, decision["verdict"])
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--oracle-path", type=Path)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument(
        "--features-path", type=Path,
        help="Parquet consolidé ou dossier du backfill compact E20.",
    )
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("artifacts/research/oracle_opening_price_confirmation"),
    )
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    oracle_path = args.oracle_path or (
        Path("artifacts/models") / args.batch_id / "_oracle_oof_gate.parquet"
    )
    output = run(
        batch_id=args.batch_id, horizon=args.horizon, oracle_path=oracle_path,
        output_root=args.output_root,
        config=E20BConfig(bootstrap_samples=args.bootstrap_samples),
        start_date=args.start_date, end_date=args.end_date,
        features_path=args.features_path,
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E20-B terminé: {output}")
    print(report["verdict"])


if __name__ == "__main__":
    main()
