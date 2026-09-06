"""Evaluation PIT des catégories structurées 8-K dans Oracle TOP20.

Première étape sans NLP : seules les catégories fournies par Eroya sont
utilisées. L'heure de dépôt étant absente, chaque disclosure devient disponible
au premier jour ouvré suivant. Ce module ne modifie aucune table de production.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.directional_data_research.eroya_features import (
    assemble_bundle_pool_at_horizon,
)
from modelFactory.directional_data_research.harness import assemble_pool
from modelFactory.global_direction.dataset import DECILE_COL, RETURN_COL

FAMILIES = {
    "distress": {
        "accounting_error_correction", "audit_opinion_withdrawal", "auditor_resignation",
        "covenant_violation", "debt_acceleration", "delisting_determination",
        "financial_restatement", "going_concern", "guidance_withdrawal",
        "internal_control_weakness", "listing_deficiency_notice", "payment_default",
        "rating_downgrade_trigger", "voluntary_bankruptcy",
    },
    "operational_negative": {
        "asset_impairment", "business_line_exit", "cybersecurity_incident",
        "facility_closure", "goodwill_impairment", "investment_impairment",
        "natural_disaster_impact", "restructuring_plan", "workforce_reduction",
    },
    "legal_regulatory_negative": {
        "class_action_filing", "material_litigation", "regulatory_investigation",
    },
    "dilution_financing": {
        "acquisition_consideration_shares", "pipe_transaction", "private_placement",
        "public_offering", "rights_offering", "underwriting_agreement",
        "warrant_or_conversion",
    },
    "leadership_departure": {
        "ceo_departure", "cfo_departure", "director_departure",
        "executive_officer_departure",
    },
    "leadership_appointment": {
        "ceo_appointment", "cfo_appointment", "director_appointment",
        "executive_officer_appointment",
    },
    "shareholder_return": {"dividend_declaration", "share_repurchase_program"},
    "positive_business_event": {
        "bankruptcy_emergence", "listing_compliance_regained", "patent_milestone",
        "product_or_service_launch", "significant_contract_award",
    },
}


def load_8k_disclosures(path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            document = json.loads(line)
            payload = document.get("payload") or {}
            for item in payload.get("results") or []:
                if not isinstance(item, dict):
                    continue
                for ticker in item.get("tickers") or []:
                    rows.append({
                        "symbol": str(ticker).upper(),
                        "accession_number": item.get("accession_number"),
                        "filing_date": item.get("filing_date"),
                        "primary_category": item.get("primary_category"),
                        "secondary_category": item.get("secondary_category"),
                        "tertiary_category": item.get("tertiary_category"),
                        "supporting_text": item.get("supporting_text"),
                    })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["filing_date"] = pd.to_datetime(frame["filing_date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["symbol", "filing_date", "tertiary_category"])
    frame = frame.drop_duplicates([
        "symbol", "accession_number", "primary_category", "secondary_category",
        "tertiary_category", "supporting_text",
    ])
    frame["available_date"] = frame["filing_date"] + pd.offsets.BDay(1)
    reverse = {category: family for family, categories in FAMILIES.items() for category in categories}
    frame["family"] = frame["tertiary_category"].map(reverse).fillna("other")
    return frame.sort_values(["symbol", "available_date", "accession_number"])


def build_8k_count_features(pool: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    keys = pool[["date", "symbol"]].drop_duplicates().copy()
    output: list[pd.DataFrame] = []
    families = list(FAMILIES)
    for symbol, dates_part in keys.groupby("symbol"):
        part = dates_part.sort_values("date").copy()
        event = events[events["symbol"].eq(symbol)].sort_values("available_date")
        dates = part["date"].to_numpy(dtype="datetime64[ns]")
        event_dates = event["available_date"].to_numpy(dtype="datetime64[ns]")
        hi = np.searchsorted(event_dates, dates, side="right")
        for family in families:
            values = event["family"].eq(family).to_numpy(float)
            cumulative = np.r_[0.0, np.cumsum(values)]
            for window in (5, 20, 60):
                lo = np.searchsorted(event_dates, dates - np.timedelta64(window, "D"), side="left")
                part[f"eroya_8k_{family}_{window}d"] = cumulative[hi] - cumulative[lo]
        output.append(part)
    return pd.concat(output, ignore_index=True) if output else keys


def evaluate_family_rules(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    groups = [("ALL", frame), *[(str(k), v) for k, v in frame.groupby("fold_start")]]
    for fold, part in groups:
        base_return = float(part[RETURN_COL].mean())
        base_long = float((part[DECILE_COL] >= 8).mean())
        base_short = float((part[DECILE_COL] <= 3).mean())
        for family in FAMILIES:
            for window in (5, 20, 60):
                selected = part[part[f"eroya_8k_{family}_{window}d"] > 0]
                if selected.empty:
                    continue
                for side in ("LONG", "SHORT"):
                    if side == "LONG":
                        pnl = float(selected[RETURN_COL].mean())
                        precision = float((selected[DECILE_COL] >= 8).mean())
                        lift = pnl - base_return
                        precision_lift = precision - base_long
                    else:
                        pnl = float(-selected[RETURN_COL].mean())
                        precision = float((selected[DECILE_COL] <= 3).mean())
                        lift = pnl + base_return
                        precision_lift = precision - base_short
                    rows.append({
                        "fold": fold, "family": family, "window_days": window,
                        "side": side, "n": len(selected),
                        "symbols": int(selected["symbol"].nunique()),
                        "dates": int(selected["date"].nunique()),
                        "coverage_ratio": len(selected) / len(part),
                        "mean_realized_pnl": pnl, "pnl_lift": lift,
                        "precision_d1d3_or_d8d10": precision,
                        "precision_lift": precision_lift,
                    })
    return pd.DataFrame(rows)


def evaluate_tertiary_discovery(pool: pd.DataFrame, events: pd.DataFrame,
                                *, window_days: int = 20) -> pd.DataFrame:
    """Scan exploratoire; chaque ligne doit être confirmée à cause des tests multiples."""
    rows: list[dict[str, Any]] = []
    keys = pool[["date", "symbol"]].drop_duplicates()
    for category, category_events in events.groupby("tertiary_category"):
        pieces = []
        for symbol, left in keys.groupby("symbol"):
            right = category_events[category_events["symbol"].eq(symbol)][["available_date"]].sort_values("available_date")
            if right.empty:
                continue
            merged = pd.merge_asof(left.sort_values("date"), right,
                                   left_on="date", right_on="available_date",
                                   direction="backward", allow_exact_matches=True)
            age = (merged["date"] - merged["available_date"]).dt.days
            pieces.append(merged[age.between(0, window_days)][["date", "symbol"]])
        if not pieces:
            continue
        selected_keys = pd.concat(pieces).drop_duplicates()
        selected = pool.merge(selected_keys, on=["date", "symbol"], how="inner")
        if len(selected) < 100:
            continue
        annual = selected.groupby("fold_start")[RETURN_COL].mean()
        rows.append({
            "tertiary_category": category, "n": len(selected),
            "symbols": int(selected["symbol"].nunique()),
            "mean_long_return": float(selected[RETURN_COL].mean()),
            "mean_short_pnl": float(-selected[RETURN_COL].mean()),
            "long_precision_d8_d10": float((selected[DECILE_COL] >= 8).mean()),
            "short_precision_d1_d3": float((selected[DECILE_COL] <= 3).mean()),
            "positive_return_folds": int((annual > 0).sum()),
            "negative_return_folds": int((annual < 0).sum()),
            "n_folds": int(len(annual)),
        })
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--collection", type=Path, required=True)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--horizon", type=int, choices=[3, 10, 20], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    engine = get_sqlalchemy_engine()
    pool = assemble_pool(engine, args.batch_id, start_date=args.start_date,
                         end_date=args.end_date, horizon=args.horizon)
    if pool.empty:
        pool = assemble_bundle_pool_at_horizon(
            engine, args.batch_id, start_date=args.start_date,
            end_date=args.end_date, horizon=args.horizon)
    if pool.empty:
        raise SystemExit("Pool Oracle TOP20 vide.")
    events = load_8k_disclosures(args.collection)
    features = build_8k_count_features(pool, events)
    frame = pool.merge(features, on=["date", "symbol"], how="left", validate="one_to_one")
    feature_columns = [c for c in features if c.startswith("eroya_8k_")]
    frame[feature_columns] = frame[feature_columns].fillna(0.0)
    rules = evaluate_family_rules(frame)
    discovery = evaluate_tertiary_discovery(pool, events)
    args.output.mkdir(parents=True, exist_ok=False)
    rules.to_csv(args.output / "family_rules.csv", index=False)
    discovery.to_csv(args.output / "tertiary_discovery_20d.csv", index=False)
    frame[["date", "symbol", *feature_columns]].to_parquet(
        args.output / "features_oracle_top20.parquet", index=False)
    report = {
        "batch_id": args.batch_id, "horizon": args.horizon,
        "period": [args.start_date, args.end_date], "pool_rows": len(pool),
        "pool_symbols": int(pool["symbol"].nunique()), "disclosures": len(events),
        "disclosure_symbols": int(events["symbol"].nunique()),
        "pit_contract": "filing_date plus one business day; no same-day use",
        "families": {k: sorted(v) for k, v in FAMILIES.items()},
        "tertiary_scan_is_exploratory": True,
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
