"""Daily observable risk proxies, separate from the stock trading universe."""


def required_factor_proxies(config):
    return ('SPY', 'IWM', 'MTUM') if (config.get('risk_management') or {}).get('enable_factor_model', False) else ()
