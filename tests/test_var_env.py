import csv
from pathlib import Path

import pytest

from ihm.services import varEnv


@pytest.mark.unit
def test_get_var_env_filters_by_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(varEnv, "get_conf_var_env", lambda: ["LOGIN_DB", "PASSWORD_DB"])
    monkeypatch.setenv("LOGIN_DB", "demo_user")
    monkeypatch.setenv("PASSWORD_DB", "demo_pass")
    monkeypatch.setenv("SHOULD_NOT_BE_EXPORTED", "hidden")

    csv_path = Path(varEnv.get_var_env())

    assert csv_path.exists()
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))

    assert rows == [
        ["Variable", "Valeur"],
        ["LOGIN_DB", "demo_user"],
        ["PASSWORD_DB", "demo_pass"],
    ]


@pytest.mark.unit
def test_set_var_env_applies_only_allowed_keys(monkeypatch) -> None:
    monkeypatch.setattr(varEnv, "get_conf_var_env", lambda: ["LOGIN_DB"])
    monkeypatch.delenv("LOGIN_DB", raising=False)
    monkeypatch.delenv("PASSWORD_DB", raising=False)

    payload = b"Variable,Valeur\nLOGIN_DB,demo_user\nPASSWORD_DB,secret\n"

    result = varEnv.set_var_env(payload, apply=True)

    assert result == {
        "applied": {"LOGIN_DB": "demo_user"},
        "skipped": ["PASSWORD_DB"],
    }
    assert varEnv.os.environ["LOGIN_DB"] == "demo_user"
    assert "PASSWORD_DB" not in result["applied"]


@pytest.mark.unit
def test_set_var_env_does_not_apply_when_apply_is_false(monkeypatch) -> None:
    monkeypatch.setattr(varEnv, "get_conf_var_env", lambda: ["LOGIN_DB"])
    monkeypatch.delenv("LOGIN_DB", raising=False)

    payload = b"Variable,Valeur\nLOGIN_DB,demo_user\n"

    result = varEnv.set_var_env(payload, apply=False)

    assert result == {"applied": {"LOGIN_DB": "demo_user"}, "skipped": []}
    assert "LOGIN_DB" not in varEnv.os.environ

