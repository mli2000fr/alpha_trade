"""scripts/send_batch_email.py — Envoie un mail de fin de batch (statut + logs du run).

Appelé par les launchers PowerShell en fin d'exécution :
    scripts/windows/analyst_snapshot_launcher.ps1
    scripts/windows/earnings_calendar_launcher.ps1

Arguments :
    --event       analyst_snapshot_collect | earnings_calendar_sync
    --status      OK | ERROR
    --exit-code   code de sortie du batch
    --duration    durée d'exécution (ex. 0h05m12s)
    --log-file    chemin du fichier temporaire contenant la sortie de CE run

Utilise ``ihm.services.email_notifier`` (env ``ALPHA_TRADE_EMAIL_*`` / ``ALPHA_TRADE_SMTP_*``).
Best-effort : ne fait JAMAIS échouer le batch (email désactivé ou en erreur → 0).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _read_run_log(log_file: str, *, max_lines: int, max_chars: int) -> str:
    """Lit la sortie capturée de CE run (fichier temporaire écrit par le launcher)."""
    lines: list[str] = []
    if log_file:
        p = Path(log_file)
        if p.exists():
            try:
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                lines = []
    if not lines:
        return "(aucune sortie capturée pour ce run)"
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = "… (tronqué)\n" + text[-max_chars:]
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Email de fin de batch (statut + logs).")
    parser.add_argument("--event", required=True)
    parser.add_argument("--status", required=True, choices=["OK", "ERROR"])
    parser.add_argument("--exit-code", type=int, default=0)
    parser.add_argument("--duration", default="")
    parser.add_argument("--log-file", default="")
    parser.add_argument("--max-lines", type=int, default=300)
    parser.add_argument("--max-chars", type=int, default=20000)
    args = parser.parse_args()

    log_text = _read_run_log(args.log_file, max_lines=args.max_lines, max_chars=args.max_chars)

    payload = {
        "batch": args.event,
        "status": args.status,
        "exit_code": args.exit_code,
        "duration": args.duration,
        # Liste de lignes → rendu lisible dans le JSON du mail (une ligne par entrée).
        "logs_du_run": log_text.splitlines() if log_text else ["(aucune sortie)"],
    }

    from ihm.services.email_notifier import send_notification

    try:
        sent = send_notification(event=f"{args.event}_{args.status.lower()}", payload=payload)
    except Exception as exc:  # noqa: BLE001 — best-effort
        print(f"send_batch_email: échec envoi email : {exc}", file=sys.stderr)
        return 0  # ne fait jamais échouer le batch
    if not sent:
        print(
            "send_batch_email: notificateur désactivé (ALPHA_TRADE_EMAIL_ENABLED != 1) — email non envoyé.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
