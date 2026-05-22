"""Sprint S8 — Étude empirique attribution alpha sentiment vs quant pur.

Compare 4 scénarios de fusion sur un même panneau de scores historiques :

- ``quant_only``      : ``final_score = quant``
- ``ml_only``         : ``final_score = quant + ml`` (sentiment désactivé)
- ``sentiment_only``  : ``final_score = quant + sentiment`` (ML désactivé)
- ``full``            : fusion complète quant + sentiment + ML

Pour chaque scénario, on évalue :

- IC moyen (Spearman score → forward return) ;
- hit-rate (signe(score) == signe(forward_return)) ;
- Sharpe annualisé du portefeuille top-N equal-weighted ;
- alpha vs benchmark (proxy : moyenne univers).

L'objectif est de **prouver/réfuter empiriquement** l'apport métier du
sentiment et du ML, conformément au plan §S8.

Le module est volontairement *self-contained* (pas de dépendance forte au
``BacktestEngine``) : il consomme un panneau de scores+returns déjà calculé
afin d'être testable rapidement et reproductible.
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)

DEFAULT_TOP_N = 10
DEFAULT_TRADING_DAYS = 252


@dataclass(frozen=True)
class AttributionScenario:
    """Définition d'un scénario d'attribution."""

    name: str
    use_quant: bool = True
    use_sentiment: bool = False
    use_ml: bool = False

    def fused_score(self, panel: pd.DataFrame) -> pd.Series:
        score = pd.Series(0.0, index=panel.index, dtype=float)
        if self.use_quant and "quant_score" in panel.columns:
            score = score + pd.to_numeric(panel["quant_score"], errors="coerce").fillna(0.0)
        if self.use_sentiment and "sentiment_score" in panel.columns:
            score = score + pd.to_numeric(panel["sentiment_score"], errors="coerce").fillna(0.0)
        if self.use_ml and "ml_score" in panel.columns:
            score = score + pd.to_numeric(panel["ml_score"], errors="coerce").fillna(0.0)
        return score


@dataclass
class AttributionResult:
    scenario: str
    ic_mean: float
    hit_rate: float
    portfolio_return: float
    portfolio_sharpe: float
    alpha_vs_benchmark: float
    n_dates: int
    n_obs: int

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "ic_mean": round(float(self.ic_mean), 6),
            "hit_rate": round(float(self.hit_rate), 6),
            "portfolio_return": round(float(self.portfolio_return), 6),
            "portfolio_sharpe": round(float(self.portfolio_sharpe), 6),
            "alpha_vs_benchmark": round(float(self.alpha_vs_benchmark), 6),
            "n_dates": int(self.n_dates),
            "n_obs": int(self.n_obs),
        }


@dataclass
class AttributionReport:
    results: list[AttributionResult]
    deltas: dict[str, dict[str, float]] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    regime_results: dict[str, list[AttributionResult]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "results": [r.to_dict() for r in self.results],
            "deltas": self.deltas,
            "metadata": self.metadata,
            "regime_results": {
                regime: [result.to_dict() for result in results]
                for regime, results in self.regime_results.items()
            },
        }


DEFAULT_SCENARIOS: tuple[AttributionScenario, ...] = (
    AttributionScenario("quant_only", use_quant=True),
    AttributionScenario("ml_only", use_quant=True, use_ml=True),
    AttributionScenario("sentiment_only", use_quant=True, use_sentiment=True),
    AttributionScenario("full", use_quant=True, use_sentiment=True, use_ml=True),
)


def _spearman_ic(scores: pd.Series, fwd: pd.Series) -> float:
    """IC Spearman simple (rang(score) vs rang(fwd))."""
    df = pd.DataFrame({"s": scores, "f": fwd}).dropna()
    if len(df) < 3:
        return float("nan")
    rs = df["s"].rank(method="average")
    rf = df["f"].rank(method="average")
    if rs.std(ddof=0) == 0 or rf.std(ddof=0) == 0:
        return 0.0
    return float(np.corrcoef(rs, rf)[0, 1])


def evaluate_scenario(
    panel: pd.DataFrame,
    scenario: AttributionScenario,
    *,
    top_n: int = DEFAULT_TOP_N,
    trading_days: int = DEFAULT_TRADING_DAYS,
) -> AttributionResult:
    """Évalue un scénario sur un panneau ``[date, symbol, *_score, fwd_return]``."""
    required = {"date", "symbol", "fwd_return"}
    missing = required - set(panel.columns)
    if missing:
        raise ValueError(f"panel : colonnes manquantes {missing}")

    work = panel.copy()
    work["_score"] = scenario.fused_score(work)
    fwd = pd.to_numeric(work["fwd_return"], errors="coerce")
    work["_fwd"] = fwd

    daily_ic: list[float] = []
    daily_hits: list[float] = []
    daily_port_returns: list[float] = []
    daily_bench_returns: list[float] = []

    for trade_date, slice_df in work.groupby("date", sort=True):
        ic = _spearman_ic(slice_df["_score"], slice_df["_fwd"])
        if not math.isnan(ic):
            daily_ic.append(ic)
        with_score = slice_df.dropna(subset=["_score", "_fwd"])
        if with_score.empty:
            continue
        ranked = with_score.sort_values("_score", ascending=False)
        top = ranked.head(max(1, top_n))
        port_r = float(top["_fwd"].mean())
        bench_r = float(ranked["_fwd"].mean())
        daily_port_returns.append(port_r)
        daily_bench_returns.append(bench_r)
        sign_score = np.sign(with_score["_score"].to_numpy())
        sign_fwd = np.sign(with_score["_fwd"].to_numpy())
        if len(sign_score) > 0:
            daily_hits.append(float(np.mean(sign_score == sign_fwd)))

    n_dates = len(daily_port_returns)
    if n_dates == 0:
        return AttributionResult(
            scenario=scenario.name,
            ic_mean=float("nan"),
            hit_rate=float("nan"),
            portfolio_return=0.0,
            portfolio_sharpe=0.0,
            alpha_vs_benchmark=0.0,
            n_dates=0,
            n_obs=int(len(work)),
        )

    port_returns = np.array(daily_port_returns)
    bench_returns = np.array(daily_bench_returns)
    mean_port = float(port_returns.mean())
    std_port = float(port_returns.std(ddof=0))
    sharpe = (mean_port / std_port * math.sqrt(trading_days)) if std_port > 1e-12 else 0.0
    alpha = mean_port - float(bench_returns.mean())

    return AttributionResult(
        scenario=scenario.name,
        ic_mean=float(np.mean(daily_ic)) if daily_ic else float("nan"),
        hit_rate=float(np.mean(daily_hits)) if daily_hits else float("nan"),
        portfolio_return=mean_port,
        portfolio_sharpe=sharpe,
        alpha_vs_benchmark=alpha,
        n_dates=n_dates,
        n_obs=int(len(work)),
    )


def run_attribution(
    panel: pd.DataFrame,
    scenarios: Iterable[AttributionScenario] = DEFAULT_SCENARIOS,
    *,
    top_n: int = DEFAULT_TOP_N,
    trading_days: int = DEFAULT_TRADING_DAYS,
    output_dir: Path | str | None = None,
    regime_column: str | None = "market_regime",
) -> AttributionReport:
    """Exécute tous les scénarios et produit un :class:`AttributionReport`.

    Si ``output_dir`` est fourni :
    - écrit ``attribution_summary.json`` (résumé complet) ;
    - écrit ``attribution_per_scenario.csv`` (lignes par scénario).
    """
    scenario_list = tuple(scenarios)
    results = [
        evaluate_scenario(panel, scenario, top_n=top_n, trading_days=trading_days)
        for scenario in scenario_list
    ]

    by_name = {r.scenario: r for r in results}
    deltas: dict[str, dict[str, float]] = {}
    if "quant_only" in by_name:
        baseline = by_name["quant_only"]
        for r in results:
            if r.scenario == "quant_only":
                continue
            deltas[r.scenario] = {
                "delta_ic_vs_quant_only": round(float(r.ic_mean - baseline.ic_mean), 6),
                "delta_sharpe_vs_quant_only": round(float(r.portfolio_sharpe - baseline.portfolio_sharpe), 6),
                "delta_alpha_vs_quant_only": round(float(r.alpha_vs_benchmark - baseline.alpha_vs_benchmark), 6),
            }

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "top_n": int(top_n),
        "trading_days": int(trading_days),
        "n_panel_rows": int(len(panel)),
        "n_panel_dates": int(panel["date"].nunique()) if "date" in panel.columns else 0,
        "n_panel_symbols": int(panel["symbol"].nunique()) if "symbol" in panel.columns else 0,
        "regime_column": regime_column,
    }

    regime_results: dict[str, list[AttributionResult]] = {}
    if regime_column and regime_column in panel.columns:
        regime_series = panel[regime_column].fillna("unknown").astype(str).str.strip().replace("", "unknown")
        for regime_name in sorted(regime_series.unique()):
            regime_slice = panel.loc[regime_series == regime_name].copy()
            if regime_slice.empty:
                continue
            regime_results[regime_name] = [
                evaluate_scenario(regime_slice, scenario, top_n=top_n, trading_days=trading_days)
                for scenario in scenario_list
            ]
        metadata["n_regimes"] = len(regime_results)
    else:
        metadata["n_regimes"] = 0

    report = AttributionReport(results=results, deltas=deltas, metadata=metadata, regime_results=regime_results)

    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "attribution_summary.json").write_text(
            json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8"
        )
        df_rows = pd.DataFrame([r.to_dict() for r in results])
        df_rows.to_csv(out / "attribution_per_scenario.csv", index=False)
        if regime_results:
            regime_rows = [
                {"regime": regime, **result.to_dict()}
                for regime, result_list in regime_results.items()
                for result in result_list
            ]
            pd.DataFrame(regime_rows).to_csv(out / "attribution_by_regime.csv", index=False)
        LOGGER.info("[attribution] artefacts écrits dans %s", out)

    return report


__all__ = [
    "AttributionScenario",
    "AttributionResult",
    "AttributionReport",
    "DEFAULT_SCENARIOS",
    "evaluate_scenario",
    "run_attribution",
]

