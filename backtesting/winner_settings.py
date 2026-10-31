"""Validated per-replay settings; never write production configuration."""
from dataclasses import fields, replace
import json
import math

from common.winner_pyramiding import WinnerPyramidingConfig

BOOL_FIELDS={'sector_weight_limit_enabled','sector_ticker_limit_enabled','correlation_check_enabled',
             'force_close_on_breaker'}
INT_FIELDS={'max_tickers_per_sector','correlation_lookback_days','correlation_min_overlap',
    'vol_target_lookback_days','concentration_max_trades_per_symbol','concentration_window_calendar_days',
    'concentration_max_consecutive_losses','concentration_blacklist_duration_days'}
FLOAT_FIELDS={'risk_per_trade_pct','min_position_notional','enforce_min_notional','max_position_weight',
    'max_sector_weight','correlation_threshold','max_portfolio_drawdown_pct','max_daily_loss_pct',
    'force_close_pct','target_annual_vol','max_portfolio_beta'}
NULLABLE={'max_tickers_per_sector','enforce_min_notional','target_annual_vol'}
POLICY_FIELDS={f.name for f in fields(WinnerPyramidingConfig)}-{'enabled'}


def mapping(value):
    if value is None:
        return {}
    result=json.loads(value) if isinstance(value,str) else value
    if not isinstance(result,dict):
        raise ValueError('Les réglages Winner doivent être un objet JSON')
    return dict(result)


def risk_overrides(value):
    result=mapping(value)
    unknown=set(result)-(BOOL_FIELDS|INT_FIELDS|FLOAT_FIELDS)
    if unknown:
        raise ValueError('Paramètres risque non raccordés au replay : '+', '.join(sorted(unknown)))
    for key,v in result.items():
        if v is None and key in NULLABLE:
            continue
        if key in BOOL_FIELDS:
            valid=type(v) is bool
        elif key in INT_FIELDS:
            valid=type(v) is int and v>=1
        else:
            valid=type(v) in (int,float) and math.isfinite(v) and v>0
            if key not in ('min_position_notional','enforce_min_notional','max_portfolio_beta'):
                valid=valid and v<=1
            if key in ('risk_per_trade_pct','max_portfolio_drawdown_pct','max_daily_loss_pct'):
                valid=valid and v<1
        if not valid:
            raise ValueError(f'Valeur de risque invalide : {key}={v!r}')
    return result


def policy_overrides(value):
    result=mapping(value)
    if set(result)-POLICY_FIELDS:
        raise ValueError('Paramètres de politique Winner inconnus ou non modifiables')
    return result


def production_risk_defaults(risk,raw=None):
    """Match the explicit production breaker settings, not a legacy fallback."""
    if raw is None:
        from common.config_loader import load_config
        raw=load_config()
    section=(raw or {}).get('risk_management',{})
    enabled=section.get('prod_force_close_on_breaker',section.get('force_close_on_breaker',risk.force_close_on_breaker))
    fraction=section.get('prod_force_close_pct',section.get('force_close_pct',risk.force_close_pct))
    if type(enabled) is not bool or type(fraction) not in (int,float) or not math.isfinite(fraction) or not 0<fraction<=1:
        raise ValueError('Configuration de liquidation de production invalide')
    return replace(risk,force_close_on_breaker=enabled,force_close_pct=float(fraction))


def apply_risk_settings(risk,value):
    risk=replace(risk,**risk_overrides(value))
    if risk.correlation_check_enabled and risk.correlation_min_overlap>risk.correlation_lookback_days:
        raise ValueError('Le minimum de séances communes dépasse la fenêtre de corrélation')
    return risk


def apply_policy_settings(policy,value):
    return replace(policy,**policy_overrides(value))
