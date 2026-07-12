"""Rollback a governed model champion and write an immutable audit event."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
from risk_management.model_registry import rollback_persisted_registry


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rollback du champion modèle gouverné")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--registry-path", default="artifacts/model_registry.json")
    parser.add_argument("--journal-path", default="artifacts/model_registry_journal.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    restored = rollback_persisted_registry(
        symbol=args.symbol,
        reason=args.reason,
        operator=args.operator,
        registry_path=args.registry_path,
        journal_path=args.journal_path,
    )
    print(json.dumps(restored.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())