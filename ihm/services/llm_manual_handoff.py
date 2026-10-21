"""Explicit handoff between independent PAPER buttons, from local run history.

Never query a SQL 'latest' selection. Only the most recent upstream attempt
for this account may supply an ID; failures never fall back to an older run.
The CLI still validates the complete archived analysis before risk/execution.
"""
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from common.us_signal_date import resolve_us_signal_date


@dataclass(frozen=True)
class Handoff:
    run_id: str | None = None
    source_run_id: str | None = None
    finished_at_paris: str | None = None
    source_step: str | None = None
    error: str | None = None
    manual: bool = False


def _flag(command, name):
    values = []
    for index, part in enumerate(command):
        if part == name and index + 1 < len(command):
            values.append(command[index + 1])
        elif isinstance(part, str) and part.startswith(name + '='):
            values.append(part.split('=', 1)[1])
    return values[0] if len(values) == 1 else None


def _valid_id(value):
    return (isinstance(value, str) and 0 < len(value) <= 80 and value != 'auto'
            and all(char.isalnum() or char in '-_' for char in value))


def _paris(value):
    instant = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    # Historical IHM records use naive Windows/Paris local times.
    instant = instant.replace(tzinfo=ZoneInfo('Europe/Paris')) if instant.tzinfo is None else instant
    return instant.astimezone(ZoneInfo('Europe/Paris')).strftime('%d/%m/%Y à %H:%M:%S %Z')


def _final_llm_summary(source):
    summary = source.get('run_summary') or {}
    if isinstance(summary, dict) and isinstance(summary.get('selected'), list):
        return summary
    # Compatibility for already completed runs whose final event was prefixed
    # with an ANSI reset and therefore saved as a plain log instead of summary.
    from ihm.services.process_registry import RUNS_DIR, _extract_run_summary
    try:
        path = Path(source['stdout_path']).resolve()
        path.relative_to(RUNS_DIR.resolve())
        if path.name != 'stdout.log':
            return {}
        with path.open('rb') as handle:
            handle.seek(0, 2)
            handle.seek(max(0, handle.tell() - 65536))
            tail = handle.read().decode('utf-8', errors='replace')
        for line in reversed(tail.splitlines()):
            candidate = _extract_run_summary(line)
            if candidate and isinstance(candidate.get('selected'), list):
                return candidate
    except (KeyError, OSError, ValueError):
        pass
    return {}


def bind_manual_handoff(step_key, options, records):
    source_step = {'risk_management': 'ml_predict', 'execution': 'risk_management'}.get(step_key)
    if not options.llm_filter_enabled or source_step is None:
        return options, None
    explicit = (options.llm_filter_run_id or '').strip()
    if explicit:
        if not _valid_id(explicit):
            return options, Handoff(error='Identifiant analyse LLM invalide ; ne pas utiliser auto.')
        return replace(options, llm_filter_run_id=explicit), Handoff(run_id=explicit, manual=True)
    source_number = '10' if source_step == 'ml_predict' else '11'

    def blocked(reason):
        return options, Handoff(source_step=source_number, error=reason)

    account = options.account_id or 'default'
    sources = [record for record in records if record.get('step_key') == source_step
               and (record.get('account_id') or 'default') == account
               and not record.get('history_deleted')]
    if not sources:
        return blocked(f'Aucun lancement de l’étape {source_number} pour ce compte. '
                       'Lancer l’étape précédente ou renseigner explicitement l’identifiant analyse LLM.')
    # Latest attempt, not latest success: do not conceal a newer failed run.
    source = max(sources, key=lambda record: str(record.get('executed_at') or record.get('actual_started_at') or ''))
    if source.get('status') != 'completed' or source.get('returncode') not in (None, 0):
        return blocked(f'Le dernier lancement de l’étape {source_number} n’est pas terminé avec succès. '
                       'Aucune ancienne analyse réutilisée automatiquement.')
    command = source.get('command')
    phase = 'predict' if source_step == 'ml_predict' else 'risk'
    if (not isinstance(command, list) or len(command) < 4
            or command[1:4] != ['-u', '-m', 'service.llm_directional.pipeline']
            or _flag(command, '--phase') != phase):
        return blocked(f'Le dernier lancement de l’étape {source_number} ne contient pas d’analyse LLM liée.')
    try:
        signal_day = resolve_us_signal_date(options.trade_date or None).isoformat()
        finished_at = _paris(source['finished_at'])
    except (KeyError, TypeError, ValueError):
        return blocked('Date de séance ou date de fin amont indisponible ; reprise automatique refusée.')
    if _flag(command, '--trade-date') != signal_day:
        return blocked(f'L’étape {source_number} concerne une autre séance que {signal_day}. '
                       'Vérifier la date ; aucune substitution automatique.')
    if source_step == 'ml_predict':
        batch = options.ml_predict_batch_id or options.ml_live_predict_batch_id
        if batch and _flag(command, '--batch-id') != batch:
            return blocked('Le modèle Oracle sélectionné diffère du dernier lancement de l’étape 10.')
        if _flag(command, '--symbol-source') != options.ml_predict_symbol_source:
            return blocked('L’univers sélectionné diffère du dernier lancement de l’étape 10.')
        summary = _final_llm_summary(source)
        if not isinstance(summary, dict) or summary.get('status') != 'completed' or not isinstance(summary.get('selected'), list):
            return blocked('Résumé final de l’analyse LLM absent ou incomplet ; reprise automatique refusée.')
        run_id = summary.get('run_id')
        requested_id = _flag(command, '--run-id')
        if requested_id not in ('auto', run_id):
            return blocked('Identifiant analyse LLM du résumé incompatible avec la commande amont.')
    else:
        run_id = _flag(command, '--run-id')
    if not _valid_id(run_id):
        return blocked('Identifiant analyse LLM exact absent du dernier lancement terminé.')
    return replace(options, llm_filter_run_id=run_id, trade_date=signal_day), Handoff(
        run_id=run_id, source_run_id=str(source['run_id']), finished_at_paris=finished_at,
        source_step=source_number)
