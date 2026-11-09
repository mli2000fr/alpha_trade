"""A Winner replay resolves one validated market registry for its whole lifetime."""
from functools import wraps

from common.config_loader import load_market_registry, replay_market_registry


def frozen_market_registry(function):
    @wraps(function)
    def run(*args, **kwargs):
        registry = load_market_registry()
        registry.assert_compatible('US_EQ', 'us_primary')
        registry.resolve('US_EQ', require_enabled=True)
        with replay_market_registry(registry):
            result = function(*args, **kwargs)
        result.tracker_snapshot['winner_replay']['market_registry'] = dict(
            mode='VALIDATED_ONCE_PINNED_FOR_REPLAY',
            contexts={code.value: registry.resolve(code).to_manifest() for code in registry.market_codes})
        return result
    return run
