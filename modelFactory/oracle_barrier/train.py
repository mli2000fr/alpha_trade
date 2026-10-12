"""Separate two-head TP-before-SL research training. Read-only price/feature SQL.

Shared path utilities are used only for feature construction, hashing and the
binary LightGBM fit. No terminal/path labels, predictions or champions are reused.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.dataset import build_feature_matrix
from modelFactory.oracle.security_continuity import load_security_discontinuities
from modelFactory.oracle.train import roc_auc
from modelFactory.oracle.walk_forward import build_folds_adaptive
from modelFactory.oracle_path import TARGET as FIT_TARGET
from modelFactory.oracle_path.train import (atomic_json, digest, restore_ranks, feature_columns,
                                            train_model as _fit_binary)
from modelFactory.runtime_status import update_runtime_status
from . import MODE, TARGETS, SCORES, ANY_TARGET, ANY_SCORE
from .labels import load_bars, symbol_barriers

LOGGER = logging.getLogger(__name__)
CHUNK_SIZE = 25


def is_barrier_batch(artifacts_dir, batch_id):
    root = Path(artifacts_dir)
    return any((candidate / "oracle_barrier" / "protocol.json").is_file()
               for candidate in (root, root / str(batch_id)))


def train_model(train, val, columns, cfg, target):
    return _fit_binary(train.rename(columns={target: FIT_TARGET}),
                       val.rename(columns={target: FIT_TARGET}), columns, cfg)


def metrics(frame, target, score):
    evaluated = frame.dropna(subset=[target, score])
    result = {"scored_rows": int(frame[score].notna().sum()), "evaluated_rows": len(evaluated),
        "excluded_labels": int((frame[score].notna() & frame[target].isna()).sum()),
        "auc": roc_auc(evaluated[target].to_numpy(), evaluated[score].to_numpy()) if len(evaluated) else None,
        "prevalence": float(evaluated[target].mean()) if len(evaluated) else None}
    # Select BEFORE filtering future unknown outcomes: do not replace missing labels
    # with lower-ranked known symbols. Report selected/evaluated coverage separately.
    for fraction in (.1, .2):
        selected = []
        for _, group in frame.dropna(subset=[score]).groupby("date"):
            top = group.sort_values([score, "symbol"], ascending=[False, True]).head(
                max(1, int(np.ceil(len(group) * fraction))))
            selected.append(top)
        top = pd.concat(selected, ignore_index=True) if selected else frame.iloc[:0]
        known = top.dropna(subset=[target])
        key = int(fraction * 100)
        result[f"precision_at_{key}pct"] = float(known[target].mean()) if len(known) else None
        result[f"selected_at_{key}pct"] = len(top)
        result[f"evaluated_at_{key}pct"] = len(known)
    return result


def all_metrics(frame):
    return {side: metrics(frame, target, SCORES[side]) for side, target in TARGETS.items()} | {
        "either": metrics(frame, ANY_TARGET, ANY_SCORE)}


def annotate_direction(frame, threshold):
    """Independent scores need not sum to one. Ties and low scores abstain.

    This rule is frozen before OOF evaluation, never adjusted on test outcomes.
    The model learns barrier success, not terminal return sign or D1/D10 deciles.
    """
    frame = frame.copy()
    both = frame[list(SCORES.values())].notna().all(axis=1)
    frame[ANY_SCORE] = frame[list(SCORES.values())].max(axis=1).where(both)
    difference = frame[SCORES["long"]] - frame[SCORES["short"]]
    known = both & difference.abs().gt(1e-12) & frame[ANY_SCORE].ge(threshold)
    frame["research_direction"] = np.where(known, np.where(difference > 0, "LONG", "SHORT"), "ABSTAIN")
    for suffix in ("tp_before_sl", "gross_return"):
        frame[f"chosen_{suffix}"] = np.where(frame.research_direction.eq("LONG"), frame[f"long_{suffix}"],
            np.where(frame.research_direction.eq("SHORT"), frame[f"short_{suffix}"], np.nan))
    return frame


def direction_metrics(frame):
    selected = frame[frame.research_direction.ne("ABSTAIN")]
    evaluated = selected.dropna(subset=["chosen_tp_before_sl"])
    # Constant-side baselines on the SAME qualified observations, not different samples.
    paired = evaluated.dropna(subset=list(TARGETS.values()))
    return {"rows": len(frame), "abstentions": int(frame.research_direction.eq("ABSTAIN").sum()),
        "long_selected": int(frame.research_direction.eq("LONG").sum()),
        "short_selected": int(frame.research_direction.eq("SHORT").sum()), "evaluated": len(evaluated),
        "selected_unknown_outcomes": len(selected) - len(evaluated),
        "chosen_tp_rate": float(evaluated.chosen_tp_before_sl.mean()) if len(evaluated) else None,
        "paired_evaluated": len(paired),
        "paired_chosen_tp_rate": float(paired.chosen_tp_before_sl.mean()) if len(paired) else None,
        "paired_always_long_tp_rate": float(paired[TARGETS["long"]].mean()) if len(paired) else None,
        "paired_always_short_tp_rate": float(paired[TARGETS["short"]].mean()) if len(paired) else None}


def fit_folds(dataset, columns, cfg, root, progress):
    wf = cfg.walk_forward
    folds = build_folds_adaptive(dataset, min_train_dates=wf.min_train_size,
        val_dates=wf.val_size, test_dates=wf.test_size, step_dates=wf.step_size,
        max_splits=wf.max_splits, forecast_horizon=cfg.oracle_barrier.max_sessions + 2, materialize=False)
    if not folds:
        raise ValueError("Oracle TP avant SL : historique insuffisant pour les folds")
    parts, summaries = [], []
    for number, fold in enumerate(folds):
        folder = root / "folds" / str(fold["t_start"])
        folder.mkdir(parents=True, exist_ok=True)
        marker = folder / "done.json"
        if marker.exists():
            saved = json.loads(marker.read_text(encoding="utf-8"))
            if not all((folder / name).is_file() and digest(folder / name) == checksum
                       for name, checksum in saved["files"].items()):
                raise ValueError(f"Corrupt Oracle barrier fold checkpoint: {folder}")
            parts.append(pd.read_parquet(folder / "oof.parquet"))
            summaries.append(saved["metrics"])
            continue
        train = dataset[dataset.date.isin(fold["train_dates"])
                        & (dataset.oracle_available_date < pd.Timestamp(fold["val_start"]))]
        val = dataset[dataset.date.isin(fold["val_dates"])
                      & (dataset.oracle_available_date < pd.Timestamp(fold["t_start"]))]
        test = dataset[dataset.date.isin(fold["test_dates"])]
        oof = test.drop(columns=columns).copy()
        progress("training_fold", number, len(folds), str(fold["t_start"]))
        files, states = [], {}
        for side, target in TARGETS.items():
            a, b = train.dropna(subset=[target]), val.dropna(subset=[target])
            oof[SCORES[side]] = np.nan
            if any(frame.empty or frame[target].nunique() < 2 for frame in (a, b)):
                states[side] = {"status": "SKIPPED", "reason": "EMPTY_OR_CONSTANT_TRAIN_VALIDATION"}
                continue
            model = train_model(a, b, columns, cfg, target)
            oof[SCORES[side]] = model.predict(test[columns])
            if not np.isfinite(oof[SCORES[side]]).all():
                raise ValueError("Oracle TP avant SL : scores non finis")
            name = f"{side}_model.txt"
            model.save_model(str(folder / name))
            files.append(name)
            states[side] = {"status": "TRAINED", "n_train": len(a), "n_val": len(b),
                "train_available_max": str(a.oracle_available_date.max()),
                "val_available_max": str(b.oracle_available_date.max())}
        # Both scores required; do not hide an absent head with max(skipna=True).
        oof = annotate_direction(oof, cfg.data.decision_threshold)
        oof["fold_start"] = str(fold["t_start"])
        oof.to_parquet(folder / "oof.parquet", index=False)
        files.append("oof.parquet")
        summary = {"fold_start": str(fold["t_start"]), "val_start": str(fold["val_start"]),
            "test_end": str(fold["t_end"]), "heads": states, "metrics": all_metrics(oof),
            "direction": direction_metrics(oof)}
        atomic_json(marker, {"metrics": summary, "files": {name: digest(folder / name) for name in files}})
        summaries.append(summary)
        parts.append(oof)
        LOGGER.info("Oracle TP avant SL fold terminé : %s", summary)
    oof = pd.concat(parts, ignore_index=True)
    if oof.duplicated(["date", "symbol"]).any():
        raise ValueError("Oracle TP avant SL : doublons OOF")
    if not oof[ANY_SCORE].notna().any():
        raise ValueError("Oracle TP avant SL : aucun fold avec deux modèles LONG/SHORT valides")
    oof.to_parquet(root / "oof_predictions.parquet", index=False)
    return {"folds": summaries, "n_folds": len(summaries), "overall": all_metrics(oof),
            "direction": direction_metrics(oof)}


def format_report(report):
    c = report["barriers"]
    lines = ["# Oracle TP avant SL — recherche", "",
        f"TP {100*c['take_profit_pct']:g} %, SL {100*c['stop_loss_pct']:g} %, {c['max_sessions']} séances.",
        "Entrée J+1 open ; expiration à l'ouverture suivante après les séances de détention.",
        "Deux modèles séparés LONG et SHORT. SL et expiration = cible 0 ; TP avant SL = 1.",
        "L'ordre inconnu intrabar exclut la cible concernée ; aucun ordre broker ni PnL portefeuille.", "",
        "| Sens | AUC OOF | Taux TP univers | Précision TOP10 % | Évalués / sélectionnés TOP10 % |",
        "| --- | ---: | ---: | ---: | ---: |"]
    def value(number):
        return "—" if number is None else f"{number:.4f}"
    for side, m in report["overall"].items():
        lines.append(f"| {side} | {value(m['auc'])} | {value(m['prevalence'])} | "
                     f"{value(m['precision_at_10pct'])} | {m['evaluated_at_10pct']} / {m['selected_at_10pct']} |")
    lines.extend(["", "either est classé par le maximum des deux scores, pas une probabilité calibrée d'union.",
        f"Direction hors échantillon : {report['direction']['long_selected']} LONG, "
        f"{report['direction']['short_selected']} SHORT, {report['direction']['abstentions']} abstentions ; "
        f"taux TP des directions qualifiées : {value(report['direction']['chosen_tp_rate'])}.",
        "Comparer aux baselines toujours LONG/SHORT sur les mêmes observations dans report.json/direction.",
        "Les métriques utilisent les labels qualifiés ; voir quality.json et les exclusions pour la couverture.",
        "Prix ajustés actuels et univers statique : limites PIT/survivance. Les features conservent leurs limites de lineage.",
        "SHORT hypothétique : emprunt/disponibilité/coûts/fills non qualifiés. Aucun gain net démontré.",
        "Pas de trailing ni de TP/SL optimisé sur le test ; modèles non promus PAPER/LIVE."])
    return "\n".join(lines) + "\n"


def train_oracle_barrier(cfg, engine, batch_id, symbols):
    from modelFactory.orchestrator import _oracle_generator_options
    from modelFactory.feature_profiles import load_feature_profile

    root = Path(cfg.artifacts_dir) / "oracle_barrier"
    if root.parent.exists() and any(child.name != "oracle_barrier" for child in root.parent.iterdir()):
        raise ValueError("Oracle TP avant SL : campagne occupée ; aucun artefact existant remplacé")
    root.mkdir(parents=True, exist_ok=True)
    symbols = sorted({str(s).strip().upper() for s in symbols if str(s).strip()})
    if len(symbols) < 20:
        raise ValueError("Oracle TP avant SL requiert au moins 20 symboles")
    start, end = str(cfg.data.training_start_date), str(cfg.data.training_end_date)
    if pd.Timestamp(start) >= pd.Timestamp(end) or pd.Timestamp(end) > pd.Timestamp.today().normalize():
        raise ValueError("Oracle TP avant SL : dates invalides/futures")
    profile = load_feature_profile("oracle", cfg.standalone_oracle_feature_profile) if cfg.standalone_oracle_feature_profile else None
    options = _oracle_generator_options(cfg, profile)
    registry = load_security_discontinuities()
    protocol = {"schema_version": 1, "mode": MODE, "batch_id": batch_id, "serving_ready": False,
        "targets": TARGETS, "scores": SCORES, "barriers": asdict(cfg.oracle_barrier), "universe": symbols,
        "training_config": asdict(cfg), "generator_options": options, "profile": profile,
        "security_discontinuities": {s: [asdict(e) for e in events] for s, events in registry.items()},
        "entry": "J+1 adjusted open", "holding": "entry=session1; H sessions; time exit J+H+1 open",
        "availability": "J+H+2 for all outcomes", "ambiguous_daily_order": "exclude_side_target",
        "research_direction": {"min_score": cfg.data.decision_threshold, "rule": "larger_score; ties_abstain",
                               "score_calibration": "none; not normalized between sides"},
        "gap": "open before intrabar; hypothetical execution at gap open", "trailing": False,
        "price_basis": "current adj_close/close factor; fallback raw when adj_close absent; not revision-PIT",
        "universe_bias": "static_current_file; not historical PIT membership", "backend": "lightgbm_cpu"}
    fingerprint = sha256(json.dumps(protocol, sort_keys=True, default=str).encode()).hexdigest()
    protocol_path = root / "protocol.json"
    if protocol_path.exists():
        if json.loads(protocol_path.read_text(encoding="utf-8")).get("fingerprint") != fingerprint:
            raise ValueError("Oracle TP avant SL : protocole différent ; créer un nouveau batch")
    else:
        atomic_json(protocol_path, {**protocol, "fingerprint": fingerprint})

    def progress(phase, current, total, item):
        atomic_json(root / "progress.json", {"status": "RUNNING", "phase": phase,
            "completed": current, "total": total, "item": item})
        update_runtime_status(current_phase=f"oracle_barrier_{phase}", progress_current=current,
            progress_total=total, progress_item=item, progress_label="Oracle TP avant SL")
        LOGGER.info("Oracle TP avant SL %s %d/%d %s", phase, current, total, item)

    try:
        sessions = nyse_sessions(pd.Timestamp(start).date(), (pd.Timestamp(end) + pd.Timedelta(days=180)).date())
        feature_parts, label_parts = [], []
        total = int(np.ceil(len(symbols) / CHUNK_SIZE))
        for number, offset in enumerate(range(0, len(symbols), CHUNK_SIZE)):
            chunk = symbols[offset:offset + CHUNK_SIZE]
            folder = root / "chunks" / f"{number:04d}"
            folder.mkdir(parents=True, exist_ok=True)
            marker = folder / "done.json"
            progress("dataset", number, total, ",".join(chunk))
            if marker.exists():
                saved = json.loads(marker.read_text(encoding="utf-8"))
                if not all((folder / name).is_file() and digest(folder / name) == checksum
                           for name, checksum in saved["files"].items()):
                    raise ValueError(f"Corrupt Oracle barrier dataset checkpoint: {folder}")
            else:
                bars = load_bars(engine, chunk, start, end)
                labels, memberships = [], []
                for _, group in bars.groupby("symbol"):
                    paths, membership = symbol_barriers(group, sessions, start=start, end=end,
                                                        registry=registry, config=cfg.oracle_barrier)
                    labels.append(paths)
                    memberships.append(membership)
                if not labels:
                    raise ValueError(f"Oracle TP avant SL : aucune barre pour {chunk}")
                labels = pd.concat(labels, ignore_index=True)
                membership = pd.concat(memberships, ignore_index=True)
                features = build_feature_matrix(engine, chunk, start_date=start, end_date=end,
                    generator_options={**options, "enable_cross_sectional_ranks": False}, membership=membership)
                for col in features.select_dtypes(include=["float64"]).columns:
                    features[col] = features[col].astype(np.float32)
                bars.to_parquet(folder / "bars.parquet", index=False)
                labels.to_parquet(folder / "labels.parquet", index=False)
                features.to_parquet(folder / "features.parquet", index=False)
                atomic_json(marker, {"symbols": chunk, "files": {name: digest(folder / name)
                    for name in ("bars.parquet", "labels.parquet", "features.parquet")}})
            feature_parts.append(pd.read_parquet(folder / "features.parquet"))
            label_parts.append(pd.read_parquet(folder / "labels.parquet"))
        features = restore_ranks(pd.concat(feature_parts, ignore_index=True), options)
        labels = pd.concat(label_parts, ignore_index=True)
        if labels.duplicated(["date", "symbol"]).any() or features.duplicated(["date", "symbol"]).any():
            raise ValueError("Oracle TP avant SL : doublons date/symbol")
        labels["feature_eligible"] = pd.MultiIndex.from_frame(labels[["date", "symbol"]]).isin(
            pd.MultiIndex.from_frame(features[["date", "symbol"]]))
        labels.to_parquet(root / "labels.parquet", index=False)
        quality = {"requested_symbols": len(symbols), "observed_symbols": int(labels.symbol.nunique()),
            "missing_symbols": sorted(set(symbols) - set(labels.symbol)), "rows": len(labels),
            "qualified_paths": int(labels.path_qualified.sum()), "feature_ineligible_at_j": int((~labels.feature_eligible).sum()),
            "reasons": labels.path_quality_reason.value_counts().to_dict(),
            "outcomes": {side: labels[f"{side}_outcome"].value_counts().to_dict() for side in TARGETS}}
        atomic_json(root / "quality.json", quality)
        whitelist = profile.get("feature_whitelist") if profile else (
            cfg.data.feature_whitelist if cfg.data.feature_whitelist_enabled else None)
        columns = feature_columns(features, options, whitelist)
        atomic_json(root / "feature_profile.json", {"mode": MODE, "serving_ready": False,
            "feature_columns": columns, "generator_options": options, "targets": TARGETS})
        # Preserve every observable J candidate, including future ambiguous/missing paths.
        dataset = features[["date", "symbol", *columns]].merge(labels, on=["date", "symbol"], validate="one_to_one")
        for col in columns:
            dataset[col] = pd.to_numeric(dataset[col], errors="coerce").replace([np.inf, -np.inf], np.nan).astype(np.float32)
        del features, labels, feature_parts, label_parts
        result = fit_folds(dataset, columns, cfg, root, progress)
        report = {"status": "completed", "mode": MODE, "batch_id": batch_id, "serving_ready": False,
            "artifact_root": str(root), "barriers": asdict(cfg.oracle_barrier), "quality": quality,
            "n_features": len(columns), **result}
        atomic_json(root / "report.json", report)
        (root / "report.md").write_text(format_report(report), encoding="utf-8")
        atomic_json(root / "progress.json", {"status": "COMPLETED", "n_folds": result["n_folds"]})
        return report
    except Exception as exc:
        atomic_json(root / "progress.json", {"status": "FAILED", "error": str(exc)})
        raise
