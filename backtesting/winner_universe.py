"""Frozen model scope for automatic Winner backtests, without file substitution."""

MODEL_UNIVERSE_SOURCE='model-universe'


def universe_from_model(contract):
    symbols=contract.get('universe')
    if (not isinstance(symbols,(list,tuple)) or not symbols
        or any(not isinstance(s,str) or not s or s!=s.strip().upper() for s in symbols)
        or len(set(symbols))!=len(symbols)):
        raise ValueError('Univers du modèle absent, invalide ou dupliqué ; choisir un batch qualifié')
    return list(symbols)
