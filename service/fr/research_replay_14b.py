"""One frozen FR development cell, local archives only: no SQL/network/fitting."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from decimal import Decimal
import json
from pathlib import Path
import time

from service.fr.exploitable_scope_12e import sha
from service.fr.research_catalog_14a import ROOT, load_campaign

OUTPUT_PARENT = ROOT / "artifacts/ihm_backtesting_runs/fr-research-replay"
PROGRESS_PREFIX = "::fr_replay_progress::"


@dataclass(frozen=True, slots=True)
class FRResearchReplayOptions:
    market_code: str = "FR_EQ"
    database_alias: str = "fr_primary"
    fold: int = 6
    policy: str = "oracle_top20_long"
    variant: str = "baseline"
    tax_scenario: str = "unknown_taxed"
    cost_scenario: str = "nominal"
    output_root: str | None = None


def validate_options(options: FRResearchReplayOptions, *, require_output=False) -> None:
    if options.market_code != "FR_EQ" or options.database_alias != "fr_primary":
        raise ValueError("Replay réservé à FR_EQ / fr_primary")
    if type(options.fold) is not int or options.fold not in (6, 7):
        raise ValueError("Folds de développement 6/7 uniquement, confirmation 2026 réservée")
    allowed = {
        "policy": ("oracle_top20_long", "atr_top20_long", "uniform_control_long"),
        "variant": ("baseline", "delay_1", "cap_10pct", "delay_1_cap_10pct"),
        "tax_scenario": ("unknown_taxed", "unknown_untaxed"),
        "cost_scenario": ("nominal", "stress_execution_x2"),
    }
    for name, choices in allowed.items():
        if getattr(options, name) not in choices:
            raise ValueError(f"{name} hors protocole FR")
    if require_output:
        if not options.output_root or not Path(options.output_root).resolve().is_relative_to(OUTPUT_PARENT.resolve()):
            raise ValueError("Sortie hors des runs FR IHM")
        if Path(options.output_root).resolve() == OUTPUT_PARENT.resolve():
            raise ValueError("Répertoire individuel requis")


def preflight(options: FRResearchReplayOptions) -> dict:
    validate_options(options)
    campaign = load_campaign("robustness_13d")
    protocol = campaign["manifest"]
    source = Path(protocol["source"])
    if not source.is_absolute():
        source = ROOT / source
    if not source.resolve().is_relative_to((ROOT / "artifacts/fr").resolve()):
        raise ValueError("Source hors du périmètre FR")
    for filename, key in (("report.json", "source_report_sha256"), ("protocol.json", "source_protocol_sha256")):
        if sha(source / filename) != protocol[key]:
            raise ValueError(f"Archive FR modifiée : {filename}")
    source_report = json.loads((source / "report.json").read_text(encoding="utf-8"))
    source_protocol = json.loads((source / "protocol.json").read_text(encoding="utf-8"))
    for name, expected in source_report["output_hashes"].items():
        path = (source / name).resolve()
        if not path.is_relative_to(source.resolve()) or sha(path) != expected:
            raise ValueError(f"Sortie source FR modifiée : {name}")
    for name, expected in source_protocol["local_hashes"].items():
        path = Path(name)
        path = path if path.is_absolute() else ROOT / path
        if sha(path) != expected:
            raise ValueError(f"Entrée/implémentation figée modifiée : {name}")
    for name, expected in protocol["implementation_hashes"].items():
        path = Path(name)
        path = path if path.is_absolute() else ROOT / path
        if sha(path) != expected:
            raise ValueError(f"Moteur figé modifié : {name}")
    matches = [c for c in campaign["report"]["cells"] if all(
        c[key] == getattr(options, key) for key in ("fold", "policy", "variant", "tax_scenario", "cost_scenario"))]
    if len(matches) != 1 or matches[0].get("metrics") is None:
        raise ValueError("Cellule archivée absente ou bloquée")
    return {"campaign": campaign, "source": source, "protocol": source_protocol, "cell": matches[0]}


def latest_progress_event(journal: str) -> dict | None:
    for line in reversed(journal.splitlines()):
        if PROGRESS_PREFIX not in line:
            continue
        try:
            event = json.loads(line.split(PROGRESS_PREFIX, 1)[1])
            if event.get("stage") in ("preflight", "loading", "replaying", "report_written", "failed"):
                return event
        except (ValueError, AttributeError):
            pass
    return None


def run(options: FRResearchReplayOptions) -> dict:
    validate_options(options, require_output=True)
    output = Path(options.output_root).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    def emit(stage):
        print(PROGRESS_PREFIX + json.dumps({"stage": stage, "elapsed_seconds": round(time.monotonic()-started, 2)}), flush=True)
    try:
        emit("preflight")
        context = preflight(options)
        from service.fr.provider_exploratory_13b import load_frozen, write_json
        from service.fr.robustness_13d import VARIANTS, delayed_tape
        from service.fr.robustness_engine_13d import replay_assumed
        from service.fr.execution_costs import load_cost_profile
        from service.fr.provider_exploratory_metrics_13b import ledger_metrics
        import pandas as pd
        config = context["protocol"]["config"]
        emit("loading")
        _, scores, intents, _ = load_frozen(config)
        shared = json.loads((context["source"] / f"fold-{options.fold}-supplier-shared.json").read_text(encoding="utf-8"))
        if any(day > "2025-12-31" for day in shared["sessions"]):
            raise ValueError("Confirmation réservée")
        available = scores[scores.fold.eq(options.fold)].set_index(["decision_session_date", "research_uid"]).max_input_available_at
        selected = intents[intents.fold.eq(options.fold) & intents.policy.eq(options.policy)]
        if selected.empty:
            raise ValueError("Aucun candidat FR, aucun remplacement synthétique")
        tape = dict(shared)
        tape["candidates"] = [{"session": r.decision_session_date, "uid": r.research_uid,
            "rank": int(r.candidate_rank), "available_at": available.loc[(r.decision_session_date, r.research_uid)]}
            for r in selected.itertuples()]
        settings = VARIANTS[options.variant]
        tape = delayed_tape(tape, settings["delay_sessions"])
        tax = pd.read_parquet(config["tax_review"])
        known = {f"{r.symbol}/{r.year}": True for r in tax.itertuples() if r.status.startswith("POSITIVE_")}
        write_json(output / "protocol.json", {
            "options": asdict(options), "source_report_sha256": context["campaign"]["report_sha256"],
            "candidate_count": len(tape["candidates"]), "sessions": [tape["sessions"][0], tape["sessions"][-1]],
            "implementation_sha256": sha(Path(__file__)), "assumptions": config["assumptions"],
            "economic_go_allowed": False, "serving_enabled": False, "canonical_writes": False,
        })
        emit("replaying")
        result = replay_assumed(tape, load_cost_profile(Path(config["cost_profile"])),
            {"known_positive": known, "unknown_liable": options.tax_scenario == "unknown_taxed"},
            stress_multiplier=Decimal(str(config["cost_scenarios"][options.cost_scenario])),
            position_cap_pct=settings["position_cap_pct"])
        write_json(output / "ledger.json", result)
        metrics = ledger_metrics(result, data_kind="EXPLORATORY_PROVIDER_ASSUMED")
        if metrics != context["cell"]["metrics"]:
            raise ValueError("Régression FR : métriques différentes de la cellule archivée")
        report = {
            "market_code": "FR_EQ", "currency": "EUR", "database_alias": "fr_primary",
            "status": "COMPLETED_EXPLORATORY_REPRODUCTION", "options": asdict(options), "metrics": metrics,
            "exact_archive_reproduction": True, "economic_go_allowed": False, "serving_enabled": False,
            "canonical_writes": False, "strict_sprint13_complete": False, "confirmation_2026_evaluated": False,
            "protocol_sha256": sha(output / "protocol.json"), "ledger_sha256": sha(output / "ledger.json"),
        }
        write_json(output / "report.json", report)
        emit("report_written")
        return report
    except Exception as exc:
        if hasattr(exc, "ledger"):
            (output / "partial_ledger.json").write_text(json.dumps(exc.ledger, default=str, indent=2), encoding="utf-8")
        (output / "failure.json").write_text(json.dumps({"status": "FAILED", "error": str(exc),
            "market_code": "FR_EQ", "economic_go_allowed": False}, ensure_ascii=False, indent=2), encoding="utf-8")
        emit("failed")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market-code", required=True)
    parser.add_argument("--database-alias", required=True)
    parser.add_argument("--fold", type=int, required=True)
    for name in ("policy", "variant", "tax-scenario", "cost-scenario", "output-root"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    report = run(FRResearchReplayOptions(**vars(args)))
    print(json.dumps({"status": report["status"], "net_return_pct": report["metrics"]["net_return_pct"]}), flush=True)


if __name__ == "__main__":
    main()
