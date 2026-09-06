"""E6-B0 research-only: faisabilité d'un backtest options post-Oracle.

Le module audite les snapshots déjà collectés et transforme les preuves d'accès
aux historiques en décision explicite. Il ne télécharge aucun historique massif,
ne modifie aucune table et ne produit aucune performance simulée.
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class OptionsFeasibilityConfig:
    oracle_oof_start: str = "2018-07-05"
    oracle_oof_end: str = "2025-07-11"
    historical_quote_start: str = "2022-03-07"
    entry_clock: str = "09:35 America/New_York"
    exit_clock: str = "15:55 America/New_York"
    min_dte_calendar: int = 35
    max_dte_calendar: int = 55
    minimum_exit_buffer_days: int = 5
    entry_quote_side: str = "ask"
    exit_quote_side: str = "bid"


def iter_jsonl_gzip(paths: Iterable[Path]) -> Iterable[dict[str, Any]]:
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    value = json.loads(line)
                    if isinstance(value, dict):
                        yield value


def audit_snapshot_collections(paths: Iterable[Path]) -> dict[str, Any]:
    """Mesure la complétude effective des petits snapshots options existants."""
    paths = list(paths)
    pages = errors = 0
    symbols: set[str] = set()
    contracts: dict[str, dict[str, Any]] = {}
    for envelope in iter_jsonl_gzip(paths):
        symbol = str(envelope.get("symbol_requested") or "").upper()
        if symbol:
            symbols.add(symbol)
        if envelope.get("error") or int(envelope.get("http_status") or 200) >= 400:
            errors += 1
            continue
        pages += 1
        payload = envelope.get("payload") or {}
        results = payload.get("results") if isinstance(payload, dict) else None
        for item in results if isinstance(results, list) else []:
            if not isinstance(item, dict):
                continue
            details = item.get("details") or {}
            ticker = str(details.get("ticker") or "")
            if ticker:
                contracts[ticker] = item
    values = list(contracts.values())
    types = [str((item.get("details") or {}).get("contract_type") or "unknown") for item in values]
    quotes = [item.get("last_quote") or {} for item in values]
    bid_ask = [
        quote for quote in quotes
        if float(quote.get("bid") or 0) > 0 and float(quote.get("ask") or 0) > 0
    ]
    iv_count = sum(np.isfinite(item.get("implied_volatility", np.nan)) for item in values)
    oi_count = sum(item.get("open_interest") is not None for item in values)
    strike_pairs = {
        (
            str((item.get("underlying_asset") or {}).get("ticker") or ""),
            str((item.get("details") or {}).get("expiration_date") or ""),
            float((item.get("details") or {}).get("strike_price") or 0),
        ): set()
        for item in values
    }
    for item in values:
        key = (
            str((item.get("underlying_asset") or {}).get("ticker") or ""),
            str((item.get("details") or {}).get("expiration_date") or ""),
            float((item.get("details") or {}).get("strike_price") or 0),
        )
        strike_pairs[key].add(str((item.get("details") or {}).get("contract_type") or ""))
    complete_pairs = sum({"call", "put"}.issubset(sides) for sides in strike_pairs.values())
    spreads = []
    for quote in bid_ask:
        bid, ask = float(quote["bid"]), float(quote["ask"])
        midpoint = (bid + ask) / 2.0
        if midpoint > 0:
            spreads.append((ask - bid) / midpoint)
    return {
        "files": len(paths),
        "pages": pages, "errors": errors, "symbols": len(symbols),
        "unique_contracts": len(values),
        "contract_types": {name: types.count(name) for name in sorted(set(types))},
        "contracts_with_bid_and_ask": len(bid_ask),
        "contracts_with_implied_volatility": int(iv_count),
        "contracts_with_open_interest_field": int(oi_count),
        "complete_same_strike_call_put_pairs": int(complete_pairs),
        "median_relative_bid_ask_spread": float(np.median(spreads)) if spreads else None,
        "suitable_for_historical_backtest": False,
        "reason": "snapshot courant, pagination volontairement bornée et absence de paires ATM complètes",
    }


def assess_remote_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Décide séparément faisabilité REST, flat files et backtest exact."""
    rest_required = ("contracts_as_of", "daily_aggregates", "historical_trades", "historical_quotes")
    rest_ok = all(int(evidence.get(name, {}).get("http_status") or 0) == 200 for name in rest_required)
    catalog = evidence.get("flatfile_catalog", {})
    day_entitled = bool(catalog.get("day_entitled"))
    minute_entitled = bool(catalog.get("minute_entitled"))
    object_status = int(evidence.get("flatfile_object", {}).get("http_status") or 0)
    flatfile_ok = day_entitled and minute_entitled and object_status in {200, 206}
    return {
        "historical_rest_access": rest_ok,
        "flatfile_catalog_entitled": day_entitled and minute_entitled,
        "flatfile_download_verified": flatfile_ok,
        "exact_bid_ask_backtest_period": "2022-03-07..2025-07-11" if rest_ok else None,
        "full_2018_2025_exact_bid_ask_possible": False,
        "pilot_possible_now": rest_ok,
        "full_scale_preferred_transport_ready": flatfile_ok,
        "decision": (
            "GO_REST_PILOT_FLATFILES_BLOCKED" if rest_ok and not flatfile_ok
            else "GO_FULL_PIPELINE" if rest_ok and flatfile_ok
            else "BLOCKED"
        ),
    }


def build_report(
    snapshot: dict[str, Any], evidence: dict[str, Any],
    config: OptionsFeasibilityConfig | None = None,
) -> dict[str, Any]:
    contract = config or OptionsFeasibilityConfig()
    assessment = assess_remote_evidence(evidence)
    return {
        "schema_version": 1,
        "experiment": "E6_B0_oracle_options_data_feasibility_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "research_only": True, "serving_ready": False,
        "configuration": asdict(contract),
        "existing_snapshot_audit": snapshot,
        "remote_access_evidence": evidence,
        "assessment": assessment,
        "pit_contract_for_E6_B1": {
            "signal": "Oracle OOF TOP20 connu à la clôture J",
            "underlying_reference": "open action J+1, après contrôle du gap",
            "contract_selection": "même strike call/put le plus proche du sous-jacent; expiration 35-55 jours",
            "contract_query": "utiliser as_of seul; ne pas le combiner avec expired=true",
            "entry": "première paire NBBO complète à partir de 09:35 ET; achat aux asks",
            "exit": "dernière paire NBBO complète avant 15:55 ET à H3/H5/H10/H20; vente aux bids",
            "missing_quote": "observation exclue, aucune interpolation de prix de transaction",
            "minimum_expiry_buffer": f"expiration au moins {contract.minimum_exit_buffer_days} jours après la sortie",
            "costs": "spread observé intégré par ask->bid; commissions ajoutées séparément",
            "corporate_actions": "fenêtres avec contrat ajusté ou ticker discontinu isolées et auditées",
        },
        "staged_plan": [
            {
                "stage": "E6-B1 pilot REST",
                "period": "2022-03-07..2025-07-11",
                "population": "échantillon temporel préfixé de dates Oracle, puis tous les TOP20 de ces dates",
                "purpose": "valider sélection de contrats, NBBO, couverture et coût réel sans téléchargement massif",
            },
            {
                "stage": "E6-B2 broad daily screen",
                "period": "2018-07-05..2025-07-11",
                "population": "TOP20, NEXT20 et REST80",
                "condition": "flat files day/minute réellement téléchargeables",
                "limitation": "OHLC de transactions sans NBBO exact avant mars 2022",
            },
            {
                "stage": "E6-B3 exact confirmation",
                "period": "période 2022+ intacte",
                "population": "une politique fixée après E6-B1/B2",
                "purpose": "confirmation ask->bid nette, sans choix de seuil sur la confirmation",
            },
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, action="append", default=[])
    parser.add_argument("--evidence-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    snapshot = audit_snapshot_collections(args.snapshot) if args.snapshot else {}
    evidence = json.loads(args.evidence_json.read_text(encoding="utf-8"))
    report = build_report(snapshot, evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"E6-B0 terminé: {args.output}")
    print(f"Décision: {report['assessment']['decision']}")


if __name__ == "__main__":
    main()
