"""Sprint S9 — CLI quotidien de parité backtest ↔ live.

Usage::

    python -m scripts.run_daily_parity --trade-date 2026-05-05
    python -m scripts.run_daily_parity --trade-date 2026-05-05 --no-alert
    python -m scripts.run_daily_parity --threshold 0.05 --account default

Exit codes :
- ``0`` : parité OK (divergence_score ≤ seuil) ou pas de données.
- ``2`` : divergence > seuil (utile pour scheduler/cron monitoring).
- ``1`` : erreur inattendue.

Les loaders ``live`` / ``replay`` peuvent être surchargés via les hooks
``--use-stub-replay`` (utile pour tests d'intégration sans BacktestEngine).
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from backtesting.parity import (
    DEFAULT_ARTIFACTS_DIR,
    DEFAULT_DIVERGENCE_THRESHOLD,
    DEFAULT_QTY_TOLERANCE_ABS,
    DEFAULT_QTY_TOLERANCE_PCT,
    compare_risk_layers,
    run_daily_parity,
)
from common.utils import configure_root_logging
from service.alerting import build_notifier_from_env

LOGGER = logging.getLogger("scripts.run_daily_parity")


def _default_live_loader(trade_date: date, account_id: str) -> pd.DataFrame:
    """Loader live par défaut : interroge ``risk_decisions`` via :class:`RiskRepository`."""
    from risk_management.db_io import RiskRepository

    repo = RiskRepository()
    acct = None if account_id in (None, "", "default") else account_id
    return repo.load_risk_decisions_for_date(trade_date, account_id=acct)


def _stub_replay_loader(trade_date: date, account_id: str) -> pd.DataFrame:
    """Loader replay « stub » : ré-utilise le live comme baseline (zéro divergence).

    Utilisé par défaut tant que le replay réel
    (``backtesting.signal_replay`` + ``backtesting.risk_bridge``) n'est pas
    intégré derrière une API stable. Permet à la CI de valider la mécanique
    parité (artefacts + alerting) sans BacktestEngine.
    """
    df = _default_live_loader(trade_date, account_id)
    if df.empty:
        return df
    out = df.copy()
    if "run_id" in out.columns:
        out["run_id"] = out["run_id"].astype(str) + "-replay-stub"
    return out


def build_replay_risk_context(tag: str, trade_date: date) -> dict:
    """Contexte risk ATTENDU d'un run backtest B4 pour une date donnée.

    Lit ``drawdown_breaker_daily.csv`` de l'artefact : régime SPY, allocation
    B4, état breaker (tripped, episode peak/trough/alloc), date du dernier
    réarmement <= date. Couvre le gate quotidien strict (régime C2 + allocation
    B4 + état breaker + rearm).
    """
    from pathlib import Path

    path = Path(f"f:/projets/artifacts/backtesting/{tag}/drawdown_breaker_daily.csv")
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    target = pd.Timestamp(trade_date)
    sub = df[df["trade_date"] <= target].copy()
    if sub.empty:
        return {}
    row = sub.iloc[-1]
    sub2 = sub.copy()
    sub2["prev_alloc"] = sub2["allocation_scale"].shift(1).fillna(1.0)
    re = sub2[(sub2["tripped"] == True) & (sub2["allocation_scale"] - sub2["prev_alloc"] >= 0.09)]
    rearm_date = str(re["trade_date"].iloc[-1].date()) if len(re) else None

    def _f(col):
        v = row.get(col)
        try:
            f = float(v)
            return None if f != f else f  # NaN -> None
        except (TypeError, ValueError):
            return None

    alloc_target = _f("alloc_target")
    if alloc_target is None:
        alloc_target = _f("allocation_scale")
    return {
        "regime": str(row.get("spy_regime") or ""),
        "trailing_policy": "c2",
        "allocation_scale": _f("allocation_scale") or 0.0,
        "breaker_tripped": bool(row.get("tripped")),
        "episode_peak": _f("episode_peak"),
        "episode_trough": _f("episode_trough"),
        "episode_alloc": alloc_target,
        "rearm_date": rearm_date,
        "force_close": False,
        "protections": {},
    }


def _persist_risk_layer_artifacts(
    trade_date: date,
    live_ctx: dict,
    replay_ctx: dict,
    divergences: list[dict],
) -> dict:
    """Persiste les contextes risk (live + replay) et les divergences du jour.

    Écrit sous ``artifacts/parity_runs/<date>/`` :
    - ``risk_layers_live.json`` / ``risk_layers_replay.json`` : contexte complet
      utilisé par le gate (régime, allocation, peak/trough, protections,
      force-close) — permet de REJOUER une divergence a posteriori ;
    - ``risk_layers_divergences.json`` : liste des divergences du jour ;
    - met à jour ``paper_coverage.json`` (accumulation des journées vertes).

    Retourne le dict des chemins écrits (vide si erreur d'écriture).
    """
    import json as _json

    day_dir = Path(f"f:/projets/artifacts/parity_runs/{trade_date.isoformat()}")
    day_dir.mkdir(parents=True, exist_ok=True)

    def _safe(v):
        try:
            _json.dumps(v)
            return v
        except (TypeError, ValueError):
            return str(v)

    paths: dict[str, Path] = {}
    try:
        paths["live"] = day_dir / "risk_layers_live.json"
        paths["live"].write_text(_json.dumps(_safe(live_ctx), indent=2, ensure_ascii=False), encoding="utf-8")
        paths["replay"] = day_dir / "risk_layers_replay.json"
        paths["replay"].write_text(_json.dumps(_safe(replay_ctx), indent=2, ensure_ascii=False), encoding="utf-8")
        paths["divergences"] = day_dir / "risk_layers_divergences.json"
        paths["divergences"].write_text(_json.dumps(_safe(divergences), indent=2, ensure_ascii=False), encoding="utf-8")

        # Accumulation du coverage paper (jours verts uniquement).
        from backtesting.parity import summarize_paper_coverage

        cov_path = Path("f:/projets/artifacts/parity_runs/paper_coverage.json")
        cov: dict = {}
        if cov_path.exists():
            try:
                cov = _json.loads(cov_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                cov = {}
        green = cov.get("green_days", [])
        if not divergences and trade_date.isoformat() not in green:
            green.append(trade_date.isoformat())
        contexts = cov.get("contexts", [])
        if not divergences:
            contexts = [c for c in contexts if c.get("date") != trade_date.isoformat()]
            contexts.append({"date": trade_date.isoformat(), **live_ctx})
        summary = summarize_paper_coverage([c for c in contexts if c.get("date") in green])
        cov.update({
            "green_days": sorted(green),
            "contexts": contexts,
            "summary": summary,
        })
        paths["coverage"] = cov_path
        cov_path.write_text(_json.dumps(cov, indent=2, ensure_ascii=False), encoding="utf-8")
        LOGGER.info(
            "[parity] risk layers persistés | date=%s live=%s replay=%s divergences=%d coverage=%s",
            trade_date, paths["live"].name, paths["replay"].name, len(divergences),
            "représentative" if summary.get("representative") else "pas encore représentative",
        )
    except Exception:  # noqa: BLE001
        LOGGER.warning("[parity] persistance risk_layers échouée", exc_info=True)
    return {k: v for k, v in paths.items() if v.exists()}


def build_arg_parser() -> argparse.ArgumentParser:
    today = date.today()
    p = argparse.ArgumentParser(description="Job quotidien de parité backtest ↔ live (Sprint S9).")
    p.add_argument("--trade-date", type=str, default=today.isoformat(),
                   help="Date au format YYYY-MM-DD (défaut : aujourd'hui).")
    p.add_argument("--account", default="default", help="ID du compte (défaut: default).")
    p.add_argument("--threshold", type=float, default=DEFAULT_DIVERGENCE_THRESHOLD,
                   help="Seuil de divergence_score déclenchant l'alerte.")
    p.add_argument("--qty-tolerance-pct", type=float, default=DEFAULT_QTY_TOLERANCE_PCT,
                   help="Tolérance relative sur approved_shares.")
    p.add_argument("--qty-tolerance-abs", type=float, default=DEFAULT_QTY_TOLERANCE_ABS,
                   help="Tolérance absolue sur approved_shares (en parts).")
    p.add_argument("--artifacts-dir", default=str(DEFAULT_ARTIFACTS_DIR),
                   help="Dossier d'écriture des artefacts.")
    p.add_argument("--no-alert", action="store_true", help="Désactive l'envoi d'alerte.")
    p.add_argument("--use-stub-replay", action="store_true",
                   help="Utilise un replay stub (live recopié) — utile en CI.")
    # E23 — gate quotidien des couches risk (régime C2 + allocation B4 + état breaker)
    p.add_argument("--replay-tag", default="e23b4_main",
                   help="Tag de l'artefact backtest de référence pour le contexte risk (défaut: e23b4_main).")
    p.add_argument("--live-risk-context", default=None, metavar="PATH_JSON",
                   help="Chemin vers le JSON du contexte risk LIVE (émit par le flux paper/live). "
                        "Si absent, on se limite au contexte replay (référence) sans comparaison.")
    p.add_argument("--risk-float-tol", type=float, default=1e-6,
                   help="Tolérance flottante (minuscule) sur allocation/épisode/protections.")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    configure_root_logging(level=logging.INFO, log_path="./log/run_daily_parity.log",
                          fmt="%(asctime)s %(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    try:
        trade_date_value = date.fromisoformat(args.trade_date)
    except ValueError:
        LOGGER.error("[parity] --trade-date invalide: %s", args.trade_date)
        return 1

    notifier = None if args.no_alert else build_notifier_from_env()
    replay_loader = _stub_replay_loader if args.use_stub_replay else _default_replay_loader

    try:
        report = run_daily_parity(
            trade_date_value,
            live_loader=_default_live_loader,
            replay_loader=replay_loader,
            account_id=args.account,
            artifacts_dir=Path(args.artifacts_dir),
            notifier=notifier,
            divergence_threshold=float(args.threshold),
            qty_tolerance_pct=float(args.qty_tolerance_pct),
            qty_tolerance_abs=float(args.qty_tolerance_abs),
        )
    except Exception:
        LOGGER.exception("[parity] échec inattendu du job")
        return 1

    LOGGER.info(
        "[parity] résumé | date=%s account=%s matched=%d divergent=%d score=%.4f live_run=%s replay_run=%s",
        report.trade_date, report.account_id, report.n_matched, report.n_divergent,
        report.divergence_score, report.live_run_id, report.replay_run_id,
    )

    # ── E23 — gate quotidien des couches risk (régime C2 / allocation B4 / état breaker) ──
    exit_code = 2 if report.divergence_score > float(args.threshold) else 0
    replay_ctx = build_replay_risk_context(str(args.replay_tag), trade_date_value)
    if replay_ctx and args.live_risk_context:
        from pathlib import Path as _P
        import json as _json

        live_path = _P(args.live_risk_context)
        if live_path.exists():
            try:
                live_ctx = _json.loads(live_path.read_text(encoding="utf-8"))
                divergences = compare_risk_layers(live_ctx, replay_ctx, float_tol=float(args.risk_float_tol))
                # Persister le contexte live/replay complet + divergences pour rejouer
                # toute anomalie a posteriori (gate paper : nécessaire au coverage check).
                _persist_risk_layer_artifacts(trade_date_value, live_ctx, replay_ctx, divergences)
                if divergences:
                    LOGGER.error(
                        "[parity] RISK_LAYERS divergence (%d) | date=%s\n%s",
                        len(divergences), trade_date_value,
                        "\n".join(
                            f"  {d['layer']}: live={d['live']!r} replay={d['replay']!r}"
                            for d in divergences
                        ),
                    )
                    exit_code = 2
                    if notifier is not None:
                        try:
                            notifier(
                                f"RISK_LAYERS divergence {trade_date_value}",
                                "\n".join(
                                    f"{d['layer']}: live={d['live']!r} replay={d['replay']!r}"
                                    for d in divergences[:25]
                                ),
                            )
                        except Exception:  # noqa: BLE001
                            LOGGER.warning("[parity] envoi alerte risk_layers échoué", exc_info=True)
                else:
                    LOGGER.info("[parity] RISK_LAYERS ok | date=%s régime=%s alloc=%.4f tripped=%s",
                                trade_date_value, replay_ctx.get("regime"),
                                float(replay_ctx.get("allocation_scale") or 0.0),
                                replay_ctx.get("breaker_tripped"))
            except Exception:  # noqa: BLE001
                LOGGER.exception("[parity] comparaison risk_layers échouée")
        else:
            LOGGER.warning("[parity] --live-risk-context introuvable: %s", args.live_risk_context)
    elif replay_ctx:
        LOGGER.info(
            "[parity] contexte risk replay dispo (régime=%s alloc=%.4f tripped=%s) — "
            "fournir --live-risk-context pour activer la comparaison",
            replay_ctx.get("regime"), float(replay_ctx.get("allocation_scale") or 0.0),
            replay_ctx.get("breaker_tripped"),
        )
    return exit_code


def _default_replay_loader(trade_date: date, account_id: str) -> pd.DataFrame:
    """Loader replay réel — délègue à ``backtesting.parity_replay`` si dispo,
    sinon retombe sur le stub avec WARNING.

    Le module ``backtesting/parity_replay.py`` (replay backtest réel via
    ``signal_replay`` + ``risk_bridge``) est laissé en TODO post-S9 :
    nécessite de figer une API stable au-dessus de
    ``RiskRepository.load_selection_inputs_asof`` + ``PortfolioBuilder``.
    """
    try:
        from backtesting.parity_replay import replay_decisions_for_date  # type: ignore[import-not-found]
        return replay_decisions_for_date(trade_date, account_id=account_id)
    except ImportError:
        LOGGER.warning(
            "[parity] backtesting.parity_replay indisponible -> stub (live=replay). "
            "Implémenter parity_replay pour activer la comparaison effective."
        )
        return _stub_replay_loader(trade_date, account_id)


if __name__ == "__main__":
    sys.exit(main())

