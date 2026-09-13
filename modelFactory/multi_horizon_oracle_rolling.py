"""POC causal multi-horizon Oracle et confirmation rolling.

Le module est volontairement *research-only*. Il aligne quatre prédictions OOF
Oracle (H5/H10/H15/H20), construit les cohortes MH0..MH3 et mesure la valeur
incrémentale du prix et de l'Oracle restant. Il ne modifie ni le serving, ni le
backtest, ni les tables SQL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.data_loader import load_benchmark_bars, load_universe_bars
from modelFactory.oracle.artifact_contract import resolve_oracle_artifact_horizon
from modelFactory.oracle.predictions_store import load_oracle_predictions

LOGGER = logging.getLogger(__name__)
HORIZONS = (5, 10, 15, 20)
CHECKPOINTS = (5, 10, 15)


@dataclass(frozen=True, slots=True)
class RollingConfig:
    top_pct: float = 0.20
    strong_winner_return: float = 0.03
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    bootstrap_samples: int = 2_000
    bootstrap_block_sessions: int = 21
    bootstrap_seed: int = 20260910

    def __post_init__(self) -> None:
        if not 0 < self.top_pct < 0.5:
            raise ValueError("top_pct doit être dans ]0, 0.5[.")
        if min(self.commission_bps, self.slippage_bps) < 0:
            raise ValueError("Les coûts ne peuvent pas être négatifs.")

    @property
    def round_trip_cost(self) -> float:
        return 2.0 * (self.commission_bps + self.slippage_bps) / 10_000.0


def read_universe(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8-sig")
    symbols = sorted({part.strip().upper() for part in raw.replace("\n", ",").split(",") if part.strip()})
    if not symbols:
        raise ValueError(f"Univers vide: {path}")
    return symbols


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_batch_horizons(batch_ids: dict[int, str], artifacts_root: Path) -> None:
    if set(batch_ids) != set(HORIZONS):
        raise ValueError(f"Quatre batches requis, horizons attendus={HORIZONS}.")
    for expected, batch_id in batch_ids.items():
        actual = resolve_oracle_artifact_horizon(batch_id, artifacts_root)
        if actual != expected:
            raise ValueError(
                f"Contrat Oracle invalide: {batch_id} attendu H{expected}, artefact H{actual}."
            )


def _profile_contract(batch_id: str, artifacts_root: Path) -> dict[str, Any] | None:
    path = artifacts_root / batch_id / "oracle" / "feature_profile.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "profile_id": payload.get("profile_id"),
        "feature_set": payload.get("feature_set"),
        "generator_options": payload.get("generator_options"),
        "feature_columns": payload.get("feature_columns"),
    }


def audit_profile_contracts(batch_ids: dict[int, str], artifacts_root: Path) -> dict[str, Any]:
    contracts = {h: _profile_contract(batch_id, artifacts_root) for h, batch_id in batch_ids.items()}
    available = [value for value in contracts.values() if value is not None]
    identical = len(available) == len(HORIZONS) and all(value == available[0] for value in available[1:])
    return {
        "all_profiles_present": len(available) == len(HORIZONS),
        "profiles_identical_excluding_horizon": identical,
        "feature_counts": {
            f"h{h}": len((contract or {}).get("feature_columns") or [])
            for h, contract in contracts.items()
        },
    }


def _prepare_prediction(frame: pd.DataFrame, horizon: int, symbols: set[str]) -> pd.DataFrame:
    required = {"date", "symbol", "proba_extreme", "fold_start"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"H{horizon}: colonnes absentes {sorted(missing)}")
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["symbol"] = out["symbol"].astype(str).str.strip().str.upper()
    out["proba_extreme"] = pd.to_numeric(out["proba_extreme"], errors="coerce")
    out = out[out["symbol"].isin(symbols) & out["fold_start"].notna()]
    out = out.dropna(subset=["date", "symbol", "proba_extreme"])
    if out.duplicated(["date", "symbol"]).any():
        raise ValueError(f"H{horizon}: doublons (date,symbol) dans les prédictions OOF.")
    return out[["date", "symbol", "proba_extreme", "fold_start"]].rename(
        columns={"proba_extreme": f"score_h{horizon}", "fold_start": f"fold_h{horizon}"}
    )


def align_predictions(frames: dict[int, pd.DataFrame], symbols: Iterable[str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    symbol_set = {str(symbol).upper() for symbol in symbols}
    prepared = {h: _prepare_prediction(frames[h], h, symbol_set) for h in HORIZONS}
    row_counts = {f"h{h}": int(len(frame)) for h, frame in prepared.items()}
    aligned: pd.DataFrame | None = None
    for horizon in HORIZONS:
        aligned = prepared[horizon] if aligned is None else aligned.merge(
            prepared[horizon], on=["date", "symbol"], how="inner", validate="one_to_one"
        )
    assert aligned is not None
    if aligned.empty:
        raise ValueError("Intersection commune H5/H10/H15/H20 vide.")
    for horizon in HORIZONS:
        aligned[f"pct_h{horizon}"] = aligned.groupby("date")[f"score_h{horizon}"].rank(
            method="average", pct=True
        )
    pct_cols = [f"pct_h{h}" for h in HORIZONS]
    aligned["consensus_mean"] = aligned[pct_cols].mean(axis=1)
    aligned["consensus_min"] = aligned[pct_cols].min(axis=1)
    aligned["consensus_std"] = aligned[pct_cols].std(axis=1, ddof=0)
    aligned["consensus_rank"] = aligned.groupby("date")["consensus_mean"].rank(method="average", pct=True)
    threshold = 0.80
    aligned["mh0"] = aligned["pct_h20"].ge(threshold)
    aligned["mh1"] = aligned[pct_cols].ge(threshold).all(axis=1)
    aligned["mh2"] = aligned[pct_cols].ge(threshold).sum(axis=1).ge(3)
    aligned["mh3"] = aligned["consensus_rank"].ge(threshold)
    for checkpoint, remaining in {5: (5, 10, 15), 10: (5, 10), 15: (5,)}.items():
        cols = [f"pct_h{h}" for h in remaining]
        mean_col = f"remaining_mean_{checkpoint}"
        aligned[mean_col] = aligned[cols].mean(axis=1)
        aligned[f"remaining_rank_{checkpoint}"] = aligned.groupby("date")[mean_col].rank(
            method="average", pct=True
        )
        aligned[f"remaining_strict_{checkpoint}"] = aligned[cols].ge(threshold).all(axis=1)
    min_rows = min(row_counts.values())
    coverage = {
        "rows_by_horizon": row_counts,
        "common_rows": int(len(aligned)),
        "common_dates": int(aligned["date"].nunique()),
        "common_symbols": int(aligned["symbol"].nunique()),
        "intersection_share_of_smallest": float(len(aligned) / min_rows) if min_rows else 0.0,
        "first_date": aligned["date"].min().date().isoformat(),
        "last_date": aligned["date"].max().date().isoformat(),
    }
    return aligned.sort_values(["date", "symbol"]).reset_index(drop=True), coverage


def score_correlations(aligned: pd.DataFrame) -> pd.DataFrame:
    return aligned[[f"pct_h{h}" for h in HORIZONS]].corr(method="spearman")


def selection_overlaps(aligned: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for date, group in aligned.groupby("date", sort=True):
        sets = {f"mh{i}": set(group.loc[group[f"mh{i}"], "symbol"]) for i in range(4)}
        for left in sets:
            for right in sets:
                union = sets[left] | sets[right]
                rows.append({
                    "date": date, "left": left, "right": right,
                    "jaccard": len(sets[left] & sets[right]) / len(union) if union else np.nan,
                })
    return pd.DataFrame(rows)


def build_price_panel(bars: pd.DataFrame) -> pd.DataFrame:
    required = {"symbol", "date", "open", "close"}
    missing = required - set(bars.columns)
    if missing:
        raise ValueError(f"Barres: colonnes absentes {sorted(missing)}")
    frame = bars.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    for column in ("open", "close", "adj_close"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "adj_close" in frame:
        factor = frame["adj_close"] / frame["close"].replace(0, np.nan)
        frame["px_close"] = frame["adj_close"].where(frame["adj_close"].gt(0), frame["close"])
        frame["px_open"] = (frame["open"] * factor).where(factor.gt(0), frame["open"])
    else:
        frame["px_close"], frame["px_open"] = frame["close"], frame["open"]
    frame = frame.dropna(subset=["date", "symbol", "px_open", "px_close"])
    frame = frame[frame["px_open"].gt(0) & frame["px_close"].gt(0)].sort_values(["symbol", "date"])
    grouped = frame.groupby("symbol", sort=False)
    frame["entry_date"] = grouped["date"].shift(-1)
    frame["entry_open"] = grouped["px_open"].shift(-1)
    for checkpoint in CHECKPOINTS:
        frame[f"cp{checkpoint}_date"] = grouped["date"].shift(-checkpoint)
        frame[f"cp{checkpoint}_close"] = grouped["px_close"].shift(-checkpoint)
        frame[f"cp{checkpoint}_exit_open"] = grouped["px_open"].shift(-(checkpoint + 1))
    frame["terminal_date"] = grouped["date"].shift(-21)
    frame["terminal_exit_open"] = grouped["px_open"].shift(-21)
    return frame


def attach_paths(aligned: pd.DataFrame, prices: pd.DataFrame, round_trip_cost: float) -> pd.DataFrame:
    cols = ["symbol", "date", "px_close", "entry_date", "entry_open", "terminal_date", "terminal_exit_open"]
    for checkpoint in CHECKPOINTS:
        cols += [f"cp{checkpoint}_date", f"cp{checkpoint}_close", f"cp{checkpoint}_exit_open"]
    events = aligned.merge(prices[cols], on=["date", "symbol"], how="left", validate="one_to_one")
    events["long_terminal_gross"] = events["terminal_exit_open"] / events["entry_open"] - 1.0
    events["long_terminal_net"] = events["long_terminal_gross"] - round_trip_cost
    lookup_base = aligned[["date", "symbol"] + [
        name for checkpoint in CHECKPOINTS for name in (
            f"remaining_rank_{checkpoint}", f"remaining_strict_{checkpoint}", f"remaining_mean_{checkpoint}"
        )
    ]]
    for checkpoint in CHECKPOINTS:
        events[f"cp{checkpoint}_long_gross"] = events[f"cp{checkpoint}_close"] / events["entry_open"] - 1.0
        events[f"cp{checkpoint}_long_net"] = events[f"cp{checkpoint}_long_gross"] - round_trip_cost
        events[f"cp{checkpoint}_continuation_gross"] = (
            events["terminal_exit_open"] / events[f"cp{checkpoint}_exit_open"] - 1.0
        )
        events[f"cp{checkpoint}_continuation_net"] = (
            events[f"cp{checkpoint}_continuation_gross"] - round_trip_cost
        )
        rolling = lookup_base[["date", "symbol", f"remaining_rank_{checkpoint}",
                               f"remaining_strict_{checkpoint}", f"remaining_mean_{checkpoint}"]].rename(columns={
            "date": f"cp{checkpoint}_date",
            f"remaining_rank_{checkpoint}": f"cp{checkpoint}_remaining_rank",
            f"remaining_strict_{checkpoint}": f"cp{checkpoint}_remaining_strict",
            f"remaining_mean_{checkpoint}": f"cp{checkpoint}_remaining_mean",
        })
        events = events.merge(rolling, on=[f"cp{checkpoint}_date", "symbol"], how="left", validate="many_to_one")
        events[f"cp{checkpoint}_oracle_confirmed"] = events[f"cp{checkpoint}_remaining_rank"].ge(0.80)
        events[f"cp{checkpoint}_oracle_rank_change"] = (
            events[f"cp{checkpoint}_remaining_rank"] - events["consensus_rank"]
        )
    return events


def attach_benchmark_paths(events: pd.DataFrame, benchmark_prices: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les rendements SPY sur exactement la même horloge d'exécution."""
    if benchmark_prices.empty:
        return events
    source = benchmark_prices.sort_values("date").drop_duplicates("date")
    columns = ["date", "entry_open", "terminal_exit_open"]
    for checkpoint in CHECKPOINTS:
        columns.append(f"cp{checkpoint}_exit_open")
    rename = {name: f"spy_{name}" for name in columns if name != "date"}
    out = events.merge(source[columns].rename(columns=rename), on="date", how="left", validate="many_to_one")
    out["spy_terminal_gross"] = out["spy_terminal_exit_open"] / out["spy_entry_open"] - 1.0
    out["long_terminal_excess_spy"] = out["long_terminal_gross"] - out["spy_terminal_gross"]
    for checkpoint in CHECKPOINTS:
        out[f"cp{checkpoint}_spy_continuation_gross"] = (
            out["spy_terminal_exit_open"] / out[f"spy_cp{checkpoint}_exit_open"] - 1.0
        )
        out[f"cp{checkpoint}_continuation_excess_spy"] = (
            out[f"cp{checkpoint}_continuation_gross"]
            - out[f"cp{checkpoint}_spy_continuation_gross"]
        )
    return out


def deduplicate_entries(events: pd.DataFrame, variant: str) -> pd.DataFrame:
    """Une seule position théorique par symbole jusqu'à la liquidation H20."""
    candidates = events[events[variant] & events["terminal_date"].notna()].sort_values(
        ["symbol", "date"]
    )
    kept: list[Any] = []
    for _, group in candidates.groupby("symbol", sort=False):
        available_after = pd.Timestamp.min
        for index, row in group.iterrows():
            signal_date = pd.Timestamp(row["date"])
            if signal_date <= available_after:
                continue
            kept.append(index)
            available_after = pd.Timestamp(row["terminal_date"])
    return candidates.loc[kept].sort_values(["date", "symbol"]).copy()


def _price_group(values: pd.Series, strong: float) -> pd.Series:
    return pd.Series(np.select(
        [values.le(0), values.ge(strong)], ["loser", "winner_strong"], default="winner_weak"
    ), index=values.index)


def block_bootstrap_mean(values_by_date: pd.Series, config: RollingConfig) -> tuple[float, float]:
    values = pd.to_numeric(values_by_date, errors="coerce").dropna().to_numpy(dtype=float)
    if len(values) < max(10, config.bootstrap_block_sessions * 2):
        return np.nan, np.nan
    block = min(config.bootstrap_block_sessions, len(values))
    blocks = int(np.ceil(len(values) / block))
    rng = np.random.default_rng(config.bootstrap_seed)
    means = np.empty(config.bootstrap_samples, dtype=float)
    for index in range(config.bootstrap_samples):
        starts = rng.integers(0, len(values) - block + 1, size=blocks)
        sample = np.concatenate([values[start:start + block] for start in starts])[:len(values)]
        means[index] = sample.mean()
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def build_event_study(events: pd.DataFrame, config: RollingConfig) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant in ("mh0", "mh1", "mh2", "mh3"):
        selected = deduplicate_entries(events, variant)
        for checkpoint in CHECKPOINTS:
            required = [f"cp{checkpoint}_long_net", f"cp{checkpoint}_continuation_net",
                        f"cp{checkpoint}_oracle_confirmed"]
            part = selected.dropna(subset=required).copy()
            part["price_group"] = _price_group(part[f"cp{checkpoint}_long_net"], config.strong_winner_return)
            for (price_group, confirmed), group in part.groupby(
                ["price_group", f"cp{checkpoint}_oracle_confirmed"], observed=True
            ):
                daily = group.groupby("date")[f"cp{checkpoint}_continuation_net"].mean().sort_index()
                low, high = block_bootstrap_mean(daily, config)
                rows.append({
                    "variant": variant.upper(), "checkpoint": checkpoint,
                    "price_group": str(price_group), "oracle_confirmed": bool(confirmed),
                    "events": int(len(group)), "dates": int(group["date"].nunique()),
                    "symbols": int(group["symbol"].nunique()),
                    "checkpoint_mean_gross": float(group[f"cp{checkpoint}_long_gross"].mean()),
                    "checkpoint_mean_net": float(group[f"cp{checkpoint}_long_net"].mean()),
                    "continuation_mean_gross": float(group[f"cp{checkpoint}_continuation_gross"].mean()),
                    "continuation_mean_net": float(group[f"cp{checkpoint}_continuation_net"].mean()),
                    "continuation_mean_excess_spy": (
                        float(group[f"cp{checkpoint}_continuation_excess_spy"].mean())
                        if f"cp{checkpoint}_continuation_excess_spy" in group else np.nan
                    ),
                    "continuation_positive_rate": float(group[f"cp{checkpoint}_continuation_net"].gt(0).mean()),
                    "continuation_daily_ci95_low": low, "continuation_daily_ci95_high": high,
                    "mean_oracle_rank_change": float(group[f"cp{checkpoint}_oracle_rank_change"].mean()),
                })
    return pd.DataFrame(rows)


def build_selection_control(events: pd.DataFrame, config: RollingConfig) -> pd.DataFrame:
    """Contrôle quotidien sélection vs REST, sur la cohorte non chevauchante."""
    rows: list[dict[str, Any]] = []
    for variant in ("mh0", "mh1", "mh2", "mh3"):
        selected = deduplicate_entries(events, variant)
        selected_keys = set(zip(selected["date"], selected["symbol"], strict=True))
        for checkpoint in CHECKPOINTS:
            metric = f"cp{checkpoint}_continuation_net"
            population = events.dropna(subset=[metric])
            mask = [
                key in selected_keys
                for key in zip(population["date"], population["symbol"], strict=True)
            ]
            chosen = population[mask]
            rest = population[[not value for value in mask]]
            chosen_daily = chosen.groupby("date")[metric].mean()
            rest_daily = rest.groupby("date")[metric].mean()
            paired = pd.concat([chosen_daily.rename("selected"), rest_daily.rename("rest")], axis=1).dropna()
            delta = paired["selected"] - paired["rest"]
            low, high = block_bootstrap_mean(delta, config)
            rows.append({
                "variant": variant.upper(), "checkpoint": checkpoint,
                "paired_dates": int(len(paired)), "selected_events": int(len(chosen)),
                "selected_mean_net": float(chosen[metric].mean()) if len(chosen) else np.nan,
                "rest_mean_net": float(rest[metric].mean()) if len(rest) else np.nan,
                "paired_daily_delta": float(delta.mean()) if len(delta) else np.nan,
                "paired_daily_delta_ci95_low": low, "paired_daily_delta_ci95_high": high,
            })
    return pd.DataFrame(rows)


def build_s6_ls(events: pd.DataFrame, config: RollingConfig) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = deduplicate_entries(events, "mh3")
    frame = frame[frame["cp5_oracle_confirmed"]].dropna(
        subset=["px_close", "cp5_close", "cp5_exit_open", "terminal_exit_open"]
    ).copy()
    frame["revealed_return"] = frame["cp5_close"] / frame["px_close"] - 1.0
    frame["direction"] = np.where(frame["revealed_return"].ge(0), "LONG", "SHORT")
    unsigned = frame["terminal_exit_open"] / frame["cp5_exit_open"] - 1.0
    frame["s6_ls_gross"] = np.where(frame["direction"].eq("LONG"), unsigned, -unsigned)
    frame["s6_ls_net"] = frame["s6_ls_gross"] - config.round_trip_cost
    daily = frame.groupby("date")["s6_ls_net"].mean().sort_index()
    low, high = block_bootstrap_mean(daily, config)
    summary = {
        "events": int(len(frame)), "dates": int(frame["date"].nunique()),
        "symbols": int(frame["symbol"].nunique()),
        "long_share": float(frame["direction"].eq("LONG").mean()) if len(frame) else None,
        "mean_gross_return": float(frame["s6_ls_gross"].mean()) if len(frame) else None,
        "mean_net_return": float(frame["s6_ls_net"].mean()) if len(frame) else None,
        "positive_rate": float(frame["s6_ls_net"].gt(0).mean()) if len(frame) else None,
        "daily_mean_ci95": [low, high],
    }
    return frame, summary


def _rolling_winner_delta(
    events: pd.DataFrame, variant: str, config: RollingConfig,
) -> dict[str, Any]:
    selected = deduplicate_entries(events, variant)
    selected = selected[selected["cp5_long_net"].gt(0)].dropna(
        subset=["cp5_continuation_net", "cp5_oracle_confirmed"]
    )
    confirmed = selected[selected["cp5_oracle_confirmed"]]
    unconfirmed = selected[~selected["cp5_oracle_confirmed"]]
    left = confirmed.groupby("date")["cp5_continuation_net"].mean().rename("confirmed")
    right = unconfirmed.groupby("date")["cp5_continuation_net"].mean().rename("unconfirmed")
    paired = pd.concat([left, right], axis=1).dropna()
    delta = paired["confirmed"] - paired["unconfirmed"]
    low, high = block_bootstrap_mean(delta, config)
    return {
        "confirmed_events": int(len(confirmed)),
        "unconfirmed_events": int(len(unconfirmed)),
        "paired_dates": int(len(paired)),
        "confirmed_mean_net": float(confirmed["cp5_continuation_net"].mean()),
        "unconfirmed_mean_net": float(unconfirmed["cp5_continuation_net"].mean()),
        "event_weighted_delta": float(
            confirmed["cp5_continuation_net"].mean()
            - unconfirmed["cp5_continuation_net"].mean()
        ),
        "paired_daily_delta": float(delta.mean()),
        "paired_daily_delta_ci95": [low, high],
    }


def evaluate_verdict(
    event_study: pd.DataFrame, events: pd.DataFrame, config: RollingConfig,
) -> dict[str, Any]:
    target = event_study[
        event_study["variant"].eq("MH3")
        & event_study["checkpoint"].eq(5)
        & event_study["price_group"].isin(["winner_weak", "winner_strong"])
    ]
    confirmed = target[target["oracle_confirmed"]]
    unconfirmed = target[~target["oracle_confirmed"]]
    n_confirmed = int(confirmed["events"].sum()) if not confirmed.empty else 0
    confirmed_mean = float(np.average(
        confirmed["continuation_mean_net"], weights=confirmed["events"]
    )) if n_confirmed else np.nan
    unconfirmed_n = int(unconfirmed["events"].sum()) if not unconfirmed.empty else 0
    unconfirmed_mean = float(np.average(
        unconfirmed["continuation_mean_net"], weights=unconfirmed["events"]
    )) if unconfirmed_n else np.nan
    eligible = deduplicate_entries(events, "mh3")
    eligible = eligible[
        eligible["cp5_oracle_confirmed"] & eligible["cp5_long_net"].gt(0)
    ].dropna(
        subset=["cp5_continuation_net"]
    ).copy()
    eligible["semester"] = eligible["date"].dt.year.astype(str) + "H" + np.where(
        eligible["date"].dt.month.le(6), "1", "2"
    )
    semester_means = eligible.groupby("semester")["cp5_continuation_net"].mean()
    positive_semester_ratio = float(semester_means.gt(0).mean()) if len(semester_means) else 0.0
    incremental = confirmed_mean - unconfirmed_mean
    primary_delta = _rolling_winner_delta(events, "mh3", config)
    delta_ci_low = primary_delta["paired_daily_delta_ci95"][0]
    gates = {
        "confirmed_events_ge_200": n_confirmed >= 200,
        "confirmed_continuation_net_positive": bool(np.isfinite(confirmed_mean) and confirmed_mean > 0),
        "incremental_vs_unconfirmed_positive": bool(np.isfinite(incremental) and incremental > 0),
        "incremental_paired_daily_ci95_above_zero": bool(
            np.isfinite(delta_ci_low) and delta_ci_low > 0
        ),
        "positive_semester_ratio_ge_60pct": positive_semester_ratio >= 0.60,
    }
    passed = sum(gates.values())
    verdict = (
        "GO_RESEARCH" if passed == len(gates)
        else "WEAK_SIGNAL" if passed >= 3
        else "NO_GO"
    )
    return {
        "verdict": verdict, "strong_go_allowed": False,
        "reason_strong_go_forbidden": "univers courant fixe; univers historique PIT requis",
        "mh3_j5_confirmed_winner_events": n_confirmed,
        "confirmed_mean_continuation_net": confirmed_mean,
        "unconfirmed_mean_continuation_net": unconfirmed_mean,
        "incremental_mean_net": incremental,
        "positive_semester_ratio": positive_semester_ratio,
        "primary_paired_daily_test": primary_delta,
        "pre_registered_alternative_screens": {
            "mh0_h20_only": _rolling_winner_delta(events, "mh0", config),
            "mh2_three_of_four": _rolling_winner_delta(events, "mh2", config),
        },
        "gates": gates,
    }


def _markdown_report(report: dict[str, Any]) -> str:
    verdict = report["decision"]["verdict"]
    coverage = report["coverage"]
    decision = report["decision"]
    return "\n".join([
        "# Multi-Horizon Oracle + Rolling Confirmation — résultat", "",
        f"- Verdict : **{verdict}**",
        f"- Lignes communes : {coverage['common_rows']:,}",
        f"- Dates communes : {coverage['common_dates']:,}",
        f"- Symboles communs : {coverage['common_symbols']:,}",
        f"- Couverture de l'intersection : {coverage['intersection_share_of_smallest']:.1%}",
        f"- Continuation nette J+5 confirmée : {decision['confirmed_mean_continuation_net']:+.3%}",
        f"- Valeur incrémentale Oracle : {decision['incremental_mean_net']:+.3%}",
        f"- Semestres positifs : {decision['positive_semester_ratio']:.1%}", "",
        "Le résultat reste research-only. Aucun changement du backtest ou du live n'est effectué.",
    ])


def run(
    *, engine: Any, batch_ids: dict[int, str], universe_file: Path,
    start_date: str, end_date: str, artifacts_root: Path,
    output_root: Path, config: RollingConfig,
) -> Path:
    validate_batch_horizons(batch_ids, artifacts_root)
    profile_audit = audit_profile_contracts(batch_ids, artifacts_root)
    if not profile_audit["profiles_identical_excluding_horizon"]:
        raise ValueError(f"Profils Oracle non comparables: {profile_audit}")
    symbols = read_universe(universe_file)
    raw_frames = {
        h: load_oracle_predictions(
            engine, batch_id=batch_ids[h], start_date=start_date, end_date=end_date
        ) for h in HORIZONS
    }
    aligned, coverage = align_predictions(raw_frames, symbols)
    if coverage["intersection_share_of_smallest"] < 0.70:
        raise ValueError(f"Couverture commune insuffisante: {coverage}")
    bar_start = pd.Timestamp(coverage["first_date"]).date()
    future_end = (pd.Timestamp(coverage["last_date"]) + pd.offsets.BDay(25)).date()
    bars = load_universe_bars(
        engine, sorted(aligned["symbol"].unique()),
        start_date=bar_start, end_date=future_end,
    )
    events = attach_paths(aligned, build_price_panel(bars), config.round_trip_cost)
    benchmark = load_benchmark_bars(
        engine, "SPY", start_date=bar_start, end_date=future_end,
    )
    events = attach_benchmark_paths(events, build_price_panel(benchmark))
    event_study = build_event_study(events, config)
    selection_control = build_selection_control(events, config)
    s6_events, s6_summary = build_s6_ls(events, config)
    decision = evaluate_verdict(event_study, events, config)
    run_id = f"multi-horizon-rolling-{datetime.now(UTC):%Y%m%d%H%M%S}-{batch_ids[20][-6:]}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    aligned.to_parquet(output / "aligned_predictions.parquet", index=False)
    events.to_parquet(output / "fixed_origin_events.parquet", index=False)
    s6_events.to_parquet(output / "s6_ls_events.parquet", index=False)
    event_study.to_csv(output / "event_study.csv", index=False)
    selection_control.to_csv(output / "selection_vs_rest_control.csv", index=False)
    score_correlations(aligned).to_csv(output / "score_correlations.csv")
    selection_overlaps(aligned).to_csv(output / "selection_overlaps.csv", index=False)
    report = {
        "schema_version": 1, "run_id": run_id,
        "experiment": "multi_horizon_oracle_rolling_confirmation_signal_poc",
        "status": "complete", "research_only": True,
        "backtest_modified": False, "live_modified": False, "database_modified": False,
        "generated_at": datetime.now(UTC).isoformat(),
        "period": {"start": start_date, "end": end_date},
        "batches": {f"h{h}": batch_ids[h] for h in HORIZONS},
        "universe": {"path": str(universe_file), "symbols": len(symbols),
                     "sha256": file_sha256(universe_file), "historical_pit": False},
        "profile_audit": profile_audit, "coverage": coverage,
        "execution_clock": {
            "signal": "close J", "entry": "open J+1",
            "checkpoints": "close of holding session 5/10/15",
            "checkpoint_decision_execution": "next open",
            "terminal_exit": "open after holding session 20",
            "lifecycle": "not applied in phase 1 signal event study",
        },
        "config": asdict(config), "s6_ls": s6_summary, "decision": decision,
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (output / "report.md").write_text(_markdown_report(report), encoding="utf-8")
    LOGGER.info("Multi-horizon rolling terminé: %s verdict=%s", output, decision["verdict"])
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for horizon in HORIZONS:
        parser.add_argument(f"--h{horizon}-batch-id", required=True)
    parser.add_argument("--universe-file", type=Path,
                        default=Path("config/univers/univers_filtred_equities.txt"))
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--artifacts-root", type=Path, default=Path("artifacts/models"))
    parser.add_argument("--output-root", type=Path,
                        default=Path("artifacts/research/multi_horizon_oracle_rolling"))
    parser.add_argument("--commission-bps", type=float, default=1.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    batch_ids = {h: getattr(args, f"h{h}_batch_id") for h in HORIZONS}
    output = run(
        engine=get_sqlalchemy_engine(), batch_ids=batch_ids,
        universe_file=args.universe_file, start_date=args.start_date,
        end_date=args.end_date, artifacts_root=args.artifacts_root,
        output_root=args.output_root,
        config=RollingConfig(
            commission_bps=args.commission_bps, slippage_bps=args.slippage_bps,
            bootstrap_samples=args.bootstrap_samples,
        ),
    )
    print(output)


if __name__ == "__main__":
    main()
