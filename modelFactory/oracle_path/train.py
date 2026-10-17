"""Independent H20 path-amplitude classifier, causal WF and local artifacts only.

The Model Factory campaign journal is managed by the caller. This module makes
no SQL writes and never uses terminal Oracle labels/predictions/champions.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
import time
from uuid import uuid4

import numpy as np
import pandas as pd

from modelFactory.features import get_feature_columns
from modelFactory.global_ranking import _XS_RANK_SOURCE_FEATURES, _xs_rank_column_name
from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.dataset import build_feature_matrix, deduplicate_oracle_feature_columns
from modelFactory.oracle.security_continuity import load_security_discontinuities
from modelFactory.oracle.train import precision_recall_at_top_pct, roc_auc
from modelFactory.oracle.walk_forward import build_folds_adaptive
from modelFactory.oracle_path import HORIZON, MODE, SCORE, TARGET
from modelFactory.oracle_path.backend import resolve_backend, candidates_for, selection_policy, DECLARATIONS, NAMES
from modelFactory.oracle_path.labels import classify, load_bars, symbol_paths
from modelFactory.runtime_status import update_runtime_status

LOGGER = logging.getLogger(__name__)
CHUNK_SIZE = 25


def digest(path):
    result = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def atomic_json(path, value):
    """Unique sibling temp + bounded retry for Windows readers holding the file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str,
                                        allow_nan=False), encoding="utf-8")
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(.1 * 2 ** attempt)
    finally:
        temporary.unlink(missing_ok=True)


def is_path_batch(artifacts_dir, batch_id):
    root = Path(artifacts_dir)
    return any((candidate / "oracle_path" / "protocol.json").is_file()
               for candidate in (root, root / str(batch_id)))


def format_report(report):
    lines = ["# Oracle Extreme parcours H20", "", "Classifieur d'amplitude séparé, raccordé à predict/backtest/live ; aucune activation de compte automatique.",
             "Cible : TOP20 % de l'amplitude absolue maximale entre J+1 et J+20, depuis le close ajusté J.",
             "Ce score ne donne ni la direction ni un prix de sortie exécutable.", "",
             f"Batch : {report['batch_id']} ; features : {report['n_features']} ; folds : {report['n_folds']}.", "",
             (f"Algorithme imposé : {report['training_backend']}. Aucun choix du modèle sur validation/test."
              if report.get('selection')=='explicit_backend' else
              "Champion par fold : AUC de validation ; égalité exacte → LightGBM. Aucun choix sur le test."), "",
             "| Fold test | Champion | AUC | Précision TOP10 % | Précision TOP20 % | Amplitude moyenne TOP10 % |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    def value(number):
        return "—" if number is None else f"{number:.4f}"
    for fold in report["folds"]:
        lines.append(f"| {fold['fold_start']} | {fold.get('selected_backend', 'lightgbm')} | {value(fold['auc'])} | {value(fold['precision_at_10pct'])} | "
                     f"{value(fold['precision_at_20pct'])} | {value(fold['mean_path_amplitude_top10_pct'])} % |")
    lines.extend(["", "## Comparaison hors échantillon (diagnostic, pas sélection du champion)", "",
                  "| Algorithme | AUC | Précision 10 titres | Amplitude 10 titres | Amplitude 20 titres | Amplitude 50 titres |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for backend, candidate in report.get("comparison_oof", {}).items():
        lines.append(f"| {backend} | {value(candidate['auc'])} | {value(candidate['precision_top_10_titles'])} | "
                     f"{value(candidate['mean_path_amplitude_top_10_titles_pct'])} % | "
                     f"{value(candidate['mean_path_amplitude_top_20_titles_pct'])} % | "
                     f"{value(candidate['mean_path_amplitude_top_50_titles_pct'])} % |")
    lines.extend(["", "Les amplitudes sont des maxima observés a posteriori, pas des gains réalisables.",
                  "Univers de fichier statique : biais de survivance possible. Prix ajustés actuels : pas de garantie PIT des révisions.",
                  "Voir quality.json pour les exclusions et report.json pour la couverture et les métriques complètes."])
    return "\n".join(lines) + "\n"


def restore_ranks(features, options):
    """Never rank each chunk separately or restrict membership to future-good labels."""
    if not options.get("enable_cross_sectional_ranks", True):
        return features
    columns = [c for c in _XS_RANK_SOURCE_FEATURES if c in features]
    ranked = features.groupby("date")[columns].rank(pct=True)
    ranked.columns = [_xs_rank_column_name(c) for c in columns]
    return pd.concat([features, ranked.astype(np.float32)], axis=1)


def feature_columns(features, options, whitelist=None):
    keys = ("include_sentiment", "include_screener_scores", "include_short_score", "include_macro_vix",
            "include_macro_vxn", "include_macro_vix3m", "include_macro_move", "include_fundamentals",
            "include_factors", "include_macro_regime", "include_score_components", "include_volume_features")
    base = get_feature_columns(feature_set=options.get("feature_set", "expert"),
                               **{k: bool(options.get(k, False)) for k in keys})
    candidates = deduplicate_oracle_feature_columns(
        [c for c in base if c in features] + [c for c in features if c.endswith("_xs_rank")])
    if whitelist is not None:
        missing = set(whitelist) - set(candidates)
        if missing:
            raise ValueError(f"Oracle parcours : features demandées indisponibles : {sorted(missing)}")
        candidates = list(dict.fromkeys(whitelist))
    if not candidates:
        raise ValueError("Oracle parcours : aucune feature d'entrée")
    return candidates


def qualify_feature_membership(labels, features):
    """Eligibility is decided using only features at J, before future label ranks.

    New listings without historical warm-up cannot be scored. Their paths remain
    archived but must not distort ranks for the observable scoring population.
    """
    if features.duplicated(["date", "symbol"]).any() or labels.duplicated(["date", "symbol"]).any():
        raise ValueError("Oracle parcours : doublons date/symbol")
    labels = labels.copy()
    labels["feature_eligible"] = pd.MultiIndex.from_frame(labels[["date", "symbol"]]).isin(
        pd.MultiIndex.from_frame(features[["date", "symbol"]]))
    eligible = classify(labels[labels.feature_eligible])
    columns = ["date", "symbol", "daily_count", "daily_coverage", TARGET, "path_amplitude_rank"]
    return labels.merge(eligible[columns], on=["date", "symbol"], how="left", validate="one_to_one")


def metrics(frame):
    result = {"auc": roc_auc(frame[TARGET].to_numpy(), frame[SCORE].to_numpy()),
              "prevalence": float(frame[TARGET].mean()), "rows": len(frame),
              "dates": int(frame.date.nunique())}
    for fraction in (.1, .2):
        label = int(fraction * 100)
        pr = precision_recall_at_top_pct(frame, SCORE, pct=fraction, target_col=TARGET)
        result[f"precision_at_{label}pct"] = pr["precision"]
        result[f"recall_at_{label}pct"] = pr["recall"]
        selected = []
        baseline = []
        for _, group in frame.groupby("date"):
            if len(group) < 20:
                continue
            top = group.sort_values([SCORE, "symbol"], ascending=[False, True]).head(
                max(1, int(np.ceil(len(group) * fraction))))
            selected.append(float(top.path_amplitude.mean()))
            baseline.append(float(group.path_amplitude.mean()))
        result[f"mean_path_amplitude_top{label}_pct"] = 100 * float(np.mean(selected)) if selected else None
        result[f"mean_path_amplitude_universe_pct"] = 100 * float(np.mean(baseline)) if baseline else None
    for count in (10, 20, 50):
        selected = [g.sort_values([SCORE, "symbol"], ascending=[False, True]).head(count)
                    for _, g in frame.groupby("date") if len(g) >= count]
        result[f"precision_top_{count}_titles"] = float(np.mean([g[TARGET].mean() for g in selected])) if selected else None
        result[f"mean_path_amplitude_top_{count}_titles_pct"] = 100 * float(np.mean(
            [g.path_amplitude.mean() for g in selected])) if selected else None
        result[f"dates_top_{count}_titles"] = len(selected)
    return result


def train_model(train, val, columns, cfg):
    """LightGBM early stopping only on chronological validation, never on test."""
    import lightgbm as lgb
    b = cfg.baseline
    params = {"objective": "binary", "metric": "auc", "learning_rate": b.learning_rate,
              "max_depth": b.max_depth, "num_leaves": min(b.lgbm_num_leaves, 2 ** b.max_depth),
              "min_data_in_leaf": b.lgbm_min_child_samples, "lambda_l1": b.lgbm_reg_alpha,
              "lambda_l2": b.lgbm_reg_lambda, "bagging_fraction": b.lgbm_subsample,
              "bagging_freq": 1, "feature_fraction": b.lgbm_colsample_bytree,
              "seed": cfg.reproducibility.seed, "num_threads": cfg.max_workers,
              "verbosity": -1, "device_type": "cpu", "force_col_wise": True}
    training = lgb.Dataset(train[columns], label=train[TARGET].astype(int))
    validation = lgb.Dataset(val[columns], label=val[TARGET].astype(int), reference=training)
    callbacks = [lgb.log_evaluation(50)]
    if b.lgbm_early_stopping_rounds > 0:
        callbacks.append(lgb.early_stopping(b.lgbm_early_stopping_rounds, verbose=False))
    return lgb.train(params, training, num_boost_round=b.n_estimators,
                     valid_sets=[validation], callbacks=callbacks)


def train_catboost(train, val, columns, cfg):
    """Same numerical matrix/target and validation; no ranking loss for this classifier."""
    from catboost import CatBoostClassifier
    b = cfg.baseline
    model = CatBoostClassifier(iterations=b.catboost_iterations, depth=b.catboost_depth,
        learning_rate=b.catboost_learning_rate, l2_leaf_reg=b.catboost_l2_leaf_reg,
        border_count=b.catboost_border_count, random_strength=b.catboost_random_strength,
        bootstrap_type="Bayesian", bagging_temperature=b.catboost_bagging_temperature,
        od_type=b.catboost_od_type, od_wait=b.catboost_od_wait, loss_function="Logloss",
        eval_metric="AUC", random_seed=cfg.reproducibility.seed, thread_count=cfg.max_workers,
        task_type="CPU", allow_writing_files=False, verbose=False)
    model.fit(train[columns], train[TARGET].astype(int),
              eval_set=(val[columns], val[TARGET].astype(int)), use_best_model=True)
    return model


def model_probabilities(model, backend, matrix):
    values = (model.predict_proba(matrix)[:, 1] if backend == "catboost"
              else model.predict(matrix, num_threads=4))
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
        raise ValueError("Oracle parcours : probabilités invalides")
    return values


def select_champion(validation):
    """Frozen validation AUC, exact tie => LightGBM. No test data accepted here."""
    if any(v.get("auc") is None or not np.isfinite(v["auc"]) for v in validation.values()):
        raise ValueError("Oracle parcours : AUC de validation non qualifiée")
    return max(validation, key=lambda name: (validation[name]["auc"], name == "lightgbm"))


def fit_folds(dataset, columns, cfg, root, progress):
    """Checkpoint each complete model/OOS pair; bad/missing artifacts are not reused."""
    wf = cfg.walk_forward
    requested=cfg.oracle_path_backend
    backend_mode=resolve_backend(requested,enable_catboost=cfg.baseline.enable_catboost)
    required=candidates_for(backend_mode)
    selection=selection_policy(requested)
    expected_files={NAMES[b] for b in required}|{'oof.parquet'}
    if wf.step_size < wf.test_size:
        raise ValueError("Oracle parcours : wf step doit être >= wf test (pas de tests OOF dupliqués)")
    folds = build_folds_adaptive(dataset, min_train_dates=wf.min_train_size,
        val_dates=wf.val_size, test_dates=wf.test_size, step_dates=wf.step_size,
        max_splits=wf.max_splits, forecast_horizon=HORIZON, materialize=False)
    if not folds:
        raise ValueError("Oracle parcours : historique insuffisant pour les folds demandés")
    parts, summaries, skipped = [], [], []
    for number, fold in enumerate(folds):
        folder = root / "folds" / str(fold["t_start"])
        folder.mkdir(parents=True, exist_ok=True)
        complete = folder / "done.json"
        if complete.exists():
            saved = json.loads(complete.read_text(encoding="utf-8"))
            if (set(saved.get('validation_candidates',{}))!=set(required)
                    or saved.get('champion',{}).get('selection')!=selection
                    or set(saved.get('files',{}))!=expected_files
                    or (backend_mode!='auto' and saved.get('champion',{}).get('backend')!=backend_mode)
                    or (backend_mode=='auto' and saved.get('champion',{}).get('backend')!=select_champion(saved.get('validation_candidates',{})))):
                raise ValueError('Oracle parcours : checkpoint différent du backend demandé ; nouveau batch requis')
            if all((folder / name).is_file() and digest(folder / name) == checksum
                   for name, checksum in saved["files"].items()):
                parts.append(pd.read_parquet(folder / "oof.parquet"))
                summaries.append(saved["metrics"])
                continue
            raise ValueError(f"Corrupt Oracle parcours fold checkpoint: {folder}")
        train = dataset[dataset.date.isin(fold["train_dates"])
                        & (dataset.oracle_available_date < pd.Timestamp(fold["val_start"]))]
        val = dataset[dataset.date.isin(fold["val_dates"])
                      & (dataset.oracle_available_date < pd.Timestamp(fold["t_start"]))]
        test = dataset[dataset.date.isin(fold["test_dates"])]
        if test.empty or any(frame.empty or frame[TARGET].nunique() < 2 for frame in (train, val)):
            skipped.append({"fold_start": str(fold["t_start"]), "reason": "EMPTY_OR_CONSTANT_TARGET"})
            continue
        progress("training_fold", number, len(folds), str(fold["t_start"]))
        models = {}
        if 'lightgbm' in required:
            models['lightgbm']=train_model(train,val,columns,cfg)
        if 'catboost' in required:
            progress("training_catboost_fold", number, len(folds), str(fold["t_start"]))
            models["catboost"] = train_catboost(train, val, columns, cfg)
        validation = {}
        for backend, model in models.items():
            frame = val[["date", "symbol", TARGET, "path_amplitude"]].copy()
            frame[SCORE] = model_probabilities(model, backend, val[columns])
            validation[backend] = metrics(frame)
        champion = select_champion(validation) if backend_mode=='auto' else backend_mode
        model_files = {"lightgbm": "path_model.txt", "catboost": "catboost_model.cbm"}
        for backend, model in models.items():
            model.save_model(str(folder / model_files[backend]))
        oof = test[["date", "symbol", TARGET, "path_amplitude", "terminal_return",
                    "up_excursion", "down_excursion", "oracle_available_date"]].copy()
        for backend, model in models.items():
            oof[f"score_{backend}"] = model_probabilities(model, backend, test[columns])
        oof[SCORE] = oof[f"score_{champion}"]
        oof["selected_backend"] = champion
        oof["fold_start"] = str(fold["t_start"])
        oof.to_parquet(folder / "oof.parquet", index=False)
        summary = {"fold_start": str(fold["t_start"]), "n_train": len(train), "n_val": len(val),
            "train_available_max": str(train.oracle_available_date.max()),
            "val_start": str(fold["val_start"]), "val_available_max": str(val.oracle_available_date.max()),
            "test_start": str(fold["t_start"]), "test_end": str(fold["t_end"]),
            "selected_backend": champion, "validation_candidates": validation,
            "test_candidates": {backend: metrics(oof.assign(**{SCORE: oof[f"score_{backend}"]}))
                                for backend in models}, **metrics(oof)}
        atomic_json(complete, {"metrics": summary,
            "champion": {"backend": champion, "model_file": model_files[champion],
                         "selection": selection},
            "validation_candidates": validation,
            "files": {name: digest(folder / name) for name in
                      [*(model_files[b] for b in models), "oof.parquet"]}})
        summaries.append(summary)
        parts.append(oof)
        LOGGER.info("Oracle parcours fold terminé : %s", summary)
    if not parts:
        raise ValueError("Oracle parcours : aucun fold OOF valide")
    oof = pd.concat(parts, ignore_index=True)
    if oof.duplicated(["date", "symbol"]).any():
        raise ValueError("Oracle parcours : doublons OOF")
    oof.to_parquet(root / "oof_predictions.parquet", index=False)
    candidates = {backend: metrics(oof.assign(**{SCORE: oof[f"score_{backend}"]}))
                  for backend in ("lightgbm", "catboost") if f"score_{backend}" in oof}
    return {"folds": summaries, "skipped_folds": skipped, "overall": metrics(oof),
            "comparison_oof": candidates, "selection": selection, 'training_backend':backend_mode,
            "n_folds": len(summaries)}


def train_oracle_path(cfg, engine, batch_id, symbols):
    from modelFactory.orchestrator import _oracle_generator_options
    from modelFactory.feature_profiles import load_feature_profile

    root = Path(cfg.artifacts_dir) / "oracle_path"
    if root.parent.exists() and any(child.name != "oracle_path" for child in root.parent.iterdir()):
        raise ValueError("Oracle parcours : dossier de campagne déjà occupé ; aucun artefact existant ne sera remplacé")
    root.mkdir(parents=True, exist_ok=True)
    symbols = sorted({str(s).strip().upper() for s in symbols if str(s).strip()})
    if len(symbols) < 20:
        raise ValueError("Oracle parcours requiert au moins 20 symboles (univers complet recommandé)")
    start, end = str(cfg.data.training_start_date), str(cfg.data.training_end_date)
    if pd.Timestamp(start) >= pd.Timestamp(end) or pd.Timestamp(end) > pd.Timestamp.today().normalize():
        raise ValueError("Oracle parcours : dates invalides/futures")
    profile = load_feature_profile("oracle", cfg.standalone_oracle_feature_profile) if cfg.standalone_oracle_feature_profile else None
    options = _oracle_generator_options(cfg, profile)
    registry = load_security_discontinuities()
    backend=resolve_backend(cfg.oracle_path_backend,enable_catboost=cfg.baseline.enable_catboost)
    training_config=asdict(cfg)
    if cfg.oracle_path_backend is None:
        # Keep the pre-existing legacy protocol fingerprint on resume.
        training_config.pop('oracle_path_backend',None)
    protocol = {"schema_version": 1, "mode": MODE, "batch_id": batch_id, "serving_ready": True,
        "target": TARGET, "score": SCORE, "horizon": HORIZON, "top_fraction": .2,
        "min_daily_coverage": .95, "min_daily_universe": 20, "universe": symbols,
        "training_config": training_config, "generator_options": options, "profile": profile,
        "security_discontinuities": {s: [asdict(e) for e in events] for s, events in registry.items()},
        "price_basis": "adjusted_close_J; adjusted_high_low_J+1..J+20; adj_close_fallback=close; available_J+21",
        "universe_bias": "static_current_file; not historical PIT membership",
        "backend": DECLARATIONS[backend]}
    if backend=='auto':
        protocol.update(champion_selection="validation_auc; exact_tie_lightgbm", catboost_objective="Logloss")
    if cfg.oracle_path_backend is not None:
        protocol.update(training_backend=backend,champion_selection=selection_policy(backend))
        if backend=='catboost':protocol.update(catboost_objective='Logloss')
    fingerprint = sha256(json.dumps(protocol, sort_keys=True, default=str).encode()).hexdigest()
    protocol_path = root / "protocol.json"
    if protocol_path.exists():
        saved = json.loads(protocol_path.read_text(encoding="utf-8"))
        if saved.get("fingerprint") != fingerprint:
            raise ValueError("Oracle parcours : protocole différent ; créer un nouveau batch")
    else:
        atomic_json(protocol_path, {**protocol, "fingerprint": fingerprint})

    def progress(phase, current, total, item):
        atomic_json(root / "progress.json", {"status": "RUNNING", "phase": phase,
                                             "completed": current, "total": total, "item": item})
        update_runtime_status(current_phase=f"oracle_path_{phase}", progress_current=current,
            progress_total=total, progress_item=item, progress_label="Oracle parcours H20")
        LOGGER.info("Oracle parcours %s %d/%d %s", phase, current, total, item)

    try:
        sessions = nyse_sessions(pd.Timestamp(start).date(), (pd.Timestamp(end) + pd.Timedelta(days=90)).date())
        total = int(np.ceil(len(symbols) / CHUNK_SIZE))
        feature_parts, label_parts = [], []
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
                    raise ValueError(f"Corrupt Oracle parcours dataset checkpoint: {folder}")
            else:
                bars = load_bars(engine, chunk, start, end)
                labels, memberships = [], []
                for _, group in bars.groupby("symbol"):
                    paths, membership = symbol_paths(group, sessions, start=start, end=end, registry=registry)
                    labels.append(paths)
                    memberships.append(membership)
                if not labels:
                    raise ValueError(f"Oracle parcours : aucune barre pour la tranche {chunk}")
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
        labels = qualify_feature_membership(pd.concat(label_parts, ignore_index=True), features)
        labels.to_parquet(root / "labels.parquet", index=False)
        quality = {"requested_symbols": len(symbols), "observed_symbols": int(labels.symbol.nunique()),
                   "missing_symbols": sorted(set(symbols) - set(labels.symbol)),
                   "rows": len(labels), "qualified_paths": int(labels.path_qualified.sum()),
                   "feature_ineligible_at_j": int((~labels.feature_eligible).sum()),
                   "eligible_targets": int(labels[TARGET].notna().sum()),
                   "reasons": labels.path_quality_reason.value_counts().to_dict()}
        atomic_json(root / "quality.json", quality)
        del feature_parts, label_parts
        whitelist = profile.get("feature_whitelist") if profile else (
            cfg.data.feature_whitelist if cfg.data.feature_whitelist_enabled else None)
        columns = feature_columns(features, options, whitelist)
        feature_profile={"mode": MODE, "serving_ready": True,
            "feature_columns": columns, "generator_options": options, "target": TARGET}
        if cfg.oracle_path_backend is not None:feature_profile['training_backend']=backend
        atomic_json(root / "feature_profile.json",feature_profile)
        if features.duplicated(["date", "symbol"]).any():
            raise ValueError("Oracle parcours : doublons de features")
        dataset = features[["date", "symbol", *columns]].merge(
            labels.dropna(subset=[TARGET]), on=["date", "symbol"], validate="one_to_one")
        del features, labels
        for col in columns:
            dataset[col] = pd.to_numeric(dataset[col], errors="coerce").replace([np.inf, -np.inf], np.nan).astype(np.float32)
        # Membership at J was frozen before ranking the future targets.
        if len(dataset) != quality["eligible_targets"]:
            raise ValueError("Oracle parcours : features manquantes pour des labels éligibles ; voir quality.json")
        result = fit_folds(dataset, columns, cfg, root, progress)
        report = {"status": "completed", "mode": MODE, "batch_id": batch_id, "serving_ready": True,
                  "artifact_root": str(root), "quality": quality, "n_features": len(columns), **result}
        atomic_json(root / "report.json", report)
        (root / "report.md").write_text(format_report(report), encoding="utf-8")
        atomic_json(root / "progress.json", {"status": "COMPLETED", "n_folds": result["n_folds"]})
        return report
    except Exception as exc:
        atomic_json(root / "progress.json", {"status": "FAILED", "error": str(exc)})
        raise
