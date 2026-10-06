"""Read-only France research catalogue shared by UI and CLI. No SQL or broker."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "artifacts/fr/research"
CATALOG = {
    "oracle_h5_repaired": ("Oracle H5 — après réparation fold 7", "fold7_repair/rebuild-20261003-v1/confirmation/oracle/fr-oracle-h5-6e72b9d2e600/report.json", "ml"),
    "direction_h5_repaired": ("Direction H5 — après réparation fold 7", "fold7_repair/rebuild-20261003-v1/confirmation/direction/fr-shared-direction-h5-6c203bea5a09/report.json", "ml"),
    "oracle_h5": ("Oracle amplitude H5 — pilote initial archivé", "oracle_h5_pilot/fr-oracle-h5-d0f5fe0e2b07/report.json", "ml"),
    "direction_h5": ("Direction H5 — diagnostic exploratoire", "direction_h5_shared/fr-shared-direction-h5-5387843f8432/report.json", "ml"),
    "robustness_13d": ("Replay économique — robustesse 13-D", "robustness_13d/fixed-20261004-v2/report.json", "economic"),
}


def load_campaign(identifier: str, *, root: Path = RESEARCH) -> dict:
    """Only allow curated FR paths; unknown/missing reports never fall back to US."""
    if identifier not in CATALOG:
        raise ValueError("Campagne FR inconnue")
    label, relative, kind = CATALOG[identifier]
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Rapport hors du périmètre FR")
    raw = path.read_bytes()
    report = json.loads(raw)
    if report.get("serving_enabled") is not False or report.get("canonical_writes") is not False:
        raise ValueError("Rapport non conforme à la recherche sans serving/écriture canonique")
    config = report.get("config", {})
    if kind == "ml":
        if config.get("market_code") != "FR_EQ" or config.get("horizon") != 5:
            raise ValueError("Contrat modèle FR H5 absent")
    else:
        if (report.get("status") != "COMPLETED_EXPLORATORY_SENSITIVITY"
                or report.get("economic_go_allowed") is not False
                or report.get("strict_sprint13_complete") is not False
                or report.get("confirmation_2026_evaluated") is not False):
            raise ValueError("Contrat économique exploratoire incompatible")
        protocol_path = path.parent / "protocol.json"
        if hashlib.sha256(protocol_path.read_bytes()).hexdigest() != report.get("protocol_sha256"):
            raise ValueError("Hash du protocole FR incorrect")
        config = json.loads(protocol_path.read_text(encoding="utf-8"))
    return {
        "campaign_id": identifier, "label": label, "kind": kind,
        "market_code": "FR_EQ", "database": "alpha_trade_fr",
        "currency": "EUR", "calendar": "XPAR", "oracle_horizon": 5,
        "report_path": str(path), "report_sha256": hashlib.sha256(raw).hexdigest(),
        "status": report.get("status", report.get("verdict", "REPORT_AVAILABLE")),
        "serving_enabled": False, "live_enabled": False,
        "report": report, "manifest": config,
    }


def economic_rows(campaign: dict) -> list[dict]:
    if campaign["kind"] != "economic":
        return []
    rows = []
    for cell in campaign["report"].get("cells", []):
        metrics = cell.get("metrics") or {}
        costs = metrics.get("costs_eur") or {}
        rows.append({
            "Marché": "FR_EQ", "Devise": "EUR", "Fold": cell["fold"],
            "Politique": cell["policy"], "Variante": cell["variant"],
            "Fiscalité": cell["tax_scenario"], "Coûts": cell["cost_scenario"],
            "État": cell["status"], "Rendement net %": metrics.get("net_return_pct"),
            "PnL net EUR": metrics.get("net_pnl_eur"),
            "Sharpe": metrics.get("daily_sharpe"), "Drawdown %": metrics.get("max_drawdown_pct"),
            "Exposition brute %": metrics.get("mean_gross_exposure_pct"),
            "Trades": metrics.get("closed_trades"), "Win rate": metrics.get("win_rate"),
            **{f"{name} EUR": costs.get(key) for name, key in (
                ("Commission", "commission"), ("Spread", "spread"),
                ("Slippage", "slippage"), ("Taxes", "taxes"))},
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", choices=tuple(CATALOG), default="robustness_13d")
    args = parser.parse_args()
    print(json.dumps(load_campaign(args.campaign), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
