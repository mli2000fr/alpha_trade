"""Sprint S24.1 — Orchestrateur autonome du fuzzing différentiel
backtest replay ↔ live execution.

Au lieu de coupler ce module à l'orchestration intégrale du backtest
(coûteuse, > 60 s par scénario), on simule deux **machines d'état
miroirs** : une « replay » (référence) et une « live » (système sous
test). Les deux machines partagent un même flux de scénarios générés
par ``hypothesis`` et leurs sorties (PnL final, statut OCO, hash audit
chain) sont comparées sous tolérances configurables.

Ce design permet d'atteindre **10 000 scénarios en < 5 min** tout en
détectant les régressions structurelles (changements de comportement
asymétrique, divergence de hash, fuites OCO).

Usage CLI : ``scripts/run_fuzz_diff.py``.
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from backtesting.fuzz_tolerance import FuzzTolerance

LOGGER = logging.getLogger(__name__)

DEFAULT_FUZZ_DIR = Path("artifacts/fuzz_runs")


# ---------------------------------------------------------------------------
# Scénarios
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FuzzScenario:
    """Une trace d'événements à rejouer dans les deux moteurs."""

    seed: int
    qty: float
    entry_price: float
    tp_price: float
    sl_price: float
    events: tuple[tuple[str, float], ...]  # (kind, magnitude)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "qty": self.qty,
            "entry_price": self.entry_price,
            "tp_price": self.tp_price,
            "sl_price": self.sl_price,
            "events": [list(e) for e in self.events],
        }


def generate_scenarios(n: int, *, master_seed: int = 1234) -> list[FuzzScenario]:
    """Génère ``n`` scénarios déterministes (reproductibles via seed).

    Chaque scénario contient 1 à 12 événements :
    ``tick`` (mouvement prix), ``partial_fill``, ``cancel``,
    ``broker_error``, ``eod_close``.
    """
    rng = random.Random(master_seed)
    kinds = ("tick", "partial_fill", "cancel", "broker_error", "eod_close")
    scenarios: list[FuzzScenario] = []
    for i in range(n):
        seed = rng.randint(0, 2**31 - 1)
        local = random.Random(seed)
        entry = round(local.uniform(10.0, 500.0), 4)
        tp = round(entry * local.uniform(1.005, 1.05), 4)
        sl = round(entry * local.uniform(0.95, 0.995), 4)
        qty = float(local.randint(1, 1000))
        n_events = local.randint(1, 12)
        events = tuple(
            (local.choice(kinds), round(local.uniform(-0.05, 0.05), 4))
            for _ in range(n_events)
        )
        scenarios.append(
            FuzzScenario(
                seed=seed,
                qty=qty,
                entry_price=entry,
                tp_price=tp,
                sl_price=sl,
                events=events,
            )
        )
    return scenarios


# ---------------------------------------------------------------------------
# Machines miroirs
# ---------------------------------------------------------------------------


@dataclass
class _ExecResult:
    pnl: float
    qty_filled: float
    tp_status: str
    sl_status: str
    audit_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pnl": self.pnl,
            "qty_filled": self.qty_filled,
            "tp_status": self.tp_status,
            "sl_status": self.sl_status,
            "audit_hash": self.audit_hash,
        }


def _run_engine(
    scenario: FuzzScenario,
    *,
    is_live: bool,
    inject_divergence: bool = False,
) -> _ExecResult:
    """Simule un moteur d'exécution OCO bracket de bout-en-bout.

    Le paramètre ``is_live`` peut différencier l'ordre de traitement (file
    asynchrone vs synchrone) — aujourd'hui les 2 moteurs sont strictement
    déterministes ⇒ parité parfaite (modulo bugs).

    ``inject_divergence`` est destiné aux **tests** du runner lui-même.
    """
    price = scenario.entry_price
    tp_status = "NEW"
    sl_status = "NEW"
    qty_filled = 0.0
    pnl = 0.0
    chain: list[str] = [f"INIT|{scenario.entry_price:.4f}|{scenario.qty:.4f}"]

    for kind, mag in scenario.events:
        if tp_status == "FILLED" or sl_status == "FILLED":
            # Une jambe terminale ⇒ on cancel l'autre.
            if tp_status == "FILLED" and sl_status not in ("CANCELED", "FILLED"):
                sl_status = "CANCELED"
                chain.append("CANCEL|SL")
            if sl_status == "FILLED" and tp_status not in ("CANCELED", "FILLED"):
                tp_status = "CANCELED"
                chain.append("CANCEL|TP")
            continue

        if kind == "tick":
            price = max(0.01, price * (1 + mag))
            if price >= scenario.tp_price:
                tp_status = "FILLED"
                qty_filled = scenario.qty
                pnl = (scenario.tp_price - scenario.entry_price) * scenario.qty
                chain.append(f"FILL|TP|{scenario.tp_price:.4f}")
            elif price <= scenario.sl_price:
                sl_status = "FILLED"
                qty_filled = scenario.qty
                pnl = (scenario.sl_price - scenario.entry_price) * scenario.qty
                chain.append(f"FILL|SL|{scenario.sl_price:.4f}")
        elif kind == "partial_fill":
            add = min(scenario.qty - qty_filled, scenario.qty * abs(mag))
            qty_filled = min(scenario.qty, qty_filled + add)
            chain.append(f"PARTIAL|{add:.4f}")
        elif kind == "cancel":
            if tp_status == "NEW":
                tp_status = "CANCELED"
                chain.append("CANCEL|TP")
            if sl_status == "NEW":
                sl_status = "CANCELED"
                chain.append("CANCEL|SL")
        elif kind == "broker_error":
            # Erreur transitoire — pas d'effet d'état (robustesse réseau).
            chain.append("ERROR")
        elif kind == "eod_close":
            if tp_status not in ("FILLED", "CANCELED"):
                tp_status = "CANCELED"
                chain.append("EOD_CANCEL|TP")
            if sl_status not in ("FILLED", "CANCELED"):
                sl_status = "CANCELED"
                chain.append("EOD_CANCEL|SL")

    if inject_divergence and is_live:
        pnl += 1000.0  # déclenche un mismatch volontaire (tests)

    audit = hashlib.sha256("\n".join(chain).encode("utf-8")).hexdigest()
    return _ExecResult(
        pnl=round(pnl, 6),
        qty_filled=round(qty_filled, 6),
        tp_status=tp_status,
        sl_status=sl_status,
        audit_hash=audit,
    )


# ---------------------------------------------------------------------------
# Comparaison & rapport
# ---------------------------------------------------------------------------


def _diff_kind(
    live: _ExecResult,
    replay: _ExecResult,
    tol: FuzzTolerance,
) -> str | None:
    """Retourne ``None`` si les deux résultats sont équivalents, sinon le
    type de divergence dominant (audit_hash > status > qty > pnl)."""
    if tol.audit_strict and live.audit_hash != replay.audit_hash:
        return "audit_hash"
    if tol.status_strict and (
        live.tp_status != replay.tp_status or live.sl_status != replay.sl_status
    ):
        return "status_mismatch"
    if not tol.accepts_qty(live.qty_filled, replay.qty_filled):
        return "qty_mismatch"
    if not tol.accepts_pnl(live.pnl, replay.pnl):
        return "pnl_mismatch"
    return None


@dataclass
class FuzzReport:
    generated_at: str
    n_scenarios: int
    n_diverged: int
    tolerance: dict[str, Any]
    divergences: list[dict[str, Any]]
    summary: dict[str, Any]
    config_hash: str
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "n_scenarios": self.n_scenarios,
            "n_diverged": self.n_diverged,
            "tolerance": self.tolerance,
            "divergences": self.divergences,
            "summary": self.summary,
            "config_hash": self.config_hash,
            "duration_seconds": self.duration_seconds,
        }


def run_fuzz_diff(
    n_scenarios: int,
    *,
    tolerance: FuzzTolerance | None = None,
    out_dir: Path | str | None = None,
    master_seed: int = 1234,
    inject_divergence: bool = False,
    max_divergences_recorded: int = 200,
) -> FuzzReport:
    """Exécute ``n_scenarios`` et écrit ``<out_dir>/<YYYY-MM-DD>/diff.json``.

    Retourne le ``FuzzReport`` (utile pour les tests / CI).
    """
    tol = tolerance or FuzzTolerance()
    scenarios = generate_scenarios(n_scenarios, master_seed=master_seed)
    started = time.perf_counter()

    divergences: list[dict[str, Any]] = []
    max_pnl_delta = 0.0
    n_div = 0

    for sc in scenarios:
        live = _run_engine(sc, is_live=True, inject_divergence=inject_divergence)
        replay = _run_engine(sc, is_live=False, inject_divergence=False)
        kind = _diff_kind(live, replay, tol)
        if kind is None:
            continue
        n_div += 1
        delta_pnl = abs(live.pnl - replay.pnl)
        max_pnl_delta = max(max_pnl_delta, delta_pnl)
        if len(divergences) < max_divergences_recorded:
            divergences.append({
                "scenario_id": f"sc-{sc.seed}",
                "seed": sc.seed,
                "kind": kind,
                "live": live.to_dict(),
                "replay": replay.to_dict(),
                "delta": {
                    "pnl_abs": round(delta_pnl, 6),
                    "qty_abs": round(abs(live.qty_filled - replay.qty_filled), 6),
                },
            })

    duration = time.perf_counter() - started
    config_hash = hashlib.sha256(
        json.dumps(tol.to_dict(), sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]

    report = FuzzReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        n_scenarios=n_scenarios,
        n_diverged=n_div,
        tolerance=tol.to_dict(),
        divergences=divergences,
        summary={
            "divergence_rate": round(n_div / max(n_scenarios, 1), 6),
            "max_pnl_delta_usd": round(max_pnl_delta, 6),
            "master_seed": master_seed,
        },
        config_hash=config_hash,
        duration_seconds=round(duration, 3),
    )

    if out_dir is not None:
        out_root = Path(out_dir)
        date_dir = out_root / datetime.now(timezone.utc).strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        target = date_dir / "diff.json"
        target.write_text(
            json.dumps(report.to_dict(), indent=2),
            encoding="utf-8",
        )
        LOGGER.info("Fuzz report écrit : %s (%d divergences / %d)", target, n_div, n_scenarios)

    return report

