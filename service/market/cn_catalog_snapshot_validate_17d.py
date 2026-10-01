"""Validate a CN 17-D rollback snapshot without changing tasks or catalogs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

import yaml

from service.market.cn_catalog_preflight_17d import RESEARCH_BATCHES, ROOT

TASKS = {
    "AlphaTrade-CnDragonTigerBeforeOpen": ("cn_dragon_tiger_before_open", "cn_dragon_tiger_launcher_15d6.ps1"),
    "AlphaTrade-CnDragonTigerDailyMatch": ("cn_dragon_tiger_daily_match", "cn_dragon_tiger_daily_launcher_15d10.ps1"),
    "AlphaTrade-CnDragonTigerAfterClose": ("cn_dragon_tiger_after_close", "cn_dragon_tiger_launcher_15d6.ps1"),
    "AlphaTrade-CnOracleProspectiveDaily": ("cn_oracle_prospective_daily", "cn_oracle_daily_launcher_15d9.ps1"),
}
NS = {"task": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


def validate(snapshot: Path, *, current_root: Path | None = None) -> dict:
    """Check hashes, legacy ownership and scheduler actions in an exported snapshot."""
    snapshot = snapshot.resolve()
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8-sig"))
    blockers = []
    expected_names = {"batch.yaml", "batch_cn.yaml"} | {f"{name}.xml" for name in TASKS}
    entries = manifest.get("files") or []
    if {item.get("name") for item in entries} != expected_names or len(entries) != len(expected_names):
        blockers.append("snapshot_file_set_mismatch")
    for item in entries:
        name = str(item.get("name", ""))
        path = snapshot / name
        if path.resolve().parent != snapshot or not path.is_file():
            blockers.append(f"unsafe_or_missing_file:{name}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item.get("sha256"):
            blockers.append(f"hash_mismatch:{name}")
    if blockers:
        return {"status": "BLOCKED", "blockers": sorted(set(blockers)),
                "snapshot": str(snapshot), "scheduler_changed": False}

    us = yaml.safe_load((snapshot / "batch.yaml").read_text(encoding="utf-8")) or {}
    cn = yaml.safe_load((snapshot / "batch_cn.yaml").read_text(encoding="utf-8")) or {}
    if not isinstance(us, dict) or not isinstance(cn, dict):
        blockers.append("catalog_not_mapping")
    else:
        for name in RESEARCH_BATCHES:
            cfg = us.get(name)
            if not isinstance(cfg, dict) or cfg.get("enabled") is not True or cfg.get("status") != "RESEARCH_ONLY":
                blockers.append(f"legacy_section_invalid:{name}")
            if name in cn:
                blockers.append(f"duplicate_section:{name}")

    for task_name, (batch_name, launcher) in TASKS.items():
        try:
            xml = ElementTree.fromstring((snapshot / f"{task_name}.xml").read_bytes())
        except ElementTree.ParseError:
            blockers.append(f"invalid_task_xml:{task_name}")
            continue
        command = xml.findtext("task:Actions/task:Exec/task:Command", namespaces=NS) or ""
        arguments = xml.findtext("task:Actions/task:Exec/task:Arguments", namespaces=NS) or ""
        logon = xml.findtext("task:Principals/task:Principal/task:LogonType", namespaces=NS)
        triggers = xml.find("task:Triggers", NS)
        if (Path(command).name.lower() != "wscript.exe"
                or launcher.lower() not in arguments.lower()
                or f'"{batch_name}"' not in arguments
                or "batch_cn.yaml" in arguments.lower()
                or "run_forward_pit_hidden.vbs" not in arguments.lower()
                or logon != "InteractiveToken"
                or triggers is None or len(triggers) != 1):
            blockers.append(f"task_action_mismatch:{task_name}")

    if manifest.get("task_definitions_exported") != 4 or manifest.get("scheduler_changed") is not False:
        blockers.append("snapshot_manifest_invalid")
    if current_root is not None:
        for catalog in ("batch.yaml", "batch_cn.yaml"):
            current = current_root / catalog
            if not current.is_file() or current.read_bytes() != (snapshot / catalog).read_bytes():
                blockers.append(f"snapshot_stale:{catalog}")
    return {"status": "VALID_LEGACY_SNAPSHOT" if not blockers else "BLOCKED",
            "blockers": sorted(set(blockers)), "snapshot": str(snapshot),
            "scheduler_changed": False, "catalogs_modified": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--current-root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(validate(args.snapshot, current_root=args.current_root),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
