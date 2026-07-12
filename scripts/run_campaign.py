#!/usr/bin/env python
"""scripts/run_campaign.py — Entrypoint de campagne shadow/paper (Point 13).

Usage :
    python scripts/run_campaign.py init \
        --campaign-id shadow_2026Q3 \
        --phase shadow \
        --model-run-id mdl_abc123 \
        --approved-by "operator@example.com"

    python scripts/run_campaign.py daily \
        --campaign-id shadow_2026Q3 \
        [--trade-date 2026-07-12]

    python scripts/run_campaign.py report \
        --campaign-id shadow_2026Q3

    python scripts/run_campaign.py promote \
        --campaign-id shadow_2026Q3 \
        --approved-by "manager@example.com"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def cmd_init(args: argparse.Namespace) -> None:
    """Initialise une nouvelle campagne."""
    from risk_management.campaign_orchestrator import (
        CampaignPhase, create_campaign,
    )

    phase = args.phase or CampaignPhase.SHADOW
    dry_run = phase == CampaignPhase.SHADOW

    orchestrator = create_campaign(
        campaign_id=args.campaign_id,
        phase=phase,
        model_run_id=args.model_run_id,
        policy_version=args.policy_version,
        config_fingerprint=args.config_fingerprint,
        run_mode=args.run_mode or phase,
        dry_run=dry_run,
        approved_by=args.approved_by,
        start_date=date.today(),
        auto_promote=args.auto_promote,
        frozen_model_path=args.frozen_model_path or "",
        frozen_calibrator_path=args.frozen_calibrator_path or "",
        frozen_config_path=args.frozen_config_path or "",
    )

    print(f"Campagne initialisée : {orchestrator.config.campaign_id}")
    print(f"  Phase     : {orchestrator.config.phase}")
    print(f"  Modèle    : {orchestrator.config.model_run_id}")
    print(f"  Dry-run   : {orchestrator.config.dry_run}")
    print(f"  Approved  : {orchestrator.config.approved_by or 'N/A'}")
    print(f"  Répertoire: {orchestrator.campaign_dir}")


def cmd_daily(args: argparse.Namespace) -> None:
    """Exécute le cycle quotidien de campagne."""
    from risk_management.campaign_orchestrator import CampaignOrchestrator, CampaignConfig

    campaign_dir = PROJECT_ROOT / "artifacts" / "campaigns" / args.campaign_id
    config_path = campaign_dir / "campaign_config.json"

    if not config_path.exists():
        print(f"Campagne introuvable : {args.campaign_id}")
        print(f"  -> Lancer d'abord : python scripts/run_campaign.py init --campaign-id {args.campaign_id} ...")
        sys.exit(1)

    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config = CampaignConfig(
        campaign_id=config_data["campaign_id"],
        phase=config_data.get("phase", "shadow"),
        start_date=date.fromisoformat(config_data["start_date"]) if config_data.get("start_date") else date.today(),
        model_run_id=config_data.get("model_run_id", ""),
        policy_version=int(config_data.get("policy_version", 1)),
        config_fingerprint=config_data.get("config_fingerprint", ""),
        run_mode=config_data.get("run_mode", "shadow"),
        dry_run=bool(config_data.get("dry_run", True)),
        frozen_artifacts=config_data.get("frozen_artifacts", {}),
    )

    orchestrator = CampaignOrchestrator(config)
    td = date.fromisoformat(args.trade_date) if args.trade_date else date.today()

    print(f"Campaign daily cycle | id={args.campaign_id} date={td}")
    result = orchestrator.run_daily_cycle(trade_date=td)

    print(f"  Status          : {result.status}")
    print(f"  Entries         : {result.entries_count} ({result.entries_long}L/{result.entries_short}S)")
    if not config.dry_run:
        print(f"  Orders          : {result.orders_submitted} submitted, {result.orders_filled} filled, {result.orders_failed} failed")
        if result.slippage_median_bps:
            print(f"  Slippage median : {result.slippage_median_bps:.1f} bps")
    if result.shadow_divergence_rate > 0:
        print(f"  Divergence      : {result.shadow_divergence_rate:.4f}")
    if result.errors:
        print(f"  Errors          : {result.errors}")


def cmd_report(args: argparse.Namespace) -> None:
    """Produit le rapport de campagne."""
    from risk_management.campaign_orchestrator import CampaignOrchestrator, CampaignConfig

    campaign_dir = PROJECT_ROOT / "artifacts" / "campaigns" / args.campaign_id
    config_path = campaign_dir / "campaign_config.json"

    if not config_path.exists():
        print(f"Campagne introuvable : {args.campaign_id}")
        sys.exit(1)

    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config = CampaignConfig(
        campaign_id=config_data["campaign_id"],
        phase=config_data.get("phase", "shadow"),
        start_date=date.fromisoformat(config_data["start_date"]) if config_data.get("start_date") else date.today(),
        model_run_id=config_data.get("model_run_id", ""),
        policy_version=int(config_data.get("policy_version", 1)),
        config_fingerprint=config_data.get("config_fingerprint", ""),
        run_mode=config_data.get("run_mode", "shadow"),
        dry_run=bool(config_data.get("dry_run", True)),
    )

    orchestrator = CampaignOrchestrator(config)
    report = orchestrator.build_campaign_report()

    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))

    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(f"\nRapport sauvegardé → {args.output}")


def cmd_promote(args: argparse.Namespace) -> None:
    """Tente de promouvoir la campagne au palier suivant."""
    from risk_management.campaign_orchestrator import CampaignOrchestrator, CampaignConfig, CampaignPhase

    campaign_dir = PROJECT_ROOT / "artifacts" / "campaigns" / args.campaign_id
    config_path = campaign_dir / "campaign_config.json"

    if not config_path.exists():
        print(f"Campagne introuvable : {args.campaign_id}")
        sys.exit(1)

    config_data = json.loads(config_path.read_text(encoding="utf-8"))
    config = CampaignConfig(
        campaign_id=config_data["campaign_id"],
        phase=config_data.get("phase", "shadow"),
        start_date=date.fromisoformat(config_data["start_date"]) if config_data.get("start_date") else date.today(),
        model_run_id=config_data.get("model_run_id", ""),
        policy_version=int(config_data.get("policy_version", 1)),
        config_fingerprint=config_data.get("config_fingerprint", ""),
        run_mode=config_data.get("run_mode", "shadow"),
        dry_run=bool(config_data.get("dry_run", True)),
    )

    orchestrator = CampaignOrchestrator(config)
    can_promote, issues = orchestrator._check_promotion_gates()

    if not can_promote:
        print("PROMOTION REFUSÉE — gates en échec :")
        for issue in issues:
            print(f"  ❌ {issue}")
        sys.exit(1)

    if not args.approved_by:
        print("PROMOTION BLOQUÉE — approbation humaine requise (--approved-by)")
        sys.exit(1)

    # Promotion : shadow → paper, paper → live_5pct, etc.
    next_phase = {
        CampaignPhase.SHADOW: CampaignPhase.PAPER,
        CampaignPhase.PAPER: "live_5pct",
    }.get(config.phase, config.phase)

    config.phase = next_phase
    config.dry_run = next_phase == CampaignPhase.SHADOW
    config.approved_by = args.approved_by
    config.approved_at = datetime.now()

    # Persister la config mise à jour
    (campaign_dir / "campaign_config.json").write_text(
        json.dumps(config.to_dict(), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # Enregistrer l'approbation dans le journal immuable
    try:
        from risk_management.immutable_journal import ImmutableJournal
        journal = ImmutableJournal.load_or_create(
            str(campaign_dir / "approval_journal.json")
        )
        journal.add_entry(
            entry_type="campaign_promotion",
            payload={
                "campaign_id": args.campaign_id,
                "from_phase": config_data.get("phase"),
                "to_phase": next_phase,
                "approved_by": args.approved_by,
                "approved_at": datetime.now().isoformat(),
                "reason": args.reason or "",
            },
        )
        journal.save_atomic(str(campaign_dir / "approval_journal.json"))
    except ImportError:
        pass

    print(f"✅ Campagne promue : {config_data.get('phase')} → {next_phase}")
    print(f"   Approuvé par : {args.approved_by}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Campagne shadow/paper — Point 13",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialiser une nouvelle campagne")
    p_init.add_argument("--campaign-id", required=True)
    p_init.add_argument("--phase", default="shadow", choices=["shadow", "paper"])
    p_init.add_argument("--model-run-id", required=True)
    p_init.add_argument("--policy-version", type=int, default=1)
    p_init.add_argument("--config-fingerprint", default="")
    p_init.add_argument("--run-mode", default="", choices=["shadow", "paper"])
    p_init.add_argument("--approved-by")
    p_init.add_argument("--auto-promote", action="store_true")
    p_init.add_argument("--frozen-model-path", default="")
    p_init.add_argument("--frozen-calibrator-path", default="")
    p_init.add_argument("--frozen-config-path", default="")

    # daily
    p_daily = sub.add_parser("daily", help="Exécuter le cycle quotidien")
    p_daily.add_argument("--campaign-id", required=True)
    p_daily.add_argument("--trade-date")

    # report
    p_report = sub.add_parser("report", help="Produire le rapport de campagne")
    p_report.add_argument("--campaign-id", required=True)
    p_report.add_argument("--output")

    # promote
    p_promote = sub.add_parser("promote", help="Promouvoir au palier suivant")
    p_promote.add_argument("--campaign-id", required=True)
    p_promote.add_argument("--approved-by", required=True)
    p_promote.add_argument("--reason", default="")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "daily":
        cmd_daily(args)
    elif args.command == "report":
        cmd_report(args)
    elif args.command == "promote":
        cmd_promote(args)


if __name__ == "__main__":
    main()
