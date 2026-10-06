"""Small explicit issuer-document archive; no quotes, SQL or serving."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "config/research_fr/evidence_16e.json"
MAX_BYTES = 12_000_000
HOSTS = {"invest.bnpparibas", "www.spie.com", "www.compagniedelodet.net",
         "www.globenewswire.com", "www.actusnews.com", "trigano-finance.com",
         "www.amaxperteye.com"}


def validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username or parsed.password:
        raise ValueError("Only explicit HTTPS issuer document hosts allowed")


def download(url):
    validate_url(url)
    request = Request(url, headers={"User-Agent": "AlphaTrade-Research/1.0 (public-document-review)"})
    with urlopen(request, timeout=25) as response:
        validate_url(response.url)
        raw = response.read(MAX_BYTES + 1)
        mime = response.headers.get_content_type()
        final_url = response.url
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Empty or oversized document")
    if not raw.startswith(b"%PDF-") and mime not in {"text/html", "application/xhtml+xml"}:
        raise ValueError("Unexpected document format")
    return raw, mime, final_url


def available(record, cutoff):
    """A date printed in a document never backdates our observation."""
    decision = datetime.fromisoformat(cutoff)
    if decision.tzinfo is None:
        raise ValueError("Aware decision required")
    if record.get("status") != "ARCHIVED":
        return False
    observed = datetime.fromisoformat(record["observed_at"])
    known = datetime.fromisoformat(record["available_at"])
    if observed.tzinfo is None or known.tzinfo is None or known < observed:
        raise ValueError("Invalid observation availability")
    return observed <= decision and known <= decision


def verify_record(record, output):
    if record.get("status") != "ARCHIVED":
        return False
    raw_path = (output / record["raw_path"]).resolve()
    if not raw_path.is_relative_to(output.resolve()):
        raise ValueError("Archive path escapes output")
    if hashlib.sha256(raw_path.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError("Archive checksum mismatch")
    return True


def collect(output, spec, *, fetch=download):
    if spec.get("market_code") != "FR_EQ" or spec.get("serving_enabled") is not False:
        raise ValueError("FR research-only spec required")
    output.mkdir(parents=True, exist_ok=False)
    (output / "raw").mkdir()
    (output / "text").mkdir()
    (output / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    records = []
    for source in spec["sources"]:
        row = {"id": source["id"], "symbol": source["symbol"], "url": source["url"],
               "claims": source.get("claims", {}), "claim_status": "CURATED_REQUIRES_CONTENT_REVIEW"}
        try:
            validate_url(source["url"])
            raw, mime, final_url = fetch(source["url"])
            stamp = datetime.now(UTC).isoformat()
            digest = hashlib.sha256(raw).hexdigest()
            suffix = ".pdf" if raw.startswith(b"%PDF-") else ".html"
            target = output / "raw" / (digest + suffix)
            if not target.exists():
                target.write_bytes(raw)
            row.update(status="ARCHIVED", observed_at=stamp, available_at=stamp,
                       sha256=digest, raw_path="raw/" + target.name, mime=mime, final_url=final_url)
            if suffix == ".pdf":
                try:
                    from pypdf import PdfReader
                    pages = PdfReader(io.BytesIO(raw)).pages
                    text = "\n".join(f"\n--- PAGE {n + 1} ---\n" + (p.extract_text() or "")
                                     for n, p in enumerate(pages))
                    text_path = output / "text" / (digest + ".txt")
                    text_path.write_text(text, encoding="utf-8")
                    row.update(text_path="text/" + text_path.name, page_count=len(pages))
                except Exception as exc:
                    row["text_error"] = type(exc).__name__ + ": " + str(exc)[:140]
            verify_record(row, output)
        except Exception as exc:
            row.update(status="FAILED", error=type(exc).__name__ + ": " + str(exc)[:200])
        records.append(row)
        report = {"schema_version": 1, "market_code": "FR_EQ", "status": "ARCHIVED_PENDING_QUALIFICATION",
                  "requested": len(spec["sources"]), "processed": len(records),
                  "archived": sum(r["status"] == "ARCHIVED" for r in records),
                  "failed": sum(r["status"] == "FAILED" for r in records), "records": records,
                  "serving_enabled": False, "sql_writes": False, "orders_allowed": False}
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{row['id']} {row['status']}", flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-id", action="append", help="Retry only explicit configured source IDs")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    allowed = (ROOT / "artifacts/fr/research/evidence_16e").resolve()
    if output == allowed or not output.is_relative_to(allowed) or output.exists():
        parser.error("New folder within FR evidence_16e required")
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    if args.source_id:
        wanted = set(args.source_id)
        if wanted - {row["id"] for row in spec["sources"]}:
            parser.error("Unknown source ID")
        spec["sources"] = [row for row in spec["sources"] if row["id"] in wanted]
    result = collect(output, spec)
    print(json.dumps({k: v for k, v in result.items() if k != "records"}))


if __name__ == "__main__":
    main()
