import json
from datetime import date

import pytest

from service.fr.esma_firds_annual_chain import (
    _select_latest_full_date,
    validate_history,
)


def test_select_latest_full_date_requires_complete_name_and_honors_end() -> None:
    names = [
        "FULINS_E_20221224_01of02.zip",
        "FULINS_E_20221224_02of02.zip",
        "FULINS_E_20221231_01of02.zip",
        "FULINS_E_20221231_02of02.zip",
        "FULINS_E_20230107_01of02.zip",
        "DLTINS_20221231_01of01.zip",
    ]
    assert _select_latest_full_date(names, date(2022, 12, 31)) == date(2022, 12, 31)


def test_validate_history_accepts_only_complete_exact_report(tmp_path) -> None:
    path = tmp_path / "history.json"
    path.write_text(json.dumps({
        "end": "2022-12-31", "complete": True,
        "files_processed": 10, "files_indexed": 10, "missing_files": [],
    }), encoding="utf-8")
    assert validate_history(path, date(2022, 12, 31))["complete"] is True


@pytest.mark.parametrize("update", [
    {"complete": False},
    {"files_processed": 9},
    {"missing_files": ["x.zip"]},
    {"end": "2022-12-30"},
])
def test_validate_history_rejects_unsafe_resume(tmp_path, update) -> None:
    payload = {
        "end": "2022-12-31", "complete": True,
        "files_processed": 10, "files_indexed": 10, "missing_files": [],
    }
    payload.update(update)
    path = tmp_path / "history.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_history(path, date(2022, 12, 31))
