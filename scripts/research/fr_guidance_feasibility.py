"""Freeze a public French-disclosure sample and audit guidance PDF extractability.

Research only: no application tables, model training or trading decisions.
Run ``metadata`` with the project Python, then ``pdf`` with the bundled Python
runtime that includes pypdf. The selected sample is for parser feasibility,
not a point-in-time tradable equity universe.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


ROOT = "https://www.info-financiere.gouv.fr/api/explore/v2.0/catalog/datasets/flux-amf-new-prod"
HEADERS = {"User-Agent": "AlphaTrade-Research/1.0 (public-data-readonly)"}
ISIN = re.compile(r"^FR[A-Z0-9]{10}$")
REVISION = re.compile(
    r"revis|revu|revoit|releve|rehauss|abaisse|guidance|profit warning|"
    r"avertissement sur resultat|nouveaux objectifs|nouvelles perspectives"
)
FINANCIAL = re.compile(
    r"objectif|perspectiv|prevision|resultat|chiffre d.affaires|benefice|ebitda|cash.flow"
)
NUMBER = re.compile(r"\b\d[\d\s.,]*\s*(?:%|milliards?|millions?|m[€$]|[€$])(?=$|\W)", re.I)
OLD = re.compile(r"ancien|precedent|anterieur|initial")
NEW = re.compile(r"nouveau|revise|desormais|mis a jour|actualise")


def fetch_bytes(url: str, *, max_bytes: int = 15_000_000) -> bytes:
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError(f"Response exceeds {max_bytes} bytes")
            return data
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def api_url(path: str, **params: object) -> str:
    return ROOT + path + "?" + urllib.parse.urlencode(params)


def normalized(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(ch for ch in raw if not unicodedata.combining(ch))


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def classify_title(title: object) -> str | None:
    text = normalized(title)
    # A timetable of future publications is not an earnings forecast. Keep
    # already-frozen research selections unchanged; this applies to new runs.
    if "calendrier previsionnel" in text and "communication financiere" in text:
        return None
    if "regroupement" in text and "actions" in text and "calendrier previsionnel" in text:
        return None
    if REVISION.search(text) and FINANCIAL.search(text):
        return "revision_title"
    if FINANCIAL.search(text):
        return "financial_title"
    return None


def issuer_groups() -> list[dict]:
    where = (
        "uin_dat_amf >= '2024-01-01' AND uin_dat_amf < '2026-01-01' "
        "AND identificationsociete_iso_cd_isi IS NOT NULL"
    )
    groups = []
    for offset in range(0, 10_000, 100):
        payload = json.loads(fetch_bytes(api_url(
            "/records", select="identificationsociete_iso_cd_isi, count(*) as n",
            group_by="identificationsociete_iso_cd_isi", where=where,
            order_by="n DESC", limit=100, offset=offset,
        )))
        records = payload.get("records", [])
        for item in records:
            fields = item.get("record", {}).get("fields", {})
            isin = str(fields.get("identificationsociete_iso_cd_isi") or "")
            count = int(fields.get("n") or 0)
            if ISIN.fullmatch(isin) and count >= 2:
                groups.append({"isin": isin, "announcements_2024_25": count})
        if len(records) < 100:
            break
    return list({item["isin"]: item for item in groups}.values())


def choose_issuers(groups: list[dict], size: int, seed: str) -> list[dict]:
    # Stratify on disclosure frequency. There is no sector field in this API.
    buckets: dict[str, list[dict]] = {"2-9": [], "10-29": [], "30-99": [], "100+": []}
    for item in groups:
        count = item["announcements_2024_25"]
        bucket = "2-9" if count < 10 else "10-29" if count < 30 else "30-99" if count < 100 else "100+"
        buckets[bucket].append(item)
    for items in buckets.values():
        items.sort(key=lambda item: hashlib.sha256(f"{seed}:{item['isin']}".encode()).hexdigest())
    selected = []
    per_bucket = size // len(buckets)
    for name, items in buckets.items():
        selected.extend({**item, "activity_bucket": name} for item in items[:per_bucket])
    if len(selected) < size:
        chosen = {item["isin"] for item in selected}
        rest = [{**item, "activity_bucket": name} for name, items in buckets.items() for item in items if item["isin"] not in chosen]
        rest.sort(key=lambda item: hashlib.sha256(f"fill:{seed}:{item['isin']}".encode()).hexdigest())
        selected.extend(rest[: size - len(selected)])
    return selected[:size]


def fetch_issuer(item: dict, run_dir: Path) -> tuple[dict, list[dict]]:
    isin = item["isin"]
    where = (
        f"identificationsociete_iso_cd_isi = '{isin}' "
        "AND uin_dat_amf >= '2018-01-01' AND uin_dat_amf < '2026-01-01'"
    )
    raw = fetch_bytes(api_url("/exports/json", where=where), max_bytes=25_000_000)
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError("Export is not a JSON list")
    path = run_dir / "metadata" / f"{isin}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    counter = json.loads(fetch_bytes(api_url("/records", where=where, limit=1)))
    total = counter.get("total_count")
    manifest = {
        **item, "export_count": len(payload), "records_total_count": total,
        "count_matches": total == len(payload), "sha256": sha(raw),
        "source_url": ROOT, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    rows = []
    for record in payload:
        if not isinstance(record, dict):
            continue
        title = str(record.get("informationdeposee_inf_tit_inf") or "")
        group = classify_title(title)
        url = str(record.get("url_de_recuperation") or "")
        if not group or not url.lower().split("?")[0].endswith(".pdf"):
            continue
        published = str(record.get("uin_dat_amf") or "")
        rows.append({
            "isin": isin, "published_at": published, "title": title,
            "kind": group, "url": url,
            "subtype": str(record.get("sous_type_d_information") or ""),
        })
    return manifest, rows


def choose_pdfs(candidates: list[dict], seed: str, per_kind: int = 12) -> list[dict]:
    # Pre-select by metadata only; never look at document outcomes.
    unique = list({item["url"]: item for item in candidates}.values())
    selected = []
    for kind in ("revision_title", "financial_title"):
        options = [item for item in unique if item["kind"] == kind]
        options.sort(key=lambda item: hashlib.sha256(f"{seed}:{item['url']}".encode()).hexdigest())
        by_issuer: dict[str, int] = {}
        for item in options:
            if by_issuer.get(item["isin"], 0) >= 2:
                continue
            selected.append(item)
            by_issuer[item["isin"]] = by_issuer.get(item["isin"], 0) + 1
            if sum(row["kind"] == kind for row in selected) >= per_kind:
                break
    return selected


def metadata_stage(run_dir: Path, size: int, workers: int, seed: str) -> None:
    if run_dir.exists():
        raise FileExistsError(f"Refusing to overwrite snapshot: {run_dir}")
    run_dir.mkdir(parents=True)
    groups = issuer_groups()
    selected = choose_issuers(groups, size, seed)
    json_dump(run_dir / "universe_groups.json", groups)
    json_dump(run_dir / "selected_issuers.json", selected)
    print(f"groups={len(groups)} selected={len(selected)}", flush=True)
    manifests, candidates, failures = [], [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_issuer, item, run_dir): item for item in selected}
        for index, future in enumerate(as_completed(futures), 1):
            item = futures[future]
            try:
                manifest, rows = future.result()
                manifests.append(manifest)
                candidates.extend(rows)
            except Exception as exc:
                failures.append({"isin": item["isin"], "error": str(exc)})
            if index % 20 == 0 or index == len(selected):
                print(f"metadata {index}/{len(selected)} failed={len(failures)}", flush=True)
    pdfs = choose_pdfs(candidates, seed)
    json_dump(run_dir / "manifest.json", sorted(manifests, key=lambda row: row["isin"]))
    json_dump(run_dir / "candidate_pdfs.json", candidates)
    json_dump(run_dir / "selected_pdfs.json", pdfs)
    json_dump(run_dir / "metadata_report.json", {
        "purpose": "guidance parser feasibility only, not a PIT tradable universe",
        "run_dir": str(run_dir), "seed": seed, "issuer_groups": len(groups),
        "selected_issuers": len(selected), "exports_completed": len(manifests),
        "export_count_mismatches": sum(not row["count_matches"] for row in manifests),
        "candidate_pdfs": len(candidates), "selected_pdfs": len(pdfs),
        "selected_by_kind": {kind: sum(row["kind"] == kind for row in pdfs) for kind in ("revision_title", "financial_title")},
        "failures": failures,
    })
    print(f"Metadata report: {run_dir / 'metadata_report.json'}", flush=True)


def pdf_stage(run_dir: Path) -> None:
    from pypdf import PdfReader

    selected = json.loads((run_dir / "selected_pdfs.json").read_text(encoding="utf-8"))
    previous_path = run_dir / "pdf_audit.json"
    previous = {
        row["url"]: row
        for row in json.loads(previous_path.read_text(encoding="utf-8"))
    } if previous_path.exists() else {}
    audits = []
    for index, item in enumerate(selected, 1):
        audit = {key: item[key] for key in ("isin", "published_at", "title", "kind", "url")}
        try:
            cached = Path(previous.get(item["url"], {}).get("pdf_path") or "")
            raw = cached.read_bytes() if cached.is_file() else fetch_bytes(item["url"], max_bytes=6_000_000)
            if not raw.startswith(b"%PDF"):
                raise ValueError("Response is not PDF")
            digest = sha(raw)
            pdf_path = run_dir / "pdfs" / f"{digest[:16]}.pdf"
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(raw)
            reader = PdfReader(io.BytesIO(raw))
            if len(reader.pages) > 80:
                raise ValueError(f"Document has {len(reader.pages)} pages (>80)")
            page_texts = [page.extract_text() or "" for page in reader.pages]
            plain = "\n\n".join(page_texts)
            text_path = run_dir / "pdf_text" / f"{digest[:16]}.txt"
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text(plain, encoding="utf-8")
            norm = normalized(plain)
            audit.update({
                "status": "EXTRACTED", "sha256": digest, "pdf_path": str(pdf_path),
                "text_path": str(text_path), "bytes": len(raw), "pages": len(reader.pages),
                "text_chars": len(plain), "revision_in_body": bool(REVISION.search(norm)),
                "old_marker": bool(OLD.search(norm)), "new_marker": bool(NEW.search(norm)),
                "numeric_mentions": len(NUMBER.findall(norm)),
                "old_new_numeric_candidate": bool(OLD.search(norm) and NEW.search(norm) and len(NUMBER.findall(norm)) >= 2),
            })
        except Exception as exc:
            audit.update({"status": "FAILED", "error": str(exc)})
        audits.append(audit)
        print(f"PDF {index}/{len(selected)} {audit['status']} {audit['isin']}", flush=True)
    json_dump(run_dir / "pdf_audit.json", audits)
    extracted = [row for row in audits if row["status"] == "EXTRACTED"]
    json_dump(run_dir / "pdf_report.json", {
        "selected": len(selected), "extracted": len(extracted),
        "text_usable_500_chars": sum(row["text_chars"] >= 500 for row in extracted),
        "old_new_numeric_candidates": sum(row["old_new_numeric_candidate"] for row in extracted),
        "failures": [row for row in audits if row["status"] != "EXTRACTED"],
        "warning": "Keyword co-occurrence is not validated extraction of old/new guidance values.",
    })
    print(f"PDF report: {run_dir / 'pdf_report.json'}", flush=True)


def recheck_stage(run_dir: Path, sample_size: int = 20) -> None:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    sample = sorted(
        manifest,
        key=lambda row: hashlib.sha256(f"recheck:{row['isin']}".encode()).hexdigest(),
    )[:sample_size]
    results = []
    for index, row in enumerate(sample, 1):
        isin = row["isin"]
        where = (
            f"identificationsociete_iso_cd_isi = '{isin}' "
            "AND uin_dat_amf >= '2018-01-01' AND uin_dat_amf < '2026-01-01'"
        )
        try:
            raw = fetch_bytes(api_url("/exports/json", where=where), max_bytes=25_000_000)
            payload = json.loads(raw)
            counter = json.loads(fetch_bytes(api_url("/records", where=where, limit=1)))
            results.append({
                "isin": isin, "original_count": row["export_count"],
                "recheck_count": len(payload),
                "original_sha256": row["sha256"], "recheck_sha256": sha(raw),
                "records_total_count": counter.get("total_count"),
                "count_changed": len(payload) != row["export_count"],
                "bytes_changed": sha(raw) != row["sha256"],
            })
        except Exception as exc:
            results.append({"isin": isin, "error": str(exc)})
        if index % 5 == 0 or index == len(sample):
            print(f"recheck {index}/{len(sample)}", flush=True)
    json_dump(run_dir / "recheck_report.json", {
        "checked": len(sample),
        "count_changed": sum(row.get("count_changed", False) for row in results),
        "bytes_changed": sum(row.get("bytes_changed", False) for row in results),
        "errors": sum("error" in row for row in results),
        "results": results,
    })
    print(f"Recheck report: {run_dir / 'recheck_report.json'}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="stage", required=True)
    meta = sub.add_parser("metadata")
    meta.add_argument("--size", type=int, default=120)
    meta.add_argument("--workers", type=int, default=4)
    meta.add_argument("--seed", default="fr-guidance-20260917")
    meta.add_argument("--output-root", type=Path, default=Path("artifacts/research/fr_guidance_feasibility"))
    pdf = sub.add_parser("pdf")
    pdf.add_argument("--run-dir", type=Path, required=True)
    recheck = sub.add_parser("recheck")
    recheck.add_argument("--run-dir", type=Path, required=True)
    recheck.add_argument("--sample-size", type=int, default=20)
    args = parser.parse_args()
    if args.stage == "metadata":
        stamp = datetime.now(timezone.utc).strftime("pilot-%Y%m%d-%H%M%S")
        metadata_stage(args.output_root / stamp, args.size, args.workers, args.seed)
    elif args.stage == "pdf":
        pdf_stage(args.run_dir)
    else:
        recheck_stage(args.run_dir, args.sample_size)


if __name__ == "__main__":
    main()
