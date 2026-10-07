"""Free-source guidance expansion, provenance only; no returns or model fit."""
import argparse
import gzip
import json
import re
import shutil
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlencode, urlparse

from service.fr.guidance_corpus_11d import ROOT, dump, fetch, normalized, pdf_stage, sha

CASES = {
    "FR0000121964": "2023-08-01", "FR0010766667": "2021-05-12",
    "FR0000031577": "2023-07-17", "FR0000121972": "2021-11-30",
    "FR0000073298": "2024-10-15", "FR0000131906": "2022-07-29",
    "FR0000074148": "2024-10-24", "FR0013153541": "2021-10-26",
}


def prepare(output: Path, prior: Path):
    if output.exists():
        raise ValueError("Use a new evidence directory")
    output.mkdir(parents=True)
    (output / "metadata_raw").mkdir()
    dump(output / "protocol.json", {
        "purpose": "exhaust_remaining_105_candidates_and_previous_guidance",
        "no_returns_or_model_training": True, "previous_release_max_days": 400,
        "prior": str(prior), "cases": CASES, "max_nearest_previous_docs_per_issuer": 5,
        "source_selection_before_pdf_read": True,
    })
    reviewed = json.loads((prior / "selected_documents.json").read_text(encoding="utf-8"))
    used = {r["id"] for r in reviewed}
    candidates = json.loads((prior / "candidate_documents.json").read_text(encoding="utf-8"))
    selected = {r["id"]: {**r, "selection_reason": "remaining_frozen_candidate"}
                for r in candidates if r["id"] not in used}
    sources, failures = [], []
    for isin, before in CASES.items():
        where = f"identificationsociete_iso_cd_isi = '{isin}' AND uin_dat_amf >= '2018-01-01' AND uin_dat_amf < '{before}'"
        url = ROOT + "/exports/json?" + urlencode({"where": where})
        try:
            raw = fetch(url)
            rows = json.loads(raw)
            counter = fetch(ROOT + "/records?" + urlencode({"where": where, "limit": 1}))
            (output / "metadata_raw" / f"{isin}.json").write_bytes(raw)
            (output / "metadata_raw" / f"{isin}_counter.json").write_bytes(counter)
            count = json.loads(counter)["total_count"]
            sources.append({"isin": isin, "url": url, "rows": len(rows), "total_count": count,
                            "sha256": sha(raw), "count_matches": len(rows) == count})
            if len(rows) != count:
                raise ValueError("Incomplete issuer export")
            relevant = []
            for row in rows:
                title = normalized(str(row.get("informationdeposee_inf_tit_inf") or ""))
                day = str(row.get("uin_dat_amf") or "")[:10]
                age = (date.fromisoformat(before) - date.fromisoformat(day)).days
                if 0 < age <= 400 and any(w in title for w in (
                        "resultat", "chiffre d", "guidance", "perspective", "objectif", "prevision", "sales", "results")) and not any(
                            w in title for w in ("calendrier", "agenda", "notation")):
                    relevant.append(row)
            relevant.sort(key=lambda r: (r["uin_dat_amf"], r["uin_idt_uin"]), reverse=True)
            for row in relevant[:5]:
                identifier = row["uin_idt_uin"]
                url_pdf = str(row.get("url_de_recuperation") or "")
                if identifier in used or not urlparse(url_pdf).path.lower().endswith(".pdf"):
                    continue
                selected.setdefault(identifier, {
                    "isin": isin, "id": identifier, "issuer": row.get("identificationsociete_iso_nom_soc"),
                    "title": row["informationdeposee_inf_tit_inf"], "url": url_pdf,
                    "transmissions": {k: row.get(k) for k in ("uin_dat_amf", "uin_dat_mar", "informationdeposee_inf_dat_emt")},
                    "source_record_sha256": sha(json.dumps(row, sort_keys=True).encode()),
                    "source_metadata": row, "selection_reason": "nearest_prior_financial_release",
                })
            print(f"antecedents {isin} metadata={len(rows)} candidates={len(relevant)}", flush=True)
        except Exception as exc:
            failures.append({"isin": isin, "error": str(exc)})
        time.sleep(0.4)
    dump(output / "selected_documents.json", sorted(selected.values(), key=lambda r: (r["isin"], r["id"])))
    report = {"status": "PREPARED" if not failures else "PARTIAL", "selected": len(selected),
              "sources": sources, "failures": failures, "no_canonical_writes": True}
    dump(output / "metadata_report.json", report)
    return report


SUPPLEMENT = {"FR0000073298": ["133126_20240724", "135019_20240221"],
              "FR0000131906": ["133551_20220516", "138289_20220422", "135586_20220218"],
              "FR0000031577": ["137606_20191011", "133019_20190916"]}


def supplement(output: Path, prior: Path):
    if output.exists():
        raise ValueError("Use a new evidence directory")
    output.mkdir(parents=True)
    dump(output / "protocol.json", {"no_returns_or_training": True, "source": str(prior),
                                    "explicit_antecedents_omitted_by_title_filter": SUPPLEMENT})
    selected = []
    for isin, identifiers in SUPPLEMENT.items():
        raw_path = prior / "metadata_raw" / f"{isin}.json"
        indexed = {r["uin_idt_uin"]: r for r in json.loads(raw_path.read_text(encoding="utf-8"))}
        for identifier in identifiers:
            row = indexed[identifier]
            selected.append({"isin": isin, "id": identifier, "issuer": row["identificationsociete_iso_nom_soc"],
                "title": row["informationdeposee_inf_tit_inf"], "url": row["url_de_recuperation"],
                "transmissions": {k: row.get(k) for k in ("uin_dat_amf", "uin_dat_mar", "informationdeposee_inf_dat_emt")},
                "source_record_sha256": sha(json.dumps(row, sort_keys=True).encode()), "source_metadata": row,
                "selection_reason": "documented_antecedent_not_selected_by_title_filter", "export_sha256": sha(raw_path.read_bytes())})
    dump(output / "selected_documents.json", selected)
    return {"status": "SUPPLEMENT_PREPARED", "selected": len(selected)}


EVIDENCE_ROOTS = [
    Path("artifacts/fr/research/guidance_corpus_11d/corpus-20261004-v1"),
    Path("artifacts/fr/research/guidance_completion_11e/free-20261004-v1"),
    Path("artifacts/fr/research/guidance_completion_11e/antecedents-20261004-v1"),
]


def pair_direction(old, new):
    """Conservative non-overlapping numeric pairs; qualifiers remain mandatory."""
    import math
    if len(old) != 2 or len(new) != 2 or not all(math.isfinite(x) for x in [*old, *new]):
        raise ValueError("Finite two-bound intervals required")
    if old[0] > old[1] or new[0] > new[1]:
        raise ValueError("Unordered interval")
    return "UP" if new[0] > old[1] else "DOWN" if new[1] < old[0] else "UNRESOLVED"


def check_second_review(payload):
    """Require explicit human decisions; semantic review never proves historical PIT."""
    records = payload.get("records", [])
    if not records or len({r["id"] for r in records}) != len(records):
        raise ValueError("Nonempty unique review records required")
    accepted = []
    for record in records:
        if record.get("decision") not in {"ACCEPT", "REJECT", "RESERVE"}:
            raise ValueError(f"Pending decision: {record['id']}")
        if not str(record.get("second_reviewer") or "").strip() or not record.get("second_review_date"):
            raise ValueError("Named independent reviewer and date required")
        date.fromisoformat(record["second_review_date"])
        if not str(record.get("comments") or "").strip():
            raise ValueError("Review justification required")
        if record["decision"] == "ACCEPT":
            if record["status"] != "FIRST_REVIEW_PAIR":
                raise ValueError("Complex case requires a new evidence manifest before acceptance")
            if not all(record.get(k) is True for k in (
                    "old_is_forecast", "same_period_metric_scope", "bounds_qualifiers_correct", "not_duplicate")):
                raise ValueError("Explicit semantic gates required")
            accepted.append(record["id"])
        if record.get("training_eligible") is not False:
            raise ValueError("Second reading cannot grant training eligibility")
    return {"status": "SECOND_REVIEW_RECORDED_HISTORICAL_PIT_UNQUALIFIED", "accepted": accepted,
            "rejected": [r["id"] for r in records if r["decision"] == "REJECT"],
            "reserved": [r["id"] for r in records if r["decision"] == "RESERVE"],
            "training_eligible": False, "reviewer_independence_is_human_attestation": True}


def resolved_manifest_records(path: Path, seen=None):
    """Resolve immutable, hash-bound versions without losing earlier evidence."""
    seen = set() if seen is None else set(seen)
    resolved = path.resolve()
    if resolved in seen:
        raise ValueError("Cyclic evidence manifest")
    seen.add(resolved)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    records = list(manifest["records"])
    if manifest.get("base_manifest"):
        base = Path(manifest["base_manifest"])
        if sha(base.read_bytes()) != manifest["base_manifest_sha256"]:
            raise ValueError("Base evidence manifest changed")
        records = resolved_manifest_records(base, seen) + records
    if len({r["id"] for r in records}) != len(records):
        raise ValueError("Duplicate record in manifest chain")
    return records


def screen_documents(documents):
    """Lexical triage only. Absence of a match is NOT rejection of a document."""
    result = []
    pattern = re.compile(r"contre|precedemment|initialement|previous|formerly|au lieu|vs[.]?", re.I)
    for doc in documents:
        pages = json.loads(Path(doc["pages_path"]).read_text(encoding="utf-8"))
        hits = []
        for page in pages:
            text = " ".join(page["text"].split())
            for match in pattern.finditer(normalized(text)):
                # Normalization may shorten text; locator is page, snippet is a triage hint only.
                hits.append({"page": page["page"], "snippet": text[max(0, match.start()-180):match.end()+260]})
        result.append({"id": doc["id"], "sha256": doc["sha256"], "issuer": doc["issuer"],
                       "status": "SEMANTIC_REVIEW_REQUIRED" if hits else "NO_LEXICAL_MATCH_NOT_REJECTED",
                       "hits": hits, "semantic_validated": False})
    return result


def publication_day(doc):
    """Latest recorded transmission day in Paris; not historical web availability."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    values = []
    for raw in doc["transmissions"].values():
        if raw:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if value.tzinfo is None:
                raise ValueError("Timezone required for transmission")
            values.append(value.astimezone(ZoneInfo("Europe/Paris")))
    if not values:
        raise ValueError("Missing transmission")
    return max(values).date().isoformat()


def package(output: Path, manifest_path: Path, roots=None):
    """Build an auditable second-reader package, never an ML eligibility approval."""
    if output.exists():
        raise ValueError("Use a new review directory")
    roots = EVIDENCE_ROOTS if roots is None else roots
    indexed = {}
    reports = []
    for root in roots:
        report = json.loads((root / "pdf_report.json").read_text(encoding="utf-8"))
        reports.append({"root": str(root), "selected": report["selected"], "extracted": report["extracted"], "failed": report["failed"]})
        for doc in report["documents"]:
            if sha(Path(doc["pdf_path"]).read_bytes()) != doc["sha256"]:
                raise ValueError(f"PDF hash mismatch {doc['id']}")
            indexed[doc["id"]] = doc
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = resolved_manifest_records(manifest_path)
    # Preserve frozen 11-D classifications; only carry its four first-reader pairs here.
    prior = json.loads(Path("config/research_fr/guidance_review_11d_v1.json").read_text(encoding="utf-8"))
    by_hash = {doc["sha256"][:16]: doc for doc in indexed.values()}
    for row in prior["records"]:
        if row["status"] == "COMPARABLE_FORWARD_PAIR":
            doc = by_hash[row["id"]]
            records.append({"id": doc["id"], "pages": row["pages"], "status": "FIRST_REVIEW_PAIR",
                            **row["pairs"][0], "qualifiers": row["reason"]})
    if len({r["id"] for r in records}) != len(records):
        raise ValueError("Duplicate announcement in review package")
    output.mkdir(parents=True)
    (output / "pdfs").mkdir()
    dump(output / "input_manifest.json", {"path": str(manifest_path), "sha256": sha(manifest_path.read_bytes()),
                                           "base_manifest": manifest.get("base_manifest"),
                                           "base_manifest_sha256": manifest.get("base_manifest_sha256"), "resolved_records": records})
    grid = []
    lines = ["# Dossier de seconde revue — guidance FR Sprint 11-E", "",
             "Aucune paire ci-dessous n'est autorisée pour l'entraînement. La première revue n'est pas une seconde revue indépendante.", "",
             "Pour chaque annonce, lire les pages du PDF et les notes, puis remplir `second_review.json`. Ne pas consulter les rendements.", "",
             "Contrôler : ancienne prévision (pas résultat réalisé), même exercice encore futur, même métrique/unité/périmètre, bornes et qualificatifs, annonce non dupliquée.", "",
             "Les dates de transmission sont des proxies reconstruits ; `observed_at` est la collecte actuelle. Ne pas antidater une disponibilité Web historique non prouvée.", ""]
    pairs = []
    for record in records:
        doc = indexed[record["id"]]
        if record["status"] == "FIRST_REVIEW_PAIR":
            if record["period_end"] <= publication_day(doc):
                raise ValueError("Past period cannot be forward guidance")
            if pair_direction(record["old"], record["new"]) != record["direction"]:
                raise ValueError("Unresolved numerical direction")
            if record.get("prior_id"):
                old_doc = indexed[record["prior_id"]]
                if old_doc["isin"] != doc["isin"] or publication_day(old_doc) >= publication_day(doc):
                    raise ValueError("Invalid old guidance provenance")
            pairs.append({**record, "isin": doc["isin"], "publication_proxy_day": publication_day(doc)})
        evidence = []
        for identifier, pages in [(record["id"], record["pages"]), (record.get("prior_id"), record.get("prior_pages"))]:
            if not identifier:
                continue
            source = indexed[identifier]
            if not pages or min(pages) < 1 or max(pages) > source["pages"]:
                raise ValueError("Invalid page locator")
            filename = identifier + ".pdf"
            target = output / "pdfs" / filename
            shutil.copyfile(source["pdf_path"], target)
            evidence.append({"id": identifier, "pages": pages, "pdf": "pdfs/" + filename,
                "sha256": source["sha256"], "source_url": source["url"], "observed_at": source["observed_at"],
                "transmission_proxy_day": publication_day(source), "historical_web_available_at": None})
        grid.append({**record, "issuer": doc["issuer"], "isin": doc["isin"], "evidence": evidence,
                     "second_reviewer": None, "second_review_date": None, "decision": "PENDING",
                     "old_is_forecast": None, "same_period_metric_scope": None,
                     "bounds_qualifiers_correct": None, "not_duplicate": None, "comments": "",
                     "training_eligible": False})
        lines.extend([f"## {doc['issuer']} — {record['id']}", "", f"Statut première revue : {record['status']}.", "",
                      record.get("qualifiers", record.get("reason", "")), ""])
        if "old" in record:
            lines.extend([f"Proposition : {record['metric']} ({record['unit']}), exercice finissant le {record['period_end']}, {record['old']} → {record['new']} : {record['direction']}.", ""])
        for item in evidence:
            lines.extend([f"- [PDF {item['id']}]({item['pdf']}), pages {item['pages']}; SHA-256 `{item['sha256']}`.", ""])
    dump(output / "second_review.json", {"independent_second_review_completed": False, "records": grid})
    dump(output / "first_review_pairs.json", pairs)
    screened = screen_documents(list(indexed.values()))
    dump(output / "lexical_screen.json", screened)
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    from collections import Counter
    statuses = dict(Counter(r["status"] for r in records))
    report = {"status": "AWAITING_INDEPENDENT_SECOND_REVIEW", "source_reports": reports,
              "unique_pdf_documents": len(indexed), "first_reader_pairs": len(pairs),
              "first_reader_up": sum(p["direction"] == "UP" for p in pairs),
              "first_reader_down": sum(p["direction"] == "DOWN" for p in pairs),
              "other_review_records": len(records)-len(pairs), "classification_counts": statuses,
              "reserved_complex_cases": sum(r["status"].endswith("REVIEW_REQUIRED") for r in records),
              "lexical_candidates": sum(bool(r["hits"]) for r in screened),
              "manual_review_exhaustive": False, "paid_source_indispensable_demonstrated": False,
              "training_eligible": False, "no_canonical_writes": True}
    dump(output / "report.json", report)
    return report


def support(output: Path):
    """Support audit only; no fitted model, no return-based event selection."""
    from datetime import timedelta

    import pandas as pd
    pool_path = Path("artifacts/fr/research/fold7_repair/rebuild-20261003-v1/confirmation/direction/fr-shared-direction-h5-6c203bea5a09/oracle_oof_pool.parquet")
    expected = "8b251ed6c0028d7bff179fae7a8c0eeedf4c54fb606bfb1a356446e7c988766b"
    if sha(pool_path.read_bytes()) != expected:
        raise ValueError("Frozen Oracle pool changed")
    frame = pd.read_parquet(pool_path, columns=["research_uid", "decision_session_date", "oracle_fold", "oracle_phase", "decile", "label_available_session_date", "path_state"])
    protocol = json.loads((pool_path.parent / "protocol.json").read_text(encoding="utf-8"))
    from modelFactory.fr_labels_review import phase_mask
    with gzip.open("artifacts/fr/sprint6c_reference/identities.jsonl.gz", "rt", encoding="utf-8") as handle:
        mapping = {r["research_uid"]: r["isin"] for r in map(json.loads, handle)}
    frame["isin"] = frame["research_uid"].map(mapping)
    if frame["isin"].isna().any():
        raise ValueError("Unmapped identity in Oracle pool")
    pairs = json.loads((output / "first_review_pairs.json").read_text(encoding="utf-8"))
    days = pd.to_datetime(frame["decision_session_date"])
    rows = []
    event_support = []
    for lag in (1, 2):
        for window in (7, 30):
            matched = pd.Series(False, index=frame.index)
            matching_announcements = set()
            for pair in pairs:
                available = pd.Timestamp(date.fromisoformat(pair["publication_proxy_day"]) + timedelta(days=lag))
                mask = frame["isin"].eq(pair["isin"]) & days.ge(available) & days.lt(available + pd.Timedelta(days=window))
                if mask.any():
                    matching_announcements.add(pair["id"])
                if lag == 1 and window == 30:
                    event_support.append({"id": pair["id"], "isin": pair["isin"], "direction": pair["direction"],
                                          "publication_proxy_day": pair["publication_proxy_day"],
                                          "matched_rows": int(mask.sum()),
                                          "identity_present_in_pool": bool(frame["isin"].eq(pair["isin"]).any()),
                                          "interpretation": "MATCHED" if mask.any() else "NO_ORACLE_ROW_FOR_THIS_ISIN_IN_WINDOW"})
                matched |= mask
            groups = []
            for (fold, phase), chunk in frame.loc[matched].groupby(["oracle_fold", "oracle_phase"]):
                groups.append({"oracle_fold": int(fold), "oracle_phase": phase, "rows": len(chunk),
                               "dates": int(chunk["decision_session_date"].nunique()),
                               "d1": int(chunk["decile"].eq(1).sum()), "d10": int(chunk["decile"].eq(10).sum())})
            outer_groups = []
            for plan in protocol["plans"]:
                if plan["fold"] not in (6, 7) or plan["status"] != "ADMITTED":
                    continue
                for phase in ("train", "validation", "test"):
                    chunk = frame.loc[matched & phase_mask(frame, plan["dates"], phase, "2025-12-31")]
                    outer_groups.append({"directional_outer_fold": plan["fold"], "phase": phase,
                                         "rows_with_guidance": len(chunk), "dates_with_guidance": int(chunk["decision_session_date"].nunique()),
                                         "d1": int(chunk["decile"].eq(1).sum()), "d10": int(chunk["decile"].eq(10).sum())})
            rows.append({"lag_calendar_days": lag, "window_calendar_days": window,
                         "announcements_matching_any_pool_row": len(matching_announcements),
                         "matched_rows": int(matched.sum()), "unique_dates": int(frame.loc[matched, "decision_session_date"].nunique()),
                         "pool_groups_not_directional_outer_folds": groups, "directional_outer_support": outer_groups})
    report = {"status": "SUPPORT_ONLY_NOT_MODEL_RESULT", "pool_sha256": expected,
              "pool_rows": len(frame), "first_review_announcements": len(pairs), "scenarios": rows,
              "announcement_support_lag1_window30": event_support,
              "independent_review_required": True, "historical_vintage_unproven": True,
              "training_go": False, "no_model_fit": True,
              "note": "Oracle fold/phase groups are not the directional outer-fold train/test masks. Support cannot qualify a directional fold automatically."}
    dump(output / "support_report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "pdf", "supplement", "package", "support", "validate-second-review"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prior", type=Path, default=Path("artifacts/fr/research/guidance_corpus_11d/corpus-20261004-v1"))
    parser.add_argument("--manifest", type=Path, default=Path("config/research_fr/guidance_review_11e_v1.json"))
    parser.add_argument("--extra-evidence", type=Path, action="append", default=[])
    args = parser.parse_args()
    if args.stage == "prepare":
        result = prepare(args.output, args.prior)
    elif args.stage == "supplement":
        result = supplement(args.output, args.prior)
    elif args.stage == "package":
        result = package(args.output, args.manifest, roots=EVIDENCE_ROOTS + args.extra_evidence)
    elif args.stage == "support":
        result = support(args.output)
    elif args.stage == "validate-second-review":
        result = check_second_review(json.loads((args.output / "second_review.json").read_text(encoding="utf-8")))
        dump(args.output / "second_review_result.json", result)
    else:
        result = pdf_stage(args.output)
    print(result["status"], flush=True)


if __name__ == "__main__":
    main()
