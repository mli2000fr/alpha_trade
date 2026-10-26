"""V9: provisional tendency and independently checked retention evidence, never probabilities."""

QUALITY_LABELS = {'SUFFICIENT': 'Suffisantes', 'PARTIAL': 'Partielles', 'INSUFFICIENT': 'Insuffisantes'}


def trend_decision(result, config):
    """Validate nullable tendency independently of the eventual retention verdict."""
    score, status = result.get('direction_score'), result.get('trend_status')
    if status not in ('ASSESSED', 'UNDETERMINABLE'):
        raise ValueError('État de tendance invalide')
    if (status == 'UNDETERMINABLE') != (score is None):
        raise ValueError('Tendance indéterminable exige un score null ; tendance estimée exige un score')
    if result.get('evidence_quality') not in QUALITY_LABELS:
        raise ValueError('Qualité des preuves invalide')
    explanation = result.get('evidence_explanation')
    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError('Explication de la qualité des preuves obligatoire')
    if score is None:
        return 'ABSTAIN'
    from .direction_score import score_decision
    return score_decision(score, config)


def qualify_evidence(result):
    """May downgrade the model's claim; never remove an existing blocker or promote context."""
    reported = result['evidence_quality']
    directional_only = {'long_not_allowed', 'short_not_allowed', 'direction_score_neutral'}
    reasons = [b for b in result['selection_blockers'] if b not in directional_only]
    local_traceable = bool(result.get('local_source_qualifications'))
    web_traceable = bool(result.get('fresh_source_count'))
    usable = local_traceable or web_traceable
    if (reported == 'INSUFFICIENT' or result['direction_score'] is None
            or not result['identity_verified'] or not usable):
        effective = 'INSUFFICIENT'
    elif reasons or reported == 'PARTIAL':
        effective = 'PARTIAL'
    else:
        effective = 'SUFFICIENT'
    if reported != 'SUFFICIENT':
        reasons.append('llm_evidence_' + reported.lower())
    if result['direction_score'] is None:
        result['selection_blockers'].append('trend_undeterminable')
        reasons.append('trend_undeterminable')
    if effective != 'SUFFICIENT':
        result['selection_blockers'].append('evidence_' + effective.lower())
    result.update(reported_evidence_quality=reported, evidence_quality=effective,
                  evidence_quality_reasons=reasons, retention_evidence_verified=(effective == 'SUFFICIENT'))
