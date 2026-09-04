"""scripts/send_batch_email.py — Notification de fin de batch (email + Telegram OK/ERROR).

Appelé par les launchers PowerShell en fin d'exécution :
    scripts/windows/analyst_snapshot_launcher.ps1
    scripts/windows/earnings_calendar_launcher.ps1

Arguments :
    --event       analyst_snapshot_collect | earnings_calendar_sync
    --status      OK | ERROR
    --exit-code   code de sortie du batch
    --duration    durée d'exécution (ex. 0h05m12s)
    --log-file    chemin du fichier temporaire contenant la sortie de CE run

Canal email : ``ihm.services.email_notifier`` (env ``ALPHA_TRADE_EMAIL_*`` /
``ALPHA_TRADE_SMTP_*``). Canal Telegram : ``service.telegram`` (env
``TOKEN_TELEGRAM_BOT`` / ``TELEGRAM_CHAT_ID``) — message OK/ERROR de fin de batch.
Best-effort : ne fait JAMAIS échouer le batch (email ou Telegram désactivé ou en erreur → 0).
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


def _send_telegram_status(args) -> bool:
    """Envoie un message Telegram de fin de batch (OK/ERROR) — best-effort.

    Token lu depuis ``TOKEN_TELEGRAM_BOT``, chat cible depuis ``TELEGRAM_CHAT_ID``
    (via ``service.telegram``). Ne lève jamais ; retourne ``False`` si le canal
    n'est pas configuré ou si l'envoi échoue (le batch n'est jamais impacté).
    """
    from service.telegram import (
        TelegramConfigError,
        is_telegram_configured,
        send_telegram_message,
    )

    if not is_telegram_configured():
        print(
            "send_batch_email: Telegram non configuré (TOKEN_TELEGRAM_BOT absent) — message non envoyé.",
            file=sys.stderr,
        )
        return False

    ok_status = args.status == "OK"
    label = "OK" if ok_status else "ERROR"
    icon = "✅" if ok_status else "❌"
    lines = [f"{icon} [{args.event}] Fin de batch — {label}"]
    if args.duration:
        lines.append(f"Durée : {args.duration}")
    if args.exit_code:
        lines.append(f"Code retour : {args.exit_code}")
    # Court extrait des logs (dernières lignes) pour contexte du run.
    excerpt = _read_run_log(args.log_file, max_lines=10, max_chars=1200)
    if excerpt and excerpt != "(aucune sortie capturée pour ce run)":
        lines.append(f"Logs (fin) :\n{excerpt}")
    message = "\n".join(lines)

    try:
        ok = send_telegram_message(message)
    except TelegramConfigError as exc:
        print(f"send_batch_email: échec envoi Telegram (config) : {exc}", file=sys.stderr)
        return False
    if not ok:
        print(
            "send_batch_email: échec envoi Telegram (réseau/API) — voir logs service.telegram.",
            file=sys.stderr,
        )
        return False
    print(f"send_batch_email: message Telegram {label} envoyé.")
    return True


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

    # ── Telegram de fin de batch (OK/ERROR) — best-effort ──
    # Message envoyé indépendamment du canal email, si le token est configuré.
    try:
        _send_telegram_status(args)
    except Exception as exc:  # noqa: BLE001 — ne fait jamais échouer le batch
        print(f"send_batch_email: échec envoi Telegram : {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
