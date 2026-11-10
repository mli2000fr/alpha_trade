"""Explicit, versioned US PAPER strategy; never a global risk bypass.

The switch affects new scheduled 10/11/12 runs. Campaigns retain their frozen
profile and Winner protections; disabling it never cancels a standing stop.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parents[1]
PROFILE_ID = 'q051_vol20_regime_v1'
REFERENCE = ROOT / 'config/strategies/q051_vol20_regime_reference.json'


def reference():
    raw = REFERENCE.read_bytes()
    result = json.loads(raw)
    if result.get('profile_id') != PROFILE_ID or result.get('schema_version') != 1:
        raise ValueError('Profil Q051 de référence incompatible')
    if hashlib.sha256(json.dumps(result['risk'],sort_keys=True).encode()).hexdigest() != result['reference_risk_sha256']:
        raise ValueError('Paramètres de risque Q051 différents de la référence archivée')
    result['sha256'] = hashlib.sha256(raw).hexdigest()
    return result


def validate_frozen(value):
    if value != reference():
        raise ValueError('Contrat Q051 figé différent de la référence qualifiée')
    return value


def settings(raw=None):
    if raw is None:
        from common.config_loader import load_config
        raw = load_config()
    value = (raw.get('us_pipeline') or {}).get('q051_vol20_regime') or {}
    if not isinstance(value, dict) or type(value.get('enabled', False)) is not bool:
        raise ValueError('us_pipeline.q051_vol20_regime.enabled : booléen requis')
    return dict(enabled=value.get('enabled', False), model_batch_id=value.get('model_batch_id'),
                artifacts_dir=value.get('artifacts_dir', 'artifacts/models'))


def require_paper(account_id, mode='paper'):
    if mode != 'paper':
        raise ValueError('Q051 réservé au PAPER ; LIVE et simulation implicite interdits')
    from service.forward_pit.us_pipeline import require_paper_account
    require_paper_account(account_id)


def risk_config(equity):
    from risk_management.config import RiskConfig
    values = deepcopy(reference()['risk'])
    values['account_equity'] = float(equity)
    # B4/DD15 are not evaluated by this profile. Keep the archived thresholds
    # for provenance; callers use the explicit disabled controller below.
    return RiskConfig(**values)


def execution_config(account_id):
    from common.winner_pyramiding import WinnerPyramidingConfig
    from execution_engine.config import (ExecutionConfig, LeverageConfig,
                                         TrailingStopConfig, TimeStopConfig)
    p = reference()
    return ExecutionConfig(broker_mode='paper', account_id=account_id, account_type='margin',
        swing_only=False, dry_run=False, entry_order_type='market', max_entry_gap_pct=0.,
        winner_pyramiding=WinnerPyramidingConfig(**p['winner']),
        leverage=LeverageConfig(**p['leverage']), trailing_stop=TrailingStopConfig(enabled=False),
        time_stop=TimeStopConfig(enabled=False), force_close_on_breaker=False,
        enable_dynamic_trailing_transition=False, paper_strategy_profile=p)


def pipeline_options(options, policy):
    value = settings({'us_pipeline': policy})
    if not value['enabled']:
        return options
    require_paper(options.account_id or 'default', options.execution_mode)
    batch = value['model_batch_id']
    if not isinstance(batch, str) or not batch:
        raise ValueError('Q051 : model_batch_id H10 explicite requis')
    import uuid
    return replace(options, q051_paper_enabled=True, q051_run_id='q051-'+uuid.uuid4().hex,
        ml_predict_batch_id=batch, ml_live_predict_batch_id=batch,
        ml_artifacts_dir=value['artifacts_dir'], llm_filter_enabled=False,
        llm_filter_run_id=None, options_filter_enabled=False, options_filter_run_id=None,
        ml_predict_use_historical_range=False, force_trade_date_to_latest_snapshot=False,
        execution_account_type='margin', allow_fractional_shares=False)


class NoDrawdownController:
    """The reference explicitly disables B4/DD15, not an invented equity seed."""
    def is_active(self):
        return False


def entry_window(state, now):
    """Only queue for J+1, never turn a missed opening into a late purchase."""
    from common.winner_pyramiding import aware
    from zoneinfo import ZoneInfo
    from common.market_calendar import get_market_calendar
    now = aware(now)
    opening = aware(state['earliest_entry_open'])
    # OPG: Alpaca accepts before 09:28 NY or after 19:00 for next auction.
    # Calendar sessions still decide J+1, including holidays and weekends.
    if now >= opening.replace(second=0, microsecond=0) - timedelta(minutes=2):
        return False
    signal = date.fromisoformat(state['signal_date'])
    cal = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    previous = next(s for s in cal.sessions(signal, signal) if s.is_open)
    local = now.astimezone(ZoneInfo('America/New_York'))
    if now <= previous.close_at_utc:
        return False
    clock_ok = local.hour >= 19 or (local.hour, local.minute) < (9, 28)
    return clock_ok and local.date() <= opening.astimezone(ZoneInfo('America/New_York')).date()
