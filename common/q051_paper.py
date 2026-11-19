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
from contextlib import contextmanager
from contextvars import ContextVar

ROOT = Path(__file__).resolve().parents[1]
PROFILE_ID = 'q051_vol20_regime_v1'
REFERENCE = ROOT / 'config/strategies/q051_vol20_regime_reference.json'
PROFILE_FILES = {
    PROFILE_ID: REFERENCE,
    'q051_b_witness_v1': ROOT / 'config/strategies/q051_b_reference.json',
    'q051_b_anti_sl_witness_v1': ROOT / 'config/strategies/q051_b_anti_sl_reference.json',
}
_PROFILE = ContextVar('q051_paper_profile', default=PROFILE_ID)


@contextmanager
def profile_scope(profile_id):
    """Scope one run/watcher admission; never mutate profiles of existing lots."""
    reference(profile_id)  # Validate before entering the scope.
    token = _PROFILE.set(profile_id)
    try:
        yield
    finally:
        _PROFILE.reset(token)


def reference(profile_id=None):
    profile_id = profile_id or _PROFILE.get()
    path = REFERENCE if profile_id == PROFILE_ID else PROFILE_FILES.get(profile_id)
    if path is None:
        raise ValueError('Profil PAPER inconnu')
    raw = path.read_bytes()
    result = json.loads(raw)
    if result.get('profile_id') != profile_id or result.get('schema_version') != 1:
        raise ValueError('Profil Q051 de référence incompatible')
    if hashlib.sha256(json.dumps(result['risk'],sort_keys=True).encode()).hexdigest() != result['reference_risk_sha256']:
        raise ValueError('Paramètres de risque Q051 différents de la référence archivée')
    result['sha256'] = hashlib.sha256(raw).hexdigest()
    return result


def validate_frozen(value):
    if not isinstance(value, dict) or value != reference(value.get('profile_id')):
        raise ValueError('Contrat Q051 figé différent de la référence qualifiée')
    return value


def settings(raw=None):
    if raw is None:
        from common.config_loader import load_config
        raw = load_config()
    policy = raw.get('us_pipeline') or {}
    old = policy.get('q051_vol20_regime') or {}
    new = policy.get('b_anti_sl_reference') or {}
    for name, value in [('q051_vol20_regime', old), ('b_anti_sl_reference', new)]:
        if not isinstance(value, dict) or type(value.get('enabled', False)) is not bool:
            raise ValueError('us_pipeline.' + name + '.enabled : booléen requis')
    if old.get('enabled') and new.get('enabled'):
        raise ValueError('Activer un seul profil PAPER : Q051 vol20/régime ou B témoin')
    if type(new.get('apply_anti_sl', True)) is not bool:
        raise ValueError('us_pipeline.b_anti_sl_reference.apply_anti_sl : booléen requis')
    value = new if new.get('enabled') else old
    profile_id = ('q051_b_anti_sl_witness_v1' if new.get('apply_anti_sl', True) else 'q051_b_witness_v1') if new.get('enabled') else PROFILE_ID
    return dict(enabled=value.get('enabled', False), model_batch_id=value.get('model_batch_id'),
                artifacts_dir=value.get('artifacts_dir', 'artifacts/models'), profile_id=profile_id)


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


def execution_config(account_id, profile_id=None):
    from common.winner_pyramiding import WinnerPyramidingConfig
    from execution_engine.config import (ExecutionConfig, LeverageConfig,
                                         TrailingStopConfig, TimeStopConfig)
    p = reference(profile_id)
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
        q051_profile_id=value['profile_id'],
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
