"""Bounded free-source provenance audit. No models, DB writes or serving."""
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from service.fr.guidance_corpus_11d import ROOT, dump, fetch, normalized, sha

CASES = {
    "FR0000054470": {"before": "2024-09-25", "name": "Ubisoft"},
    "FR0013214145": {"before": "2019-12-06", "name": "SMCP"},
}
PUBLIC_WEB_CHECKS = [
    ("SMCP_previous_2019", "https://www.smcp.com/en/h1-2019-results-in-line-with-expectations/", "20191205"),
    ("Virbac_repeat", "https://echanges.dila.gouv.fr/OPENDATA/AMF/MKW/2023/07/FCMKW130221_20230717.pdf", "20230717"),
]


def within_archive_boundary(payload, cutoff):
    snapshot = payload.get("archived_snapshots", {}).get("closest", {})
    stamp = str(snapshot.get("timestamp") or "")
    return bool(snapshot.get("available") and len(stamp) == 14 and stamp.isdigit()
                and stamp[:8] <= cutoff and snapshot.get("status") == "200")


def collect(output: Path):
    if output.exists():
        raise ValueError("Use a new evidence directory")
    output.mkdir(parents=True)
    (output / "raw").mkdir()
    dump(output / "protocol.json", {"purpose": "missing_previous_guidance_and_archive_availability",
        "cases": CASES, "web_checks": PUBLIC_WEB_CHECKS, "no_returns_or_training": True,
        "no_tls_bypass": True, "no_paywall_bypass": True, "candidate_cap_per_isin": 4})
    results, selected = [], []
    for isin, case in CASES.items():
        where = f"identificationsociete_iso_cd_isi = '{isin}' AND uin_dat_amf >= '2018-01-01' AND uin_dat_amf < '{case['before']}'"
        url = ROOT + "/exports/json?" + urlencode({"where": where})
        try:
            raw = fetch(url)
            rows = json.loads(raw)
            counter_raw = fetch(ROOT + "/records?" + urlencode({"where": where, "limit": 1}))
            count = json.loads(counter_raw)["total_count"]
            (output / "raw" / f"{isin}.json").write_bytes(raw)
            (output / "raw" / f"{isin}_counter.json").write_bytes(counter_raw)
            if len(rows) != count:
                raise ValueError("Incomplete metadata export")
            candidates = []
            for row in rows:
                title = normalized(str(row.get("informationdeposee_inf_tit_inf") or ""))
                day = str(row.get("uin_dat_amf") or "")[:10]
                age = (datetime.fromisoformat(case["before"]) - datetime.fromisoformat(day)).days
                if 0 < age <= 365 and any(w in title for w in ("resultat", "sales", "ventes", "chiffre", "results", "guidance")):
                    candidates.append(row)
            candidates.sort(key=lambda r: (r["uin_dat_amf"], r["uin_idt_uin"]), reverse=True)
            for row in candidates[:4]:
                selected.append({"id":row["uin_idt_uin"], "isin":isin,
                    "issuer":row["identificationsociete_iso_nom_soc"], "title":row["informationdeposee_inf_tit_inf"],
                    "url":row["url_de_recuperation"], "source_metadata":row,
                    "source_record_sha256":sha(json.dumps(row, sort_keys=True).encode()),
                    "transmissions":{k:row.get(k) for k in ("uin_dat_amf","uin_dat_mar","informationdeposee_inf_dat_emt")},
                    "selection_reason":"prior_financial_release_metadata_not_performance"})
            results.append({"name":case["name"], "url":url, "status":"COMPLETE_METADATA",
                            "rows":len(rows), "counter":count, "sha256":sha(raw), "candidates":len(candidates)})
        except Exception as exc:
            results.append({"name":case["name"], "url":url, "status":"SOURCE_ERROR", "error":str(exc)})
    for name, url, cutoff in PUBLIC_WEB_CHECKS:
        for kind, target in [("CURRENT_PRIMARY",url), ("ARCHIVE_AVAILABILITY",
                "https://archive.org/wayback/available?" + urlencode({"url":url,"timestamp":cutoff+"235959"}))]:
            record = {"name":name, "kind":kind, "url":target, "cutoff_day":cutoff,
                      "observed_at":datetime.now(UTC).isoformat()}
            try:
                raw = fetch(target)
                (output / "raw" / f"{name}_{kind}.bin").write_bytes(raw)
                record.update(status="FETCHED", bytes=len(raw), sha256=sha(raw))
                if kind == "ARCHIVE_AVAILABILITY":
                    payload = json.loads(raw)
                    record["snapshot_within_cutoff"] = within_archive_boundary(payload, cutoff)
                    record["archive_response"] = payload
                    record["historical_content_hash_verified"] = False
            except Exception as exc:
                record.update(status="SOURCE_ERROR", error=str(exc))
            results.append(record)
    # Same URL repeated in metadata must not produce two downloaded documents.
    selected = list({r["url"]:r for r in selected}.values())
    dump(output / "selected_documents.json", selected)
    report = {"status":"BOUNDED_FREE_SOURCE_AUDIT_NOT_EXHAUSTIVE_WEB", "sources":results,
              "selected_previous_documents":len(selected), "paid_source_indispensable":False,
              "strict_historical_pit_qualified":False, "no_canonical_writes":True}
    dump(output / "source_audit_report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(collect(args.output)["status"], flush=True)


if __name__ == "__main__":
    main()
