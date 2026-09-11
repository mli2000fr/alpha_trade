"""E8-A: audit local et read-only de l'historique options PIT disponible."""
from __future__ import annotations

import argparse
import gzip
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from database.connection import get_sqlalchemy_engine


@dataclass(frozen=True, slots=True)
class OptionsPitRequirements:
    required_start: str = "2018-07-05"
    required_end: str = "2024-05-08"
    minimum_dates: int = 504
    minimum_symbols: int = 100
    minimum_complete_rate: float = 0.40
    require_bid_ask: bool = True
    require_historical_contract_reference: bool = True
    require_entry_exit_valuation: bool = True


def audit_database(engine: Engine) -> dict[str, Any]:
    inspector = inspect(engine)
    names = inspector.get_table_names()
    candidates = sorted(
        name for name in names
        if any(token in name.lower() for token in ("option", "derivative", "greek"))
    )
    return {
        "dialect": engine.dialect.name,
        "candidate_tables": candidates,
        "persistent_options_storage": bool(candidates),
        "table_count": len(candidates),
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def audit_directional_collection(path: Path) -> dict[str, Any]:
    report = _read_json(path / "collection_report.json")
    parquet = path / "option_features.parquet"
    result: dict[str, Any] = {
        "path": str(path), "collection_report_present": bool(report),
        "features_present": parquet.is_file(),
    }
    if not parquet.is_file():
        return result
    frame = pd.read_parquet(parquet)
    dates = pd.to_datetime(frame.get("date"), errors="coerce").dropna()
    complete = frame.get("status", pd.Series(index=frame.index, dtype=object)).eq("complete")
    quote_columns = [
        "atm_call_relative_spread", "atm_put_relative_spread",
        "otm_call_relative_spread", "otm_put_relative_spread",
    ]
    iv_observed = "implied_volatility" in frame.columns
    result.update({
        "rows": int(len(frame)), "dates": int(dates.nunique()),
        "date_start": str(dates.min().date()) if len(dates) else None,
        "date_end": str(dates.max().date()) if len(dates) else None,
        "symbols": int(frame.get("symbol", pd.Series(dtype=object)).nunique()),
        "complete_rows": int(complete.sum()),
        "complete_rate": float(complete.mean()) if len(frame) else None,
        "bid_ask_derived_fields": [column for column in quote_columns if column in frame],
        "historical_iv_observed": iv_observed,
        "historical_iv_approximation": "approx_atm_iv" in frame,
        "historical_greeks": any(column in frame for column in ("delta", "gamma", "vega", "theta")),
        "historical_open_interest": "open_interest" in frame,
        "raw_event_checkpoint": (path / "event_results.jsonl").is_file(),
        "purpose": "directional surface snapshot at signal close; not a daily option PnL history",
    })
    return result


def audit_snapshot_file(path: Path) -> dict[str, Any]:
    envelopes = contracts = bid_ask = iv = open_interest = greeks = 0
    symbols: set[str] = set()
    try:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                envelopes += 1
                envelope = json.loads(line)
                symbol = str(envelope.get("symbol_requested") or "").upper()
                if symbol:
                    symbols.add(symbol)
                payload = envelope.get("payload") or {}
                values = payload.get("results") if isinstance(payload, dict) else []
                for item in values if isinstance(values, list) else []:
                    if not isinstance(item, dict):
                        continue
                    contracts += 1
                    quote = item.get("last_quote") or {}
                    if float(quote.get("bid") or 0) > 0 and float(quote.get("ask") or 0) > 0:
                        bid_ask += 1
                    iv += int(np.isfinite(item.get("implied_volatility", np.nan)))
                    open_interest += int(item.get("open_interest") is not None)
                    greek = item.get("greeks") or {}
                    greeks += int(bool(greek))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {"path": str(path), "readable": False}
    return {
        "path": str(path), "readable": True, "envelopes": envelopes,
        "symbols": len(symbols), "contracts": contracts,
        "contracts_with_bid_ask": bid_ask, "contracts_with_iv": iv,
        "contracts_with_open_interest": open_interest,
        "contracts_with_greeks": greeks,
        "pit_role": "current snapshot only; cannot be joined retrospectively",
    }


def audit_local_artifacts(root: Path) -> dict[str, Any]:
    directional = [
        audit_directional_collection(path)
        for path in sorted(root.glob("options-directional-*")) if path.is_dir()
    ]
    snapshots = [
        audit_snapshot_file(path)
        for path in sorted(root.glob("eroya-collect-*/options_chain.jsonl.gz"))
    ]
    volume_repairs = [str(path) for path in sorted(root.glob("options-volume-repair-*/report.json"))]
    return {
        "directional_collections": directional,
        "current_snapshot_files": snapshots,
        "volume_repair_reports": volume_repairs,
    }


def assess_readiness(
    database: dict[str, Any], artifacts: dict[str, Any],
    requirements: OptionsPitRequirements,
) -> dict[str, Any]:
    collections = artifacts["directional_collections"]
    best = max(collections, key=lambda item: int(item.get("complete_rows") or 0), default={})
    dates = int(best.get("dates") or 0)
    symbols = int(best.get("symbols") or 0)
    complete_rate = float(best.get("complete_rate") or 0)
    gates = {
        "persistent_storage": bool(database["persistent_options_storage"]),
        "minimum_dates": dates >= requirements.minimum_dates,
        "minimum_symbols": symbols >= requirements.minimum_symbols,
        "minimum_complete_rate": complete_rate >= requirements.minimum_complete_rate,
        "historical_bid_ask": bool(best.get("bid_ask_derived_fields")),
        "historical_contract_reference": bool(best.get("complete_rows")),
        "historical_iv_observed": bool(best.get("historical_iv_observed")),
        "historical_greeks": bool(best.get("historical_greeks")),
        "historical_open_interest": bool(best.get("historical_open_interest")),
        "daily_entry_exit_valuation": False,
        "rates_dividends_corporate_actions": False,
    }
    blocking = [
        "no_persistent_option_tables" if not gates["persistent_storage"] else None,
        "only_sparse_signal_dates" if not gates["minimum_dates"] else None,
        "no_dense_entry_exit_quotes" if not gates["daily_entry_exit_valuation"] else None,
        "no_observed_historical_iv_greeks_oi" if not all((
            gates["historical_iv_observed"], gates["historical_greeks"],
            gates["historical_open_interest"],
        )) else None,
        "missing_rates_dividends_corporate_actions" if not gates["rates_dividends_corporate_actions"] else None,
    ]
    blocking = [reason for reason in blocking if reason]
    return {
        "best_local_collection": best, "gates": gates,
        "blocking_reasons": blocking,
        "verdict": "BLOCKED_NO_DENSE_PIT_HISTORY" if blocking else "GO_E8_B",
        "e8_b_authorized": not blocking,
        "interpretation": (
            "Les fichiers locaux permettent des POC sur huit dates, pas un backtest "
            "Walk-Forward quotidien de volatilité implicite contre réalisée."
        ),
    }


def run(*, artifacts_root: Path, output_root: Path, requirements: OptionsPitRequirements) -> Path:
    database = audit_database(get_sqlalchemy_engine())
    artifacts = audit_local_artifacts(artifacts_root)
    assessment = assess_readiness(database, artifacts, requirements)
    run_id = f"options-pit-audit-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "schema_version": 1, "run_id": run_id,
        "experiment": "E8_A_OPTIONS_PIT_HISTORY_AUDIT",
        "status": "complete", "research_only": True, "network_calls": False,
        "generated_at": datetime.now(UTC).isoformat(),
        "requirements": asdict(requirements), "database": database,
        "local_artifacts": artifacts, "assessment": assessment,
        "remote_capability_known_from_previous_evidence": {
            "historical_contracts_as_of": True,
            "historical_nbbo_rest_start": "2022-03-07",
            "current_chain_snapshot_has_iv_greeks_oi": True,
            "current_snapshot_is_not_historical": True,
            "minute_aggregate_archive": "previously entitled but catalog returned HTTP 502",
            "full_quotes_trades_flatfiles": "Premium entitlement previously absent",
        },
        "next_data_contract": {
            "unit": "contract x timestamp/date",
            "minimum_period": "2022-03-07 onward for exact NBBO",
            "required": [
                "underlying", "option_ticker", "as_of", "expiration", "strike",
                "call_put", "bid", "ask", "quote_timestamp", "underlying_price",
            ],
            "strongly_recommended": [
                "implied_volatility", "delta", "gamma", "vega", "theta",
                "open_interest", "volume", "risk_free_rate", "dividend_schedule",
                "contract_adjustment", "corporate_action",
            ],
        },
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-root", type=Path,
                        default=Path("artifacts/research/eroya_directional"))
    parser.add_argument("--output-root", type=Path,
                        default=Path("artifacts/research/options_pit_audit"))
    args = parser.parse_args()
    output = run(
        artifacts_root=args.artifacts_root, output_root=args.output_root,
        requirements=OptionsPitRequirements(),
    )
    print(f"E8-A terminé: {output}")
    print(json.loads((output / "report.json").read_text(encoding="utf-8"))["assessment"]["verdict"])


if __name__ == "__main__":
    main()
