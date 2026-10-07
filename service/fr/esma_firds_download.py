"""Téléchargement reprenable des FULINS_E et DLTINS officiels pour l'audit FR.

Les archives sont des preuves de référence, pas une autorisation de promotion
canonique. TLS est vérifié, les ZIP sont testés et les MD5 ESMA sont contrôlés
quand l'index en publie (les anciennes lignes n'en contiennent parfois pas).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import ssl
import time
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

from service.fr.eodhd_backfill import _atomic_json

INDEX_URL = "https://registers.esma.europa.eu/solr/esma_registers_firds_files/select"
ARCHIVE_HOST = "firds.esma.europa.eu"
NAME_PATTERN = re.compile(r"^(FULINS_E|DLTINS)_(\d{8})_\d+of\d+\.zip$")


def _tls_context() -> ssl.SSLContext:
    if not hasattr(ssl, "enum_certificates"):
        return ssl.create_default_context()
    pem = "".join(ssl.DER_cert_to_PEM_cert(cert)
                  for cert, encoding, _ in ssl.enum_certificates("ROOT")
                  if encoding == "x509_asn")
    return ssl.create_default_context(cadata=pem)


def _get_json(url: str, context: ssl.SSLContext) -> dict:
    with urllib.request.urlopen(url, context=context, timeout=45) as response:
        return json.load(response)


def list_files(start: date, end: date, full_date: date,
               context: ssl.SSLContext) -> list[dict]:
    if start != full_date or end < start:
        raise ValueError("le replay doit commencer le jour du FULINS_E initial")
    rows = []
    for year in range(start.year, end.year + 1):
        lower = max(start, date(year, 1, 1))
        upper = min(end, date(year, 12, 31))
        if lower > upper:
            continue
        for file_type in ("DLTINS", "FULINS" if year == full_date.year else None):
            if file_type is None:
                continue
            offset = 0
            while True:
                params = urllib.parse.urlencode({
                    "q": f"file_type:{file_type}",
                    "fq": f"publication_date:[{lower}T00:00:00Z TO {upper}T23:59:59Z]",
                    "wt": "json", "start": offset, "rows": 1000, "sort": "id asc",
                })
                result = _get_json(f"{INDEX_URL}?{params}", context)["response"]
                docs = result["docs"]
                for doc in docs:
                    name = doc.get("file_name", "")
                    match = NAME_PATTERN.fullmatch(name)
                    if not match:
                        continue
                    day = date.fromisoformat(f"{match[2][:4]}-{match[2][4:6]}-{match[2][6:]}")
                    if match[1] == "FULINS_E" and day != full_date:
                        continue
                    if match[1] == "DLTINS" and day <= full_date:
                        continue
                    link = doc.get("download_link", "")
                    parsed = urllib.parse.urlparse(link)
                    if parsed.scheme != "https" or parsed.hostname != ARCHIVE_HOST or not parsed.path.endswith("/" + name):
                        raise ValueError(f"lien ESMA inattendu : {name}")
                    rows.append({"file": name, "date": day.isoformat(), "type": match[1],
                                 "url": link, "md5": doc.get("checksum") or None})
                offset += len(docs)
                if not docs or offset >= result["numFound"]:
                    break
    names = [item["file"] for item in rows]
    if len(names) != len(set(names)):
        raise ValueError("doublons dans l'index ESMA")
    if not any(item["type"] == "FULINS_E" for item in rows):
        raise ValueError("FULINS_E initial absent de l'index ESMA")
    return sorted(rows, key=lambda item: (item["date"], item["type"] != "FULINS_E", item["file"]))


def _check(path: Path, expected_md5: str | None) -> dict:
    sha = hashlib.sha256()
    md5 = hashlib.md5()  # noqa: S324 - vérification d'une empreinte publiée par ESMA
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
            md5.update(block)
    if expected_md5 and md5.hexdigest().lower() != expected_md5.lower():
        raise ValueError(f"MD5 ESMA incorrect : {path.name}")
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        if len(members) != 1 or not members[0].endswith(".xml") or archive.testzip():
            raise ValueError(f"ZIP ESMA corrompu/inattendu : {path.name}")
    return {"sha256": sha.hexdigest(), "md5": md5.hexdigest(),
            "official_md5_available": bool(expected_md5), "bytes": path.stat().st_size}


def _download(item: dict, root: Path, context: ssl.SSLContext) -> dict:
    target = root / item["date"][:4] / item["file"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        try:
            return {"file": item["file"], **_check(target, item["md5"]), "reused": True}
        except (ValueError, zipfile.BadZipFile):
            raise ValueError(f"archive existante invalide, intervention requise : {target}")
    temporary = target.with_name(target.name + ".part")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(item["url"], context=context, timeout=60) as response, temporary.open("wb") as output:
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    output.write(block)
            evidence = _check(temporary, item["md5"])
            os.replace(temporary, target)
            time.sleep(0.1)
            return {"file": item["file"], **evidence, "reused": False}
        except Exception:
            temporary.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError("retry impossible")


def run(start: date, end: date, full_date: date, root: Path,
        *, max_files: int | None = None, workers: int = 3) -> dict:
    context = _tls_context()
    index = list_files(start, end, full_date, context)
    root.mkdir(parents=True, exist_ok=True)
    _atomic_json(root / "index.json", {"start": start.isoformat(),
                                      "end": end.isoformat(), "full_date": full_date.isoformat(),
                                      "files": index})
    selected = index[:max_files] if max_files is not None else index
    results = []
    failures = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_download, item, root, context): item for item in selected}
        for future in as_completed(futures):
            item = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"file": item["file"], "error": str(exc)})
            if (len(results) + len(failures)) % 100 == 0:
                print(f"ESMA archives={len(results)+len(failures)}/{len(selected)} échecs={len(failures)}", flush=True)
    observed_days = {item["date"] for item in index if item["type"] == "DLTINS"}
    missing_days = []
    day = full_date + timedelta(days=1)
    while day <= end:
        if day.isoformat() not in observed_days:
            missing_days.append(day.isoformat())
        day += timedelta(days=1)
    state = {"indexed": len(index), "selected": len(selected), "downloaded_or_reused": len(results),
             "failed": failures, "missing_delta_publication_days": missing_days,
             "official_md5_missing": sum(not row["official_md5_available"] for row in results),
             "complete": len(selected) == len(index) and not failures,
             "publication_continuity_confirmed": not missing_days,
             "files": sorted(results, key=lambda row: row["file"])}
    _atomic_json(root / "download_state.json", state)
    print(json.dumps({key: value for key, value in state.items() if key not in {"files", "failed", "missing_delta_publication_days"}},
                     ensure_ascii=False))
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-date", type=date.fromisoformat, default=date(2018, 1, 6))
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--root", type=Path, default=Path("artifacts/fr/esma_firds/replay_2018"))
    parser.add_argument("--max-files", type=int)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 4:
        parser.error("workers doit être entre 1 et 4")
    state = run(args.full_date, args.end_date, args.full_date, args.root,
                max_files=args.max_files, workers=args.workers)
    if state["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
