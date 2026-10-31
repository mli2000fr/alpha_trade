"""Explicit run-wide exclusions after Oracle TOP-N, without replacement."""
import re


def excluded_symbols(value):
    if not isinstance(value,str):
        raise ValueError('Les exclusions Winner doivent être une liste de symboles séparés par des virgules')
    symbols=sorted(set(s.upper() for s in re.split(r'[,;\s]+',value.strip()) if s))
    if any(not re.fullmatch(r'[A-Z0-9][A-Z0-9.\-]{0,19}',s) for s in symbols):
        raise ValueError('Symbole exclu invalide : utiliser des symboles comme SDGR, APP')
    return symbols


def apply_exclusions(selected,symbols):
    mask=selected.symbol.isin(symbols)
    removed=selected.loc[mask].copy()
    removed['selected']=False
    removed['exclusion_reason']='USER_DECLARED_RUN_WIDE_EXCLUSION'
    return selected.loc[~mask].copy(),removed
