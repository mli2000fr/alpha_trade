"""Sprint S25.4 — Tests du script ``audit_private_api_exposure.py``.

Vérifie :
* la collecte des symboles publics et expositions privées sur un
  workspace temporaire ;
* l'écriture du rapport JSON ;
* le mode ``--apply`` (dry-run) qui produit
  ``suggested_patches.json`` sans modifier les fichiers source ;
* l'idempotence du mode ``--apply`` (re-exécution = même payload modulo
  ``generated_at``).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import audit_private_api_exposure as audit


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Crée un mini repo avec un symbole privé exposé."""
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "__init__.py").write_text("")
    (tmp_path / "core" / "secrets.py").write_text(
        "def public_get_secret():\n"
        "    return 'public'\n"
        "\n"
        "def _private_helper():\n"
        "    return 'private'\n"
        "\n"
        "PUBLIC_CONST = 1\n",
        encoding="utf-8",
    )
    (tmp_path / "service").mkdir()
    (tmp_path / "service" / "__init__.py").write_text("")
    (tmp_path / "service" / "user.py").write_text(
        "from core.secrets import _private_helper\n"
        "\n"
        "def use():\n"
        "    return _private_helper()\n",
        encoding="utf-8",
    )
    (tmp_path / "risk_management").mkdir()
    (tmp_path / "risk_management" / "__init__.py").write_text("")

    monkeypatch.setattr(audit, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(audit, "GOLDEN_FILE",
                        tmp_path / "doc" / "api_v1_public_symbols.txt")
    return tmp_path


def test_collect_public_symbols(fake_repo: Path) -> None:
    public = audit._collect_public_symbols(audit.SCANNED_PACKAGES)
    qnames = {s.qualname() for s in public}
    assert "core.secrets.public_get_secret" in qnames
    assert "core.secrets.PUBLIC_CONST" in qnames
    assert all("_private_helper" not in q for q in qnames)


def test_collect_private_exposures(fake_repo: Path) -> None:
    # service.user importe core.secrets._private_helper → exposition.
    private = audit._collect_private_exposures(audit.SCANNED_PACKAGES)
    assert any(
        e.symbol == "_private_helper" and e.source_module == "core.secrets"
        for e in private
    )


def test_main_apply_emits_suggested_patches(
    fake_repo: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "out"
    rc = audit.main(["--out", str(out_dir), "--apply"])
    assert rc == 0
    patches = list(out_dir.rglob("suggested_patches.json"))
    assert len(patches) == 1
    payload = json.loads(patches[0].read_text("utf-8"))
    assert payload["mode"] == "dry-run"
    assert payload["n_suggestions"] >= 1
    sug = payload["suggestions"][0]
    assert sug["symbol"] == "_private_helper"
    assert sug["source_module"] == "core.secrets"
    assert sug["target_file"] == "core\\secrets.py" or \
           sug["target_file"] == "core/secrets.py"
    assert sug["definition_line"] is not None
    assert "@deprecated_v1" in sug["suggested_patch"]["decorator"]


def test_apply_does_not_modify_source(fake_repo: Path, tmp_path: Path) -> None:
    src = (fake_repo / "core" / "secrets.py").read_text("utf-8")
    audit.main(["--out", str(tmp_path / "out"), "--apply"])
    assert (fake_repo / "core" / "secrets.py").read_text("utf-8") == src


def test_apply_is_idempotent(fake_repo: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    audit.main(["--out", str(out_dir), "--apply"])
    p1 = json.loads(next(out_dir.rglob("suggested_patches.json"))
                     .read_text("utf-8"))
    audit.main(["--out", str(out_dir), "--apply"])
    p2 = json.loads(next(out_dir.rglob("suggested_patches.json"))
                     .read_text("utf-8"))
    p1.pop("generated_at"); p2.pop("generated_at")
    assert p1 == p2


def test_strict_fails_on_new_public_symbol(
    fake_repo: Path, tmp_path: Path
) -> None:
    # Pas de golden → strict ne fail pas (rien à comparer).
    rc = audit.main(["--out", str(tmp_path / "out"), "--strict"])
    assert rc == 0

    # Initialise le golden avec un seul symbole bidon → tous les
    # symboles réels deviennent "nouveaux" non listés.
    audit.GOLDEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    audit.GOLDEN_FILE.write_text("# golden\nplaceholder.symbol\n", "utf-8")
    rc = audit.main(["--out", str(tmp_path / "out2"), "--strict"])
    assert rc == 1


