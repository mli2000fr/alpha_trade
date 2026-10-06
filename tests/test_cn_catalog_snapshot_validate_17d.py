"""A 17-D rollback export must be restorable, unique and unchanged."""

import hashlib
import json
from pathlib import Path

import yaml

from service.market.cn_catalog_snapshot_validate_17d import TASKS, validate


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    snapshot, current = tmp_path / "snapshot", tmp_path / "current"
    snapshot.mkdir()
    current.mkdir()
    us = {batch: {"enabled": True, "status": "RESEARCH_ONLY"}
          for batch, _launcher in TASKS.values()}
    cn = {"defaults": {"database_alias": "cn_primary"}}
    for folder in (snapshot, current):
        (folder / "batch.yaml").write_text(yaml.safe_dump(us), encoding="utf-8")
        (folder / "batch_cn.yaml").write_text(yaml.safe_dump(cn), encoding="utf-8")
    for name, (batch, launcher) in TASKS.items():
        xml = ("<?xml version='1.0' encoding='UTF-16'?>"
               "<Task xmlns='http://schemas.microsoft.com/windows/2004/02/mit/task'>"
               "<Triggers><CalendarTrigger /></Triggers>"
               "<Principals><Principal><LogonType>InteractiveToken</LogonType></Principal></Principals>"
               "<Actions><Exec><Command>wscript.exe</Command><Arguments>"
               f'"run_forward_pit_hidden.vbs" "{launcher}" "{batch}"'
               "</Arguments></Exec></Actions></Task>")
        (snapshot / f"{name}.xml").write_bytes(xml.encode("utf-16"))
    files = [{"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
             for path in snapshot.iterdir()]
    (snapshot / "manifest.json").write_text(json.dumps({
        "files": files, "task_definitions_exported": 4, "scheduler_changed": False,
    }), encoding="utf-8")
    return snapshot, current


def _refresh_hash(snapshot: Path, name: str) -> None:
    path = snapshot / name
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    next(item for item in manifest["files"] if item["name"] == name)["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (snapshot / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_valid_legacy_snapshot_and_stale_catalog(tmp_path):
    snapshot, current = _fixture(tmp_path)
    assert validate(snapshot, current_root=current)["status"] == "VALID_LEGACY_SNAPSHOT"
    (current / "batch.yaml").write_text("changed: true", encoding="utf-8")
    assert "snapshot_stale:batch.yaml" in validate(snapshot, current_root=current)["blockers"]


def test_hash_and_declared_encoding_must_both_be_valid(tmp_path):
    snapshot, current = _fixture(tmp_path)
    name = f"{next(iter(TASKS))}.xml"
    path = snapshot / name
    path.write_bytes(path.read_bytes() + b"changed")
    assert f"hash_mismatch:{name}" in validate(snapshot, current_root=current)["blockers"]
    # Correct hash cannot disguise a UTF-8 file declaring itself UTF-16.
    path.write_bytes("<?xml version='1.0' encoding='UTF-16'?><Task/>".encode("utf-8"))
    _refresh_hash(snapshot, name)
    assert f"invalid_task_xml:{next(iter(TASKS))}" in validate(snapshot, current_root=current)["blockers"]


def test_duplicate_section_and_changed_launcher_block(tmp_path):
    snapshot, current = _fixture(tmp_path)
    cn = yaml.safe_load((snapshot / "batch_cn.yaml").read_text(encoding="utf-8"))
    cn[next(iter(TASKS.values()))[0]] = {"enabled": True}
    (snapshot / "batch_cn.yaml").write_text(yaml.safe_dump(cn), encoding="utf-8")
    _refresh_hash(snapshot, "batch_cn.yaml")
    name = f"{next(iter(TASKS))}.xml"
    path = snapshot / name
    xml = path.read_bytes().decode("utf-16").replace("run_forward_pit_hidden.vbs", "wrong.vbs")
    path.write_bytes(xml.encode("utf-16"))
    _refresh_hash(snapshot, name)
    blockers = validate(snapshot, current_root=current)["blockers"]
    assert any(item.startswith("duplicate_section:") for item in blockers)
    assert any(item.startswith("task_action_mismatch:") for item in blockers)
