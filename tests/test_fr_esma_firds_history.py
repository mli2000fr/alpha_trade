import zipfile
import json
from datetime import date

from service.fr.esma_firds_download import _check
from service.fr.esma_firds_history import (
    _observed_interval, _trading_episodes, apply_event, archive_records, replay,
)


def _record(event, *, first="2017-01-01T00:00:00Z", termination=None):
    return {"isin": "FR0000000000", "mic": "XPAR", "event": event,
            "currency": "EUR", "cfi": "ESVUFR", "name": "Test",
            "first_trade_reported": first,
            "termination_reported": termination,
            "publication_from_reported": None}


def test_replay_preserves_publication_and_termination_dates():
    history = {}
    anomalies = []
    apply_event(history, _record("Full"), date(2018, 1, 6), "full.zip", anomalies)
    apply_event(history, _record("ModfdRcrd"), date(2018, 1, 8), "delta1.zip", anomalies)
    apply_event(history, _record("TermntdRcrd", termination="2018-01-08T23:59:59Z"),
                date(2018, 1, 9), "delta2.zip", anomalies)
    versions = history[("FR0000000000", "XPAR")]
    assert not anomalies
    assert versions[0]["asof_to"] == "2018-01-07"
    assert versions[1]["asof_to"] == "2018-01-08"
    assert _observed_interval(versions[1])["to"] == "2018-01-08"
    episode = _trading_episodes(versions)[0]
    assert episode["observed_from"] == "2018-01-06"
    assert episode["observed_to"] == "2018-01-08"
    assert episode["termination_reported"] == "2018-01-08"
    assert episode["left_censored_by_initial_full"]


def test_reentry_after_termination_is_a_new_episode():
    history = {}
    anomalies = []
    for event, day in [("Full", 6), ("TermntdRcrd", 8), ("NewRcrd", 10)]:
        apply_event(history, _record(event), date(2018, 1, day), f"{day}.zip", anomalies)
    assert not anomalies
    episodes = _trading_episodes(history[("FR0000000000", "XPAR")])
    assert len(episodes) == 2
    assert episodes[0]["observed_to"] == "2018-01-07"
    assert episodes[1]["observed_from"] == "2018-01-10"


def test_retroactive_publication_does_not_overlap_observed_versions():
    history = {}
    anomalies = []
    apply_event(history, _record("Full"), date(2018, 1, 6), "full.zip", anomalies)
    retro = _record("ModfdRcrd")
    retro["publication_from_reported"] = "2018-01-08"
    apply_event(history, retro, date(2018, 1, 8), "delta1.zip", anomalies)
    apply_event(history, retro, date(2018, 1, 9), "delta2.zip", anomalies)
    versions = history[("FR0000000000", "XPAR")]
    assert versions[1]["asof_from"] == "2018-01-08"
    assert versions[1]["asof_to"] == "2018-01-08"
    assert versions[2]["asof_from"] == "2018-01-09"
    assert versions[2]["publication_from_reported"] == "2018-01-08"
    assert not anomalies


def test_future_declared_publication_is_observed_on_archive_day():
    history = {}
    anomalies = []
    future = _record("NewRcrd")
    future["publication_from_reported"] = "2018-01-09"
    apply_event(history, future, date(2018, 1, 8), "delta.zip", anomalies)
    version = history[("FR0000000000", "XPAR")][0]
    assert version["asof_from"] == "2018-01-08"
    assert version["publication_from_reported"] == "2018-01-09"
    assert [item["type"] for item in anomalies] == ["future_publication_date"]


def test_streamed_delta_and_zip_integrity(tmp_path):
    archive = tmp_path / "delta.zip"
    payload = ('<Document><FinInstrm><TermntdRcrd>'
               '<FinInstrmGnlAttrbts><Id>FR0000000000</Id><FullNm>Test</FullNm>'
               '<ClssfctnTp>ESVUFR</ClssfctnTp><NtnlCcy>EUR</NtnlCcy></FinInstrmGnlAttrbts>'
               '<TradgVnRltdAttrbts><Id>XPAR</Id><FrstTradDt>2017-01-01</FrstTradDt>'
               '<TermntnDt>2018-01-08</TermntnDt></TradgVnRltdAttrbts>'
               '<TechAttrbts><PblctnPrd><FrDt>2018-01-09</FrDt></PblctnPrd></TechAttrbts>'
               '</TermntdRcrd></FinInstrm></Document>')
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("delta.xml", payload)
    record = list(archive_records(archive, {"FR0000000000"}, {"XPAR"}))[0]
    assert record["event"] == "TermntdRcrd"
    assert record["publication_from_reported"] == "2018-01-09"
    assert _check(archive, None)["official_md5_available"] is False


def test_resume_matches_uninterrupted_replay(tmp_path, monkeypatch):
    root = tmp_path / "archives"
    (root / "2018").mkdir(parents=True)
    for filename in ("full.zip", "delta.zip"):
        (root / "2018" / filename).touch()
    index = {"full_date": "2018-01-06", "files": [
        {"date": "2018-01-06", "file": "full.zip", "type": "FULINS"},
        {"date": "2018-01-07", "file": "delta.zip", "type": "DLTINS"},
    ]}
    subset = {"rule_version": "fr_s5_subset_v1", "symbols": [
        {"symbol": "ABC", "isin_reported": "FR0000000000",
         "status": "CANDIDATE_REQUIRES_EXTERNAL_PROOFS", "provider_status_current": "Active"},
    ]}
    index_path = root / "index.json"
    subset_path = tmp_path / "subset.json"
    index_path.write_text(json.dumps(index), encoding="utf-8")
    subset_path.write_text(json.dumps(subset), encoding="utf-8")
    monkeypatch.setattr("service.fr.esma_firds_history._check",
                        lambda path, md5: {"sha256": path.name,
                                           "official_md5_available": False})
    monkeypatch.setattr("service.fr.esma_firds_history.archive_records",
                        lambda path, isins, mics: iter([_record(
                            "Full" if path.name == "full.zip" else "ModfdRcrd")]))
    prior = replay(index_path, subset_path, root, end=date(2018, 1, 6))
    prior_path = tmp_path / "prior.json"
    prior_path.write_text(json.dumps(prior), encoding="utf-8")
    resumed = replay(index_path, subset_path, root, end=date(2018, 1, 7),
                     resume_from=prior_path)
    direct = replay(index_path, subset_path, root, end=date(2018, 1, 7))
    assert resumed == direct
