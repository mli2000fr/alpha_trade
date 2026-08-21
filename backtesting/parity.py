"""Sprint S9 — Parité backtest ↔ live.

Compare les décisions risk **live** d'une journée J avec les décisions
**replay backtest** rejouées sur les mêmes intrants PIT. Détecte les
divergences (action incohérente, taille position trop éloignée, symbole
manquant d'un côté ou de l'autre) et déclenche une alerte si la
proportion de divergence dépasse un seuil.

Design "loaders injectables" : :func:`run_daily_parity` accepte un
``live_loader(trade_date) -> pd.DataFrame`` et un
``replay_loader(trade_date) -> pd.DataFrame`` afin de :

- rester testable unitairement (mocks),
- ne pas coupler le module à l'implémentation interne du replay
  (qui peut évoluer indépendamment),
- permettre une exécution standalone via le CLI
  ``scripts/run_daily_parity.py`` qui injecte les loaders prod par défaut.

Format DataFrame attendu (mêmes colonnes pour live & replay) :

- ``symbol`` (str, requis, normalisé en upper)
- ``decision`` (str, ex. ``"BUY"`` / ``"HOLD"`` / ``"SELL"``)
- ``approved_shares`` (int, optionnel, défaut 0)
- ``target_weight`` (float, optionnel, défaut 0.0)
- ``conviction_score`` (float, optionnel)
- ``predicted_proba`` (float, optionnel)
- ``run_id`` (str, optionnel — utilisé pour le résumé)
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

LOGGER = logging.getLogger(__name__)


DEFAULT_QTY_TOLERANCE_PCT = 0.05
DEFAULT_QTY_TOLERANCE_ABS = 1.0
DEFAULT_DIVERGENCE_THRESHOLD = 0.10
DEFAULT_ARTIFACTS_DIR = Path("artifacts/parity_runs")

DivergenceKind = str  # "match" | "action_mismatch" | "qty_mismatch" | "missing_live" | "missing_replay"


@dataclass(frozen=True)
class ParityRow:
    symbol: str
    live_decision: Optional[str]
    replay_decision: Optional[str]
    live_qty: float
    replay_qty: float
    live_weight: float
    replay_weight: float
    live_conviction: Optional[float]
    replay_conviction: Optional[float]
    divergence_kind: DivergenceKind

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParityReport:
    trade_date: str
    account_id: str
    live_run_id: Optional[str]
    replay_run_id: Optional[str]
    n_symbols_live: int
    n_symbols_replay: int
    n_matched: int
    n_divergent: int
    divergence_score: float
    rows: list[ParityRow] = field(default_factory=list)
    generated_at: str = ""
    qty_tolerance_pct: float = DEFAULT_QTY_TOLERANCE_PCT
    qty_tolerance_abs: float = DEFAULT_QTY_TOLERANCE_ABS

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_date": self.trade_date,
            "account_id": self.account_id,
            "live_run_id": self.live_run_id,
            "replay_run_id": self.replay_run_id,
            "n_symbols_live": int(self.n_symbols_live),
            "n_symbols_replay": int(self.n_symbols_replay),
            "n_matched": int(self.n_matched),
            "n_divergent": int(self.n_divergent),
            "divergence_score": round(float(self.divergence_score), 6),
            "qty_tolerance_pct": float(self.qty_tolerance_pct),
            "qty_tolerance_abs": float(self.qty_tolerance_abs),
            "generated_at": self.generated_at,
            "rows": [r.to_dict() for r in self.rows],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str, ensure_ascii=False)

    def to_dataframe(self) -> pd.DataFrame:
        if not self.rows:
            return pd.DataFrame(
                columns=[
                    "symbol", "live_decision", "replay_decision", "live_qty", "replay_qty",
                    "live_weight", "replay_weight", "live_conviction", "replay_conviction",
                    "divergence_kind",
                ]
            )
        return pd.DataFrame([r.to_dict() for r in self.rows])


# ---------------------------------------------------------------------------
# Helpers normalisation
# ---------------------------------------------------------------------------


def _norm_symbol(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().upper()
    return s or None


def _norm_action(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().upper()
    return s or None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        out = float(value)
    except (TypeError, ValueError):
        return default
    if out != out:  # NaN
        return default
    return out


def _safe_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:
        return None
    return out


def _qty_within_tolerance(live: float, replay: float, *, pct: float, abs_: float) -> bool:
    diff = abs(live - replay)
    if diff <= abs_:
        return True
    base = max(abs(live), abs(replay), 1.0)
    return (diff / base) <= pct


# ---------------------------------------------------------------------------
# Coeur de comparaison
# ---------------------------------------------------------------------------


def _index_by_symbol(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Indexe un DataFrame par symbole normalisé (dernière entrée gagne)."""
    if df is None or df.empty:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for raw in df.to_dict(orient="records"):
        sym = _norm_symbol(raw.get("symbol"))
        if sym is None:
            continue
        out[sym] = raw
    return out


def compare_decisions(
    live_df: pd.DataFrame,
    replay_df: pd.DataFrame,
    *,
    trade_date: str | date | None = None,
    account_id: str = "default",
    qty_tolerance_pct: float = DEFAULT_QTY_TOLERANCE_PCT,
    qty_tolerance_abs: float = DEFAULT_QTY_TOLERANCE_ABS,
) -> ParityReport:
    """Compare les décisions live vs replay et produit un :class:`ParityReport`.

    Algorithmie :

    - outer-merge sur ``symbol``,
    - classification ``divergence_kind`` :
      * ``missing_live``    : symbole absent côté live,
      * ``missing_replay``  : symbole absent côté replay,
      * ``action_mismatch`` : ``decision`` différent,
      * ``qty_mismatch``    : ``approved_shares`` hors tolérance (mixte
        ``max(abs_, pct * max(qtys))``),
      * ``match``           : sinon.
    - ``divergence_score = n_divergent / max(1, n_symbols_union)``.
    """
    live_idx = _index_by_symbol(live_df)
    replay_idx = _index_by_symbol(replay_df)
    union_symbols = sorted(set(live_idx) | set(replay_idx))

    # Extract run_ids
    live_run_id = None
    replay_run_id = None
    if live_idx:
        first_live = next(iter(live_idx.values()))
        live_run_id = (str(first_live.get("run_id")) if first_live.get("run_id") is not None else None)
    if replay_idx:
        first_replay = next(iter(replay_idx.values()))
        replay_run_id = (str(first_replay.get("run_id")) if first_replay.get("run_id") is not None else None)

    rows: list[ParityRow] = []
    n_matched = 0
    n_divergent = 0
    for sym in union_symbols:
        live = live_idx.get(sym)
        replay = replay_idx.get(sym)

        live_decision = _norm_action(live.get("decision")) if live is not None else None
        replay_decision = _norm_action(replay.get("decision")) if replay is not None else None
        live_qty = _safe_float(live.get("approved_shares")) if live is not None else 0.0
        replay_qty = _safe_float(replay.get("approved_shares")) if replay is not None else 0.0
        live_weight = _safe_float(live.get("target_weight")) if live is not None else 0.0
        replay_weight = _safe_float(replay.get("target_weight")) if replay is not None else 0.0
        live_conviction = _safe_optional_float(live.get("conviction_score")) if live is not None else None
        replay_conviction = _safe_optional_float(replay.get("conviction_score")) if replay is not None else None

        if live is None:
            kind = "missing_live"
        elif replay is None:
            kind = "missing_replay"
        elif live_decision != replay_decision:
            kind = "action_mismatch"
        elif not _qty_within_tolerance(
            live_qty, replay_qty, pct=qty_tolerance_pct, abs_=qty_tolerance_abs
        ):
            kind = "qty_mismatch"
        else:
            kind = "match"

        if kind == "match":
            n_matched += 1
        else:
            n_divergent += 1

        rows.append(
            ParityRow(
                symbol=sym,
                live_decision=live_decision,
                replay_decision=replay_decision,
                live_qty=live_qty,
                replay_qty=replay_qty,
                live_weight=live_weight,
                replay_weight=replay_weight,
                live_conviction=live_conviction,
                replay_conviction=replay_conviction,
                divergence_kind=kind,
            )
        )

    n_union = max(1, len(union_symbols))
    score = n_divergent / n_union

    if isinstance(trade_date, date):
        trade_date_str = trade_date.isoformat()
    elif trade_date is None:
        trade_date_str = ""
    else:
        trade_date_str = str(trade_date)

    return ParityReport(
        trade_date=trade_date_str,
        account_id=account_id,
        live_run_id=live_run_id,
        replay_run_id=replay_run_id,
        n_symbols_live=len(live_idx),
        n_symbols_replay=len(replay_idx),
        n_matched=n_matched,
        n_divergent=n_divergent,
        divergence_score=score,
        rows=rows,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        qty_tolerance_pct=float(qty_tolerance_pct),
        qty_tolerance_abs=float(qty_tolerance_abs),
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


LiveLoader = Callable[[date, str], pd.DataFrame]
ReplayLoader = Callable[[date, str], pd.DataFrame]

# ───────────────────────────────────────────────────────────────────────────
# E23 — Couches risk quotidiennes (gate strict : régime C2, allocation B4,
# état breaker, protections TP/SL/trailing). Discret = égalité stricte ;
# flottant = tolérance minuscule (aucune tolérance sur les décisions discrètes).
# ───────────────────────────────────────────────────────────────────────────
RISK_LAYER_DISCRETE = ("regime", "trailing_policy", "breaker_tripped", "rearm_date", "force_close")
RISK_LAYER_FLOAT = ("allocation_scale", "episode_peak", "episode_trough", "episode_alloc")
RISK_PROTECTION_FIELDS = ("tp", "sl", "trailing")


def compare_risk_layers(
    live_ctx: dict | None,
    replay_ctx: dict | None,
    *,
    float_tol: float = 1e-6,
) -> list[dict[str, Any]]:
    """Compare les couches risk (régime/trailing/breaker/protections) d'un jour.

    Gate strict : aucune tolérance sur les champs discrets (régime, policy,
    tripped, rearm_date, force_close) ; tolérance ``float_tol`` (minuscule)
    sur les flottants (allocation, episode peak/trough/alloc) et les
    protections (tp/sl/trailing par symbole).

    Format attendu des contextes (dict) ::

        {
            "regime": "SLIDE", "trailing_policy": "c2",
            "allocation_scale": 0.10, "breaker_tripped": True,
            "episode_peak": 4200.0, "episode_trough": 3300.0,
            "episode_alloc": 0.10, "rearm_date": "2025-05-06" | None,
            "force_close": False,
            "protections": {"AAPL": {"tp": 0.07, "sl": 0.025, "trailing": 0.07}},
        }

    Retourne une liste de divergences ``{"layer": str, "live": Any, "replay": Any}``.
    Vide = parité.
    """
    live_ctx = live_ctx or {}
    replay_ctx = replay_ctx or {}
    divergences: list[dict[str, Any]] = []

    def _note(layer: str, live: Any, replay: Any) -> None:
        divergences.append({"layer": layer, "live": live, "replay": replay})

    # Couches discrètes : égalité stricte.
    for layer in RISK_LAYER_DISCRETE:
        lv = live_ctx.get(layer)
        rv = replay_ctx.get(layer)
        if lv != rv:
            _note(layer, lv, rv)

    # Couches flottantes : tolérance minuscule.
    for layer in RISK_LAYER_FLOAT:
        lv = live_ctx.get(layer)
        rv = replay_ctx.get(layer)
        if lv is None and rv is None:
            continue
        if lv is None or rv is None:
            _note(layer, lv, rv)
            continue
        try:
            if abs(float(lv) - float(rv)) > float_tol:
                _note(layer, lv, rv)
        except (TypeError, ValueError):
            _note(layer, lv, rv)

    # Protections par symbole (TP/SL/trailing).
    live_prot = live_ctx.get("protections") or {}
    replay_prot = replay_ctx.get("protections") or {}
    for sym in sorted(set(live_prot) | set(replay_prot)):
        lp = live_prot.get(sym) or {}
        rp = replay_prot.get(sym) or {}
        for field in RISK_PROTECTION_FIELDS:
            lf = lp.get(field)
            rf = rp.get(field)
            if lf is None and rf is None:
                continue
            if lf is None or rf is None:
                _note(f"protection.{sym}.{field}", lf, rf)
                continue
            try:
                if abs(float(lf) - float(rf)) > float_tol:
                    _note(f"protection.{sym}.{field}", lf, rf)
            except (TypeError, ValueError):
                _note(f"protection.{sym}.{field}", lf, rf)

    return divergences


PAPER_COVERAGE_ARTIFACT = "paper_coverage.json"


def summarize_paper_coverage(
    contexts: list[dict],
    *,
    min_days: int = 2,
) -> dict[str, Any]:
    """Résume la représentativité d'une période paper (gate GO live réel).

    Critères (recommandation E23) :
    - **obligatoire** : au moins ``min_days`` journées vertes ET au moins un
      changement de régime entre deux jours consécutifs (sinon on ne teste que
      le chemin nominal) ;
    - **idéal** : au moins un jour où l'allocation < 1.0 (épisode non-nominal,
      contrôle effectif du breaker B4) — rapporté séparément.

    ``contexts`` : contexte LIVE (ou replay, à défaut) d'un jour, au format
    ``compare_risk_layers``. Retourne un dict de synthèse avec ``representative``.
    """
    n = len(contexts)
    if n == 0:
        return {"days": 0, "regimes": [], "regime_changes": 0, "non_full_alloc_days": 0,
                "tripped_days": 0, "min_days": min_days, "representative": False,
                "missing": ["aucun jour enregistré"]}

    regimes = []
    allocs = []
    tripped = 0
    for ctx in contexts:
        r = str(ctx.get("regime") or "")
        if r:
            regimes.append(r)
        else:
            regimes.append("<vide>")
        try:
            allocs.append(float(ctx.get("allocation_scale") or 0.0))
        except (TypeError, ValueError):
            allocs.append(0.0)
        if bool(ctx.get("breaker_tripped")):
            tripped += 1

    distinct = sorted(set(regimes))
    regime_changes = sum(1 for a, b in zip(regimes, regimes[1:]) if a != b)
    non_full = sum(1 for a in allocs if a < 0.999)

    missing = []
    if n < min_days:
        missing.append(f"{min_days - n} jour(s) vert(s) manquant(s)")
    if regime_changes < 1:
        missing.append("aucun changement de régime")
    if non_full < 1:
        missing.append("aucun épisode allocation<1.0 (idéal)")

    return {
        "days": n, "regimes": distinct, "regime_changes": regime_changes,
        "non_full_alloc_days": non_full, "tripped_days": tripped,
        "min_days": min_days, "missing": missing,
        "representative": (n >= min_days) and (regime_changes >= 1),
    }


def write_parity_artifacts(report: ParityReport, output_dir: Path | str) -> dict[str, Path]:
    """Écrit ``parity_summary.json`` + ``rows.csv`` dans ``output_dir``.

    Retourne le mapping ``{"summary": Path, "rows_csv": Path}``.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "parity_summary.json"
    rows_csv_path = out / "rows.csv"
    summary_path.write_text(report.to_json(), encoding="utf-8")
    report.to_dataframe().to_csv(rows_csv_path, index=False)
    LOGGER.info(
        "[parity] artefacts écrits | summary=%s rows=%s n_divergent=%d score=%.4f",
        summary_path,
        rows_csv_path,
        report.n_divergent,
        report.divergence_score,
    )
    return {"summary": summary_path, "rows_csv": rows_csv_path}


def _build_alert_body(report: ParityReport, threshold: float) -> str:
    by_kind: dict[str, int] = {}
    for r in report.rows:
        by_kind[r.divergence_kind] = by_kind.get(r.divergence_kind, 0) + 1
    lines = [
        f"trade_date: {report.trade_date}",
        f"account: {report.account_id}",
        f"live_run_id: {report.live_run_id}",
        f"replay_run_id: {report.replay_run_id}",
        f"divergence_score: {report.divergence_score:.4f} (seuil={threshold:.4f})",
        f"matched: {report.n_matched}",
        f"divergent: {report.n_divergent}",
        "détails par catégorie:",
    ]
    for kind, count in sorted(by_kind.items()):
        lines.append(f"  - {kind}: {count}")
    return "\n".join(lines)


def run_daily_parity(
    trade_date: date,
    *,
    live_loader: LiveLoader,
    replay_loader: ReplayLoader,
    account_id: str = "default",
    artifacts_dir: Path | str = DEFAULT_ARTIFACTS_DIR,
    notifier=None,
    divergence_threshold: float = DEFAULT_DIVERGENCE_THRESHOLD,
    qty_tolerance_pct: float = DEFAULT_QTY_TOLERANCE_PCT,
    qty_tolerance_abs: float = DEFAULT_QTY_TOLERANCE_ABS,
) -> ParityReport:
    """Pipeline complet : load live + replay → compare → écrit → alerte.

    Idempotent : ré-écrase ``artifacts_dir/<trade_date>/`` à chaque appel.
    """
    LOGGER.info("[parity] démarrage | date=%s account=%s", trade_date.isoformat(), account_id)
    live_df = live_loader(trade_date, account_id)
    replay_df = replay_loader(trade_date, account_id)
    report = compare_decisions(
        live_df,
        replay_df,
        trade_date=trade_date,
        account_id=account_id,
        qty_tolerance_pct=qty_tolerance_pct,
        qty_tolerance_abs=qty_tolerance_abs,
    )

    out_dir = Path(artifacts_dir) / trade_date.isoformat()
    write_parity_artifacts(report, out_dir)

    if notifier is not None and report.divergence_score > divergence_threshold:
        subject = (
            f"[Alpha Trade] Parité backtest/live divergente "
            f"({report.divergence_score:.2%} > {divergence_threshold:.2%}) — {trade_date.isoformat()}"
        )
        body = _build_alert_body(report, divergence_threshold)
        try:
            notifier.send(subject, body, severity="warning")
        except Exception as exc:  # noqa: BLE001 — never raise to caller
            LOGGER.warning("[parity] notifier.send a levé : %s", exc)
    return report


__all__ = [
    "DEFAULT_QTY_TOLERANCE_PCT",
    "DEFAULT_QTY_TOLERANCE_ABS",
    "DEFAULT_DIVERGENCE_THRESHOLD",
    "DEFAULT_ARTIFACTS_DIR",
    "ParityRow",
    "ParityReport",
    "compare_decisions",
    "write_parity_artifacts",
    "run_daily_parity",
]

