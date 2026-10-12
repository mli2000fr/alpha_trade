"""Audit archived barrier-Oracle OOF rankings; no DB, broker or model fitting.

Selections precede filtering unknown future outcomes. The threshold-free argmax
is an explicitly separate diagnostic, NOT the trained batch's trading policy.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.oracle_barrier import ANY_SCORE, ANY_TARGET, MODE, SCORES, TARGETS
from modelFactory.oracle_path.train import atomic_json, digest

LOGGER = logging.getLogger(__name__)
POLICIES = (
    "LONG_TOP10", "SHORT_TOP10", "MAX_TOP10_ARGMAX_DIAGNOSTIC",
    "MAX_TOP10_FROZEN_THRESHOLD",
)
KNOWN_OUTCOMES = {"TP", "SL", "EXPIRED"}


def validate_frame(frame, protocol, training_report):
    required = {"date", "symbol", "fold_start", "research_direction", ANY_SCORE, ANY_TARGET,
        *SCORES.values(), *TARGETS.values(), "long_outcome", "short_outcome"}
    if missing := required - set(frame):
        raise ValueError(f"Missing OOF columns: {sorted(missing)}")
    if frame.empty or frame[["date", "symbol", "fold_start"]].isna().any().any():
        raise ValueError("Empty OOF or missing decision identity")
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("Duplicate OOF date/symbol")
    if set(frame.symbol) - set(protocol["universe"]):
        raise ValueError("OOF symbols outside frozen universe")
    if len(frame) != training_report["direction"]["rows"]:
        raise ValueError("OOF count differs from training report")
    for side, score in SCORES.items():
        values = frame[score].dropna()
        if not np.isfinite(values).all() or not values.between(0, 1).all():
            raise ValueError(f"Invalid {side} scores")
        target, outcome = frame[TARGETS[side]], frame[f"{side}_outcome"]
        if not target.dropna().isin([0, 1]).all():
            raise ValueError(f"Invalid {side} labels")
        if not target.notna().eq(outcome.isin(KNOWN_OUTCOMES)).all():
            raise ValueError(f"{side} label/outcome qualification mismatch")
        if not target.eq(1).eq(outcome.eq("TP")).all():
            raise ValueError(f"{side} TP target mismatch")
    both = frame[list(SCORES.values())].notna().all(axis=1)
    expected_max = frame[list(SCORES.values())].max(axis=1).where(both)
    if not np.allclose(frame[ANY_SCORE], expected_max, equal_nan=True, atol=1e-12, rtol=0):
        raise ValueError("Archived maximum score mismatch")
    delta = frame[SCORES["long"]] - frame[SCORES["short"]]
    active = both & delta.abs().gt(1e-12) & expected_max.ge(protocol["research_direction"]["min_score"])
    direction = np.where(active, np.where(delta.gt(0), "LONG", "SHORT"), "ABSTAIN")
    if not np.array_equal(direction, frame.research_direction.to_numpy()):
        raise ValueError("Archived direction differs from frozen policy")
    if not frame.groupby("date").fold_start.nunique().eq(1).all():
        raise ValueError("One decision date belongs to multiple folds")
    if set(frame.fold_start) != {fold["fold_start"] for fold in training_report["folds"]}:
        raise ValueError("Fold set mismatch")
    for fold in training_report["folds"]:
        part = frame[frame.fold_start.eq(fold["fold_start"])]
        if part.date.min() != pd.Timestamp(fold["fold_start"]) or part.date.max() != pd.Timestamp(fold["test_end"]):
            raise ValueError("OOF fold bounds mismatch")
        for head in fold["heads"].values():
            if head["status"] != "TRAINED":
                raise ValueError("Audit requires two trained heads per fold")
            if not (pd.Timestamp(head["train_available_max"]) < pd.Timestamp(fold["val_start"])
                    and pd.Timestamp(head["val_available_max"]) < part.date.min()):
                raise ValueError("Label-availability purge violation")


def select_top(frame, policy, *, top_n=10):
    """Do NOT filter labels or paths before ranking; ties use symbol ascending."""
    if policy not in POLICIES or top_n < 1:
        raise ValueError("Invalid policy/top_n")
    score = {"LONG_TOP10": SCORES["long"], "SHORT_TOP10": SCORES["short"]}.get(policy, ANY_SCORE)
    eligible = frame.dropna(subset=[score])
    top = eligible.sort_values(["date", score, "symbol"], ascending=[True, False, True]).groupby(
        "date", sort=False).head(top_n).copy()
    top["selection_rank"] = top.groupby("date", sort=False).cumcount() + 1
    if policy == "LONG_TOP10":
        direction = np.full(len(top), "LONG", dtype=object)
    elif policy == "SHORT_TOP10":
        direction = np.full(len(top), "SHORT", dtype=object)
    elif policy == "MAX_TOP10_FROZEN_THRESHOLD":
        direction = top.research_direction.to_numpy()
    else:
        delta = top[SCORES["long"]] - top[SCORES["short"]]
        direction = np.where(delta.abs().le(1e-12), "ABSTAIN", np.where(delta.gt(0), "LONG", "SHORT"))
    top["policy"] = policy
    top["audit_direction"] = direction
    top["audit_target"] = np.where(direction == "LONG", top[TARGETS["long"]],
        np.where(direction == "SHORT", top[TARGETS["short"]], np.nan))
    top["audit_outcome"] = np.where(direction == "LONG", top.long_outcome,
        np.where(direction == "SHORT", top.short_outcome, "ABSTAIN"))
    return top


def daily_counts(top):
    chosen = top.audit_direction.ne("ABSTAIN")
    known = chosen & top.audit_target.notna()
    paired = known & top[list(TARGETS.values())].notna().all(axis=1)
    counts = pd.DataFrame({"date": top.date, "selected": 1, "chosen": chosen.astype(int),
        "long": top.audit_direction.eq("LONG").astype(int),
        "short": top.audit_direction.eq("SHORT").astype(int), "evaluated": known.astype(int),
        "tp": (known & top.audit_target.eq(1)).astype(int),
        "sl": top.audit_outcome.eq("SL").astype(int),
        "expired": top.audit_outcome.eq("EXPIRED").astype(int),
        "ambiguous": top.audit_outcome.eq("AMBIGUOUS").astype(int),
        "unqualified": top.audit_outcome.eq("UNQUALIFIED").astype(int),
        "abstain": (~chosen).astype(int), "unknown": (chosen & ~known).astype(int),
        "paired": paired.astype(int), "paired_tp": (paired & top.audit_target.eq(1)).astype(int),
        "paired_long_tp": (paired & top[TARGETS["long"]].eq(1)).astype(int),
        "paired_short_tp": (paired & top[TARGETS["short"]].eq(1)).astype(int),
        "either_evaluated": top[ANY_TARGET].notna().astype(int),
        "either_tp": top[ANY_TARGET].eq(1).astype(int)})
    return counts.groupby("date", sort=True).sum()


def _ratio(a, b):
    return float(a / b) if b else None


def block_intervals(daily, *, block=20, repetitions=2000, seed=12026):
    """Resample entire consecutive decision-date blocks, not individual stocks.

    Descriptive uncertainty, not a profitability/significance certification.
    The 20-session blocks approximate overlapping label dependence; long-lived
    regime and symbol dependence can remain outside this resampling scheme.
    """
    if not len(daily) or repetitions < 1:
        return {}
    n, width = len(daily), min(block, len(daily))
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n - width + 1, size=(repetitions, int(np.ceil(n / width))))
    indices = (starts[:, :, None] + np.arange(width)).reshape(repetitions, -1)[:, :n]
    cols = ["tp", "evaluated", "paired", "paired_tp", "paired_long_tp", "paired_short_tp"]
    sums = daily[cols].to_numpy(dtype=float)[indices].sum(axis=1)
    results = {}
    for name, numerator, denominator in (
        ("tp_rate", sums[:, 0], sums[:, 1]),
        ("paired_delta_vs_long", sums[:, 3] - sums[:, 4], sums[:, 2]),
        ("paired_delta_vs_short", sums[:, 3] - sums[:, 5], sums[:, 2]),
    ):
        values = np.divide(numerator, denominator, out=np.full(len(sums), np.nan), where=denominator > 0)
        finite = values[np.isfinite(values)]
        results[name] = {"lower": float(np.quantile(finite, .025)) if len(finite) else None,
            "upper": float(np.quantile(finite, .975)) if len(finite) else None,
            "valid_replicates": len(finite)}
    return results


def summarize(top, *, bootstrap=False):
    daily = daily_counts(top)
    total = {key: int(value) for key, value in daily.sum().items()}
    result = {"start": top.date.min().date().isoformat(), "end": top.date.max().date().isoformat(),
        "sessions": len(daily), "symbols": int(top.symbol.nunique()), **total,
        "tp_rate": _ratio(total["tp"], total["evaluated"]),
        "evaluated_coverage": _ratio(total["evaluated"], total["selected"]),
        "direction_coverage": _ratio(total["chosen"], total["selected"]),
        "paired_tp_rate": _ratio(total["paired_tp"], total["paired"]),
        "paired_always_long_tp_rate": _ratio(total["paired_long_tp"], total["paired"]),
        "paired_always_short_tp_rate": _ratio(total["paired_short_tp"], total["paired"]),
        "paired_delta_vs_long": _ratio(total["paired_tp"] - total["paired_long_tp"], total["paired"]),
        "paired_delta_vs_short": _ratio(total["paired_tp"] - total["paired_short_tp"], total["paired"]),
        "either_tp_rate": _ratio(total["either_tp"], total["either_evaluated"])}
    concentration = top.symbol.value_counts().head(10)
    result["most_selected_symbols"] = {str(k): int(v) for k, v in concentration.items()}
    result["top10_symbols_selection_share"] = _ratio(concentration.sum(), len(top))
    if bootstrap:
        result["block_bootstrap_95pct"] = block_intervals(daily)
    return result


def population_summary(frame):
    result = {"sessions": int(frame.date.nunique()), "rows": len(frame), "symbols": int(frame.symbol.nunique())}
    for side, target in TARGETS.items():
        known = frame.dropna(subset=[target, SCORES[side]])
        result[side] = {"evaluated": len(known), "tp_rate": float(known[target].mean()) if len(known) else None}
    return result


def score_diagnostics(frame):
    """Descriptive OOF reliability only. Never fit calibration on these labels."""
    result = {}
    for side, target in TARGETS.items():
        known = frame.dropna(subset=[target, SCORES[side]])
        probability, actual = known[SCORES[side]], known[target]
        bucket = np.minimum((probability * 10).astype(int), 9)
        bins = []
        for index in range(10):
            mask = bucket.eq(index)
            bins.append({"lower_inclusive": index / 10, "upper": (index + 1) / 10,
                "count": int(mask.sum()), "mean_score": float(probability[mask].mean()) if mask.any() else None,
                "tp_rate": float(actual[mask].mean()) if mask.any() else None})
        result[side] = {"evaluated": len(known),
            "mean_score": float(probability.mean()) if len(known) else None,
            "observed_tp_rate": float(actual.mean()) if len(known) else None,
            "brier": float(((probability - actual) ** 2).mean()) if len(known) else None,
            "fixed_10bin_ece": sum(row["count"] * abs(row["mean_score"] - row["tp_rate"])
                for row in bins if row["count"]) / len(known) if len(known) else None,
            "bins": bins}
    return result


def audit_frame(frame, *, top_n=10):
    selections, results = [], {}
    for policy in POLICIES:
        LOGGER.info("Audit %s: %d candidates per session", policy, top_n)
        top = select_top(frame, policy, top_n=top_n)
        if top.empty:
            raise ValueError(f"No candidates for {policy}")
        years = {str(year): summarize(part, bootstrap=True) for year, part in top.groupby(top.date.dt.year)}
        folds = {str(fold): summarize(part, bootstrap=True) for fold, part in top.groupby("fold_start")}
        months = {str(month): summarize(part) for month, part in top.groupby(top.date.dt.to_period("M"))}
        results[policy] = {"overall": summarize(top, bootstrap=True), "years": years, "folds": folds, "months": months}
        selections.append(top)
    population = {"overall": population_summary(frame), "years": {
        str(year): population_summary(part) for year, part in frame.groupby(frame.date.dt.year)}}
    diagnostics = {"overall": score_diagnostics(frame), "years": {
        str(year): score_diagnostics(part) for year, part in frame.groupby(frame.date.dt.year)}}
    return {"policies": results, "population": population, "score_diagnostics": diagnostics}, pd.concat(selections, ignore_index=True)


def format_report(report):
    def pct(value):
        return "—" if value is None else f"{100 * value:.2f} %"
    def pp(value):
        return "—" if value is None else f"{100 * value:.2f} points"
    threshold = report["threshold"]
    lines = ["# Audit des dix premiers Oracle TP avant SL", "",
        f"Batch : `{report['batch_id']}`. TP 20 %, SL 7 %, 20 séances, entrée J+1 ; recherche uniquement.",
        "Aucun entraînement, modification des modèles, écriture SQL ou ordre. Aucun PnL portefeuille calculé.", "",
        "Les sélections sont faites avant exclusion des résultats futurs inconnus, sans remplacement.",
        "TOP10 = dix titres par séance, pas TOP10 %. Dates partielles 2018 et 2024 ; aucune observation 2025/2026.", "",
        "| Sélection | Sélectionnés | LONG / SHORT / abstentions | TP / SL / expirations | Inconnus | Taux TP évalué |",
        "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for policy, values in report["policies"].items():
        r = values["overall"]
        lines.append(f"| {policy} | {r['selected']} | {r['long']} / {r['short']} / {r['abstain']} | "
            f"{r['tp']} / {r['sl']} / {r['expired']} | {r['unknown']} | {pct(r['tp_rate'])} |")
    lines += ["", f"ARGMAX_DIAGNOSTIC retire le seuil {threshold:g} uniquement pour un diagnostic séparé : ce n'est pas la politique livrée.",
        "FROZEN_THRESHOLD conserve la règle archivée et ses abstentions. Aucun seuil recalé sur les résultats.", "",
        "## Par année — taux TP parmi les résultats qualifiés", "",
        "| Année | Séances | Univers LONG / SHORT | TOP10 LONG | TOP10 SHORT | TOP10 argmax | Politique figée : retenus / sélectionnés |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for year, population in report["population"]["years"].items():
        values = {p: report["policies"][p]["years"][year] for p in POLICIES}
        frozen = values["MAX_TOP10_FROZEN_THRESHOLD"]
        lines.append(f"| {year} | {population['sessions']} | {pct(population['long']['tp_rate'])} / {pct(population['short']['tp_rate'])} | "
            f"{pct(values['LONG_TOP10']['tp_rate'])} | {pct(values['SHORT_TOP10']['tp_rate'])} | "
            f"{pct(values['MAX_TOP10_ARGMAX_DIAGNOSTIC']['tp_rate'])} | {frozen['chosen']} / {frozen['selected']} |")
    lines += ["", "## Choix du sens — comparaison sur les mêmes titres/dates", "",
        "| Année | Argmax : choisis / toujours LONG / toujours SHORT | Écart vs LONG (points) | IC descriptif 95 % de l'écart |",
        "| --- | ---: | ---: | ---: |"]
    for year, r in report["policies"]["MAX_TOP10_ARGMAX_DIAGNOSTIC"]["years"].items():
        ci = r["block_bootstrap_95pct"]["paired_delta_vs_long"]
        interval = f"[{pp(ci['lower'])} ; {pp(ci['upper'])}]"
        lines.append(f"| {year} | {pct(r['paired_tp_rate'])} / {pct(r['paired_always_long_tp_rate'])} / "
            f"{pct(r['paired_always_short_tp_rate'])} | {pp(r['paired_delta_vs_long'])} | {interval} |")
    lines += ["", "Les écarts sont des points de pourcentage, pas des rendements. Bootstrap de blocs de vingt dates,",
        "2 000 réplications, graine 12026 ; dépendance entre titres conservée dans chaque date.",
        "Chevauchement des chemins et persistance des régimes limitent l'interprétation ; aucun test IID titre/date.", "",
        "## Par fold — confirmer la stabilité, pas seulement la moyenne", "",
        "| Début test → fin | TOP10 LONG | TOP10 SHORT | Argmax : TP / toujours LONG | Politique figée : retenus |",
        "| --- | ---: | ---: | ---: | ---: |"]
    for fold, r in report["policies"]["MAX_TOP10_ARGMAX_DIAGNOSTIC"]["folds"].items():
        long = report["policies"]["LONG_TOP10"]["folds"][fold]
        short = report["policies"]["SHORT_TOP10"]["folds"][fold]
        frozen = report["policies"]["MAX_TOP10_FROZEN_THRESHOLD"]["folds"][fold]
        lines.append(f"| {fold} → {r['end']} | {pct(long['tp_rate'])} | {pct(short['tp_rate'])} | "
            f"{pct(r['paired_tp_rate'])} / {pct(r['paired_always_long_tp_rate'])} | {frozen['chosen']} |")
    lines += ["", "## Échelle des scores — diagnostic, sans recalibration", "",
        "| Année | LONG : score moyen / fréquence TP observée | SHORT : score moyen / fréquence TP observée | Argmax : LONG / SHORT |",
        "| --- | ---: | ---: | ---: |"]
    for year, values in report["score_diagnostics"]["years"].items():
        long, short = values["long"], values["short"]
        selected = report["policies"]["MAX_TOP10_ARGMAX_DIAGNOSTIC"]["years"][year]
        lines.append(f"| {year} | {pct(long['mean_score'])} / {pct(long['observed_tp_rate'])} | "
            f"{pct(short['mean_score'])} / {pct(short['observed_tp_rate'])} | {selected['long']} / {selected['short']} |")
    lines += ["", "Un écart entre score moyen et fréquence réelle signale une mauvaise calibration sur la population évaluée,",
        "pas nécessairement un bug de prix/features. Moyennes, Brier et dix bins fixes sont archivés dans report.json.",
        "Comparer directement les scores de deux modèles non calibrés peut fausser le choix du sens.",
        "Aucune correction ni calibration apprise sur ces tests ; une éventuelle calibration doit utiliser seulement train/validation.",
        "", "## Limites et suite", "",
        "Ce sont des taux de TP +20 % avant SL −7 %, pas les déciles terminaux D1/D10, ni des bénéfices nets.",
        "La colonne either_tp_rate de report.json est une opportunité connue a posteriori, pas la réussite du sens choisi.",
        "Expirations à J+21 open ; gaps et ambiguïtés du contrat initial conservés. Les scores ne sont pas calibrés entre sens.",
        "Univers actuel statique (survivance), OHLC ajustés actuels non revision-PIT, familles de features selon leur lineage.",
        "Emprunt SHORT, spread, coûts, liquidité, sizing, capital et concurrence des positions non testés ici.",
        "Aucune promotion PAPER/LIVE. Confirmation chronologique 2025–2026 à autoriser séparément, règles et modèles figés.",
        "Artefacts : report.json (année/fold/mois/couverture/concentration), selected.parquet (tous les rangs et résultats),",
        "daily_counts.parquet (comptages par séance), protocol.json (règles/empreintes), progress.json."]
    return "\n".join(lines) + "\n"


def run(*, source, output, top_n=10):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Audit output must be separate from model artifacts")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Audit destination occupied; use a new output directory")
    output.mkdir(parents=True, exist_ok=True)
    try:
        protocol = json.loads((source / "protocol.json").read_text(encoding="utf-8"))
        training_report = json.loads((source / "report.json").read_text(encoding="utf-8"))
        if protocol["mode"] != MODE or training_report["status"] != "completed":
            raise ValueError("Source is not a completed barrier Oracle")
        if protocol["barriers"] != {"take_profit_pct": .2, "stop_loss_pct": .07, "max_sessions": 20}:
            raise ValueError("This fixed audit requires the original 20/7/20 contract")
        files = {name: digest(source / name) for name in ("protocol.json", "report.json", "oof_predictions.parquet")}
        atomic_json(output / "protocol.json", {"schema_version": 1, "batch_id": protocol["batch_id"],
            "created_at": datetime.now(timezone.utc).isoformat(), "source": str(source), "source_files_sha256": files,
            "source_protocol_fingerprint": protocol["fingerprint"], "top_n": top_n, "policies": POLICIES,
            "threshold": protocol["research_direction"]["min_score"], "ties": "symbol ascending; direction ties abstain",
            "future_unknown": "keep ranked candidates; exclude unknown outcomes from evaluated denominator; no replacement",
            "argmax_diagnostic": "separate threshold-free diagnostic; not a policy change or promotion",
            "uncertainty": {"unit": "consecutive decision-date blocks", "sessions": 20, "replications": 2000, "seed": 12026},
            "model_updates": False, "sql_writes": False, "portfolio_pnl": False})
        atomic_json(output / "progress.json", {"status": "RUNNING", "phase": "validate_sources"})
        for fold in training_report["folds"]:
            folder = source / "folds" / fold["fold_start"]
            checkpoint = json.loads((folder / "done.json").read_text(encoding="utf-8"))
            if checkpoint["metrics"] != fold or any(digest(folder / name) != checksum for name, checksum in checkpoint["files"].items()):
                raise ValueError(f"Fold checksum/report mismatch: {folder}")
        # Project only diagnostics needed here, not all execution/return columns.
        frame = pd.read_parquet(source / "oof_predictions.parquet", columns=[
            "date", "symbol", "fold_start", "research_direction", ANY_SCORE, ANY_TARGET,
            *SCORES.values(), *TARGETS.values(), "long_outcome", "short_outcome",
            "path_qualified", "path_quality_reason", "entry_date", "entry_price",
            "oracle_available_date"])
        validate_frame(frame, protocol, training_report)
        atomic_json(output / "progress.json", {"status": "RUNNING", "phase": "top10_audit", "rows": len(frame)})
        report, selections = audit_frame(frame, top_n=top_n)
        report.update({"status": "COMPLETED", "batch_id": protocol["batch_id"], "top_n": top_n,
            "source_files_sha256": files, "serving_ready": False, "net_profit_tested": False,
            "threshold": protocol["research_direction"]["min_score"]})
        if any(digest(source / name) != checksum for name, checksum in files.items()):
            raise ValueError("Source changed during audit")
        selections.to_parquet(output / "selected.parquet", index=False)
        daily = pd.concat([daily_counts(part).assign(policy=policy) for policy, part in selections.groupby("policy")])
        daily.reset_index().to_parquet(output / "daily_counts.parquet", index=False)
        atomic_json(output / "report.json", report)
        (output / "report.md").write_text(format_report(report), encoding="utf-8")
        atomic_json(output / "progress.json", {"status": "COMPLETED", "rows": len(frame),
            "sessions": int(frame.date.nunique()), "selected_rows": len(selections), "report": str(output / "report.json")})
        return report
    except Exception as exc:
        atomic_json(output / "progress.json", {"status": "FAILED", "error": str(exc)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()
    if args.top_n < 1:
        parser.error("top-n must be positive")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    report = run(**vars(args))
    print(json.dumps({"status": report["status"], "batch_id": report["batch_id"], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
