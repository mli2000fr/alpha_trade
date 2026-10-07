"""Review downloaded CNINFO guidance PDFs without publishing numeric features.

Run with a Python environment containing pypdf. The script is deliberately
separate from the market-data collector: PDF extraction can be inspected and
repeated without querying providers or writing to the database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def classify(title: str, content: str) -> dict[str, object]:
    compact = re.sub(r"\s+", "", title + " " + content[:2000])
    period = re.search(r"(20\d{2})(?:年)?(年度|半年度|前三季度|第一季度)", compact)
    correction = bool(re.search(r"更正|修正|补充", title))
    has_prior = bool(re.search(r"前次业绩预告|原预计|原预告", content))
    has_new = bool(re.search(r"更正后|修正后|本次业绩预告", content))
    units = sorted(set(re.findall(r"单位[:：]\s*(亿元|万元|元)", content)))
    return {
        "fiscal_year": int(period.group(1)) if period else None,
        "fiscal_period": period.group(2) if period else None,
        "correction": correction,
        "has_prior_section": has_prior,
        "has_new_section": has_new,
        "declared_units": units,
        "numeric_status": "QUARANTINED_MANUAL_VALIDATION_REQUIRED",
    }


def review(report_path: Path, output_path: Path) -> dict[str, object]:
    from pypdf import PdfReader

    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing review: {output_path}")
    source = json.loads(report_path.read_text(encoding="utf-8"))
    records = []
    for sample in source["cninfo_samples"]:
        pdf_path = Path(sample["pdf_path"])
        if not pdf_path.is_absolute():
            pdf_path = Path.cwd() / pdf_path
        if not pdf_path.exists():
            raise FileNotFoundError(pdf_path)
        digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        if digest != sample["pdf_sha256"]:
            raise ValueError(f"PDF checksum mismatch: {pdf_path}")
        reader = PdfReader(str(pdf_path))
        text_by_page = [page.extract_text() or "" for page in reader.pages]
        extracted = "\n\n".join(text_by_page)
        text_path = output_path.parent / f"{sample['code']}-{sample['announcement_id']}.txt"
        if text_path.exists():
            raise FileExistsError(text_path)
        text_path.write_text(extracted, encoding="utf-8")
        records.append({
            "code": sample["code"],
            "announcement_id": sample["announcement_id"],
            "title": sample["title"],
            "announcement_time_ms": sample["announcement_time_ms"],
            "pdf_url": sample["pdf_url"],
            "pdf_sha256": digest,
            "pages": len(reader.pages),
            "text_chars": len(extracted),
            "text_path": str(text_path),
            **classify(sample["title"], extracted),
        })
    result = {
        "status": "STRUCTURAL_EXTRACTION_ONLY",
        "source_report": str(report_path),
        "documents": records,
        "warning": "Archive timestamps and extracted numbers are not certified PIT features.",
    }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = review(args.report, args.output)
    print(f"Reviewed {len(result['documents'])} CNINFO PDFs: {args.output}")


if __name__ == "__main__":
    main()
