"""Sprint S24.4 — Loaders pour la page IHM Compliance & Audit.

Chaque loader est une fonction pure qui retourne un dict (ou {} si la
source est absente) ⇒ testable en isolation, page IHM purement
d'affichage.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS = PROJECT_ROOT / "artifacts"


def _safe_read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _latest_subdir(root: Path) -> Path | None:
    if not root.exists():
        return None
    candidates = [p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.name)


# ---------------------------------------------------------------------------
# HMAC chain
# ---------------------------------------------------------------------------


def load_audit_chain_status() -> dict[str, Any]:
    """Statut courant de la chaîne audit HMAC.

    Tente d'invoquer le repo SQL ; en cas d'erreur, retourne un statut
    dégradé sans planter la page.
    """
    try:
        from database.audit_chain import AuditChainRepository
        from database.connection import get_sqlalchemy_engine

        engine = get_sqlalchemy_engine()
        repo = AuditChainRepository(engine)
        anomalies = repo.verify_chain(None)
        return {
            "ok": len(anomalies) == 0,
            "anomalies_count": len(anomalies),
            "source": "live_db",
        }
    except Exception as exc:
        return {"ok": None, "anomalies_count": None,
                "error": str(exc)[:200], "source": "unavailable"}


# ---------------------------------------------------------------------------
# DR drill
# ---------------------------------------------------------------------------


def load_dr_drill_status() -> dict[str, Any]:
    root = ARTIFACTS / "dr_drill"
    latest = _latest_subdir(root)
    if not latest:
        return {"ok": None, "last_date": None, "rto_minutes": None}
    payload = _safe_read_json(latest / "result.json") or {}
    return {
        "ok": payload.get("ok", payload.get("status") == "success"),
        "last_date": latest.name,
        "rto_minutes": payload.get("rto_minutes"),
        "rpo_minutes": payload.get("rpo_minutes"),
    }


# ---------------------------------------------------------------------------
# CVE
# ---------------------------------------------------------------------------


def load_cve_status() -> dict[str, Any]:
    candidates = [
        ARTIFACTS / "sbom" / "cve_scan_latest.json",
        ARTIFACTS / "sbom" / "cve_scan.json",
    ]
    payload: dict | None = None
    for c in candidates:
        payload = _safe_read_json(c)
        if payload:
            break
    if not payload:
        return {"critical": None, "high": None, "scanned_at": None}
    return {
        "critical": payload.get("critical", payload.get("n_critical", 0)),
        "high": payload.get("high", payload.get("n_high", 0)),
        "scanned_at": payload.get("scanned_at", payload.get("generated_at")),
    }


# ---------------------------------------------------------------------------
# Couverture & mutation
# ---------------------------------------------------------------------------


def load_coverage_status() -> dict[str, Any]:
    payload = _safe_read_json(ARTIFACTS / "coverage" / "branches.json") or {}
    return {
        "branches_pct": payload.get("branches_pct", payload.get("percent")),
        "global_pct": payload.get("global_pct"),
        "generated_at": payload.get("generated_at"),
    }


def load_mutation_status() -> dict[str, Any]:
    latest = _latest_subdir(ARTIFACTS / "mutation_runs")
    if not latest:
        return {"score_pct": None, "date": None}
    payload = _safe_read_json(latest / "score.json") or {}
    return {
        "score_pct": payload.get("score", payload.get("mutation_score_pct")),
        "killed": payload.get("killed"),
        "survived": payload.get("survived"),
        "date": latest.name,
    }


# ---------------------------------------------------------------------------
# TLAPS + Fuzz
# ---------------------------------------------------------------------------


def load_tlaps_status() -> dict[str, Any]:
    latest = _latest_subdir(ARTIFACTS / "formal_runs")
    if not latest:
        return {"n_ok": None, "n_specs": None, "tool": None, "date": None}
    payload = _safe_read_json(latest / "tlaps.json") or {}
    return {
        "n_ok": payload.get("n_ok"),
        "n_specs": payload.get("n_specs"),
        "n_failed": payload.get("n_failed"),
        "tool": payload.get("tool"),
        "date": latest.name,
    }


def load_fuzz_status() -> dict[str, Any]:
    latest = _latest_subdir(ARTIFACTS / "fuzz_runs")
    if not latest:
        return {"n_scenarios": None, "n_diverged": None, "date": None}
    payload = _safe_read_json(latest / "diff.json") or {}
    return {
        "n_scenarios": payload.get("n_scenarios"),
        "n_diverged": payload.get("n_diverged"),
        "divergence_rate": (payload.get("summary") or {}).get("divergence_rate"),
        "max_pnl_delta_usd": (payload.get("summary") or {}).get("max_pnl_delta_usd"),
        "date": latest.name,
    }


def load_sandbox_streak() -> dict[str, Any]:
    """Délègue au loader sandbox_health."""
    try:
        from ihm.services.sandbox_health_loader import load_rollup

        rollup = load_rollup()
        return {
            "streak_green": rollup.get("streak_green"),
            "n_failure": rollup.get("n_failure"),
            "n_success": rollup.get("n_success"),
            "last_failure": rollup.get("last_failure"),
        }
    except Exception:
        return {"streak_green": None, "n_failure": None,
                "n_success": None, "last_failure": None}


# ---------------------------------------------------------------------------
# Snapshot complet
# ---------------------------------------------------------------------------


def load_full_snapshot() -> dict[str, Any]:
    """Agrège tous les loaders pour le bouton « download »."""
    return {
        "hmac_chain": load_audit_chain_status(),
        "dr_drill": load_dr_drill_status(),
        "cve": load_cve_status(),
        "coverage": load_coverage_status(),
        "mutation": load_mutation_status(),
        "tlaps": load_tlaps_status(),
        "fuzz": load_fuzz_status(),
        "sandbox": load_sandbox_streak(),
    }

