import pytest

from service.fr.opening_evidence_overlay import qualify_no_open


def test_official_carried_close_does_not_invent_open():
    qualify_no_open({"open": None, "high": None, "low": None, "volume": 0, "close": 9550})


@pytest.mark.parametrize("change", [{"open": 9550}, {"volume": 1}, {"volume": None}, {"close": 9500}])
def test_unknown_or_contradictory_no_open_blocked(change):
    row = {"open": None, "high": None, "low": None, "volume": 0, "close": 9550}
    row.update(change)
    with pytest.raises(ValueError):
        qualify_no_open(row)
