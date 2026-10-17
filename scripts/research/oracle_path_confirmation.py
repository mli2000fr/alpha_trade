"""Frozen path-Oracle confirmation 2024-2026; read-only SQL, no training/orders.

Scores are archived for the observable population BEFORE future label exclusions.
Both the historical conditional metric and strict original TOP-K coverage are
reported; missing outcomes never cause a replacement by the next-ranked symbol.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import argparse
import json
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, event, text

from modelFactory.oracle.build_labels import _get_nyse_calendar, nyse_sessions
from modelFactory.oracle.dataset import build_feature_matrix
from modelFactory.oracle.security_continuity import load_security_discontinuities
from modelFactory.oracle_path import HORIZON, SCORE, TARGET
from modelFactory.oracle_path.labels import load_bars, symbol_paths
from modelFactory.oracle_path.predict import load_contract, select_fold
from modelFactory.oracle_path.train import (atomic_json, digest, metrics, model_probabilities,
    qualify_feature_membership, restore_ranks)

LOGGER = logging.getLogger(__name__)
BACKENDS = ("lightgbm", "catboost", "validation_champion")
CHUNK_SIZE = 25


@contextmanager
def exclusive_run(output):
    """OS-held lock released on exit/crash, without stale PID guessing."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    handle = (output/"run.lock").open("a+b")
    try:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise RuntimeError("Une confirmation utilise déjà ce dossier") from exc
    try:
        yield
    finally:
        handle.seek(0)
        if os.name == "nt":
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def completed_session(now=None):
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    if now.tzinfo is None:
        raise ValueError("Timezone requise pour la clôture NYSE")
    calendar = _get_nyse_calendar()
    if calendar is None:
        raise ValueError("Calendrier NYSE indisponible")
    schedule = calendar.schedule(start_date=(now-pd.Timedelta(days=30)).date(), end_date=now.date())
    closed = schedule.loc[pd.to_datetime(schedule.market_close, utc=True).le(now.tz_convert("UTC"))]
    if closed.empty:
        raise ValueError("Aucune séance US clôturée")
    return pd.Timestamp(closed.index[-1]).tz_localize(None).normalize()


def resolve_window(engine, universe, start, end=None, as_of=None):
    closed = completed_session()
    query = text("SELECT MAX(`date`) FROM stock_bars_daily WHERE symbol IN :symbols AND `date`<=:closed").bindparams(
        bindparam("symbols", expanding=True))
    with engine.connect() as conn:
        latest = conn.execute(query, {"symbols": universe, "closed": closed.date()}).scalar()
    if latest is None:
        raise ValueError("Aucune barre pour l'univers figé")
    limit = min(pd.Timestamp(latest).normalize(), closed)
    as_of = pd.Timestamp(as_of).normalize() if as_of else limit
    end = pd.Timestamp(end).normalize() if end else as_of
    start = pd.Timestamp(start).normalize()
    if start > end or end > as_of or as_of > limit:
        raise ValueError("Dates invalides : décision <= as-of <= dernière barre/séance clôturée")
    return start, end, as_of


def load_candidates(root, folder_name, columns):
    """Both original weights, no fit, no calibration and no test-based choice."""
    folder = root/"folds"/folder_name
    done = json.loads((folder/"done.json").read_text(encoding="utf-8"))
    expected = {"lightgbm": "path_model.txt", "catboost": "catboost_model.cbm"}
    models, hashes = {}, {}
    for backend, filename in expected.items():
        checksum = done.get("files", {}).get(filename)
        if not checksum or digest(folder/filename) != checksum:
            raise ValueError("Deux candidats originaux intacts requis")
        if backend == "lightgbm":
            import lightgbm as lgb
            model = lgb.Booster(model_file=str(folder/filename))
            names = model.feature_name()
        else:
            from catboost import CatBoostClassifier
            model = CatBoostClassifier().load_model(str(folder/filename))
            names = model.feature_names_
        if names != columns:
            raise ValueError("Ordre des features du candidat incompatible")
        models[backend], hashes[backend] = model, checksum
    return models, hashes


def score_population(features, columns, models, champion):
    if features.duplicated(["date", "symbol"]).any() or set(columns)-set(features):
        raise ValueError("Features absentes ou clés dupliquées")
    matrix = features[columns].replace([np.inf, -np.inf], np.nan).astype(np.float32)
    if matrix.isna().all(axis=1).any():
        raise ValueError("Ligne de features entièrement absente")
    scores = features[["date", "symbol"]].copy()
    for backend in ("lightgbm", "catboost"):
        scores[f"score_{backend}"] = model_probabilities(models[backend], backend, matrix)
    scores["score_validation_champion"] = scores[f"score_{champion}"]
    return scores


def evaluate(scores, labels, sessions, as_of):
    """Daily coverage + year reports, with explicit conditional vs original ranks."""
    if scores.duplicated(["date", "symbol"]).any() or labels.duplicated(["date", "symbol"]).any():
        raise ValueError("Doublons dans l'évaluation")
    calendar = pd.DatetimeIndex(sessions)
    maturity = dict(zip(calendar[:-HORIZON-1], calendar[HORIZON+1:]))
    frame = scores.merge(labels, on=["date", "symbol"], how="left", validate="one_to_one")
    frame["expected_available_date"] = frame.date.map(maturity)
    if frame.expected_available_date.isna().any():
        raise ValueError("Calendrier de maturité incomplet")
    records, daily = [], []
    for day, group in frame.groupby("date", sort=True):
        immature = group.expected_available_date.iloc[0] > pd.Timestamp(as_of)
        usable = group[TARGET].notna()
        row = dict(date=str(pd.Timestamp(day).date()), year=int(pd.Timestamp(day).year),
            available_date=str(pd.Timestamp(group.expected_available_date.iloc[0]).date()),
            scored=len(group), labelled=int(usable.sum()), missing=int((~usable).sum()),
            status="IMMATURE" if immature else ("QUALIFIED" if usable.any() else "NO_QUALIFIED_TARGET"))
        row["conditional_metrics_allowed"] = not immature and bool(usable.any())
        for count in (10, 20, 50):
            selections = {backend: group.sort_values([f"score_{backend}", "symbol"],
                ascending=[False, True]).head(count) for backend in BACKENDS}
            # A paired metric only compares the same dates and complete original selections.
            common = (not immature and all(len(g) == count and g[TARGET].notna().all()
                                          for g in selections.values()))
            row[f"paired_complete_top{count}"] = bool(common)
            for backend, top in selections.items():
                known = top[TARGET].notna()
                record = dict(date=row["date"], year=row["year"], backend=backend, count=count,
                    scored=len(group), selected=len(top), missing=int((~known).sum()),
                    immature=bool(immature), paired_complete=bool(common),
                    precision=float(top[TARGET].mean()) if common else None,
                    mean_path_amplitude_pct=100*float(top.path_amplitude.mean()) if common else None,
                    # Bounds describe only missing outcomes within a qualified target day.
                    precision_lower_bound=float(top[TARGET].fillna(0).sum()/count) if not immature and usable.any() and len(top)==count else None,
                    precision_upper_bound=float((top[TARGET].fillna(0).sum()+(~known).sum())/count) if not immature and usable.any() and len(top)==count else None)
                records.append(record)
        daily.append(row)
    daily = pd.DataFrame(daily)
    strict = pd.DataFrame(records)
    yearly = {}
    for year, group in frame.groupby(frame.date.dt.year):
        d = daily[daily.year.eq(year)]
        eligible = group.loc[group[TARGET].notna() & group.expected_available_date.le(pd.Timestamp(as_of))]
        result = dict(scored_dates=len(d), scored_rows=len(group), evaluated_dates=int(eligible.date.nunique()),
            evaluated_rows=len(eligible), immature_dates=int(d.status.eq("IMMATURE").sum()),
            mature_unqualified_dates=int(d.status.eq("NO_QUALIFIED_TARGET").sum()),
            evaluation_start=str(eligible.date.min().date()) if not eligible.empty else None,
            evaluation_end=str(eligible.date.max().date()) if not eligible.empty else None,
            status="EVALUABLE" if not eligible.empty else "BLOCKED_COVERAGE", conditional={}, strict_original_top={})
        for backend in BACKENDS:
            # Exactly the old metric population: qualified labels only, explicitly conditional.
            result["conditional"][backend] = metrics(eligible.assign(**{SCORE: eligible[f"score_{backend}"]})) if not eligible.empty else None
            result["strict_original_top"][backend] = {}
            for count in (10, 20, 50):
                sub = strict[strict.year.eq(year) & strict.backend.eq(backend) & strict["count"].eq(count)]
                complete = sub[sub.paired_complete]
                mature = sub[~sub.immature]
                result["strict_original_top"][backend][str(count)] = dict(
                    common_complete_dates=len(complete), mature_dates=len(mature),
                    coverage=float(len(complete)/len(mature)) if len(mature) else None,
                    precision=float(complete.precision.mean()) if not complete.empty else None,
                    mean_path_amplitude_pct=float(complete.mean_path_amplitude_pct.mean()) if not complete.empty else None,
                    missing_selected_outcomes=int(mature.missing.sum()))
        yearly[str(int(year))] = result
    return yearly, daily, strict, frame


def report_markdown(report):
    lines = ["# Confirmation Oracle parcours — modèles figés", "",
        f"État : {report['status']} ; fold : {report['fixed_fold']} ; as-of : {report['as_of']}.",
        f"Champion déjà choisi : {report['validation_champion']}. Aucun réentraînement / SQL / ordre.", "",
        "Les mesures primaires TOP-K utilisent les sélections avant exclusion des résultats manquants,",
        "sur les mêmes dates complètes pour tous les candidats. Voir les couvertures et métriques conditionnelles dans report.json.", "",
        "| Année | Candidat | TOP titres | Dates complètes / matures | Précision | Amplitude absolue moyenne |",
        "| --- | --- | ---: | ---: | ---: | ---: |"]
    def pct(value):
        return "—" if value is None else f"{value:.2f} %"
    for year, result in report["years"].items():
        for backend in BACKENDS:
            for count, m in result["strict_original_top"].get(backend, {}).items():
                lines.append(f"| {year} | {backend} | {count} | {m['common_complete_dates']} / {m['mature_dates']} | "
                    f"{pct(None if m['precision'] is None else 100*m['precision'])} | {pct(m['mean_path_amplitude_pct'])} |")
    lines += ["", "Précision = vrai TOP20 % d'amplitude qualifiable, pas gain/direction ni TP atteint.",
        "Amplitudes haut/bas a posteriori, non encaissables. Pas de replay économique.",
        "Univers actuel statique, prix ajustés présents, PIT des sources optionnelles non certifié.",
        "Années déjà étudiées auparavant : confirmation temporelle, pas holdout entièrement vierge.",
        "Aucun champion n'est rechoisi sur ces résultats ; les modèles n'ont pas appris toute l'année 2023."]
    return "\n".join(lines)+"\n"


def run(engine, source, output, start="2024-01-01", end=None, as_of=None):
    output, source = Path(output), Path(source)
    if output.resolve() == source.resolve() or output.resolve() in source.resolve().parents or source.resolve() in output.resolve().parents:
        raise ValueError("Confirmation dans un dossier séparé de la source")
    with exclusive_run(output):
        atomic_json(output/"run.json", dict(status="RUNNING", pid=os.getpid(), phase="preflight"))
        try:
            root, protocol, profile, folds = load_contract(source/"models", "oracle-path-comparison")
            if protocol.get("backend") != "lightgbm_catboost_cpu":
                raise ValueError("Comparaison LightGBM/CatBoost figée requise")
            if getattr(engine.url, "database", None) != "alpha_trade":
                raise ValueError("Base US alpha_trade requise")
            original = json.loads((source/"plan.json").read_text(encoding="utf-8"))
            if any(digest(name) != checksum for name, checksum in original["source_hashes"].items()):
                raise ValueError("Sources originales modifiées ; qualifier avant confirmation")
            registry = load_security_discontinuities()
            from dataclasses import asdict
            normal = json.loads(json.dumps({s: [asdict(e) for e in events] for s, events in registry.items()}, default=str))
            if normal != protocol["security_discontinuities"]:
                raise ValueError("Registre des identités différent du protocole original")
            plan_path = output/"plan.json"
            old = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else {}
            start, end, as_of = resolve_window(engine, protocol["universe"], start,
                end or old.get("end"), as_of or old.get("as_of"))
            if start <= pd.Timestamp(protocol["training_config"]["data"]["training_end_date"]):
                raise ValueError("Confirmation après la borne de training uniquement")
            fixed_fold = select_fold(start, folds)
            if select_fold(end, folds) != fixed_fold:
                raise ValueError("Protocole de modèles fixes : plusieurs folds sélectionnés")
            models, model_hashes = load_candidates(root, fixed_fold, profile["feature_columns"])
            champion = folds[fixed_fold]["backend"]
            frozen = dict(schema_version=1, start=str(start.date()), end=str(end.date()), as_of=str(as_of.date()),
                source=str(source), source_protocol_sha256=digest(root/"protocol.json"),
                feature_profile_sha256=digest(root/"feature_profile.json"), universe=protocol["universe"],
                fixed_fold=fixed_fold, validation_champion=champion, model_hashes=model_hashes,
                train_available_max=folds[fixed_fold]["metrics"]["train_available_max"],
                val_available_max=folds[fixed_fold]["metrics"]["val_available_max"],
                source_code_sha256=digest(__file__), original_source_hashes=original["source_hashes"],
                no_training=True, no_sql_writes=True, no_orders=True, target=TARGET, horizon=HORIZON,
                metric_population="conditional_same_as_original + paired_original_TOPK_before_future_exclusions")
            if old and old != frozen:
                raise ValueError("Protocole de confirmation différent ; créer un autre dossier")
            atomic_json(plan_path, frozen)
            calendar = nyse_sessions(start.date(), (as_of+pd.Timedelta(days=90)).date())
            decision_days = calendar[calendar <= end]
            features_parts, labels_parts = [], []
            universe = protocol["universe"]
            total = int(np.ceil(len(universe)/CHUNK_SIZE))
            for number, offset in enumerate(range(0, len(universe), CHUNK_SIZE)):
                chunk = universe[offset:offset+CHUNK_SIZE]
                atomic_json(output/"progress.json", dict(status="RUNNING", phase="dataset", completed=number,
                    total=total, symbols=chunk, fixed_fold=fixed_fold, as_of=str(as_of.date())))
                LOGGER.info("Confirmation dataset %d/%d %s", number, total, ",".join(chunk))
                folder = output/"chunks"/f"{number:04d}"
                folder.mkdir(parents=True, exist_ok=True)
                marker = folder/"done.json"
                if marker.exists():
                    saved = json.loads(marker.read_text(encoding="utf-8"))
                    if saved.get("symbols") != chunk or not all((folder/n).is_file() and digest(folder/n)==h
                        for n, h in saved["files"].items()):
                        raise ValueError(f"Checkpoint corrompu : {folder}")
                else:
                    bars = load_bars(engine, chunk, str(start.date()), str(as_of.date()))
                    paths, memberships = [], []
                    for _, group in bars.groupby("symbol"):
                        path, membership = symbol_paths(group, calendar, start=start, end=as_of, registry=registry)
                        paths.append(path)
                        memberships.append(membership)
                    if not paths:
                        raise ValueError(f"Aucune barre pour la tranche {chunk}")
                    labels = pd.concat(paths, ignore_index=True)
                    membership = pd.concat(memberships, ignore_index=True)
                    features = build_feature_matrix(engine, chunk, start_date=str(start.date()), end_date=str(end.date()),
                        generator_options={**profile["generator_options"], "enable_cross_sectional_ranks": False},
                        membership=membership)
                    features = features.loc[pd.to_datetime(features.date).isin(decision_days)].copy()
                    for col in features.select_dtypes(include=["float64"]).columns:
                        features[col] = features[col].astype(np.float32)
                    for name, frame in (("bars", bars), ("features", features), ("labels", labels), ("membership", membership)):
                        frame.to_parquet(folder/f"{name}.parquet", index=False)
                    atomic_json(marker, dict(symbols=chunk, files={name: digest(folder/name) for name in
                        ("bars.parquet", "features.parquet", "labels.parquet", "membership.parquet")}))
                features_parts.append(pd.read_parquet(folder/"features.parquet"))
                labels_parts.append(pd.read_parquet(folder/"labels.parquet"))
            atomic_json(output/"progress.json", dict(status="RUNNING", phase="scoring", completed=total, total=total))
            features = restore_ranks(pd.concat(features_parts, ignore_index=True), profile["generator_options"])
            del features_parts
            labels = qualify_feature_membership(pd.concat(labels_parts, ignore_index=True), features)
            del labels_parts
            labels = labels.loc[labels.date.isin(decision_days)].copy()
            labels.to_parquet(output/"labels.parquet", index=False)
            scores = score_population(features, profile["feature_columns"], models, champion)
            del features
            scores["fold_start"] = fixed_fold
            scores.to_parquet(output/"scores.parquet", index=False)
            atomic_json(output/"progress.json", dict(status="RUNNING", phase="metrics", completed=total, total=total))
            years, daily, strict, evaluated = evaluate(scores, labels, calendar, as_of)
            # Calendar sessions without any feature rows must not disappear from coverage.
            missing_days = sorted(set(decision_days)-set(scores.date))
            for day in missing_days:
                year = str(day.year)
                years.setdefault(year, dict(status="BLOCKED_COVERAGE", strict_original_top={}))
            for year, result in years.items():
                result["expected_dates"] = int(sum(d.year == int(year) for d in decision_days))
                result["missing_scoring_dates"] = [str(d.date()) for d in missing_days if d.year==int(year)]
            daily.to_parquet(output/"daily_coverage.parquet", index=False)
            strict.to_parquet(output/"daily_original_top_metrics.parquet", index=False)
            evaluated.to_parquet(output/"evaluated.parquet", index=False)
            report = dict(status="completed" if all(y["status"]=="EVALUABLE" for y in years.values()) else "completed_with_reservations",
                years=years, as_of=str(as_of.date()), start=str(start.date()), end=str(end.date()),
                fixed_fold=fixed_fold, validation_champion=champion, model_hashes=model_hashes,
                universe_count=len(universe), n_features=len(profile["feature_columns"]),
                scored_rows=len(scores), scored_symbols=int(scores.symbol.nunique()),
                missing_symbols=sorted(set(universe)-set(scores.symbol)),
                missing_scoring_dates=[str(d.date()) for d in missing_days],
                quality_reasons=labels.path_quality_reason.value_counts().to_dict(),
                no_training=True, no_sql_writes=True, no_orders=True)
            atomic_json(output/"report.json", report)
            (output/"report.md").write_text(report_markdown(report), encoding="utf-8")
            atomic_json(output/"run.json", dict(status="COMPLETED", pid=os.getpid(), report_status=report["status"]))
            atomic_json(output/"progress.json", dict(status="COMPLETED", years=list(years), report_status=report["status"]))
            LOGGER.info("Confirmation completed: %s", output/"report.json")
            return report
        except Exception as exc:
            state = dict(status="FAILED", pid=os.getpid(), error=str(exc))
            atomic_json(output/"run.json", state)
            atomic_json(output/"progress.json", state)
            raise


def main():
    from database.connection import get_sqlalchemy_engine
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="artifacts/research/oracle_path_comparison/20261013-v1")
    parser.add_argument("--output", required=True)
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end")
    parser.add_argument("--as-of")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    engine = get_sqlalchemy_engine()
    @event.listens_for(engine, "connect")
    def read_only(dbapi_conn, connection_record):
        with dbapi_conn.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
    try:
        run(engine, **vars(args))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
