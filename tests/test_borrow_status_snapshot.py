"""Regression coverage for Alpaca borrow status snapshot normalization."""
from __future__ import annotations

import unittest
from contextlib import contextmanager
from unittest.mock import patch

from service.forward_pit import batch as forward_batch


class BorrowStatusSnapshotTest(unittest.TestCase):
    def test_active_duplicate_and_new_status_are_authoritative(self) -> None:
        saved: list[dict] = []

        class FakeConnection:
            def execute(self, _statement, params):
                saved.append(params)
                return type("Result", (), {"rowcount": 1})()

        class FakeEngine:
            @contextmanager
            def begin(self):
                yield FakeConnection()

        assets = [
            {"symbol": "AAA", "class": "us_equity", "status": "inactive",
             "tradable": False, "shortable": False},
            {"symbol": "AAA", "class": "us_equity", "status": "active",
             "tradable": True, "shortable": True,
             "easy_to_borrow": False, "borrow_status": "easy_to_borrow"},
            {"symbol": "BBB", "class": "us_equity", "status": "active",
             "tradable": True, "shortable": True,
             "easy_to_borrow": True, "borrow_status": "hard_to_borrow"},
            {"symbol": "CCC", "class": "us_equity", "status": "active",
             "tradable": True, "shortable": True},
        ]
        with patch.object(forward_batch, "fetch_alpaca_assets", return_value=assets), \
             patch.object(forward_batch, "_collection_symbols", return_value=["AAA", "BBB", "CCC"]), \
             patch.object(forward_batch, "_raw"):
            outcome = forward_batch.borrow_status_snapshot(FakeEngine(), {}, "test", False)
        self.assertEqual(outcome.persisted, 3)
        self.assertEqual({row["symbol"]: row["borrow"] for row in saved}, {
            "AAA": "EASY", "BBB": "LOCATE_REQUIRED", "CCC": "LOCATE_REQUIRED",
        })


if __name__ == "__main__":
    unittest.main()
