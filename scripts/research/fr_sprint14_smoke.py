"""Launch and follow one FR research reproduction through the IHM registry."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    from ihm.services.backtesting_registry import start_backtesting_run, poll_backtesting_run, stop_backtesting_run
    from service.fr.research_replay_14b import FRResearchReplayOptions
    record = start_backtesting_run("fr-research-replay", "FR_EQ Sprint14 smoke — EUR", FRResearchReplayOptions())
    print(f"RUN_ID={record.run_id}", flush=True)
    started = time.monotonic()
    while True:
        state = poll_backtesting_run(record.run_id)
        if state["status"] not in ("starting", "running"):
            print(json.dumps(state, ensure_ascii=False, indent=2), flush=True)
            if state["status"] != "completed":
                raise RuntimeError(f"Smoke FR failed: {state['status']}")
            break
        if time.monotonic() - started > 120:
            stop_backtesting_run(record.run_id)
            raise TimeoutError("Smoke FR stopped after 120 seconds")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
