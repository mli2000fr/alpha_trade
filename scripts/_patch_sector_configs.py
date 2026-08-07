"""Patch per-sector config.json files with run_id from DB."""
import sys, json
sys.path.insert(0, "f:/projets")
from ihm.services.db import get_engine
from sqlalchemy import text
from pathlib import Path

e = get_engine()
batch_dir = Path("f:/projets/artifacts/models/model-factory-20260805234750-f63478")

with e.connect() as conn:
    r = conn.execute(
        text("SELECT run_id, symbol FROM model_training_run WHERE batch_id = :bid"),
        {"bid": "model-factory-20260805234750-f63478"},
    )
    sector_runs = {row[1]: row[0] for row in r}
print("Sector runs from DB:")
for s, rid in sorted(sector_runs.items()):
    print(f"  {s} -> {rid}")

patched = 0
for sector_dir in sorted(batch_dir.glob("_sector_*")):
    config_path = sector_dir / "config.json"
    if not config_path.exists():
        continue
    cfg = json.loads(config_path.read_text())
    sector_name = cfg.get("sector", "")
    rid = sector_runs.get(sector_name)
    if not rid:
        print(f"SKIP {sector_dir.name}: no DB run_id for sector={sector_name}")
        continue
    if cfg.get("run_id") == rid:
        print(f"OK   {sector_dir.name}: already has run_id={rid}")
        continue
    cfg["run_id"] = rid
    config_path.write_text(json.dumps(cfg, indent=2, default=str))
    print(f"FIX  {sector_dir.name}: run_id={rid}")
    patched += 1

print(f"\nPatched {patched} config(s). Now re-run ML Predict for correct run_ids.")
