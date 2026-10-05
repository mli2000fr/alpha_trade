"""Isolated FR operations. Local run records; unqualified collectors fail closed."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import sys
import uuid
import os

from common.config_loader import load_batch_config

ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "artifacts/fr/operations"
IMPLEMENTED = {"fr_calendar_snapshot", "fr_db_backup", "fr_artifacts_backup", "fr_daily_bars_sync",
               "fr_corporate_actions_sync", "fr_amf_short_sync", "fr_dila_disclosures_sync", "fr_pit_quality_daily",
               "fr_security_master_sync", "fr_fundamentals_sync", "fr_consensus_snapshot", "fr_options_mifir_trade_sync"}


def load_section(name: str, config_path: Path) -> dict:
    cfg = load_batch_config(str(config_path))
    if name not in cfg or not name.startswith("fr_") or not isinstance(cfg[name], dict):
        raise ValueError("Section FR absente ou non autorisée")
    section = {**(cfg.get("defaults") or {}), **cfg[name]}
    if (section.get("market_code"), section.get("database_alias"), section.get("calendar")) != ("FR_EQ", "fr_primary", "XPAR"):
        raise ValueError("Batch réservé à FR_EQ / fr_primary / XPAR")
    if section.get("canonical_writes_enabled") is not False or section.get("serving_enabled") is not False:
        raise ValueError("Écritures canoniques et serving interdits pour cette tranche")
    return section


def run(name: str, *, config_path: Path = ROOT / "batch_fr.yaml", dry_run=False, today: date | None = None,
        resume=False, max_symbols: int | None = None) -> dict:
    now = datetime.now(UTC)
    result = {"batch": name, "market_code": "FR_EQ", "provider": "unknown", "status": "RUNNING",
              "started_at": now.isoformat(), "requested_count": 0, "received_count": 0,
              "persisted_count": 0, "failed_count": 0, "warning_count": 0, "dry_run": dry_run,
              "canonical_writes": False, "serving_enabled": False}
    result['limited_smoke'] = max_symbols is not None
    try:
        cfg = load_section(name, config_path)
        result["provider"] = cfg.get("provider", "unknown")
        if not dry_run and (not cfg.get("enabled") or cfg.get("status") not in ("ACTIVE", "ACTIVE_RESEARCH")):
            result["status"] = "SKIPPED_DISABLED_OR_UNQUALIFIED"
        elif name not in IMPLEMENTED:
            raise ValueError("Collecteur FR non implémenté/qualifié : aucun fallback US")
        else:
            _handle(name, cfg, result, dry_run=dry_run, today=today, resume=resume, max_symbols=max_symbols)
            result["status"] = "DRY_RUN" if dry_run else "SUCCESS"
    except Exception as exc:
        result.update(status="FAILED", failed_count=max(1, result["failed_count"]), error_message=str(exc))
    result["finished_at"] = datetime.now(UTC).isoformat()
    if not dry_run:
        # Even a malformed config gets an observable failure; no SQL connection.
        folder = OPS / "runs" / (name if name.startswith("fr_") and name.replace("_", "").isalnum() else "invalid")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{now:%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex[:8]}.json"
        with path.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, default=str)
    return result


def _handle(name, cfg, result, *, dry_run, today, resume=False, max_symbols=None):
    if name == 'fr_options_mifir_trade_sync':
        from service.fr.mifir_options_daily import collect
        identities = (ROOT / str(cfg['identities_file'])).resolve()
        if not identities.is_relative_to((ROOT/'artifacts/fr').resolve()):
            raise ValueError('Identités options hors périmètre FR')
        root = OPS/name
        if dry_run:
            collect(cfg, result, root=root, identities=identities, dry_run=True, max_symbols=max_symbols)
            return
        root.mkdir(parents=True, exist_ok=True)
        lock = root/'.lock'
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, 'w') as stream:
            stream.write(str(os.getpid()))
        try:
            collect(cfg, result, root=root, identities=identities, max_symbols=max_symbols)
        finally:
            lock.unlink(missing_ok=True)
        return
    if name == 'fr_consensus_snapshot':
        from service.fr.consensus_snapshot import collect
        identities = (ROOT / str(cfg['identities_file'])).resolve()
        if not identities.is_relative_to((ROOT/'artifacts/fr').resolve()):
            raise ValueError('Identités consensus hors périmètre FR')
        root = OPS/name
        if dry_run:
            collect(cfg, result, root=root, identities=identities, dry_run=True, max_symbols=max_symbols)
            return
        root.mkdir(parents=True, exist_ok=True)
        lock = root/'.lock'
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, 'w') as stream:
            stream.write(str(os.getpid()))
        try:
            collect(cfg, result, root=root, identities=identities, max_symbols=max_symbols)
        finally:
            lock.unlink(missing_ok=True)
        return
    if name == 'fr_fundamentals_sync':
        from service.inpi.universe_collection import collect
        manifest=(ROOT/str(cfg['issuer_manifest'])).resolve()
        if manifest != (OPS/name/'mapping/verified_manifest.json').resolve():
            raise ValueError('Collecte INPI limitée au mapping vérifié FR')
        root=OPS/name
        if dry_run:
            collect(cfg,result,root=root,manifest_path=manifest,dry_run=True,max_symbols=max_symbols)
            return
        root.mkdir(parents=True,exist_ok=True)
        lock=root/'.lock'
        try: fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError: raise RuntimeError('Collecte INPI déjà verrouillée : vérifier le processus') from None
        with os.fdopen(fd,'w') as stream: stream.write(str(os.getpid()))
        try:
            collect(cfg,result,root=root,manifest_path=manifest,max_symbols=max_symbols)
        finally: lock.unlink(missing_ok=True)
        return
    if name == 'fr_security_master_sync':
        from service.fr.security_master_daily_15e import collect
        identities=(ROOT/str(cfg['identities_file'])).resolve()
        baseline=(ROOT/str(cfg['baseline_history'])).resolve()
        if not all(p.is_relative_to((ROOT/'artifacts/fr').resolve()) for p in (identities,baseline)):
            raise ValueError('Référentiel ESMA hors périmètre FR')
        root=OPS/name
        if dry_run:
            collect(cfg,result,root=root,identities=identities,base_path=baseline,dry_run=True,today=today)
            return
        root.mkdir(parents=True,exist_ok=True)
        lock=root/'.lock'
        try: fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError: raise RuntimeError('Référentiel FR déjà verrouillé : vérifier le processus') from None
        with os.fdopen(fd,'w') as stream: stream.write(str(os.getpid()))
        try:
            collect(cfg,result,root=root,identities=identities,base_path=baseline,today=today)
        finally: lock.unlink(missing_ok=True)
        return
    if name in ('fr_corporate_actions_sync','fr_amf_short_sync','fr_dila_disclosures_sync','fr_pit_quality_daily'):
        from service.fr import operational_collectors_15c as collectors
        if name == 'fr_pit_quality_daily':
            collectors.quality(cfg,result,operations=OPS,dry_run=dry_run,today=today)
            return
        identities=(ROOT/str(cfg['identities_file'])).resolve()
        if not identities.is_relative_to((ROOT/'artifacts/fr').resolve()):
            raise ValueError('Identités hors périmètre FR')
        root=OPS/name
        if dry_run:
            if name=='fr_corporate_actions_sync':
                collectors.corporate(cfg,result,root=root,identities=identities,dry_run=True,today=today,max_symbols=max_symbols)
            else:
                collectors.public_collection(name,cfg,result,root=root,identities=identities,dry_run=True,today=today)
            return
        root.mkdir(parents=True,exist_ok=True)
        lock=root/'.lock'
        try: fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError: raise RuntimeError('Batch FR verrouillé : vérifier le processus avant suppression manuelle') from None
        with os.fdopen(fd,'w') as stream: stream.write(str(os.getpid()))
        try:
            if name=='fr_corporate_actions_sync':
                collectors.corporate(cfg,result,root=root,identities=identities,today=today,resume=resume,max_symbols=max_symbols)
            else:
                collectors.public_collection(name,cfg,result,root=root,identities=identities,today=today)
        finally: lock.unlink(missing_ok=True)
        return
    if name == "fr_daily_bars_sync":
        from service.fr.eodhd_daily_15b import collect
        identities = (ROOT / str(cfg['identities_file'])).resolve()
        if not identities.is_relative_to((ROOT/'artifacts/fr').resolve()):
            raise ValueError('Identités quotidiennes hors périmètre FR')
        collect(cfg, result, root=OPS/'eodhd_daily', identities=identities,
                dry_run=dry_run, today=today, resume=resume, max_symbols=max_symbols)
        return
    if name == "fr_calendar_snapshot":
        from common.market_calendar import get_market_calendar
        from zoneinfo import ZoneInfo
        day = today or datetime.now(ZoneInfo("Europe/Paris")).date()
        lookback, ahead = int(cfg["lookback_days"]), int(cfg["days_ahead"])
        if not 0 <= lookback <= 31 or not 1 <= ahead <= 730:
            raise ValueError("Fenêtre calendrier FR invalide")
        sessions = get_market_calendar("FR_EQ").sessions(day - timedelta(days=lookback), day + timedelta(days=ahead))
        rows = [asdict(s) for s in sessions]
        result.update(requested_count=len(rows), received_count=len(rows), window=[(day-timedelta(days=lookback)).isoformat(), (day+timedelta(days=ahead)).isoformat()])
        if not rows:
            raise ValueError("Calendrier XPAR vide")
        if not dry_run:
            target = OPS / "calendar" / f"{day}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            # Only this observation day is refreshed; previous snapshots remain.
            temporary = target.with_suffix(".tmp")
            temporary.write_text(json.dumps({"market_code": "FR_EQ", "observed_at": datetime.now(UTC).isoformat(),
                "evidence_state": "LIBRARY_CALENDAR_NOT_OFFICIAL_PROOF", "sessions": rows}, default=str, indent=2), encoding="utf-8")
            temporary.replace(target)
            result["persisted_count"] = len(rows)
            result["snapshot_path"] = str(target)
        return
    keep = cfg.get("keep")
    if type(keep) is not int or keep < 1:
        raise ValueError("keep doit être un entier positif")
    if name == "fr_db_backup":
        from database.router import resolve_database_route, _credential
        from scripts.backup_db import backup_db
        route = resolve_database_route("fr_primary", "FR_EQ")
        dest = (ROOT / str(cfg["dest_dir"])).resolve()
        if cfg.get("db") != "alpha_trade_fr" or cfg.get("archive_prefix") != "alpha_trade_fr" or dest != (ROOT / "backups/fr/db").resolve():
            raise ValueError("Sauvegarde DB FR hors périmètre")
        result["requested_count"] = 1
        report = backup_db(host=route.host, db=route.database,
            user="" if dry_run else _credential(route.user_env, route.fallback_user_env),
            password="" if dry_run else _credential(route.password_env, route.fallback_password_env),
            dest_dir=dest, keep=keep, archive_prefix="alpha_trade_fr", include_routines=True, include_triggers=True,
            mysqldump_path=cfg.get("mysqldump_path"), dry_run=dry_run)
        if report.errors:
            raise RuntimeError("; ".join(report.errors))
        result.update(received_count=1, persisted_count=0 if dry_run else 1, archive=report.dump_path)
        return
    from service.fr.backup_qualification_15d import verified_archive
    dest = (ROOT / str(cfg["dest_dir"])).resolve()
    expected = {"artifacts/fr": "data", "artifacts/models/fr_eq": "models"}
    if dest != (ROOT / "backups/fr/artifacts").resolve() or cfg.get("sources") != list(expected):
        raise ValueError("Sauvegarde artefacts FR hors périmètre")
    result["requested_count"] = len(expected)
    for relative, child in expected.items():
        source = ROOT / relative
        if not source.exists():
            if child == "models":
                continue  # No future serving models yet; never substitute US.
            raise ValueError("Racine artefacts FR absente")
        if source.is_symlink() or source.is_junction() or any(p.is_symlink() or p.is_junction() for p in source.rglob("*")):
            raise ValueError("Liens symboliques interdits dans le backup FR")
        if not dry_run:
            report = verified_archive(source, dest/child, keep=keep)
            result.setdefault('archives', []).append(report)
        result["received_count"] += 1
        result["persisted_count"] += 0 if dry_run else 1


def latest_run(name: str) -> dict | None:
    if not name.startswith("fr_") or not name.replace("_", "").isalnum():
        raise ValueError("Nom batch FR invalide")
    paths = sorted((OPS / "runs" / name).glob("*.json"), reverse=True)
    if not paths:
        return None
    return json.loads(paths[0].read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--batch-config", type=Path, default=ROOT/"batch_fr.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Reprendre uniquement les symboles incomplets de cette fenêtre")
    parser.add_argument("--max-symbols", type=int, help="Limiter le smoke FR")
    args = parser.parse_args()
    result = run(args.batch, config_path=args.batch_config, dry_run=args.dry_run,
                 resume=args.resume, max_symbols=args.max_symbols)
    summary = {"batch": args.batch, "status": result["status"],
        **{short: result[full] for short, full in (("requested", "requested_count"), ("received", "received_count"),
            ("persisted", "persisted_count"), ("failed", "failed_count"), ("warning_count", "warning_count"))},
        "error_message": result.get("error_message", "")}
    print("::alpha_trade_run_summary::" + json.dumps(summary, ensure_ascii=False), flush=True)
    print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
    if result["status"] == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
