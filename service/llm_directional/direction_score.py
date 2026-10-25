"""Versioned ordinal direction, not a probability; deterministic strict cutoffs."""


def score_policy(config):
    return dict(scale_min=1, scale_max=10, long_score_threshold=config.long_score_threshold,
        short_score_threshold=config.short_score_threshold, comparisons='strict',
        neutral='short_score_threshold <= score <= long_score_threshold')


def score_decision(score, config):
    if type(score) is not int or not 1 <= score <= 10:
        raise ValueError('direction_score doit être un entier entre 1 et 10')
    return ('LONG' if score > config.long_score_threshold else
            'SHORT' if score < config.short_score_threshold else 'ABSTAIN')


def apply_score(result, config, *, separated=False):
    if separated:
        from .trend_evidence import trend_decision
        result['decision'] = trend_decision(result, config)
    else:
        result['decision'] = score_decision(result['direction_score'], config)
    result['direction_score_policy'] = score_policy(config)
    return result


def selection_sort_key(item):
    if 'direction_score' in item:
        score = item['direction_score']
        if type(score) is not int or not 1 <= score <= 10:
            raise ValueError('Score directionnel archivé invalide')
        strength = abs(score - 5.5)  # 1/10 then 2/9; symmetric LONG/SHORT.
    else:
        strength = item['confidence']
    return (-strength, item['oracle_rank'], item['symbol'])
