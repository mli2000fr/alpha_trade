from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid4

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from common.utils import configure_root_logging
from database.connection import get_sqlalchemy_engine
from event_sentiment.signal_aggregator import SentimentSignalAggregator

LOGGER = logging.getLogger(__name__)
RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_run_id(prefix: str) -> str:
    return f"{prefix}-{_utc_now_naive().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


@dataclass(frozen=True, slots=True)
class SentimentCalibrationScenario:
    sentiment_weight: float
    macro_weight: float
    quant_weight: float

    @property
    def scenario_name(self) -> str:
        return f"sent_{self.sentiment_weight:.2f}_macro_{self.macro_weight:.2f}_quant_{self.quant_weight:.2f}"


@dataclass(frozen=True, slots=True)
class SentimentCalibrationResult:
    start_date: date
    end_date: date
    scenarios_evaluated: int
    rows_evaluated: int
    best_scenario_name: str
    best_overall_score: float
    artifact_dir: str | None = None


class SentimentWeightCalibrator:
    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or get_sqlalchemy_engine()

    @staticmethod
    def default_scenarios() -> list[SentimentCalibrationScenario]:
        scenarios: list[SentimentCalibrationScenario] = []
        for sentiment_weight in (0.05, 0.10, 0.15, 0.20, 0.25):
            for macro_weight in (0.00, 0.05, 0.10, 0.15):
                quant_weight = round(1.0 - sentiment_weight - macro_weight, 6)
                if quant_weight < 0.50:
                    continue
                scenarios.append(
                    SentimentCalibrationScenario(
                        sentiment_weight=round(sentiment_weight, 4),
                        macro_weight=round(macro_weight, 4),
                        quant_weight=quant_weight,
                    )
                )
        return scenarios

    def load_dataset(
        self,
        start_date: date,
        end_date: date,
        horizons: tuple[int, ...] = (5, 10, 20),
        candidates_only: bool = True,
    ) -> pd.DataFrame:
        query = text(
            """
            SELECT
                h.snapshot_date,
                h.symbol,
                h.sector,
                h.final_score,
                h.sentiment_net_agg,
                h.sector_impact_agg,
                h.final_score_sentiment,
                h.is_candidate,
                b.date AS bar_date,
                COALESCE(b.adj_close, b.close) AS close_price
            FROM stock_scores_history h
            JOIN stock_bars_daily b
              ON b.symbol = h.symbol
             AND b.date >= h.snapshot_date
             AND b.date <= :end_date_plus_buffer
            WHERE h.snapshot_date BETWEEN :start_date AND :end_date
              AND (:candidates_only = 0 OR h.is_candidate = 1)
            ORDER BY h.snapshot_date, h.symbol, b.date
            """
        )
        with self.engine.connect() as conn:
            raw = pd.read_sql_query(
                query,
                conn,
                params={
                    "start_date": start_date,
                    "end_date": end_date,
                    "end_date_plus_buffer": end_date + pd.Timedelta(days=max(horizons) * 3),
                    "candidates_only": 1 if candidates_only else 0,
                },
            )
        if raw.empty:
            return pd.DataFrame()
        raw["snapshot_date"] = pd.to_datetime(raw["snapshot_date"])
        raw["bar_date"] = pd.to_datetime(raw["bar_date"])
        return self.build_forward_return_frame(raw, horizons=horizons)

    @staticmethod
    def build_forward_return_frame(raw: pd.DataFrame, horizons: tuple[int, ...] = (5, 10, 20)) -> pd.DataFrame:
        if raw.empty:
            return pd.DataFrame()

        base_columns = [
            "snapshot_date",
            "symbol",
            "sector",
            "final_score",
            "sentiment_net_agg",
            "sector_impact_agg",
            "final_score_sentiment",
            "is_candidate",
        ]
        snapshot_df = raw[base_columns].drop_duplicates(subset=["snapshot_date", "symbol"], keep="first").copy()
        price_df = raw[["snapshot_date", "symbol", "bar_date", "close_price"]].copy()
        price_df = price_df.sort_values(["snapshot_date", "symbol", "bar_date"]).reset_index(drop=True)

        forward_map: dict[tuple[pd.Timestamp, str], dict[str, float]] = {}
        for (snapshot_date, symbol), group in price_df.groupby(["snapshot_date", "symbol"], sort=False):
            ordered = group.sort_values("bar_date").reset_index(drop=True)
            if ordered.empty:
                continue
            entry_price = float(ordered.loc[0, "close_price"])
            row_metrics: dict[str, float] = {}
            for horizon in horizons:
                if len(ordered) <= horizon:
                    row_metrics[f"forward_return_{horizon}d"] = float("nan")
                    continue
                exit_price = float(ordered.loc[horizon, "close_price"])
                row_metrics[f"forward_return_{horizon}d"] = (exit_price / entry_price) - 1.0 if entry_price else float("nan")
            forward_map[(pd.Timestamp(snapshot_date), str(symbol))] = row_metrics

        for horizon in horizons:
            snapshot_df[f"forward_return_{horizon}d"] = [
                forward_map.get((pd.Timestamp(row["snapshot_date"]), str(row["symbol"])), {}).get(f"forward_return_{horizon}d")
                for row in snapshot_df.to_dict(orient="records")
            ]
        return snapshot_df

    @staticmethod
    def _normalize_signal(series: pd.Series) -> pd.Series:
        return SentimentSignalAggregator._normalize_signed_signal(series)

    def evaluate_scenarios(
        self,
        dataset: pd.DataFrame,
        scenarios: Iterable[SentimentCalibrationScenario],
        horizons: tuple[int, ...] = (5, 10, 20),
        top_n: int = 20,
    ) -> pd.DataFrame:
        if dataset.empty:
            return pd.DataFrame()

        base = dataset.copy()
        base["quant_score"] = pd.Series(pd.to_numeric(base["final_score"], errors="coerce"), index=base.index).fillna(0.0).clip(0.0, 1.0)
        base["sentiment_signal_norm"] = self._normalize_signal(base["sentiment_net_agg"])
        base["macro_signal_norm"] = self._normalize_signal(base["sector_impact_agg"])

        results: list[dict[str, object]] = []
        for scenario in scenarios:
            working = base.copy()
            working["composite_score"] = (
                scenario.quant_weight * working["quant_score"]
                + scenario.sentiment_weight * working["sentiment_signal_norm"]
                + scenario.macro_weight * working["macro_signal_norm"]
            ).clip(0.0, 1.0)

            metrics: dict[str, object] = {
                "scenario_name": scenario.scenario_name,
                "sentiment_weight": scenario.sentiment_weight,
                "macro_weight": scenario.macro_weight,
                "quant_weight": scenario.quant_weight,
                "rows_evaluated": int(len(working)),
                "days_evaluated": int(working["snapshot_date"].nunique()),
            }
            per_horizon_scores: list[float] = []
            for horizon in horizons:
                return_col = f"forward_return_{horizon}d"
                ic_values: list[float] = []
                top_bucket_returns: list[float] = []
                universe_returns: list[float] = []
                for _, daily in working.groupby("snapshot_date"):
                    valid = daily[["composite_score", return_col]].dropna().copy()
                    if len(valid) < 3:
                        continue
                    score_rank = valid["composite_score"].rank(method="average")
                    return_rank = valid[return_col].rank(method="average")
                    if score_rank.nunique() > 1 and return_rank.nunique() > 1:
                        rank_ic = score_rank.corr(return_rank)
                        if pd.notna(rank_ic):
                            ic_values.append(float(rank_ic))
                    top_slice = valid.nlargest(min(top_n, len(valid)), "composite_score")
                    if not top_slice.empty:
                        top_bucket_returns.append(float(top_slice[return_col].mean()))
                    universe_returns.append(float(valid[return_col].mean()))

                mean_ic = sum(ic_values) / len(ic_values) if ic_values else 0.0
                top_mean = sum(top_bucket_returns) / len(top_bucket_returns) if top_bucket_returns else 0.0
                universe_mean = sum(universe_returns) / len(universe_returns) if universe_returns else 0.0
                spread = top_mean - universe_mean
                horizon_score = (0.65 * mean_ic) + (0.35 * spread)
                metrics[f"ic_{horizon}d"] = mean_ic
                metrics[f"top_return_{horizon}d"] = top_mean
                metrics[f"universe_return_{horizon}d"] = universe_mean
                metrics[f"spread_{horizon}d"] = spread
                metrics[f"score_{horizon}d"] = horizon_score
                per_horizon_scores.append(horizon_score)

            metrics["overall_score"] = sum(per_horizon_scores) / len(per_horizon_scores) if per_horizon_scores else 0.0
            results.append(metrics)

        return pd.DataFrame(results).sort_values("overall_score", ascending=False).reset_index(drop=True)

    @staticmethod
    def export_results(result_df: pd.DataFrame, output_dir: Path) -> dict[str, str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / "sentiment_weight_calibration.csv"
        json_path = output_dir / "sentiment_weight_calibration_best.json"
        result_df.to_csv(csv_path, index=False)
        best_payload = result_df.iloc[0].to_dict() if not result_df.empty else {}
        json_path.write_text(json.dumps(best_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return {"calibration_csv": str(csv_path), "best_json": str(json_path)}

    def calibrate(
        self,
        start_date: date,
        end_date: date,
        scenarios: Iterable[SentimentCalibrationScenario] | None = None,
        horizons: tuple[int, ...] = (5, 10, 20),
        top_n: int = 20,
        candidates_only: bool = True,
        output_dir: Path | None = None,
    ) -> tuple[SentimentCalibrationResult, pd.DataFrame, dict[str, str]]:
        scenario_list = list(scenarios or self.default_scenarios())
        dataset = self.load_dataset(start_date, end_date, horizons=horizons, candidates_only=candidates_only)
        result_df = self.evaluate_scenarios(dataset, scenario_list, horizons=horizons, top_n=top_n)
        artifacts: dict[str, str] = {}
        if output_dir is not None:
            artifacts = self.export_results(result_df, output_dir)
        if not result_df.empty:
            best_row = result_df.iloc[0].to_dict()
            best_scenario_name = str(best_row.get("scenario_name") or "none")
            best_overall_score = float(best_row.get("overall_score") or 0.0)
        else:
            best_scenario_name = "none"
            best_overall_score = 0.0
        return (
            SentimentCalibrationResult(
                start_date=start_date,
                end_date=end_date,
                scenarios_evaluated=len(scenario_list),
                rows_evaluated=int(len(dataset)),
                best_scenario_name=best_scenario_name,
                best_overall_score=best_overall_score,
                artifact_dir=str(output_dir) if output_dir is not None else None,
            ),
            result_df,
            artifacts,
        )


def _emit_run_summary(summary: dict[str, object]) -> None:
    print(f"{RUN_SUMMARY_PREFIX}{json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)}", flush=True)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calibre les poids sentiment/macro via backtest forward returns.")
    parser.add_argument("--start", required=True, help="Date de début (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="Date de fin (YYYY-MM-DD)")
    parser.add_argument("--top-n", type=int, default=20, help="Nombre de symboles retenus par jour pour mesurer le spread.")
    parser.add_argument("--horizons", type=str, default="5,10,20", help="Horizons forward CSV en jours.")
    parser.add_argument("--output-dir", default="artifacts/sentiment_calibration", help="Répertoire de sortie des artefacts.")
    parser.add_argument("--all-symbols", action="store_true", help="Utilise tout l'univers historisé, pas seulement les candidats.")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    configure_root_logging(
        level=getattr(logging, args.log_level),
        log_path="./log/sentiment_weight_calibration.log",
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end)
    horizons = tuple(int(token.strip()) for token in args.horizons.split(",") if token.strip())
    calibrator = SentimentWeightCalibrator(engine=get_sqlalchemy_engine())
    started_at = _utc_now_naive()
    result, _, artifacts = calibrator.calibrate(
        start_date=start_date,
        end_date=end_date,
        horizons=horizons,
        top_n=args.top_n,
        candidates_only=not args.all_symbols,
        output_dir=Path(args.output_dir),
    )
    finished_at = _utc_now_naive()
    _emit_run_summary(
        {
            "run_id": _build_run_id("sentiment-calibration"),
            "started_at": started_at.isoformat(timespec="seconds"),
            "finished_at": finished_at.isoformat(timespec="seconds"),
            "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
            **asdict(result),
            **artifacts,
        }
    )
    LOGGER.info("Calibration des poids sentiment terminée | result=%s", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




