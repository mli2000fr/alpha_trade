import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from modelFactory.oracle_prospective_journal import (
    canary_input_preflight, write_prospective_score_journal,
)


def scores(day: str) -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.to_datetime([day, day]),
        "symbol": ["ABC", "XYZ"],
        "proba_extreme": [0.1, 0.9],
        "champion_t_start": ["2025-01-01"] * 2,
        "future_return": [0.2, -0.2],
        "oracle_extreme10": [1, 1],
    })


class ProspectiveScoreJournalTests(unittest.TestCase):
    def test_preflight_blocks_stale_and_missing_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            observed = datetime(2026, 9, 30, 20, 0, tzinfo=UTC)
            config = {"batch_id": "batch", "baseline_shadow_dir": "baseline"}
            result = canary_input_preflight(
                config, "2026-07-10", observed, workspace_root=Path(directory))
            self.assertEqual(result["status"], "BLOCKED_PREFLIGHT")
            self.assertEqual(set(result["blockers"]), {
                "MISSING_ORACLE_CHAMPIONS", "MISSING_BASELINE_SHADOW_PARTS",
                "STALE_LATEST_BENCHMARK_DATE",
            })

    def test_preflight_allows_fresh_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            champion = root / "artifacts/models/oracle/champions/batch/oracle_champions.json"
            champion.parent.mkdir(parents=True)
            champion.write_text("[]", encoding="utf-8")
            parts = root / "baseline/parts"
            parts.mkdir(parents=True)
            (parts / "part-00000.parquet").write_bytes(b"sample")
            result = canary_input_preflight(
                {"batch_id": "batch", "baseline_shadow_dir": "baseline"},
                "2026-09-30", datetime(2026, 9, 30, 20, 0, tzinfo=UTC),
                workspace_root=root,
            )
            self.assertEqual(result["status"], "READY")

    def test_fresh_journal_records_availability_and_excludes_future_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            started = datetime(2026, 9, 30, 20, 0, tzinfo=UTC)
            available = started + timedelta(minutes=5)
            kwargs = dict(artifact_dir=root, batch_id="batch",
                          prediction_date="2026-09-30", run_started_at=started,
                          observed_at=available)
            result = write_prospective_score_journal(scores("2026-09-30"), **kwargs)
            self.assertEqual(result["status"], "CANDIDATE_INPUT_PIT_UNVERIFIED")
            self.assertEqual(result["rows"], 2)
            self.assertFalse(result["trading_eligible"])
            rows = [json.loads(line) for line in
                    (root / "prospective_score_journal.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["oracle_top20"] for row in rows], [False, True])
            self.assertEqual(len({row["score_artifact_available_at_utc"] for row in rows}), 1)
            self.assertNotIn("future_return", rows[0])
            self.assertNotIn("oracle_extreme10", rows[0])
            with self.assertRaisesRegex(FileExistsError, "immutable"):
                write_prospective_score_journal(scores("2026-09-30"), **kwargs)

    def test_stale_replay_cannot_claim_prospective_availability(self):
        with tempfile.TemporaryDirectory() as directory:
            observed = datetime(2026, 9, 30, 20, 0, tzinfo=UTC)
            result = write_prospective_score_journal(
                scores("2026-07-10"), artifact_dir=Path(directory), batch_id="batch",
                prediction_date="2026-07-10", run_started_at=observed,
                observed_at=observed,
            )
            self.assertEqual(result["status"], "SKIPPED_STALE_DATE")
            self.assertFalse((Path(directory) / "prospective_score_journal.jsonl").exists())

    def test_fresh_journal_rejects_duplicate_symbol(self):
        with tempfile.TemporaryDirectory() as directory:
            observed = datetime(2026, 9, 30, 20, 0, tzinfo=UTC)
            frame = scores("2026-09-30")
            frame.loc[1, "symbol"] = "ABC"
            with self.assertRaisesRegex(ValueError, "symbol identity"):
                write_prospective_score_journal(
                    frame, artifact_dir=Path(directory), batch_id="batch",
                    prediction_date="2026-09-30", run_started_at=observed,
                    observed_at=observed,
                )


if __name__ == "__main__":
    unittest.main()
