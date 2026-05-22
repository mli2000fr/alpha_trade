"""Sprint S5 (A-013 + suivis A-008) — pre-flight checks pour bascule live.

Module agrégeant 7 vérifications bloquantes avant un run live :

1. **Pas de kill switch global actif** — `execution_kill_switch_runs`.
2. **Dry-run paper récent** — un `execution_runs` paper/dry-run < N heures.
3. **Credentials Alpaca live valides** — résolution + ping `get_account()`
   (skippable en CI via ``--skip-network``).
4. **Drift gate ML pas en kill switch** — dernier `ml_drift_runs.payload`.
5. **Aucun secret littéral dans `config.yaml`** — délégué à
   :func:`core.secrets.scan_yaml_for_literal_secrets`.
6. **Policy secrets live conforme** — Vault explicite ou override env assumé.
7. **Aucun verrou pipeline IHM actif** — :func:`ihm.services.pipeline_lock.list_active_locks`.

Usage CLI :

.. code-block:: powershell

    python -m execution_engine.preflight --account live1 --broker-mode live
    python -m execution_engine.preflight --account default --json --skip-network

Exit code : ``0`` si tous les checks ``ok|warn|skip``, ``1`` dès un ``fail``.
"""
from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import socket
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Literal

LOGGER = logging.getLogger("preflight")

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"

CheckStatus = Literal["ok", "warn", "fail", "skip"]


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    status: CheckStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


@dataclass(frozen=True, slots=True)
class PreflightContext:
    account_id: str
    broker_mode: str
    config_path: Path
    engine: Any | None = None         # SQLAlchemy Engine (DI)
    registry: Any | None = None       # AccountRegistry (DI)
    alpaca_client_factory: Callable[..., Any] | None = None  # DI pour tests
    pipeline_lock_module: Any | None = None  # DI pour tests
    max_dry_run_age_hours: int = 24
    skip_network: bool = False


@dataclass(slots=True)
class PreflightReport:
    account_id: str
    broker_mode: str
    generated_at: str
    host: str
    user: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(c.status == "fail" for c in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "broker_mode": self.broker_mode,
            "generated_at": self.generated_at,
            "host": self.host,
            "user": self.user,
            "passed": self.passed,
            "summary": {
                "ok": sum(1 for c in self.checks if c.status == "ok"),
                "warn": sum(1 for c in self.checks if c.status == "warn"),
                "fail": sum(1 for c in self.checks if c.status == "fail"),
                "skip": sum(1 for c in self.checks if c.status == "skip"),
            },
            "checks": [c.to_dict() for c in self.checks],
        }


# ---------------------------------------------------------------------------
# Checks individuels
# ---------------------------------------------------------------------------

def check_no_global_kill_switch_active(ctx: PreflightContext) -> CheckResult:
    """Échec si un `execution_kill_switch_runs` < 24h sans run d'exécution
    `completed` postérieur sur le même compte."""
    if ctx.engine is None:
        return CheckResult("kill_switch_inactive", "skip",
                           "no engine provided", {})
    try:
        from sqlalchemy import text
        with ctx.engine.connect() as conn:
            row = conn.execute(text(
                """
                SELECT run_id, finished_at, reason
                FROM execution_kill_switch_runs
                WHERE account_id = :acct
                  AND finished_at >= :cutoff
                ORDER BY finished_at DESC
                LIMIT 1
                """,
            ), {"acct": ctx.account_id,
                "cutoff": datetime.now(timezone.utc) - timedelta(hours=24)}).fetchone()
        if row is None:
            return CheckResult("kill_switch_inactive", "ok",
                               "no recent kill switch run", {})
        return CheckResult(
            "kill_switch_inactive", "fail",
            f"kill switch fired at {row[1]} (run_id={row[0]})",
            {"run_id": row[0], "finished_at": str(row[1]), "reason": row[2]},
        )
    except Exception as exc:
        return CheckResult("kill_switch_inactive", "warn",
                           f"check skipped: {exc}", {})


def check_recent_dry_run(ctx: PreflightContext) -> CheckResult:
    """Échec si aucun run paper/dry-run `completed` n'existe sur les
    dernières ``max_dry_run_age_hours`` heures."""
    if ctx.engine is None:
        return CheckResult("recent_dry_run", "skip",
                           "no engine provided", {})
    try:
        from sqlalchemy import text
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ctx.max_dry_run_age_hours)
        with ctx.engine.connect() as conn:
            row = conn.execute(text(
                """
                SELECT exec_run_id, completed_at, broker_mode, dry_run
                FROM execution_runs
                WHERE account_id = :acct
                  AND UPPER(status) = 'COMPLETED'
                  AND (broker_mode = 'paper' OR dry_run = 1)
                  AND completed_at >= :cutoff
                ORDER BY completed_at DESC
                LIMIT 1
                """,
            ), {"acct": ctx.account_id, "cutoff": cutoff}).fetchone()
        if row is None:
            return CheckResult(
                "recent_dry_run", "fail",
                f"no paper/dry-run completed in the last "
                f"{ctx.max_dry_run_age_hours}h for account '{ctx.account_id}'",
                {"max_dry_run_age_hours": ctx.max_dry_run_age_hours},
            )
        return CheckResult(
            "recent_dry_run", "ok",
            f"last paper/dry-run exec_run_id={row[0]} at {row[1]}",
            {"exec_run_id": row[0], "completed_at": str(row[1]),
             "broker_mode": row[2], "dry_run": int(row[3])},
        )
    except Exception as exc:
        return CheckResult("recent_dry_run", "warn",
                           f"check skipped: {exc}", {})


def check_alpaca_credentials(ctx: PreflightContext) -> CheckResult:
    """Résout le compte et tente un ``get_account()`` (sauf ``--skip-network``)."""
    try:
        registry = ctx.registry
        if registry is None:
            from service.alpaca.accounts import AccountRegistry
            registry = AccountRegistry.get()
        account = registry.resolve(ctx.account_id)
    except Exception as exc:
        return CheckResult("alpaca_credentials", "fail",
                           f"cannot resolve account '{ctx.account_id}': {exc}", {})

    expected_mode = ctx.broker_mode
    if expected_mode == "live" and account.mode != "live":
        return CheckResult(
            "alpaca_credentials", "fail",
            f"account '{ctx.account_id}' is configured as '{account.mode}' "
            f"but broker_mode='live' was requested",
            {"account_mode": account.mode, "requested_mode": expected_mode},
        )

    if ctx.skip_network:
        return CheckResult("alpaca_credentials", "skip",
                           "network ping skipped (--skip-network)",
                           {"account_mode": account.mode})

    factory = ctx.alpaca_client_factory
    try:
        if factory is None:
            from service.alpaca.trading_client import AlpacaTradingClient  # type: ignore
            client = AlpacaTradingClient(
                api_key=account.api_key,
                secret_key=account.secret_key,
                paper=(account.mode != "live"),
            )
        else:
            client = factory(account)
        info = client.get_account()
        status = getattr(info, "status", None) or (info.get("status") if isinstance(info, dict) else None)
        return CheckResult(
            "alpaca_credentials", "ok",
            f"alpaca ping ok account_status={status}",
            {"account_mode": account.mode, "status": status},
        )
    except Exception as exc:
        return CheckResult("alpaca_credentials", "fail",
                           f"alpaca ping failed: {exc}",
                           {"account_mode": account.mode})


def check_ml_drift_gate(ctx: PreflightContext) -> CheckResult:
    """Échec si le dernier `ml_drift_runs` indique `kill_switch_ml`."""
    if ctx.engine is None:
        return CheckResult("ml_drift_gate", "skip",
                           "no engine provided", {})
    try:
        from sqlalchemy import text
        with ctx.engine.connect() as conn:
            row = conn.execute(text(
                """
                SELECT run_id, status, payload, computed_at
                FROM ml_drift_runs
                ORDER BY computed_at DESC
                LIMIT 1
                """,
            )).fetchone()
        if row is None:
            return CheckResult("ml_drift_gate", "ok",
                               "no ml_drift_runs recorded yet", {})
        run_id, status, payload_json, computed_at = row
        payload: dict[str, Any] = {}
        if payload_json:
            try:
                payload = json.loads(payload_json)
            except Exception:
                payload = {}
        gate_action = payload.get("gate_action")
        if gate_action == "kill_switch_ml" or status == "ALERT":
            return CheckResult(
                "ml_drift_gate", "fail",
                f"ML kill switch active (status={status} "
                f"gate_action={gate_action} run_id={run_id})",
                {"run_id": run_id, "status": status,
                 "gate_action": gate_action,
                 "computed_at": str(computed_at)},
            )
        return CheckResult(
            "ml_drift_gate", "ok",
            f"ML drift status={status}",
            {"run_id": run_id, "status": status,
             "computed_at": str(computed_at)},
        )
    except Exception as exc:
        return CheckResult("ml_drift_gate", "warn",
                           f"check skipped: {exc}", {})


def check_no_literal_secrets(ctx: PreflightContext) -> CheckResult:
    """Échec si `config.yaml` contient des secrets littéraux."""
    try:
        from core.secrets import scan_yaml_for_literal_secrets
        findings = scan_yaml_for_literal_secrets(ctx.config_path)
    except Exception as exc:
        return CheckResult("no_literal_secrets", "warn",
                           f"scanner failed: {exc}", {})
    if findings:
        return CheckResult(
            "no_literal_secrets", "fail",
            f"{len(findings)} literal secret(s) found in {ctx.config_path.name}",
            {"findings": [f.to_dict() for f in findings]},
        )
    return CheckResult("no_literal_secrets", "ok",
                       f"no literal secrets in {ctx.config_path.name}", {})


def check_no_pipeline_lock_held(ctx: PreflightContext) -> CheckResult:
    """Échec si un verrou pipeline IHM est actif."""
    try:
        mod = ctx.pipeline_lock_module
        if mod is None:
            from ihm.services import pipeline_lock as mod  # type: ignore
        active = mod.list_active_locks()
    except Exception as exc:
        return CheckResult("no_pipeline_lock_held", "warn",
                           f"check skipped: {exc}", {})
    if active:
        return CheckResult(
            "no_pipeline_lock_held", "fail",
            f"{len(active)} pipeline lock(s) currently held",
            {"locks": active},
        )
    return CheckResult("no_pipeline_lock_held", "ok",
                       "no pipeline lock held", {})


def check_live_secret_policy(ctx: PreflightContext) -> CheckResult:
    """Échec si le live n'a ni Vault explicite ni policy env assumée."""
    if ctx.broker_mode != "live":
        return CheckResult(
            "live_secret_policy",
            "skip",
            f"broker_mode={ctx.broker_mode} — check réservé au live",
            {},
        )
    try:
        from common.config_vault import is_live_secret_policy_satisfied

        ok, details = is_live_secret_policy_satisfied()
    except Exception as exc:
        return CheckResult("live_secret_policy", "warn", f"check skipped: {exc}", {})
    if ok:
        return CheckResult(
            "live_secret_policy",
            "ok",
            str(details.get("message") or "live secret policy ok"),
            details,
        )
    return CheckResult(
        "live_secret_policy",
        "fail",
        str(details.get("message") or "live secret policy failed"),
        details,
    )


CHECKS: tuple[Callable[[PreflightContext], CheckResult], ...] = (
    check_no_literal_secrets,
    check_live_secret_policy,
    check_alpaca_credentials,
    check_no_global_kill_switch_active,
    check_recent_dry_run,
    check_ml_drift_gate,
    check_no_pipeline_lock_held,
)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_preflight(
    account_id: str,
    *,
    broker_mode: str = "live",
    engine: Any | None = None,
    registry: Any | None = None,
    config_path: Path | None = None,
    alpaca_client_factory: Callable[..., Any] | None = None,
    pipeline_lock_module: Any | None = None,
    max_dry_run_age_hours: int = 24,
    skip_network: bool = False,
    checks: tuple[Callable[[PreflightContext], CheckResult], ...] | None = None,
) -> PreflightReport:
    """Exécute tous les checks et retourne un :class:`PreflightReport`."""
    ctx = PreflightContext(
        account_id=account_id,
        broker_mode=broker_mode,
        config_path=Path(config_path) if config_path else DEFAULT_CONFIG_PATH,
        engine=engine,
        registry=registry,
        alpaca_client_factory=alpaca_client_factory,
        pipeline_lock_module=pipeline_lock_module,
        max_dry_run_age_hours=max_dry_run_age_hours,
        skip_network=skip_network,
    )
    report = PreflightReport(
        account_id=account_id,
        broker_mode=broker_mode,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        host=socket.gethostname(),
        user=getpass.getuser(),
        checks=[],
    )
    for check in (checks or CHECKS):
        try:
            result = check(ctx)
        except Exception as exc:  # pragma: no cover - filet
            result = CheckResult(check.__name__, "fail",
                                 f"check raised: {exc}", {})
        report.checks.append(result)
        LOGGER.info("preflight check name=%s status=%s message=%s",
                    result.name, result.status, result.message)
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Pre-flight live readiness checks (Sprint S5).")
    p.add_argument("--account", required=True, help="ID du compte Alpaca à vérifier")
    p.add_argument("--broker-mode", choices=("paper", "live"), default="live")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    p.add_argument("--max-dry-run-age-hours", type=int, default=24)
    p.add_argument("--skip-network", action="store_true",
                   help="Ne pas pinger Alpaca (utile en CI / dev offline).")
    p.add_argument("--json", action="store_true",
                   help="Sortie JSON exclusive (pas de log human).")
    p.add_argument("--report-out", type=Path, default=None,
                   help="Chemin d'écriture du rapport JSON.")
    p.add_argument("--log-level", default="INFO",
                   choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.json:
        logging.basicConfig(level=getattr(logging, args.log_level),
                            format="%(levelname)s %(message)s")

    engine = None
    try:  # best-effort engine
        from database.connection import get_sqlalchemy_engine
        engine = get_sqlalchemy_engine()
    except Exception as exc:
        LOGGER.warning("DB engine unavailable: %s", exc)

    report = run_preflight(
        account_id=args.account,
        broker_mode=args.broker_mode,
        engine=engine,
        config_path=args.config,
        max_dry_run_age_hours=args.max_dry_run_age_hours,
        skip_network=args.skip_network,
    )
    payload = report.to_dict()
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"\n{'=' * 60}")
        print(f"  Pre-flight report — account={report.account_id} mode={report.broker_mode}")
        print(f"  generated_at={report.generated_at}  host={report.host}  user={report.user}")
        print(f"  PASSED: {report.passed}")
        print(f"{'=' * 60}")
        for c in report.checks:
            print(f"  [{c.status.upper():4s}] {c.name}: {c.message}")
        print(f"{'=' * 60}")
    return 0 if report.passed else 1


__all__ = [
    "CheckResult",
    "PreflightContext",
    "PreflightReport",
    "CHECKS",
    "check_no_global_kill_switch_active",
    "check_recent_dry_run",
    "check_alpaca_credentials",
    "check_live_secret_policy",
    "check_ml_drift_gate",
    "check_no_literal_secrets",
    "check_no_pipeline_lock_held",
    "run_preflight",
    "main",
]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())



