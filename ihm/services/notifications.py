"""Service IHM — Notifications email à la fin d'un workflow / step pipeline.

Sprint S27 / Notifications pipeline.

Hook backend : appelé depuis ``ihm.services.process_registry`` à la fin de
chaque ``_finalize_if_needed`` (steps top-level) et ``_finalize_workflow_record``
(workflows). Aucune dépendance à Streamlit pour rester utilisable depuis les
threads de fond.

Anti-doublon : un fichier marqueur ``notification_sent.flag`` est posé dans
le dossier du run. Si l'envoi échoue, le marqueur N'est pas posé, ce qui
permet une nouvelle tentative au prochain appel.

Configuration SMTP : variables d'environnement prioritaires
``ALPHA_TRADE_SMTP_HOST/_PORT/_USER/_PASSWORD/_FROM/_USE_TLS/_USE_SSL``.
Fallback sur la section ``notifications.smtp`` de ``config.yaml``
(mot de passe via placeholder ``${vault:smtp_password}``).
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Mapping

from ihm.services.notifications_preferences import (
    NotificationPreferences,
    load_persisted_notification_preferences,
)

LOGGER = logging.getLogger(__name__)

NOTIFICATION_FLAG_FILENAME = "notification_sent.flag"
LOG_TAIL_LINES = 200
ATTACHMENT_MAX_BYTES = 5 * 1024 * 1024  # 5 Mo

_TERMINAL_STATUSES = frozenset({"completed", "failed", "timeout", "stopped"})


# ---------------------------------------------------------------------------
# Config SMTP
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SmtpConfig:
    host: str
    port: int
    username: str | None
    password: str | None
    sender: str
    use_tls: bool = True
    use_ssl: bool = False

    @property
    def is_configured(self) -> bool:
        return bool(self.host and self.port and self.sender)


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_smtp_config() -> SmtpConfig:
    """Charge la config SMTP — env vars prioritaires sinon ``config.yaml``."""
    cfg_section: Mapping[str, Any] = {}
    try:
        from common.config_loader import load_config

        cfg = load_config()
        notif = cfg.get("notifications") if isinstance(cfg, dict) else None
        if isinstance(notif, dict):
            smtp = notif.get("smtp")
            if isinstance(smtp, dict):
                cfg_section = smtp
    except Exception:
        LOGGER.debug("load_smtp_config: lecture config.yaml ignorée", exc_info=True)

    host = os.getenv("ALPHA_TRADE_SMTP_HOST") or str(cfg_section.get("host") or "").strip()
    port_raw = os.getenv("ALPHA_TRADE_SMTP_PORT") or cfg_section.get("port") or 587
    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        port = 587
    username = os.getenv("ALPHA_TRADE_SMTP_USER") or (str(cfg_section.get("username") or "").strip() or None)
    password = os.getenv("ALPHA_TRADE_SMTP_PASSWORD") or (str(cfg_section.get("password") or "").strip() or None)
    sender = (
        os.getenv("ALPHA_TRADE_SMTP_FROM")
        or str(cfg_section.get("from") or "").strip()
        or username
        or ""
    )
    use_tls_env = os.getenv("ALPHA_TRADE_SMTP_USE_TLS")
    use_tls = _truthy(use_tls_env) if use_tls_env is not None else bool(cfg_section.get("use_tls", True))
    use_ssl_env = os.getenv("ALPHA_TRADE_SMTP_USE_SSL")
    use_ssl = _truthy(use_ssl_env) if use_ssl_env is not None else bool(cfg_section.get("use_ssl", False))

    # Si placeholder vault non résolu (laissé tel quel par config_loader).
    if password and password.startswith("${"):
        password = None

    return SmtpConfig(
        host=host,
        port=port,
        username=username,
        password=password,
        sender=sender,
        use_tls=use_tls,
        use_ssl=use_ssl,
    )


# ---------------------------------------------------------------------------
# Logs / contexte étape échouée
# ---------------------------------------------------------------------------

def _read_log_tail(path: str | os.PathLike[str] | None, max_lines: int = LOG_TAIL_LINES) -> str:
    if not path:
        return ""
    log_path = Path(path)
    if not log_path.exists() or not log_path.is_file():
        return ""
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return ""
    if not lines:
        return ""
    tail = lines[-max_lines:]
    return "".join(tail)


def collect_failed_step_context(record: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, str]:
    """Retourne (record_step_fautif, tail_logs) pour un workflow échoué.

    Si ``record`` n'est pas un workflow, retourne (record, tail). Si workflow
    réussi, retourne (None, ""). Robuste aux imports circulaires (lazy).
    """
    status = str(record.get("status") or "").lower()
    run_kind = str(record.get("run_kind") or "step")

    if run_kind != "workflow":
        if status in {"failed", "timeout"}:
            return record, _read_log_tail(record.get("stderr_path") or record.get("combined_path"))
        return None, ""

    if status == "completed":
        return None, ""

    child_ids_raw = record.get("workflow_child_run_ids") or []
    child_ids = [str(item) for item in child_ids_raw if item]
    current_child = str(record.get("workflow_current_child_run_id") or "").strip()
    candidates: list[str] = []
    if current_child:
        candidates.append(current_child)
    for child_id in child_ids:
        if child_id not in candidates:
            candidates.append(child_id)

    try:
        from ihm.services.process_registry import get_pipeline_run_record  # lazy
    except Exception:
        get_pipeline_run_record = None  # type: ignore[assignment]

    failed_child: Mapping[str, Any] | None = None
    if get_pipeline_run_record is not None:
        # Examine d'abord en sens inverse (dernier lancé = plus probablement le fautif).
        for candidate in reversed(candidates):
            try:
                child = get_pipeline_run_record(candidate)
            except Exception:
                child = None
            if not isinstance(child, Mapping):
                continue
            child_status = str(child.get("status") or "").lower()
            if child_status in {"failed", "timeout", "stopped"}:
                failed_child = child
                break
            if failed_child is None and child_status not in {"completed"}:
                failed_child = child

    if failed_child is None:
        # Fallback : tail du log workflow lui-même.
        return None, _read_log_tail(record.get("combined_path") or record.get("stderr_path"))

    tail = _read_log_tail(failed_child.get("stderr_path") or failed_child.get("combined_path"))
    return failed_child, tail


# ---------------------------------------------------------------------------
# Construction email
# ---------------------------------------------------------------------------

_STATUS_EMOJI = {
    "completed": "✅",
    "failed": "❌",
    "timeout": "⏱️",
    "stopped": "🛑",
}


def _format_duration(seconds: object) -> str:
    try:
        value = float(seconds) if seconds is not None else 0.0
    except (TypeError, ValueError):
        return "—"
    if value <= 0:
        return "—"
    minutes, secs = divmod(int(value), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def build_workflow_email(
    record: Mapping[str, Any],
    *,
    recipients: list[str],
    sender: str,
    failed_child: Mapping[str, Any] | None,
    log_excerpt: str,
) -> EmailMessage:
    status = str(record.get("status") or "unknown").lower()
    emoji = _STATUS_EMOJI.get(status, "ℹ️")
    run_kind = str(record.get("run_kind") or "step")
    label = str(record.get("step_label") or record.get("step_key") or "pipeline")
    run_id = str(record.get("run_id") or "—")
    account_id = str(record.get("account_id") or "—")
    duration = _format_duration(record.get("duration_seconds"))
    started = str(record.get("actual_started_at") or record.get("executed_at") or "—")
    finished = str(record.get("finished_at") or "—")
    returncode = record.get("returncode")

    subject = f"[AlphaTrade] {emoji} {run_kind.upper()} {status.upper()} — {label} — {run_id}"

    lines: list[str] = []
    lines.append(f"{emoji} Statut : {status.upper()}")
    lines.append(f"Workflow / étape : {label}")
    lines.append(f"Run ID : {run_id}")
    lines.append(f"Compte : {account_id}")
    lines.append(f"Démarré : {started}")
    lines.append(f"Terminé : {finished}")
    lines.append(f"Durée : {duration}")
    lines.append(f"Code retour : {returncode}")
    if run_kind == "workflow":
        completed_steps = record.get("workflow_completed_steps")
        total_steps = record.get("workflow_total_steps")
        lines.append(f"Étapes : {completed_steps}/{total_steps}")

    if failed_child is not None:
        lines.append("")
        lines.append("--- Étape fautive ---")
        lines.append(f"Étape : {failed_child.get('step_label') or failed_child.get('step_key') or '—'}")
        lines.append(f"Run ID enfant : {failed_child.get('run_id') or '—'}")
        lines.append(f"Statut : {failed_child.get('status') or '—'}")
        lines.append(f"Code retour : {failed_child.get('returncode')}")
        wd_msg = str(failed_child.get("watchdog_message") or "").strip()
        if wd_msg:
            lines.append(f"Watchdog : {wd_msg}")

    if log_excerpt:
        lines.append("")
        lines.append(f"--- Extrait des logs (dernières {LOG_TAIL_LINES} lignes) ---")
        lines.append(log_excerpt)

    lines.append("")
    lines.append("— Envoi automatique IHM AlphaTrade.")

    body = "\n".join(lines)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Date"] = datetime.now().astimezone().strftime("%a, %d %b %Y %H:%M:%S %z")
    msg.set_content(body)

    # Pièces jointes : combined.log de l'étape fautive + du workflow (tronquées).
    attached_paths: set[str] = set()
    for source in (failed_child, record):
        if not isinstance(source, Mapping):
            continue
        for key in ("combined_path", "stderr_path"):
            raw = source.get(key)
            if not raw:
                continue
            log_path = Path(str(raw))
            if not log_path.exists() or not log_path.is_file():
                continue
            resolved = str(log_path.resolve())
            if resolved in attached_paths:
                continue
            attached_paths.add(resolved)
            try:
                size = log_path.stat().st_size
                if size <= ATTACHMENT_MAX_BYTES:
                    payload = log_path.read_bytes()
                    filename = log_path.name
                else:
                    # tronquage par la fin (tail binaire).
                    with log_path.open("rb") as fh:
                        fh.seek(-ATTACHMENT_MAX_BYTES, os.SEEK_END)
                        payload = b"[... troncature debut de fichier ...]\n" + fh.read()
                    filename = f"{log_path.stem}.tail{log_path.suffix}"
            except OSError:
                LOGGER.debug("Pièce jointe ignorée : %s", log_path, exc_info=True)
                continue
            try:
                msg.add_attachment(
                    payload,
                    maintype="text",
                    subtype="plain",
                    filename=filename,
                )
            except Exception:
                LOGGER.debug("add_attachment a échoué pour %s", log_path, exc_info=True)
            if len(attached_paths) >= 4:
                break
        if len(attached_paths) >= 4:
            break

    return msg


# ---------------------------------------------------------------------------
# Envoi SMTP
# ---------------------------------------------------------------------------

def send_email(message: EmailMessage, smtp_config: SmtpConfig) -> bool:
    if not smtp_config.is_configured:
        LOGGER.warning(
            "send_email: SMTP non configuré (host/port/from manquants) — notification ignorée."
        )
        return False
    try:
        if smtp_config.use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_config.host, smtp_config.port, context=context, timeout=30) as smtp:
                if smtp_config.username and smtp_config.password:
                    smtp.login(smtp_config.username, smtp_config.password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=30) as smtp:
                smtp.ehlo()
                if smtp_config.use_tls:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                if smtp_config.username and smtp_config.password:
                    smtp.login(smtp_config.username, smtp_config.password)
                smtp.send_message(message)
        return True
    except Exception:
        LOGGER.exception("send_email: échec d'envoi SMTP host=%s port=%s", smtp_config.host, smtp_config.port)
        return False


# ---------------------------------------------------------------------------
# Hook fin de run
# ---------------------------------------------------------------------------

def _flag_path_for_record(record: Mapping[str, Any]) -> Path | None:
    combined = record.get("combined_path") or record.get("stdout_path")
    if not combined:
        return None
    try:
        return Path(str(combined)).parent / NOTIFICATION_FLAG_FILENAME
    except Exception:
        return None


def notify_run_finished(
    record: Mapping[str, Any],
    *,
    prefs: NotificationPreferences | None = None,
    smtp_config: SmtpConfig | None = None,
) -> bool:
    """Envoie une notification email pour un run terminé.

    Retourne True si un mail a été envoyé, False sinon (désactivé, doublon,
    statut non déclencheur, échec SMTP, etc.). Ne lève jamais d'exception.
    """
    try:
        status = str(record.get("status") or "").lower()
        if status not in _TERMINAL_STATUSES:
            return False

        # Sous-runs de workflow : ne pas notifier individuellement (le parent
        # workflow récapitule).
        if record.get("parent_run_id"):
            return False

        active_prefs = prefs or load_persisted_notification_preferences()
        if not active_prefs.enabled:
            return False
        if status not in set(active_prefs.notify_on):
            return False
        if not active_prefs.recipients:
            return False

        flag_path = _flag_path_for_record(record)
        if flag_path is not None and flag_path.exists():
            return False

        active_smtp = smtp_config or load_smtp_config()
        if not active_smtp.is_configured:
            LOGGER.info(
                "notify_run_finished: SMTP non configuré, notification ignorée (run_id=%s).",
                record.get("run_id"),
            )
            return False

        failed_child, log_excerpt = collect_failed_step_context(record)
        message = build_workflow_email(
            record,
            recipients=list(active_prefs.recipients),
            sender=active_smtp.sender,
            failed_child=failed_child,
            log_excerpt=log_excerpt,
        )
        sent = send_email(message, active_smtp)
        if sent and flag_path is not None:
            try:
                flag_path.parent.mkdir(parents=True, exist_ok=True)
                flag_path.write_text(
                    f"sent_at={datetime.now().isoformat(timespec='seconds')}\nstatus={status}\n",
                    encoding="utf-8",
                )
            except OSError:
                LOGGER.debug("notify_run_finished: impossible d'écrire le marqueur %s", flag_path, exc_info=True)
        return sent
    except Exception:
        LOGGER.exception("notify_run_finished: erreur inattendue (run_id=%s)", record.get("run_id"))
        return False


def send_test_email(
    prefs: NotificationPreferences,
    *,
    smtp_config: SmtpConfig | None = None,
) -> tuple[bool, str]:
    """Envoie un email de test pour valider la configuration depuis l'IHM."""
    active_smtp = smtp_config or load_smtp_config()
    if not active_smtp.is_configured:
        return False, "SMTP non configuré (host/port/from manquants — voir variables d'env ALPHA_TRADE_SMTP_*)."
    recipients = list(prefs.recipients)
    if not recipients:
        return False, "Aucun destinataire configuré."

    msg = EmailMessage()
    msg["Subject"] = "[AlphaTrade] ✉️ Test notification IHM"
    msg["From"] = active_smtp.sender
    msg["To"] = ", ".join(recipients)
    msg["Date"] = datetime.now().astimezone().strftime("%a, %d %b %Y %H:%M:%S %z")
    msg.set_content(
        "Ceci est un email de test envoyé depuis la page Paramètres / Santé de l'IHM AlphaTrade.\n"
        f"Destinataires : {', '.join(recipients)}\n"
        f"Statuts déclencheurs : {', '.join(prefs.notify_on)}\n"
        f"Envoi : {datetime.now().isoformat(timespec='seconds')}\n"
    )
    if send_email(msg, active_smtp):
        return True, f"Email de test envoyé à {', '.join(recipients)}."
    return False, "Échec d'envoi (voir logs ihm)."


__all__ = [
    "ATTACHMENT_MAX_BYTES",
    "LOG_TAIL_LINES",
    "NOTIFICATION_FLAG_FILENAME",
    "SmtpConfig",
    "build_workflow_email",
    "collect_failed_step_context",
    "load_smtp_config",
    "notify_run_finished",
    "send_email",
    "send_test_email",
]



