"""scripts/send_batch_email.py — Notification de fin de batch (email + Telegram OK/ERROR).

Appelé par les launchers PowerShell en fin d'exécution :
    scripts/windows/analyst_snapshot_launcher.ps1
    scripts/windows/earnings_calendar_launcher.ps1

Arguments :
    --event       analyst_snapshot_collect | earnings_calendar_sync | market_cap_sync
    --status      OK | ERROR
    --exit-code   code de sortie du batch
    --duration    durée d'exécution (ex. 0h05m12s)
    --log-file    chemin du fichier temporaire contenant la sortie de CE run
    --warning     (répétable) avertissement du run (ex. symbols_file absent /
                  introuvable → repli active-tradable). Ajouté au mail
                  (payload ``warnings`` + en-tête des logs) et au message Telegram.
    --passage     principal | secours | manuel. Sur erreur, identifie sans
                  ambiguïté le passage dans le sujet email et Telegram.

Canal email : ``ihm.services.email_notifier`` (env ``ALPHA_TRADE_EMAIL_*`` /
``ALPHA_TRADE_SMTP_*``). Canal Telegram : ``service.telegram`` (env
``TOKEN_TELEGRAM_BOT`` / ``TELEGRAM_CHAT_ID``) — message OK/ERROR de fin de batch.
Best-effort : ne fait JAMAIS échouer le batch (email ou Telegram désactivé ou en erreur → 0).
"""
from __future__ import annotations

import argparse
import json
import re
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

RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
PASSAGE_LABELS = {
    "principal": "premier passage (principal)",
    "secours": "second passage (secours conditionnel)",
    "manuel": "lancement manuel",
}
PASSAGE_EVENT_CODES = {
    "principal": "premier_passage",
    "secours": "second_passage",
    "manuel": "lancement_manuel",
}


def _extract_run_summaries(log_text: str) -> list[dict]:
    summaries: list[dict] = []
    for line in log_text.splitlines():
        marker = line.find(RUN_SUMMARY_PREFIX)
        if marker < 0:
            continue
        try:
            payload = json.loads(line[marker + len(RUN_SUMMARY_PREFIX):].strip())
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            summaries.append(payload)
    return summaries


def _as_count(value, default: int = 0) -> int:
    if isinstance(value, (list, tuple, set, dict)):
        return len(value)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _first_count(summary: dict, names: tuple[str, ...], default: int = 0) -> int:
    for name in names:
        if name in summary and summary[name] is not None:
            return _as_count(summary[name], default)
    return default


def _sum_first_counts(summaries: list[dict], names: tuple[str, ...]) -> int:
    return sum(_first_count(summary, names) for summary in summaries)


def _sum_matching_counts(summaries: list[dict], suffix: str) -> int:
    total = 0
    for summary in summaries:
        total += sum(
            _as_count(value)
            for key, value in summary.items()
            if str(key).endswith(suffix)
        )
    return total


def _extract_error_message(log_text: str, summary: dict, *, status: str) -> str:
    for key in ("error_message", "error", "fatal_error", "reason"):
        value = summary.get(key)
        if value:
            return str(value).strip()[:1000]
    if status != "ERROR":
        return ""
    pattern = re.compile(r"(error|exception|traceback|failed|échec)", re.IGNORECASE)
    candidates = [line.strip() for line in log_text.splitlines() if pattern.search(line)]
    return (candidates[-1] if candidates else "Échec sans message détaillé dans la sortie capturée.")[:1000]


def _build_metrics(args, log_text: str) -> dict[str, object]:
    summaries = _extract_run_summaries(log_text)
    summary = summaries[-1] if summaries else {}
    requested = args.requested if args.requested is not None else _sum_first_counts(
        summaries,
        ("requested", "requested_count", "requested_symbols", "symbols_requested", "symbols", "total"),
    )
    received = args.received if args.received is not None else _sum_first_counts(
        summaries,
        ("received", "received_count", "successful_symbols", "completed_symbols", "resolved"),
    )
    persisted = args.persisted if args.persisted is not None else _sum_first_counts(
        summaries,
        ("persisted", "persisted_count", "stored", "rows_upserted", "total_rows_upserted"),
    )
    if args.persisted is None and persisted == 0:
        persisted = _sum_matching_counts(summaries, "_rows_inserted")
    failed = args.failed if args.failed is not None else _sum_first_counts(
        summaries, ("failed", "failed_count", "failed_symbols", "symbols_failed")
    )
    alerts = args.alerts if args.alerts is not None else _sum_first_counts(
        summaries, ("warning_count", "warnings", "alerts")
    )
    if args.alerts is None:
        alerts += _sum_first_counts(summaries, ("rate_limit_count",))
        alerts += _sum_first_counts(summaries, ("temporary_error_count",))
        alerts += _sum_first_counts(summaries, ("schema_error_count",))
        alerts += _sum_first_counts(summaries, ("parse_error_count",))
    alerts = max(alerts, len(args.warning or []))
    if args.status == "ERROR" and failed == 0:
        failed = 1
    error_message = args.error_message or _extract_error_message(
        log_text, summary, status=args.status,
    )
    return {
        "requested": requested,
        "received": received,
        "persisted": persisted,
        "failed": failed,
        "alerts": alerts,

        "error_message": error_message,
    }

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
    if ok_status:
        # Message succès : volontairement concis.
        lines = [f"✅ [{args.event}] Fin de batch — OK"]
        if args.duration:
            lines.append(f"Durée : {args.duration}")
    else:
        # Message erreur : très visible (bandeau + emojis d'alerte).
        lines = [f"🚨🚨⛔ ÉCHEC DU BATCH — {args.event} ⛔🚨🚨", "❌ Fin de batch — ERROR"]
        if args.duration:
            lines.append(f"Durée : {args.duration}")
        if args.exit_code:
            lines.append(f"Code retour : {args.exit_code}")
        passage = str(getattr(args, "passage", "") or "").strip()
        if passage:
            lines.append(f"Passage : {PASSAGE_LABELS.get(passage, passage)}")
    metrics = args.metrics
    lines.append(
        "Demandés {requested} · reçus {received} · persistés {persisted} · "
        "échecs {failed} · alertes {alerts}".format(**metrics)
    )
    if args.status == "ERROR" and metrics.get("error_message"):
        lines.append(f"Erreur : {metrics['error_message']}")

    warnings = list(getattr(args, "warning", None) or [])
    if warnings:
        lines.append("")
        lines.append("⚠️ Avertissements :")
        lines.extend(f"• {warning}" for warning in warnings)
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
    parser.add_argument("--warning", action="append", default=[], help="Avertissement du run (répétable) : symbols_file absent/introuvable → repli active-tradable.")
    parser.add_argument("--max-lines", type=int, default=300)
    parser.add_argument("--requested", type=int)
    parser.add_argument("--received", type=int)
    parser.add_argument("--persisted", type=int)
    parser.add_argument("--failed", type=int)
    parser.add_argument("--alerts", type=int)
    parser.add_argument("--error-message", default="")
    parser.add_argument("--passage", choices=["principal", "secours", "manuel"], default="")
    parser.add_argument("--max-chars", type=int, default=20000)
    args = parser.parse_args()

    log_text = _read_run_log(args.log_file, max_lines=args.max_lines, max_chars=args.max_chars)
    warnings = list(args.warning or [])

    # Logs du run : on place les avertissements EN TÊTE pour une visibilité immédiate.
    metrics = _build_metrics(args, log_text)
    args.metrics = metrics
    log_lines = log_text.splitlines() if log_text else ["(aucune sortie)"]
    if warnings:
        log_lines = ["⚠️ AVERTISSEMENTS (univers) :"] + [f"- {warning}" for warning in warnings] + ["-----"] + log_lines

    payload = {
        "batch": args.event,
        "status": args.status,
        "exit_code": args.exit_code,
        "duration": args.duration,
        # Avertissements (symbols_file absent/introuvable → repli univers).
        "warnings": warnings,
        # Liste de lignes → rendu lisible dans le JSON du mail (une ligne par entrée).
        "requested": metrics["requested"],
        "received": metrics["received"],
        "persisted": metrics["persisted"],
        "failed": metrics["failed"],
        "alerts": metrics["alerts"],
        "error_message": metrics["error_message"],
        "passage": args.passage,
        "passage_label": PASSAGE_LABELS.get(args.passage, args.passage),
        "logs_du_run": log_lines,
    }

    from ihm.services.email_notifier import send_notification

    sent = False
    email_failed = False
    try:
        notification_event = f"{args.event}_{args.status.lower()}"
        if args.status == "ERROR" and args.passage:
            passage_code = PASSAGE_EVENT_CODES.get(args.passage, args.passage)
            notification_event = f"{args.event}_{passage_code}_{args.status.lower()}"
        sent = send_notification(event=notification_event, payload=payload)
    except Exception as exc:  # noqa: BLE001 — best-effort
        email_failed = True
        print(f"send_batch_email: échec envoi email : {exc}", file=sys.stderr)
    if not sent and not email_failed:
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
