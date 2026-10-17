"""Matched-population LightGBM/CatBoost/LSTM research from archived inputs only.

No SQL, broker, production inference or edits to the two previous experiments.
All folds/models/scalers are causal; 2024-2026 never select epochs or parameters.
"""
from dataclasses import asdict
import argparse
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import torch

from modelFactory.config import BaselineConfig
from modelFactory.global_ranking import _XS_RANK_SOURCE_FEATURES
from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.security_continuity import load_security_discontinuities
from modelFactory.oracle.train import roc_auc
from modelFactory.oracle.walk_forward import build_folds_adaptive
from modelFactory.oracle_path import TARGET
from modelFactory.oracle_path.predict import load_contract
from modelFactory.oracle_path.train import (atomic_json, digest, restore_ranks, train_model,
    train_catboost, model_probabilities)
from modelFactory.oracle_path.lstm_research import SequenceSpec, sequence_eligibility, fit, predict
from scripts.research.oracle_path_confirmation import exclusive_run, evaluate

LOGGER = logging.getLogger(__name__)
CANDIDATES = ("lightgbm", "catboost", "lstm")


def epoch_payload(fold, number, count, spec, epoch, current, total, detail):
    # Epoch-completed detail already contains 'epoch': build a merged mapping,
    # not dict(epoch=..., **detail), which raises AFTER a checkpoint was committed.
    return {**detail, "fold": fold, "fold_index": number, "total_folds": count,
            "epoch": epoch, "max_epochs": spec.max_epochs, "completed": current, "total": total}


def verify_inputs(history, confirmation):
    root, protocol, profile, folds = load_contract(history/"models", "oracle-path-comparison")
    old_plan = json.loads((history/"plan.json").read_text(encoding="utf-8"))
    for name, checksum in old_plan["source_hashes"].items():
        if digest(name) != checksum:
            raise ValueError("Code historique modifié : qualifier avant comparaison LSTM")
    confirmed = json.loads((confirmation/"run.json").read_text(encoding="utf-8"))
    cplan = json.loads((confirmation/"plan.json").read_text(encoding="utf-8"))
    if confirmed["status"] != "COMPLETED" or cplan["feature_profile_sha256"] != digest(root/"feature_profile.json"):
        raise ValueError("Confirmation préalable terminée et profil commun requis")
    if cplan["universe"] != protocol["universe"] or cplan["source_protocol_sha256"] != digest(root/"protocol.json"):
        raise ValueError("Univers/source de confirmation différents")
    if digest("scripts/research/oracle_path_confirmation.py") != cplan["source_code_sha256"]:
        raise ValueError("Code de confirmation original différent")
    registry = load_security_discontinuities()
    normalized = json.loads(json.dumps({s:[asdict(e) for e in events] for s,events in registry.items()}, default=str))
    if normalized != protocol["security_discontinuities"]:
        raise ValueError("Registre des identités différent")
    checks = {}
    for period, base in (("history", root), ("confirmation", confirmation)):
        checks[f"{period}/labels.parquet"] = digest(base/"labels.parquet")
        checks[f"{period}/report.json"] = digest(base/"report.json")
        for folder in sorted((base/"chunks").iterdir()):
            marker = folder/"done.json"
            saved = json.loads(marker.read_text(encoding="utf-8"))
            for name, checksum in saved["files"].items():
                if not (folder/name).is_file() or digest(folder/name) != checksum:
                    raise ValueError(f"Entrée archivée corrompue : {folder/name}")
            checks[f"{period}/{folder.name}"] = digest(marker)
    return root, protocol, profile, folds, cplan, registry, checks


def build_cache(root, confirmation, profile, registry, calendar, spec, output, progress):
    folder = output/"dataset"
    folder.mkdir(parents=True, exist_ok=True)
    done = folder/"done.json"
    if done.exists():
        saved = json.loads(done.read_text(encoding="utf-8"))
        if not all(digest(folder/n)==h for n,h in saved["files"].items()):
            raise ValueError("Cache séquentiel corrompu")
        return pd.read_parquet(folder/"meta.parquet"), np.load(folder/"matrix.npy", mmap_mode="r")
    columns = profile["feature_columns"]
    parts = []
    for period, base in (("history", root), ("confirmation", confirmation)):
        frames, bar_parts = [], []
        folders = sorted((base/"chunks").iterdir())
        for number, chunk in enumerate(folders):
            progress("dataset", dict(period=period, completed=number, total=len(folders)))
            available = pq.ParquetFile(chunk/"features.parquet").schema.names
            requested = ["date", "symbol", *columns, *_XS_RANK_SOURCE_FEATURES]
            requested = list(dict.fromkeys(c for c in requested if c in available))
            frames.append(pd.read_parquet(chunk/"features.parquet", columns=requested))
            bar_parts.append(pd.read_parquet(chunk/"bars.parquet",
                columns=["date", "symbol", "instrument_id", "data_source", "data_adjustment"]))
        frame = restore_ranks(pd.concat(frames, ignore_index=True), profile["generator_options"])
        del frames
        frame = frame[["date", "symbol", *columns]].copy()
        bars = pd.concat(bar_parts, ignore_index=True)
        del bar_parts
        if bars.duplicated(["date", "symbol"]).any():
            raise ValueError("Doublons d'identité archivés")
        frame = frame.merge(bars, on=["date", "symbol"], how="left", validate="one_to_one")
        labels = pd.read_parquet(base/"labels.parquet", columns=["date", "symbol", TARGET,
            "path_amplitude", "oracle_available_date"])
        frame = frame.merge(labels, on=["date", "symbol"], how="left", validate="one_to_one")
        frame["period"] = period
        parts.append(frame)
    frame = pd.concat(parts, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
    del parts
    if frame.duplicated(["date", "symbol"]).any():
        raise ValueError("Archives historiques/confirmation se chevauchent")
    matrix = np.lib.format.open_memmap(folder/"matrix.npy", mode="w+", dtype=np.float32,
        shape=(len(frame), len(columns)))
    present = np.empty(len(frame), dtype=bool)
    for offset in range(0, len(frame), 100000):
        block = frame.iloc[offset:offset+100000][columns].to_numpy(dtype=np.float32, copy=True)
        block[~np.isfinite(block)] = np.nan
        matrix[offset:offset+len(block)] = block
        present[offset:offset+len(block)] = np.isfinite(block).any(axis=1)
    matrix.flush()
    meta = frame.drop(columns=columns).copy()
    del frame
    meta["feature_present"] = present
    valid, reasons = sequence_eligibility(meta, calendar, spec.length, registry)
    meta["sequence_eligible"], meta["sequence_reason"] = valid, reasons
    meta.to_parquet(folder/"meta.parquet", index=False)
    atomic_json(done, dict(rows=len(meta), features=len(columns), sequence_reasons=meta.sequence_reason.value_counts().to_dict(),
        files={n:digest(folder/n) for n in ("meta.parquet", "matrix.npy")}))
    return meta, np.load(folder/"matrix.npy", mmap_mode="r")


def fold_indices(meta, fold, original):
    eligible = meta.period.eq("history") & meta[TARGET].notna()
    train = eligible & meta.date.isin(fold["train_dates"]) & meta.oracle_available_date.lt(pd.Timestamp(fold["val_start"]))
    val = eligible & meta.date.isin(fold["val_dates"]) & meta.oracle_available_date.lt(pd.Timestamp(fold["t_start"]))
    if int(train.sum()) != original["n_train"] or int(val.sum()) != original["n_val"]:
        raise ValueError("Folds reconstruits différents de l'expérience originale")
    test = meta.period.eq("history") & meta.date.isin(fold["test_dates"])
    indices = [np.flatnonzero((mask & meta.sequence_eligible).to_numpy()) for mask in (train, val, test)]
    return indices, dict(original_train_rows=int(train.sum()), original_val_rows=int(val.sum()),
        common_train_rows=len(indices[0]), common_val_rows=len(indices[1]), common_test_rows=len(indices[2]),
        train_available_max=str(meta.loc[train & meta.sequence_eligible, "oracle_available_date"].max()),
        val_available_max=str(meta.loc[val & meta.sequence_eligible, "oracle_available_date"].max()))


def tabular_frame(matrix, meta, indices, columns):
    frame = pd.DataFrame(np.asarray(matrix[indices]), columns=columns)
    frame[TARGET] = meta[TARGET].to_numpy()[indices]
    return frame


def score_three(matrix, meta, indices, columns, tabular, lstm, scaler, spec, device):
    result = meta.loc[indices, ["date", "symbol"]].copy().reset_index(drop=True)
    current = pd.DataFrame(np.asarray(matrix[indices]), columns=columns)
    for backend in ("lightgbm", "catboost"):
        result[f"score_{backend}"] = model_probabilities(tabular[backend], backend, current)
    del current
    result["score_lstm"] = predict(lstm, matrix, indices, scaler, spec, device)
    return result


def evaluate_three(scores, labels, calendar, as_of):
    # Reuse the previously tested generic three-branch calculation, without
    # changing its module/global constants or the old experiment's artifacts.
    adapted = scores.rename(columns={"score_lstm":"score_validation_champion"})
    years, daily, strict, frame = evaluate(adapted, labels, calendar, as_of)
    for y in years.values():
        for key in ("conditional", "strict_original_top"):
            y[key]["lstm"] = y[key].pop("validation_champion")
    strict["backend"] = strict.backend.replace({"validation_champion":"lstm"})
    frame = frame.rename(columns={"score_validation_champion":"score_lstm"})
    return years, daily, strict, frame


def format_report(report):
    lines = ["# Oracle parcours H20 — challenger LSTM", "",
        "Copies tabulaires réentraînées sur les mêmes lignes train/val éligibles aux séquences.",
        "Mêmes labels/folds/features ; représentation LSTM différente (40 séances + masques).", "",
        "| Période | Année | Candidat | TOP titres | Dates complètes / matures | Précision | Amplitude |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |"]
    def pct(v, scale=1):
        return "—" if v is None else f"{v*scale:.2f} %"
    for period in ("historical", "confirmation"):
        for year, result in report[period]["years"].items():
            for backend in CANDIDATES:
                for count, m in result["strict_original_top"][backend].items():
                    lines.append(f"| {period} | {year} | {backend} | {count} | {m['common_complete_dates']} / {m['mature_dates']} | "
                        f"{pct(m['precision'],100)} | {pct(m['mean_path_amplitude_pct'])} |")
    lines += ["", "Précision = TOP20 % réel qualifiable d'amplitude, pas trades gagnants, direction ou PnL.",
        "Population commune restreinte par les séquences ; voir couverture. Labels jamais rerankés après cette restriction.",
        "Séances et fenêtres chevauchantes non indépendantes ; univers survivant / prix ajustés actuels.",
        "Un seul seed, budget LSTM borné : un échec ne condamne pas toutes les architectures.",
        "Aucune sélection ou modification sur 2024–2026, aucun SQL ni ordre, aucune promotion automatique."]
    return "\n".join(lines)+"\n"


def run(history, confirmation, output, spec=SequenceSpec(), device="auto"):
    history, confirmation, output = Path(history), Path(confirmation), Path(output)
    for source in (history, confirmation):
        if output.resolve()==source.resolve() or output.resolve() in source.resolve().parents or source.resolve() in output.resolve().parents:
            raise ValueError("Dossier LSTM séparé des sources requis")
    with exclusive_run(output):
        def progress(phase, info):
            atomic_json(output/"progress.json", dict(status="RUNNING", phase=phase, **info))
            LOGGER.info("LSTM %s %s", phase, info)
        atomic_json(output/"run.json", dict(status="RUNNING", pid=os.getpid()))
        try:
            os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
            torch.set_num_threads(spec.threads)
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True
            torch.use_deterministic_algorithms(True, warn_only=True)
            device = "cuda" if device=="auto" and torch.cuda.is_available() else ("cpu" if device=="auto" else device)
            if device not in ("cuda", "cpu") or (device=="cuda" and not torch.cuda.is_available()):
                raise ValueError("Device LSTM indisponible")
            progress("preflight", dict(device=device))
            root, protocol, profile, originals, cplan, registry, inputs = verify_inputs(history, confirmation)
            frozen = dict(spec=asdict(spec), device=device, history=str(history), confirmation=str(confirmation),
                source_protocol_sha256=digest(root/"protocol.json"), confirmation_plan_sha256=digest(confirmation/"plan.json"),
                feature_columns=profile["feature_columns"], universe=protocol["universe"], input_checkpoints=inputs,
                torch_version=torch.__version__, gpu=torch.cuda.get_device_name(0) if device=="cuda" else None,
                refit_tabular_on_common_rows=True, no_sql=True, no_orders=True, production_changed=False,
                best_epoch_selection="validation_auc_strict_improvement; first_epoch_on_tie",
                source_hashes={n:digest(n) for n in ("modelFactory/model.py", "modelFactory/oracle_path/lstm_research.py",
                    "scripts/research/oracle_path_lstm_comparison.py", "scripts/research/oracle_path_confirmation.py")})
            plan_path = output/"plan.json"
            if plan_path.exists() and json.loads(plan_path.read_text(encoding="utf-8")) != frozen:
                raise ValueError("Plan LSTM différent ; créer un nouveau dossier")
            atomic_json(plan_path, frozen)
            first = protocol["training_config"]["data"]["training_start_date"]
            calendar = nyse_sessions(first, (pd.Timestamp(cplan["as_of"])+pd.Timedelta(days=90)).date())
            meta, matrix = build_cache(root, confirmation, profile, registry, calendar, spec, output, progress)
            hist = meta.loc[meta.period.eq("history") & meta[TARGET].notna(), ["date", "symbol", TARGET, "oracle_available_date"]]
            wf = protocol["training_config"]["walk_forward"]
            folds = build_folds_adaptive(hist, min_train_dates=wf["min_train_size"], val_dates=wf["val_size"],
                test_dates=wf["test_size"], step_dates=wf["step_size"], max_splits=wf["max_splits"],
                forecast_horizon=20, materialize=False)
            if [f["t_start"] for f in folds] != list(originals):
                raise ValueError("Calendrier des folds différent")
            cfg = SimpleNamespace(baseline=BaselineConfig(**protocol["training_config"]["baseline"]),
                reproducibility=SimpleNamespace(seed=protocol["training_config"]["reproducibility"]["seed"]),
                max_workers=protocol["training_config"]["max_workers"])
            targets = meta[TARGET].to_numpy(dtype=np.float32)
            columns = profile["feature_columns"]
            pieces, summaries = [], []
            for number, fold in enumerate(folds):
                folder = output/"folds"/fold["t_start"]
                folder.mkdir(parents=True, exist_ok=True)
                marker = folder/"done.json"
                if marker.exists():
                    saved = json.loads(marker.read_text(encoding="utf-8"))
                    if not all(digest(folder/n)==h for n,h in saved["files"].items()):
                        raise ValueError("Fold LSTM corrompu")
                    pieces.append(pd.read_parquet(folder/"scores.parquet"))
                    summaries.append(saved["summary"])
                    continue
                (train_i, val_i, test_i), coverage = fold_indices(meta, fold, originals[fold["t_start"]]["metrics"])
                if not len(test_i):
                    raise ValueError("Aucune séquence test ; pas de fold supprimé silencieusement")
                train = tabular_frame(matrix, meta, train_i, columns)
                val = tabular_frame(matrix, meta, val_i, columns)
                progress("matched_tabular_fit", dict(fold=fold["t_start"], fold_index=number, total_folds=len(folds), **coverage))
                tabular = {"lightgbm": train_model(train, val, columns, cfg), "catboost": train_catboost(train, val, columns, cfg)}
                tabular["lightgbm"].save_model(str(folder/"matched_lightgbm.txt"))
                tabular["catboost"].save_model(str(folder/"matched_catboost.cbm"))
                del train, val
                def neural_progress(phase, epoch, current, total, detail):
                    progress(phase, epoch_payload(fold["t_start"], number, len(folds), spec, epoch, current, total, detail))
                lstm, scaler, training = fit(matrix, targets, train_i, val_i, spec, folder, device, neural_progress)
                validation_scores = score_three(matrix, meta, val_i, columns, tabular, lstm, scaler, spec, device)
                validation = {b:float(roc_auc(
                    targets[val_i], validation_scores[f"score_{b}"])) for b in CANDIDATES}
                scores = score_three(matrix, meta, test_i, columns, tabular, lstm, scaler, spec, device)
                scores["fold_start"] = fold["t_start"]
                scores.to_parquet(folder/"scores.parquet", index=False)
                summary = dict(fold_start=fold["t_start"], test_end=fold["t_end"], val_start=fold["val_start"],
                    validation_auc=validation, lstm_training=training, coverage=coverage)
                atomic_json(marker, dict(summary=summary, files={n:digest(folder/n) for n in (
                    "matched_lightgbm.txt", "matched_catboost.cbm", "lstm_best.pt", "scaler.json", "best.json", "scores.parquet")}))
                pieces.append(scores)
                summaries.append(summary)
                del tabular, lstm
                if device=="cuda":
                    torch.cuda.empty_cache()
            progress("historical_metrics", dict(completed_folds=len(folds)))
            historical_scores = pd.concat(pieces, ignore_index=True)
            historical_labels = meta.loc[meta.period.eq("history"), ["date", "symbol", TARGET, "path_amplitude"]]
            years, daily, strict, combined = evaluate_three(historical_scores, historical_labels, calendar,
                protocol["training_config"]["data"]["training_end_date"])
            historical_scores.to_parquet(output/"historical_scores.parquet", index=False)
            daily.to_parquet(output/"historical_coverage.parquet", index=False)
            strict.to_parquet(output/"historical_daily_top.parquet", index=False)
            historical_result = dict(years=years, scored_rows=len(historical_scores), dates=int(historical_scores.date.nunique()))
            del pieces, combined
            progress("confirmation_scoring", dict(fold=folds[-1]["t_start"]))
            if folds[-1]["t_start"] != cplan["fixed_fold"]:
                raise ValueError("Fold de confirmation différent de la référence")
            folder = output/"folds"/folds[-1]["t_start"]
            import lightgbm as lgb
            from catboost import CatBoostClassifier
            tabular = {"lightgbm":lgb.Booster(model_file=str(folder/"matched_lightgbm.txt")),
                "catboost":CatBoostClassifier().load_model(str(folder/"matched_catboost.cbm"))}
            from modelFactory.oracle_path.lstm_research import new_model
            lstm = new_model(matrix.shape[1], spec).to(device)
            lstm.load_state_dict(torch.load(folder/"lstm_best.pt", map_location=device, weights_only=True)["weights"])
            scaler = json.loads((folder/"scaler.json").read_text(encoding="utf-8"))
            indices = np.flatnonzero((meta.period.eq("confirmation") & meta.sequence_eligible).to_numpy())
            scores = score_three(matrix, meta, indices, columns, tabular, lstm, scaler, spec, device)
            labels = meta.loc[meta.period.eq("confirmation"), ["date", "symbol", TARGET, "path_amplitude"]]
            years, daily, strict, combined = evaluate_three(scores, labels, calendar, cplan["as_of"])
            scores.to_parquet(output/"confirmation_scores.parquet", index=False)
            daily.to_parquet(output/"confirmation_coverage.parquet", index=False)
            strict.to_parquet(output/"confirmation_daily_top.parquet", index=False)
            original_counts = meta[meta.period.eq("confirmation")].groupby(meta.date.dt.year).size()
            for y, result in years.items():
                result["original_observable_rows"] = int(original_counts.loc[int(y)])
                result["sequence_population_coverage"] = result["scored_rows"]/result["original_observable_rows"]
            report = dict(status="completed", folds=summaries, n_folds=len(folds), spec=asdict(spec), device=device,
                historical=historical_result, confirmation=dict(years=years, as_of=cplan["as_of"], fixed_fold=cplan["fixed_fold"]),
                sequence_exclusions=meta.sequence_reason.value_counts().to_dict(), universe=len(protocol["universe"]),
                n_features=len(columns), refit_tabular_on_common_rows=True, no_sql=True, no_orders=True, promoted=False)
            atomic_json(output/"report.json", report)
            (output/"report.md").write_text(format_report(report), encoding="utf-8")
            atomic_json(output/"run.json", dict(status="COMPLETED", pid=os.getpid(), n_folds=len(folds)))
            atomic_json(output/"progress.json", dict(status="COMPLETED", n_folds=len(folds)))
            LOGGER.info("LSTM comparison completed: %s", output/"report.json")
            return report
        except Exception as exc:
            state = dict(status="FAILED", pid=os.getpid(), error=str(exc))
            atomic_json(output/"run.json", state)
            atomic_json(output/"progress.json", state)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", default="artifacts/research/oracle_path_comparison/20261013-v1")
    parser.add_argument("--confirmation", default="artifacts/research/oracle_path_confirmation/20261013-v1")
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(**vars(args))


if __name__ == "__main__":
    main()
