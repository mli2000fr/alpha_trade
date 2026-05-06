"""Sprint S4 (A-023) — script de purge des `artifacts/`.

Applique la politique documentée dans
``doc/artifacts_retention_policy.md``. Dry-run par défaut.

Usage::

    python scripts/prune_artifacts.py                  # dry-run
    python scripts/prune_artifacts.py --apply          # exécution réelle
    python scripts/prune_artifacts.py --rule eodhd_cache --apply
    python scripts/prune_artifacts.py --older-than 14d --apply

Exit code : 0 toujours (politique = best-effort, jamais bloquant pour la CI).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOGGER = logging.getLogger("prune_artifacts")

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = ROOT / "artifacts"
DEFAULT_REPORT = ARTIFACTS_DIR / "prune_report.json"

DURATION_RE = re.compile(r"^(\d+)\s*([dhm])$", re.IGNORECASE)


def parse_duration(value: str) -> timedelta:
    m = DURATION_RE.match(value.strip())
    if not m:
        raise argparse.ArgumentTypeError(
            f"durée invalide '{value}', attendu '<n>d', '<n>h' ou '<n>m'"
        )
    n = int(m.group(1))
    unit = m.group(2).lower()
    return {"d": timedelta(days=n), "h": timedelta(hours=n), "m": timedelta(minutes=n)}[unit]


@dataclass(frozen=True, slots=True)
class RetentionRule:
    name: str                # short id (sous-dossier sous artifacts/)
    subdir: str
    max_age_days: int | None  # None = illimité
    max_count: int | None     # None = pas de plafond
    keep_globs: tuple[str, ...] = field(default_factory=tuple)
    criticality: str = "P3"
    description: str = ""


# Single source of truth — synchroniser avec doc/artifacts_retention_policy.md
RETENTION_RULES: tuple[RetentionRule, ...] = (
    RetentionRule("eodhd_cache", "eodhd_cache", 90, None, (), "P3",
                  "Tracker bulk EOD JSON"),
    RetentionRule("finnhub_cache", "finnhub_cache", 30, None, (), "P3",
                  "Profils société (TTL fichier 7j)"),
    RetentionRule("ihm_pipeline_runs", "ihm_pipeline_runs", 60, 200, (), "P2",
                  "run_summary IHM pipeline"),
    RetentionRule("ihm_backtesting_runs", "ihm_backtesting_runs", 180, 100, (), "P2",
                  "Reports backtest IHM"),
    RetentionRule("ihm_preferences", "ihm_preferences", None, None, (), "P3",
                  "Préférences utilisateur (jamais purgé)"),
    RetentionRule("models", "models", 365, None,
                  ("**/champion*", "**/CHAMPION*", "**/*.champion.*"),
                  "P1", "Checkpoints ML (champion ∞)"),
    RetentionRule("signal_aggregator_runs", "signal_aggregator_runs", 60, None, (), "P3",
                  "Runs sentiment"),
)


@dataclass
class PruneOutcome:
    rule: str
    inspected: int = 0
    kept: int = 0
    deleted: int = 0
    bytes_freed: int = 0
    errors: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "rule": self.rule,
            "inspected": self.inspected,
            "kept": self.kept,
            "deleted": self.deleted,
            "bytes_freed": self.bytes_freed,
            "errors": self.errors,
        }


def _matches_keep(path: Path, base: Path, patterns: tuple[str, ...]) -> bool:
    if not patterns:
        return False
    rel = path.relative_to(base)
    for pat in patterns:
        if rel.match(pat):
            return True
    return False


def _enumerate_files(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return [p for p in base.rglob("*") if p.is_file()]


def _select_to_delete(
    rule: RetentionRule,
    base: Path,
    *,
    now: datetime,
    age_override: timedelta | None,
) -> tuple[list[Path], list[Path]]:
    files = _enumerate_files(base)
    if not files:
        return [], []

    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    keep: list[Path] = []
    delete: list[Path] = []

    cutoff: datetime | None = None
    if age_override is not None:
        cutoff = now - age_override
    elif rule.max_age_days is not None:
        cutoff = now - timedelta(days=rule.max_age_days)

    for idx, path in enumerate(files):
        if _matches_keep(path, base, rule.keep_globs):
            keep.append(path)
            continue
        too_old = False
        if cutoff is not None:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            too_old = mtime < cutoff
        too_many = rule.max_count is not None and idx >= rule.max_count
        if too_old or too_many:
            delete.append(path)
        else:
            keep.append(path)
    return keep, delete


def prune(
    rules: tuple[RetentionRule, ...],
    *,
    artifacts_root: Path = ARTIFACTS_DIR,
    apply: bool = False,
    age_override: timedelta | None = None,
    rule_filter: str | None = None,
    now: datetime | None = None,
) -> list[PruneOutcome]:
    now = now or datetime.now(timezone.utc)
    outcomes: list[PruneOutcome] = []
    for rule in rules:
        if rule_filter and rule.name != rule_filter:
            continue
        base = artifacts_root / rule.subdir
        outcome = PruneOutcome(rule=rule.name)
        keep, delete = _select_to_delete(rule, base, now=now, age_override=age_override)
        outcome.inspected = len(keep) + len(delete)
        outcome.kept = len(keep)
        for path in delete:
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            if apply:
                try:
                    path.unlink()
                    outcome.deleted += 1
                    outcome.bytes_freed += size
                except OSError as exc:
                    LOGGER.warning("delete failed %s: %s", path, exc)
                    outcome.errors += 1
            else:
                outcome.deleted += 1
                outcome.bytes_freed += size
        outcomes.append(outcome)
        LOGGER.info(
            "rule=%s inspected=%d kept=%d %s=%d bytes=%d",
            rule.name, outcome.inspected, outcome.kept,
            "deleted" if apply else "would_delete",
            outcome.deleted, outcome.bytes_freed,
        )
    return outcomes


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    p.add_argument("--apply", action="store_true",
                   help="Effectue la suppression (sinon dry-run).")
    p.add_argument("--rule", default=None,
                   help="Limite l'exécution à une règle (nom du sous-dossier).")
    p.add_argument("--older-than", type=parse_duration, default=None,
                   help="Override d'âge, format <n>d|h|m (e.g. 30d).")
    p.add_argument("--artifacts-root", type=Path, default=ARTIFACTS_DIR,
                   help="Racine des artifacts (override pour tests).")
    p.add_argument("--report-out", type=Path, default=DEFAULT_REPORT,
                   help="Chemin du rapport JSON.")
    p.add_argument("--json", action="store_true",
                   help="Affiche le rapport JSON sur stdout.")
    p.add_argument("--log-level", default="INFO",
                   choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(message)s")
    outcomes = prune(
        RETENTION_RULES,
        artifacts_root=args.artifacts_root,
        apply=args.apply,
        age_override=args.older_than,
        rule_filter=args.rule,
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "applied": bool(args.apply),
        "rules": [o.to_dict() for o in outcomes],
        "totals": {
            "inspected": sum(o.inspected for o in outcomes),
            "kept": sum(o.kept for o in outcomes),
            "deleted": sum(o.deleted for o in outcomes),
            "bytes_freed": sum(o.bytes_freed for o in outcomes),
            "errors": sum(o.errors for o in outcomes),
        },
    }
    try:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except OSError as exc:
        LOGGER.warning("Cannot write report: %s", exc)
    if args.json:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

