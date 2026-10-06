"""Replay as-of FIRDS FULINS_E + DLTINS pour les ISIN du Sprint 5 FR.

Le résultat décrit des enregistrements ISIN/MIC publiés et leurs versions.
Il ne transforme pas ces observations en barres négociables ni en données PIT
de 2016 : le premier Full du replay date de 2018.
"""
from __future__ import annotations

import argparse
import json
import logging
import zipfile
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

from service.fr.eodhd_backfill import _atomic_json
from service.fr.esma_firds_download import _check

EVENTS = {"NewRcrd", "ModfdRcrd", "TermntdRcrd", "CancRcrd"}
DEFAULT_MICS = {"XPAR", "ALXP", "XMLI"}
LOG = logging.getLogger(__name__)


def _value(parent: ET.Element | None, path: str) -> str | None:
    node = parent.find(path) if parent is not None else None
    return node.text.strip() if node is not None and node.text else None


def archive_records(path: Path, target_isins: set[str], target_mics: set[str]):
    """Stream les seuls couples cibles ; ne charge jamais le XML complet en mémoire."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != 1 or not names[0].endswith(".xml"):
            raise ValueError(f"archive FIRDS inattendue : {path.name}")
        with archive.open(names[0]) as stream:
            context = ET.iterparse(stream, events=("start", "end"))
            _, root = next(context)
            for event, element in context:
                if event != "end":
                    continue
                tag = element.tag.rsplit("}", 1)[-1]
                if tag not in {"RefData", "FinInstrm"}:
                    continue
                payload = element if tag == "RefData" else element[0]
                kind = "Full" if tag == "RefData" else payload.tag.rsplit("}", 1)[-1]
                if kind != "Full" and kind not in EVENTS:
                    raise ValueError(f"événement FIRDS inconnu : {kind}")
                attributes = payload.find("{*}FinInstrmGnlAttrbts")
                isin = _value(attributes, "{*}Id")
                venue = payload.find("{*}TradgVnRltdAttrbts")
                mic = _value(venue, "{*}Id")
                if isin in target_isins and mic in target_mics:
                    tech = payload.find("{*}TechAttrbts")
                    yield {
                        "isin": isin, "mic": mic, "event": kind,
                        "currency": _value(attributes, "{*}NtnlCcy"),
                        "cfi": _value(attributes, "{*}ClssfctnTp"),
                        "name": _value(attributes, "{*}FullNm"),
                        "first_trade_reported": _value(venue, "{*}FrstTradDt"),
                        "termination_reported": _value(venue, "{*}TermntnDt"),
                        "publication_from_reported": _value(tech, "{*}PblctnPrd/{*}FrDt"),
                    }
                root.clear()


def _day(value: str | None) -> date | None:
    if not value or value.startswith("9999-"):
        return None
    return date.fromisoformat(value[:10])


def apply_event(history: dict[tuple[str, str], list[dict]], record: dict,
                archive_day: date, source: str, anomalies: list[dict]) -> None:
    key = (record["isin"], record["mic"])
    versions = history.setdefault(key, [])
    published = _day(record["publication_from_reported"]) or archive_day
    if published > archive_day:
        anomalies.append({"type": "future_publication_date", "file": source,
                          "isin": key[0], "mic": key[1]})
    # Deux axes temporels distincts : FrDt est la validité FIRDS déclarée ;
    # archive_day est la première observation publique de cette version.
    # Une correction rétroactive ne doit jamais devenir disponible avant son archive.
    asof_from = archive_day
    if versions:
        previous = versions[-1]
        if record["event"] == "Full":
            anomalies.append({"type": "duplicate_full_record", "file": source,
                              "isin": key[0], "mic": key[1]})
        if record["event"] == "NewRcrd" and previous["event"] not in {"TermntdRcrd", "CancRcrd"}:
            anomalies.append({"type": "new_record_with_open_prior", "file": source,
                              "isin": key[0], "mic": key[1]})
        previous_start = date.fromisoformat(previous["asof_from"])
        if asof_from <= previous_start:
            anomalies.append({"type": "non_increasing_publication", "file": source,
                              "isin": key[0], "mic": key[1],
                              "previous_from": previous["asof_from"]})
        else:
            previous["asof_to"] = (asof_from - timedelta(days=1)).isoformat()
    elif record["event"] != "Full" and record["event"] != "NewRcrd":
        anomalies.append({"type": "event_without_prior_record", "file": source,
                          "isin": key[0], "mic": key[1], "event": record["event"]})
    versions.append({**record, "asof_from": asof_from.isoformat(), "asof_to": None,
                     "archive_date": archive_day.isoformat(), "source_file": source})


def _observed_interval(version: dict) -> dict | None:
    if version["event"] in {"TermntdRcrd", "CancRcrd"}:
        return None
    start = date.fromisoformat(version["asof_from"])
    first = _day(version["first_trade_reported"])
    if first and first > start:
        start = first
    end = _day(version["asof_to"])
    termination = _day(version["termination_reported"])
    if termination and (end is None or termination < end):
        end = termination
    if end and end < start:
        return None
    return {"from": start.isoformat(), "to": end.isoformat() if end else None,
            "source_file": version["source_file"],
            "event": version["event"]}


def _trading_episodes(versions: list[dict]) -> list[dict]:
    """Episodes de référence depuis le Full initial, explicitement censurés à gauche."""
    episodes = []
    current = None
    for version in versions:
        event = version["event"]
        observed = date.fromisoformat(version["asof_from"])
        first = _day(version["first_trade_reported"])
        end = _day(version["termination_reported"])
        if event in {"Full", "NewRcrd"}:
            if current is not None:
                current["ambiguous_reentry"] = True
                current["observed_to"] = (observed - timedelta(days=1)).isoformat()
            current = {"observed_from": observed.isoformat(), "observed_to": None,
                       "first_trade_reported": first.isoformat() if first else None,
                       "termination_reported": end.isoformat() if end else None,
                       "left_censored_by_initial_full": event == "Full",
                       "cancelled": False, "ambiguous_reentry": False,
                       "opening_source_file": version["source_file"],
                       "closing_source_file": None}
            episodes.append(current)
        elif event == "ModfdRcrd":
            if current is not None:
                if end is not None:
                    current["termination_reported"] = end.isoformat()
        elif event in {"TermntdRcrd", "CancRcrd"}:
            if current is not None:
                current["observed_to"] = (observed - timedelta(days=1)).isoformat()
                current["termination_reported"] = end.isoformat() if end else None
                current["cancelled"] = event == "CancRcrd"
                current["closing_source_file"] = version["source_file"]
                current = None
            else:
                episodes.append({"observed_from": None, "observed_to": None,
                                 "first_trade_reported": first.isoformat() if first else None,
                                 "termination_reported": end.isoformat() if end else None,
                                 "left_censored_by_initial_full": True,
                                 "cancelled": event == "CancRcrd", "ambiguous_reentry": True,
                                 "opening_source_file": None,
                                 "closing_source_file": version["source_file"]})
    return episodes


def replay(index_path: Path, subset_path: Path, root: Path, *, end: date,
           mics: set[str] = DEFAULT_MICS, require_complete: bool = True,
           resume_from: Path | None = None) -> dict:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    subset = json.loads(subset_path.read_text(encoding="utf-8"))
    if subset.get("rule_version") != "fr_s5_subset_v1":
        raise ValueError("pool Sprint 5 inattendu")
    first_day = date.fromisoformat(index["full_date"])
    target_isins = {row["isin_reported"] for row in subset["symbols"]
                    if row["status"] == "CANDIDATE_REQUIRES_EXTERNAL_PROOFS"}
    selected = [row for row in index["files"] if date.fromisoformat(row["date"]) <= end]
    present = []
    missing = []
    for item in selected:
        path = root / item["date"][:4] / item["file"]
        (present if path.is_file() else missing).append(item)
    indexed_days = {row["date"] for row in selected if row["type"] == "DLTINS"}
    missing_days = []
    day = first_day + timedelta(days=1)
    while day <= end:
        if day.isoformat() not in indexed_days:
            missing_days.append(day.isoformat())
        day += timedelta(days=1)
    if require_complete and missing:
        raise ValueError(f"replay incomplet : fichiers indexés mais absents={len(missing)}")
    history: dict[tuple[str, str], list[dict]] = {}
    anomalies: list[dict] = []
    evidence: list[dict] = []
    if resume_from is not None:
        prior = json.loads(resume_from.read_text(encoding="utf-8"))
        prior_files = prior.get("files", [])
        prior_symbols = {row["isin"] for row in prior.get("symbols", [])}
        if (not prior.get("complete") or prior.get("start") != first_day.isoformat()
                or date.fromisoformat(prior["end"]) >= end
                or prior.get("target_mics") != sorted(mics)
                or prior_symbols != target_isins
                or len(prior_files) != prior.get("files_processed")
                or len(prior_files) > len(present)
                or [row["file"] for row in prior_files]
                != [row["file"] for row in present[:len(prior_files)] ]):
            raise ValueError("rapport de reprise incompatible avec l'index, le pool ou l'horizon")
        for symbol in prior["symbols"]:
            for venue in symbol["market_reference"]:
                history[(symbol["isin"], venue["mic"])] = venue["versions"]
        anomalies = prior["anomalies"]
        evidence = prior_files
        LOG.info("ESMA replay resume files=%s end=%s", len(evidence), prior["end"])
    first_pending = len(evidence)
    for number, item in enumerate(present[first_pending:], start=first_pending + 1):
        path = root / item["date"][:4] / item["file"]
        integrity = _check(path, item.get("md5"))
        count = 0
        for record in archive_records(path, target_isins, mics):
            apply_event(history, record, date.fromisoformat(item["date"]),
                        item["file"], anomalies)
            count += 1
        evidence.append({"file": item["file"], "matched_records": count,
                         "sha256": integrity["sha256"],
                         "official_md5_available": integrity["official_md5_available"]})
        if number % 50 == 0 or number == len(present):
            LOG.info("ESMA replay files=%s/%s matched_versions=%s anomalies=%s",
                     number, len(present), sum(len(v) for v in history.values()), len(anomalies))
    by_isin = defaultdict(list)
    for (isin, mic), versions in sorted(history.items()):
        by_isin[isin].append({"mic": mic, "versions": versions,
                              "observed_asof_intervals": [window for version in versions
                                                         if (window := _observed_interval(version))],
                              "trading_episodes": _trading_episodes(versions)})
    symbols = []
    for row in subset["symbols"]:
        if row["status"] != "CANDIDATE_REQUIRES_EXTERNAL_PROOFS":
            continue
        symbols.append({"symbol": row["symbol"], "isin": row["isin_reported"],
                        "provider_status_current": row["provider_status_current"],
                        "market_reference": by_isin[row["isin_reported"]],
                        "canonical_go": False})
    counts = Counter({"symbols_with_any_target_mic": sum(bool(row["market_reference"]) for row in symbols),
                      "symbols_without_target_mic": sum(not row["market_reference"] for row in symbols),
                      "version_records": sum(len(v) for v in history.values())})
    return {"scope": "FIRDS publication-as-of from initial Full; not proof of executed trades or 2016-2017 coverage",
            "start": first_day.isoformat(), "end": end.isoformat(), "target_mics": sorted(mics),
            "files_indexed": len(selected), "files_processed": len(present),
            "missing_files": [row["file"] for row in missing], "missing_delta_days": missing_days,
            "complete": not missing,
            "publication_continuity_confirmed": not missing_days,
            "counts": dict(counts), "anomalies": anomalies, "files": evidence,
            "canonical_go": False, "symbols": symbols}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/fr/esma_firds/replay_2018"))
    parser.add_argument("--subset", type=Path,
                        default=Path("artifacts/fr/eodhd/backfill_2016/sprint5_subset_audit.json"))
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path,
                        default=Path("artifacts/fr/esma_firds/sprint5_history_replay.json"))
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument("--resume-from", type=Path,
                        help="rapport précédent vérifié, préfixe exact des archives indexées")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = replay(args.root / "index.json", args.subset, args.root,
                    end=args.end_date, require_complete=not args.allow_incomplete,
                    resume_from=args.resume_from)
    _atomic_json(args.output, result)
    print(json.dumps({key: value for key, value in result.items()
                      if key in {"start", "end", "complete", "counts", "files_processed"}}
                     | {"anomaly_count": len(result["anomalies"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
