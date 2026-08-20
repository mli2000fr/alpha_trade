import json
from pathlib import Path

d = Path("artifacts/backtesting")
for r in ["cmp_b25_h20_2025_prodparity_p23_m8",
          "cmp_b25_h20_2026_prodparity_p23_m8",
          "cmp_b25_h20_2026_prodparity_repro_h20cfg_m8"]:
    j = json.loads((d / r / "report.json").read_text(encoding="utf-8"))
    meta = j.get("run_metadata", {})
    print(f"### {r}")
    print(f"  git_commit_sha: {meta.get('git_commit_sha')}")
    print(f"  git_dirty:      {meta.get('git_dirty')}")
    print(f"  generated_at:   {meta.get('generated_at_utc')}")
    print(f"  dataset_hash:   {meta.get('dataset_hash')}")
