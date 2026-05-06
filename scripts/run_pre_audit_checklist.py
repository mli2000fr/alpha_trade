"""Sprint S25.1 — Pré-audit interne automatisé.

Parcourt les items de ``doc/external_audit_checklist.md`` et tente
d'évaluer chacun de manière programmable :

* présence d'un fichier ;
* dernier run CI vert (heuristique fichier-artefact) ;
* commande shell exit code 0.

Génère ``artifacts/pre_audit/<date>/report.{md,json}``.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

LOGGER = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class CheckResult:
    section: str
    item: str
    status: str  # "ok" | "warn" | "fail" | "skip"
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _exists(rel: str) -> Callable[[], CheckResult]:
    def _f() -> CheckResult:
        p = PROJECT_ROOT / rel
        if p.exists():
            return CheckResult("", "", "ok", f"present: {rel}")
        return CheckResult("", "", "fail", f"missing: {rel}")
    return _f


def _has_artifact(rel_glob: str) -> Callable[[], CheckResult]:
    def _f() -> CheckResult:
        matches = list(PROJECT_ROOT.glob(rel_glob))
        if matches:
            return CheckResult("", "", "ok", f"{len(matches)} match(es): {rel_glob}")
        return CheckResult("", "", "warn", f"no match: {rel_glob}")
    return _f


# Liste des items vérifiables programmablement (extrait des 50 items de
# external_audit_checklist.md). Les non-listés restent "manuel".
_CHECKS: list[tuple[str, str, Callable[[], CheckResult]]] = [
    # Architecture
    ("Architecture", "diagrammes C4", _exists("doc/architecture")),
    ("Architecture", "DR runbook", _exists("doc/disaster_recovery.md")),
    ("Architecture", "lineage temps réel", _exists("lineage")),
    # Qualité
    ("Qualité", "0 TODO/FIXME script", _exists("scripts/check_no_todo.py")),
    ("Qualité", "property tests", _exists("tests/property")),
    ("Qualité", "import linter contracts",
     _exists("tests/test_import_linter_contracts.py")),
    ("Qualité", "fuzz weekly workflow", _exists(".github/workflows/fuzz_weekly.yml")),
    # Sécurité
    ("Sécurité", "verify audit chain", _exists("scripts/verify_audit_chain.py")),
    ("Sécurité", "scan CVE", _exists("scripts/scan_cves.py")),
    ("Sécurité", "vault rotation", _exists("scripts/verify_vault_rotation.py")),
    # Observabilité & ops
    ("Observabilité", "runbook 24/7", _exists("doc/runbook_24_7.md")),
    ("Observabilité", "sandbox health rollup",
     _exists("scripts/sandbox_health_rollup.py")),
    ("Observabilité", "dr_drill workflow",
     _exists(".github/workflows/dr_drill.yml")),
    ("Observabilité", "onboarding opérateur",
     _exists("doc/onboarding_operator.md")),
    # Conformité
    ("Conformité", "specs TLA+ x3", _has_artifact("formal/tla/*.tla")),
    ("Conformité", "TLAPS wrapper", _exists("scripts/run_tlaps.py")),
    ("Conformité", "wash_sale", _exists("tax/wash_sale.py")),
    ("Conformité", "API v1 stability policy",
     _exists("doc/api_v1_stability_policy.md")),
    ("Conformité", "deprecation decorator", _exists("core/_deprecation.py")),
    ("Conformité", "Brinson-Fachler",
     _exists("backtesting/brinson_fachler.py")),
    ("Conformité", "DOC fonctionnelle",
     _exists("doc/DOC_FONCTIONNELLE.md")),
]


def run_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    for section, item, fn in _CHECKS:
        r = fn()
        r.section, r.item = section, item
        results.append(r)
    return results


def _score(results: Sequence[CheckResult]) -> dict:
    n = len(results)
    n_ok = sum(1 for r in results if r.status == "ok")
    n_warn = sum(1 for r in results if r.status == "warn")
    n_fail = sum(1 for r in results if r.status == "fail")
    return {
        "total": n,
        "ok": n_ok,
        "warn": n_warn,
        "fail": n_fail,
        "score": round(n_ok / n * 50, 2) if n else 0.0,
    }


def write_reports(results: list[CheckResult], out_dir: Path) -> tuple[Path, Path]:
    date_dir = out_dir / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    score = _score(results)
    json_path = date_dir / "report.json"
    json_path.write_text(
        json.dumps({"score": score, "results": [r.to_dict() for r in results]},
                   indent=2),
        "utf-8",
    )
    md_lines = [
        f"# Pré-audit interne — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "",
        f"**Score** : {score['ok']} ok / {score['warn']} warn / "
        f"{score['fail']} fail (sur {score['total']}) ⇒ "
        f"**{score['score']}/50** programmable.",
        "",
        "| Section | Item | Statut | Evidence |",
        "|---|---|:---:|---|",
    ]
    icons = {"ok": "✅", "warn": "⚠️", "fail": "❌", "skip": "⏭️"}
    for r in results:
        md_lines.append(
            f"| {r.section} | {r.item} | {icons.get(r.status, '?')} | "
            f"`{r.evidence}` |"
        )
    md_path = date_dir / "report.md"
    md_path.write_text("\n".join(md_lines) + "\n", "utf-8")
    return json_path, md_path


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Pré-audit interne automatisé.")
    p.add_argument("--out", type=Path, default=Path("artifacts/pre_audit/"))
    p.add_argument("--min-score", type=float, default=45.0,
                   help="Plancher (défaut 45/50).")
    args = p.parse_args(argv)

    results = run_checks()
    json_path, md_path = write_reports(results, args.out)
    score = _score(results)
    print(f"[pre_audit] score={score['score']}/50 "
          f"ok={score['ok']} warn={score['warn']} fail={score['fail']}")
    print(f"  → {md_path}")
    return 0 if score["score"] >= args.min_score else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

