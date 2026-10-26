"""Additional entry gate only; never size with an uncalibrated options rank."""
from dataclasses import replace


def filter_candidates(candidates, report):
    selected = set(report['selected'])
    return [replace(c, lineage={**(c.lineage or {}), 'options_filter_run_id': report['run_id'],
                               'options_score_semantics': 'relative_activity_not_probability'})
            for c in candidates if c.symbol in selected and c.side == 'long']
