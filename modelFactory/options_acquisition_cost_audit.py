"""E8-A2: chiffrage local de l'acquisition d'un historique options PIT.

Ce module ne contacte aucun fournisseur et ne telecharge aucune donnee. Il
dimensionne une collecte ciblee sur les evenements Oracle TOP20 deja produits.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class AcquisitionAssumptions:
    minimum_dates: int = 504
    pilot_dates: int = 60
    complete_rate_observed: float = 0.5168
    retry_overhead_rate: float = 0.15
    contract_response_kib: float = 128.0
    quote_response_kib: float = 2.0

    def __post_init__(self) -> None:
        if self.minimum_dates < 1 or self.pilot_dates < 1:
            raise ValueError("Les nombres de dates doivent etre positifs.")
        if not 0 < self.complete_rate_observed <= 1:
            raise ValueError("complete_rate_observed doit etre dans ]0, 1].")
        if self.retry_overhead_rate < 0:
            raise ValueError("retry_overhead_rate doit etre positif.")
        if self.contract_response_kib <= 0 or self.quote_response_kib <= 0:
            raise ValueError("Les tailles de reponse doivent etre positives.")


def load_oracle_population(
    path: Path, *, start_date: str, end_date: str | None = None,
) -> pd.DataFrame:
    """Charge les seuls evenements H20 TOP20, sans utiliser de futur."""
    frame = pd.read_parquet(path)
    required = {"date", "symbol"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Artefact Oracle incomplet: {missing}")
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    if "mh0" in frame:
        selected = frame["mh0"].fillna(False).astype(bool)
    elif "pct_h20" in frame:
        selected = pd.to_numeric(frame["pct_h20"], errors="coerce").ge(0.80)
    else:
        raise ValueError("Artefact sans mh0 ni pct_h20.")
    in_period = frame["date"].ge(pd.Timestamp(start_date))
    if end_date:
        in_period &= frame["date"].le(pd.Timestamp(end_date))
    result = frame.loc[selected & in_period, ["date", "symbol"]].dropna()
    return result.drop_duplicates(["date", "symbol"]).sort_values(["date", "symbol"])


def _latest_dates(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    dates = sorted(frame["date"].unique())
    if len(dates) < count:
        raise ValueError(f"Seulement {len(dates)} dates disponibles, {count} requises.")
    return frame[frame["date"].isin(dates[-count:])].copy()


def _spread_dates(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    """Echantillonne le calendrier sans concentrer le pilote sur un seul regime."""
    dates = sorted(frame["date"].unique())
    if len(dates) < count:
        raise ValueError(f"Seulement {len(dates)} dates disponibles, {count} requises.")
    if count == 1:
        selected = [dates[len(dates) // 2]]
    else:
        selected = [
            dates[round(index * (len(dates) - 1) / (count - 1))]
            for index in range(count)
        ]
    return frame[frame["date"].isin(selected)].copy()


def summarize_population(frame: pd.DataFrame) -> dict[str, Any]:
    by_date = frame.groupby("date", sort=True).size()
    return {
        "dates": int(frame["date"].nunique()),
        "date_start": str(frame["date"].min().date()),
        "date_end": str(frame["date"].max().date()),
        "events": int(len(frame)),
        "symbols": int(frame["symbol"].nunique()),
        "events_per_date_mean": float(by_date.mean()),
        "events_per_date_min": int(by_date.min()),
        "events_per_date_max": int(by_date.max()),
    }


def estimate_collection(
    event_count: int, *, quote_requests_per_event: int,
    assumptions: AcquisitionAssumptions,
) -> dict[str, Any]:
    """Estime appels et volume brut avec un referentiel partage par evenement."""
    contract_requests = event_count
    quote_requests = event_count * quote_requests_per_event
    base_requests = contract_requests + quote_requests
    attempted_requests = math.ceil(base_requests * (1 + assumptions.retry_overhead_rate))
    raw_kib = (
        contract_requests * assumptions.contract_response_kib
        + quote_requests * assumptions.quote_response_kib
    )
    return {
        "events": event_count,
        "projected_complete_events_at_observed_rate": math.floor(
            event_count * assumptions.complete_rate_observed
        ),
        "contract_reference_requests": contract_requests,
        "quote_requests": quote_requests,
        "base_requests": base_requests,
        "attempted_requests_with_retry_budget": attempted_requests,
        "estimated_raw_gib": raw_kib / (1024 * 1024),
        "duration_at_1000_requests_per_minute_hours": attempted_requests / 1000 / 60,
        "duration_at_5000_requests_per_minute_hours": attempted_requests / 5000 / 60,
    }


def provider_matrix() -> list[dict[str, Any]]:
    """Photographie tarifaire datee; toujours reverifier avant achat."""
    return [
        {
            "provider": "ThetaData", "plan": "Options Value", "monthly_usd": 40,
            "fit": "PILOT_RECOMMENDED_LOWEST_COST",
            "coverage": "1-minute options quotes, daily open interest, rolling 4-year retail history",
            "limitation": "Theta Terminal integration required; verify expired-contract coverage on a tiny sample",
            "official_urls": [
                "https://www.thetadata.net/subscribe",
                "https://docs.thetadata.us/Articles/Getting-Started/Subscriptions.html",
            ],
        },
        {
            "provider": "ThetaData", "plan": "Options Standard", "monthly_usd": 80,
            "fit": "OPTIONAL_IF_TICK_IV_GREEKS_REQUIRED",
            "coverage": "tick NBBO, 8-year retail history, historical IV and first-order Greeks",
            "limitation": "Not necessary for the first executable ask-to-bid pilot",
            "official_urls": ["https://www.thetadata.net/subscribe"],
        },
        {
            "provider": "Massive", "plan": "Options Advanced", "monthly_usd": 199,
            "fit": "BEST_OPERATIONAL_FALLBACK",
            "coverage": "historical option quotes and flat-file quotes from 2022-03-07",
            "limitation": "individual/non-professional use; full OPRA flat files are tens of TB per year",
            "official_urls": [
                "https://massive.com/pricing?product=options",
                "https://massive.com/docs/flat-files/options/quotes",
            ],
        },
        {
            "provider": "Eroya", "plan": "Pro / Premium", "monthly_usd": [10, 59],
            "fit": "DO_NOT_RELY_ON_FOR_US_OPTIONS_CURRENTLY",
            "coverage": "advertised REST and flat-file catalog",
            "limitation": "current terms say Massive/Benzinga customer delivery is paused pending rights",
            "official_urls": ["https://eroya.co/pricing", "https://eroya.co/terms"],
        },
        {
            "provider": "Cboe DataShop", "plan": "Option Quote Intervals", "monthly_usd": None,
            "fit": "GOLD_STANDARD_QUOTE_ONLY",
            "coverage": "NBBO intervals since 2012; optional IV/Greeks and open interest",
            "limitation": "selection-specific quote; All Access API starts at USD 2,499/month",
            "official_urls": [
                "https://datashop.cboe.com/option-quote-intervals",
                "https://datashop.cboe.com/cboe-all-access-api",
            ],
        },
    ]


def build_report(
    population: pd.DataFrame, *, source_path: Path,
    assumptions: AcquisitionAssumptions,
) -> dict[str, Any]:
    full = _latest_dates(population, assumptions.minimum_dates)
    pilot = _spread_dates(population, assumptions.pilot_dates)
    strategies = {
        "one_45dte_pair_four_exits": {
            "contract_reference_requests_per_event": 1,
            "quote_requests_per_event": 10,
            "description": "2 legs at entry plus the same 2 legs at H3/H5/H10/H20",
        },
        "four_horizon_specific_pairs": {
            "contract_reference_requests_per_event": 1,
            "quote_requests_per_event": 16,
            "description": "one shared contract snapshot, then 4 pairs x entry/exit x 2 legs",
        },
    }
    estimates: dict[str, Any] = {}
    for name, frame in (("pilot", pilot), ("minimum_504_dates", full)):
        estimates[name] = {
            "population": summarize_population(frame),
            "strategies": {
                key: estimate_collection(
                    len(frame), quote_requests_per_event=value["quote_requests_per_event"],
                    assumptions=assumptions,
                )
                for key, value in strategies.items()
            },
        }
    return {
        "schema_version": 1,
        "experiment": "E8_A2_OPTIONS_SOURCE_AND_ACQUISITION_COST",
        "status": "complete", "research_only": True, "network_calls": False,
        "generated_at": datetime.now(UTC).isoformat(),
        "pricing_checked_at": "2026-09-10",
        "oracle_source": str(source_path),
        "available_population": summarize_population(population),
        "assumptions": asdict(assumptions),
        "pilot_sampling": "evenly_spaced_dates_across_the_available_period",
        "request_contract": strategies,
        "estimates": estimates,
        "providers": provider_matrix(),
        "decision": {
            "recommended_pilot": "ThetaData Options Value for one month (USD 40)",
            "operational_fallback": "Massive Options Advanced for one month (USD 199)",
            "do_not_download": "full-market OPRA tick flat files",
            "e8_b_status": "STILL_BLOCKED_UNTIL_PILOT_DATA_QUALITY_GATES_PASS",
            "purchase_or_download_performed": False,
        },
    }


def run(
    *, oracle_path: Path, output_root: Path, start_date: str,
    end_date: str | None, assumptions: AcquisitionAssumptions,
) -> Path:
    population = load_oracle_population(
        oracle_path, start_date=start_date, end_date=end_date,
    )
    report = build_report(population, source_path=oracle_path, assumptions=assumptions)
    run_id = f"options-acquisition-audit-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    report["run_id"] = run_id
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path,
                        default=Path("artifacts/research/options_acquisition_audit"))
    parser.add_argument("--start-date", default="2022-03-07")
    parser.add_argument("--end-date")
    parser.add_argument("--minimum-dates", type=int, default=504)
    parser.add_argument("--pilot-dates", type=int, default=60)
    args = parser.parse_args()
    output = run(
        oracle_path=args.oracle_path, output_root=args.output_root,
        start_date=args.start_date, end_date=args.end_date,
        assumptions=AcquisitionAssumptions(
            minimum_dates=args.minimum_dates, pilot_dates=args.pilot_dates,
        ),
    )
    print(f"E8-A2 termine: {output}")


if __name__ == "__main__":
    main()
