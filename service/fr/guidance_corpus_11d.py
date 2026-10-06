"""Expand FR guidance evidence from public metadata, without prices or targets."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
import re
import time
import unicodedata
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = "https://www.info-financiere.gouv.fr/api/explore/v2.0/catalog/datasets/flux-amf-new-prod"
WORDS = ("objectifs", "perspectives", "previsions", "guidance", "warning", "avertissement")
SEED = "fr-guidance-11d-20261004-v1"
FINANCIAL = re.compile(r"\b(objectifs?|perspectives?|previsions?|guidance|resultats?|benefices?|profit|ebitda|revenus?|chiffre d.affaires)\b")
REVISION = re.compile(r"\b(revis\w*|revu\w*|revoit|releve\w*|rehauss\w*|abaisse\w*|redui\w*|actualis\w*|ajuste\w*)\b")
UP = re.compile(r"\b(hausse|releve\w*|rehauss\w*)\b")
DOWN = re.compile(r"\b(baisse|abaisse\w*|redui\w*|profit warning|avertissement sur resultats?)\b")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def normalized(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c))


def title_kind(title: str) -> str | None:
    text = normalized(title)
    if re.search(r"\b(calendrier|agenda|notation|rating|moodys|moody.s|standard.*poor)\b", text):
        return None
    # 'prevision' must not match 'revision'; a forecast is not necessarily revised.
    if not FINANCIAL.search(text):
        return None
    warning = re.search(r"\b(profit warning|avertissement sur resultats?)\b", text)
    if not REVISION.search(text) and not warning:
        return None
    up, down = bool(UP.search(text)), bool(DOWN.search(text))
    if up and down:
        return "MIXED_TITLE_NOT_VALIDATED"
    if down:
        return "DOWN_TITLE_NOT_VALIDATED"
    if up:
        return "UP_TITLE_NOT_VALIDATED"
    return "REVISION_UNSPECIFIED_TITLE_NOT_VALIDATED"


def fetch(url: str, max_bytes: int = 35_000_000) -> bytes:
    request = Request(url, headers={"User-Agent": "AlphaTrade-Research/1.0 (public-data-readonly)"})
    with urlopen(request, timeout=35) as response:
        raw = response.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("Source exceeds byte cap")
    return raw


def select(candidates: list[dict], old_isins: set[str], per_side: int = 10) -> list[dict]:
    selected, counts = [], Counter()
    for kind in ("UP_TITLE_NOT_VALIDATED", "DOWN_TITLE_NOT_VALIDATED", "REVISION_UNSPECIFIED_TITLE_NOT_VALIDATED"):
        cap = per_side if kind != "REVISION_UNSPECIFIED_TITLE_NOT_VALIDATED" else 4
        options = [r for r in candidates if r["kind"] == kind]
        options.sort(key=lambda r: (r["isin"] in old_isins, sha((SEED + r["id"]).encode())))
        side_count = 0
        for row in options:
            if counts[row["isin"]] >= 2:
                continue
            selected.append({**row, "new_issuer_vs_initial_pdf_sample": row["isin"] not in old_isins})
            counts[row["isin"]] += 1
            side_count += 1
            if side_count == cap:
                break
    return selected


def collect(output: Path, identities: Path, prior: Path) -> dict:
    if output.exists():
        raise ValueError("Use a new output to preserve evidence")
    output.mkdir(parents=True)
    (output / "metadata_raw").mkdir()
    with gzip.open(identities, "rt", encoding="utf-8") as handle:
        isins = {r["isin"] for r in map(json.loads, handle)}
    audit = json.loads((prior / "pdf_audit.json").read_text(encoding="utf-8"))
    old_isins = {r["isin"] for r in audit}
    old_urls = {r["url"] for r in audit}
    dump(output / "protocol.json", {"schema_version": 1, "market_code": "FR_EQ",
        "start": "2018-01-01", "end_exclusive": "2026-01-01", "words": WORDS,
        "seed": SEED, "per_side": 10, "unspecified": 4, "max_per_issuer": 2,
        "new_issuer_priority": True, "no_prices_or_returns": True,
        "identities_sha256": sha(identities.read_bytes()),
        "prior_audit_sha256": sha((prior / "pdf_audit.json").read_bytes()),
        "code_sha256": sha(Path(__file__).read_bytes())})
    rows, sources, failures = [], [], []
    for word in WORDS:
        where = f"uin_dat_amf >= '2018-01-01' AND uin_dat_amf < '2026-01-01' AND search(informationdeposee_inf_tit_inf, '{word}')"
        url = ROOT + "/exports/json?" + urlencode({"where": where})
        try:
            raw = fetch(url)
            data = json.loads(raw)
            if not isinstance(data, list):
                raise ValueError("Unexpected DILA export schema")
            (output / "metadata_raw" / f"{word}.json").write_bytes(raw)
            counter_url = ROOT + "/records?" + urlencode({"where": where, "limit": 1})
            count_raw = fetch(counter_url)
            (output / "metadata_raw" / f"{word}_counter.json").write_bytes(count_raw)
            count = json.loads(count_raw).get("total_count")
            sources.append({"word": word, "url": url, "sha256": sha(raw),
                            "rows": len(data), "total_count": count, "count_matches": count == len(data),
                            "counter_sha256": sha(count_raw), "observed_at": datetime.now(UTC).isoformat()})
            if count != len(data):
                raise ValueError("Export/count mismatch: archive kept, query not admitted")
            rows.extend(data)
            print(f"metadata word={word} rows={len(data)}", flush=True)
        except Exception as exc:
            failures.append({"word": word, "error": str(exc)})
            print(f"metadata word={word} FAILED {type(exc).__name__}", flush=True)
        time.sleep(0.4)
    grouped = {}
    for row in rows:
        isin, identifier = row.get("identificationsociete_iso_cd_isi"), row.get("uin_idt_uin")
        url = str(row.get("url_de_recuperation") or "")
        kind = title_kind(str(row.get("informationdeposee_inf_tit_inf") or ""))
        if isin not in isins or not identifier or not kind or url in old_urls:
            continue
        if urlparse(url).scheme != "https" or not urlparse(url).path.lower().endswith(".pdf"):
            continue
        key = (isin, identifier)
        candidate = {"isin": isin, "id": identifier, "issuer": row.get("identificationsociete_iso_nom_soc"),
                     "title": row["informationdeposee_inf_tit_inf"], "kind": kind, "url": url,
                     "transmissions": {k: row.get(k) for k in ("uin_dat_amf", "uin_dat_mar", "informationdeposee_inf_dat_emt")},
                     "source_metadata": row, "source_record_sha256": sha(json.dumps(row, sort_keys=True).encode())}
        if key in grouped and grouped[key]["url"] != url:
            failures.append({"id": identifier, "error": "Conflicting document URL for same identity"})
            grouped[key]["conflict"] = True
        else:
            grouped.setdefault(key, candidate)
    candidates = [r for r in grouped.values() if not r.get("conflict")]
    selected = select(candidates, old_isins)
    dump(output / "candidate_documents.json", candidates)
    dump(output / "selected_documents.json", selected)
    report = {"status": "METADATA_COMPLETE" if not failures else "PARTIAL_METADATA_FAILURES",
              "sources": sources, "failures": failures, "candidates": len(candidates),
              "candidate_kinds": dict(Counter(r["kind"] for r in candidates)),
              "selected": len(selected), "selected_isins": len({r["isin"] for r in selected}),
              "selected_new_isins": len({r["isin"] for r in selected if r["new_issuer_vs_initial_pdf_sample"]}),
              "title_direction_not_body_validation": True, "canonical_writes": False}
    dump(output / "metadata_report.json", report)
    return report


def pdf_stage(output: Path) -> dict:
    from pypdf import PdfReader

    selected = json.loads((output / "selected_documents.json").read_text(encoding="utf-8"))
    (output / "pdfs").mkdir(exist_ok=True)
    (output / "pages_text").mkdir(exist_ok=True)
    previous = json.loads((output / "pdf_report.json").read_text(encoding="utf-8"))["documents"] if (output / "pdf_report.json").exists() else []
    previous_by_id = {r["id"]: r for r in previous}
    documents = []
    for item in selected:
        result = {k: v for k, v in item.items() if k != "source_metadata"}
        attempts = []
        urls = [item["url"]]
        # Same exact DILA document pathname on the official archive, not an
        # unrelated substitute, and no guessed filename or TLS bypass.
        parsed = urlparse(item["url"])
        if parsed.hostname == "fr.ftp.opendatasoft.com" and parsed.path.startswith("/datadila/INFOFI/"):
            urls.append("https://echanges.dila.gouv.fr/OPENDATA/AMF/" + parsed.path.split("/INFOFI/", 1)[1])
        try:
            cached = previous_by_id.get(item["id"])
            if cached and cached.get("status") == "EXTRACTED":
                raw = Path(cached["pdf_path"]).read_bytes()
                if sha(raw) != cached["sha256"]:
                    raise ValueError("Cached PDF hash mismatch")
                successful_url = cached["download_url"]
            else:
                raw, successful_url = None, None
                for url in urls:
                    try:
                        raw = fetch(url, max_bytes=8_000_000)
                        if not raw.startswith(b"%PDF"):
                            raise ValueError("Non-PDF response")
                        successful_url = url
                        break
                    except Exception as exc:
                        attempts.append({"url": url, "error": str(exc)})
                if raw is None or successful_url is None:
                    raise ValueError("All official download attempts failed")
            pdf_hash = sha(raw)
            pdf_path = output / "pdfs" / f"{pdf_hash[:16]}.pdf"
            pdf_path.write_bytes(raw)
            reader = PdfReader(io.BytesIO(raw))
            if len(reader.pages) > 80:
                raise ValueError("Document exceeds 80-page review cap; PDF archived")
            page_records = [{"page": i + 1, "text": page.extract_text() or ""} for i, page in enumerate(reader.pages)]
            pages_path = output / "pages_text" / f"{pdf_hash[:16]}.json"
            dump(pages_path, page_records)
            result.update(status="EXTRACTED", pdf_path=str(pdf_path), sha256=pdf_hash,
                          pages_path=str(pages_path), pages=len(page_records),
                          text_chars=sum(len(r["text"]) for r in page_records), download_url=successful_url,
                          observed_at=cached["observed_at"] if cached and cached.get("status") == "EXTRACTED" else datetime.now(UTC).isoformat(),
                          reused_cached_pdf=bool(cached and cached.get("status") == "EXTRACTED"),
                          semantic_status="UNREVIEWED")
        except Exception as exc:
            result.update(status="FAILED", error=str(exc))
        result["failed_attempts"] = attempts
        documents.append(result)
        dump(output / "pdf_report.json", {"status": "RUNNING", "documents": documents})
        print(f"pdf {len(documents)}/{len(selected)} {result['status']} {result['isin']}", flush=True)
        time.sleep(0.4)
    report = {"status": "COLLECTION_FINISHED_NOT_SEMANTIC_VALIDATION", "selected": len(selected),
              "extracted": sum(r["status"] == "EXTRACTED" for r in documents),
              "failed": sum(r["status"] == "FAILED" for r in documents), "documents": documents}
    dump(output / "pdf_report.json", report)
    return report


REVIEW_STATUSES = {
    "COMPARABLE_FORWARD_PAIR", "PAST_PERIOD_ESTIMATE", "MISSING_OLD_GUIDANCE",
    "SCOPE_CHANGE", "SCOPE_REVIEW_REQUIRED", "NON_FINANCIAL_TARGET",
    "REPUBLICATION", "CONFIRMATION_NOT_NEW_REVISION",
}


def validate_pair(pair: dict, publication_day: date) -> None:
    """Check review contract, not automatic semantic understanding of a PDF."""
    for key in ("metric", "unit", "scope", "old_comparator", "new_comparator"):
        if not pair.get(key):
            raise ValueError(f"Missing pair field: {key}")
    if pair.get("scope_comparable") is not True:
        raise ValueError("Unverified scope cannot be admitted")
    if date.fromisoformat(pair["period_end"]) < publication_day:
        raise ValueError("Target period has already ended")
    old, new = pair["old"], pair["new"]
    for interval in (old, new):
        if len(interval) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in interval):
            raise ValueError("Old/new numeric anchors must be two numeric bounds")
        if interval[0] > interval[1]:
            raise ValueError("Reversed interval")
    # Bounds/qualifiers stay attached: >=35 is not an exact forecast of 35.
    up = new[0] > old[1]
    down = new[1] < old[0]
    if not ((pair.get("direction") == "UP" and up) or (pair.get("direction") == "DOWN" and down)):
        raise ValueError("Direction is not separated by the reviewed numeric anchors")


def review_stage(output: Path, review_path: Path) -> dict:
    """Bind manual review to immutable PDF evidence; never generate model labels."""
    review = json.loads(review_path.read_text(encoding="utf-8"))
    pdf = json.loads((output / "pdf_report.json").read_text(encoding="utf-8"))
    indexed = {d["sha256"][:16]: d for d in pdf["documents"] if d["status"] == "EXTRACTED"}
    if len(indexed) != pdf["extracted"]:
        raise ValueError("Duplicate PDF content/prefix: deduplicate before review")
    records = review["records"]
    if len({r["id"] for r in records}) != len(records) or {r["id"] for r in records} != set(indexed):
        raise ValueError("Review must cover exactly every extracted document once")
    validated, directions = [], Counter()
    for record in records:
        evidence = indexed[record["id"]]
        if sha(Path(evidence["pdf_path"]).read_bytes()) != evidence["sha256"]:
            raise ValueError("PDF checksum differs from archived evidence")
        if record["status"] not in REVIEW_STATUSES or not record.get("reason"):
            raise ValueError("Unknown or unjustified review classification")
        if not record.get("pages") or any(type(p) is not int or p < 1 or p > evidence["pages"] for p in record["pages"]):
            raise ValueError("Invalid PDF evidence page")
        transmissions = [datetime.fromisoformat(v) for v in evidence["transmissions"].values() if v]
        if not transmissions or any(t.tzinfo is None for t in transmissions):
            raise ValueError("Missing explicitly zoned transmission time")
        proxy = max(transmissions)
        pub_day = proxy.astimezone(ZoneInfo("Europe/Paris")).date()
        declared_day = date.fromisoformat(record["date_in_document"])
        if declared_day > pub_day:
            raise ValueError("Document date after archived transmission: quarantine")
        if declared_day < pub_day and record["status"] != "REPUBLICATION":
            raise ValueError("Earlier document date needs explicit republication review")
        pairs = record.get("pairs", [])
        if record["status"] == "COMPARABLE_FORWARD_PAIR":
            if not pairs:
                raise ValueError("Comparable classification without pair")
            for pair in pairs:
                validate_pair(pair, pub_day)
            # An announcement with several metrics is ONE observation, not N samples.
            sides = {p["direction"] for p in pairs}
            directions[next(iter(sides)) if len(sides) == 1 else "MIXED"] += 1
        elif pairs:
            raise ValueError("Quarantined review cannot expose admitted pairs")
        validated.append({**record, "isin": evidence["isin"], "issuer": evidence["issuer"],
                          "source_id": evidence["id"], "pdf_sha256": evidence["sha256"],
                          "source_record_sha256": evidence["source_record_sha256"],
                          "download_url": evidence["download_url"], "observed_at": evidence["observed_at"],
                          "transmission_proxy_at": proxy.isoformat(),
                          "historical_web_available_at": None,
                          "availability_status": "PROXY_NOT_STRICT_HISTORICAL_WEB_PIT",
                          "training_eligible": False})
    counts = Counter(r["status"] for r in validated)
    report = {"status": "MANUAL_REVIEW_COMPLETE_NOT_TRAINING_GO", "reviewed_documents": len(validated),
              "reviewed_issuers": len({r["isin"] for r in validated}), "classifications": dict(counts),
              "comparable_announcements_by_direction": dict(directions),
              "independent_second_reviewer": review["independent_second_reviewer"],
              "review_manifest_sha256": sha(review_path.read_bytes()),
              "blocked": ["small_directional_support", "no_independent_second_review",
                          "no_historical_web_availability_proof"],
              "model_training_run": False, "canonical_tables_modified": False, "records": validated}
    dump(output / "review_report.json", report)
    return report
