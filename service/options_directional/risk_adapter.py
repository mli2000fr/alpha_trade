"""Additional entry gate only; never size with an uncalibrated options rank."""
from dataclasses import replace


def archived_universe_preset(report, trade_date, account_id='default',*,shared_selection=False):
    """Use the already-qualified selection's universe, never its sizing equity."""
    from common.capital_presets import get_capital_preset_by_key
    if (report.get('status') != 'COMPLETED' or report.get('trade_date') != str(trade_date)
            or (not shared_selection and report.get('account_id') != account_id) or not report.get('run_id')):
        raise ValueError('Snapshot options incompatible avec le risque')
    key = report.get('capital_preset_key')
    if not isinstance(key, str) or not key or key != key.strip():
        raise ValueError('Preset d’univers options absent ou invalide ; aucun fallback equity')
    preset = get_capital_preset_by_key(key)
    if preset is None:
        raise ValueError(f'Preset d’univers options inconnu : {key} ; aucun fallback equity')
    return preset


def filter_candidates(candidates, report):
    selected = set(report['selected'])
    return [replace(c, lineage={**(c.lineage or {}), 'options_filter_run_id': report['run_id'],
                               'options_score_semantics': 'relative_activity_not_probability'})
            for c in candidates if c.symbol in selected and c.side == 'long']
