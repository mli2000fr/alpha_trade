import json
from datetime import date

from service.fr.esma_firds_gap_audit import audit


def test_gap_audit_distinguishes_missing_session_from_download(tmp_path):
    full = "FULINS_E_20180106_01of01.zip"
    folder = tmp_path / "2018"
    folder.mkdir()
    (folder / full).write_bytes(b"already-verified-archive")
    (tmp_path / "index.json").write_text(json.dumps({"full_date": "2018-01-06", "files": [
        {"date": "2018-01-06", "type": "FULINS_E", "file": full}]}), encoding="utf-8")
    (tmp_path / "download_state.json").write_text(json.dumps({"files": [
        {"file": full, "sha256": "evidence"}], "failed": []}), encoding="utf-8")

    result = audit(tmp_path, end=date(2018, 1, 8))
    assert result["download_verified_as_indexed"] is True
    assert result["delta_gaps_on_xpar_sessions"] == ["2018-01-08"]
    assert result["publication_continuity_verified"] is False


def test_gap_audit_detects_conflicting_file_generations(tmp_path):
    names = ["FULINS_E_20180106_01of01.zip", "DLTINS_20180107_01of01.zip",
             "DLTINS_20180107_01of02.zip", "DLTINS_20180107_02of02.zip"]
    folder = tmp_path / "2018"
    folder.mkdir()
    for name in names:
        (folder / name).write_bytes(b"already-verified-archive")
    (tmp_path / "index.json").write_text(json.dumps({"full_date": "2018-01-06", "files": [
        {"date": "2018-01-06" if name.startswith("FUL") else "2018-01-07",
         "type": "FULINS_E" if name.startswith("FUL") else "DLTINS", "file": name}
        for name in names]}), encoding="utf-8")
    (tmp_path / "download_state.json").write_text(json.dumps({"files": [
        {"file": name, "sha256": "evidence"} for name in names], "failed": []}), encoding="utf-8")

    result = audit(tmp_path, end=date(2018, 1, 7))
    assert result["download_verified_as_indexed"] is True
    assert result["part_groups_consistent"] is False
    assert result["incomplete_part_groups"][0]["declared_totals"] == [1, 2]
