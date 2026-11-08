"""Qualified observed factor context shared by risk and Winner reapproval.

No synthetic zero factor returns, default betas or metadata cap fallback. The
three observable factors are market, size (IWM-SPY) and momentum (MTUM-SPY).
All configured beta/concentration/diversification/correlation limits stay active.
"""
from dataclasses import replace
from datetime import UTC, datetime
import hashlib
import json

import numpy as np
import pandas as pd

from common.daily_bar_sources import load_daily_close_series
from risk_management.factor_inputs import refresh_inputs, PROTOCOL
from risk_management.factor_model import (build_exposures_from_score_frame,
    estimate_factor_covariance, check_factor_constraints_on_sized_weights,
    _compute_factor_implied_correlation)


def observed_factor_returns(prices, *, include_size=True):
    required = ['SPY','IWM','MTUM'] if include_size else ['SPY','MTUM']
    if set(required)-set(prices.columns) or not prices.index.is_unique or not prices.index.is_monotonic_increasing:
        raise ValueError('Observed SPY/IWM/MTUM factor prices required')
    values = prices[required].astype(float)
    if not np.isfinite(values.to_numpy()).all() or (values <= 0).any().any():
        raise ValueError('Factor proxy price missing/invalid; no forward fill')
    returns = values.pct_change(fill_method=None).iloc[1:]
    factors = pd.DataFrame(dict(market=returns.SPY,momentum=returns.MTUM-returns.SPY),index=returns.index)
    if include_size:
        factors.insert(1,'size',returns.IWM-returns.SPY)
    if len(factors) < 126 or not np.isfinite(factors.to_numpy()).all() or (factors.var() <= 1e-14).any():
        raise ValueError('Insufficient/nonvarying observed factor returns')
    return factors


def qualify_factor_context(frame, prices, stock_returns, required, asof, cutoff, cfg, *, reconstructed=False,include_size=True):
    """Pure qualification; supplied inputs must carry their actual availability."""
    if type(reconstructed) is not bool or type(include_size) is not bool:
        raise ValueError('Explicit boolean reconstruction mode required')
    if frame.empty or frame.symbol.duplicated().any():
        raise ValueError('Risk factor input snapshot absent/duplicated')
    stock_returns = stock_returns.copy()
    stock_returns.index = pd.DatetimeIndex(pd.to_datetime(stock_returns.index))
    if (stock_returns.index.hasnans or not stock_returns.index.is_unique
            or stock_returns.index.tz is not None or (stock_returns.index.date > asof).any()):
        raise ValueError('Unqualified stock-return session index')
    cutoff = pd.Timestamp(cutoff)
    if cutoff.tzinfo is None:
        raise ValueError('Factor context cutoff requires timezone')
    observed = pd.to_datetime(frame.observed_at, utc=True)
    if reconstructed:
        if ('input_available_at' not in frame or 'reconstructed_at' not in frame or 'evidence_kind' not in frame
                or not frame.evidence_kind.eq('RECONSTRUCTED_HISTORICAL_INPUTS').all()):
            raise ValueError('Explicit historical reconstruction provenance required')
        available = pd.to_datetime(frame.input_available_at, utc=True)
        computed = pd.to_datetime(frame.reconstructed_at, utc=True)
        if computed.isna().any() or not computed.eq(observed).all() or (computed < available).any():
            raise ValueError('Invalid actual reconstruction timestamp')
    else:
        available = observed
    if available.isna().any() or observed.isna().any():
        raise ValueError('Factor availability timestamp missing')
    if (available > cutoff).any() or not frame.asof_date.eq(asof).all():
        raise ValueError('Future or wrong-session risk factor snapshot')
    complete = frame.loc[frame.quality.eq('QUALIFIED')].copy()
    if len(complete) < 20 or set(required)-set(complete.symbol):
        missing = sorted(set(required)-set(complete.symbol))
        details={}
        for symbol in missing:
            rows=frame.loc[frame.symbol.eq(symbol)]
            try:
                details[symbol]=json.loads(rows.iloc[0]['details_json']).get('reasons',[]) if len(rows) else ['NO_INPUT_ROW']
            except (KeyError,TypeError,ValueError):
                details[symbol]=['INCOMPLETE_FACTOR_INPUTS']
        raise ValueError(f'Factor inputs not qualified: missing={missing}, '
            f'qualified_cross_section={len(complete)}, minimum=20, reasons={details}')
    values = complete[['beta_126','market_cap','trend_score'] if include_size else ['beta_126','trend_score']].astype(float)
    if (not np.isfinite(values.to_numpy()).all()
            or not values.trend_score.between(0,1).all()
            or values.trend_score.std(ddof=0) <= 1e-9
            or include_size and ((values.market_cap <= 0).any() or np.log(values.market_cap).std(ddof=0)<=1e-9)):
        raise ValueError('Unqualified factor inputs; no neutral imputation')
    if include_size:
        exposures = build_exposures_from_score_frame(complete, asof)
    else:
        from risk_management.factor_model import _cross_sectional_zscore
        from risk_management.models import FactorExposures
        momentum=_cross_sectional_zscore(complete.set_index('symbol').trend_score)
        exposures={r.symbol:FactorExposures(r.symbol,asof,float(r.beta_126),0.,float(momentum[r.symbol]))
            for r in complete.itertuples()}
    # Preserve observed market betas at the guard boundary, rather than clipping
    # a high-beta candidate below its real configured risk threshold.
    for row in complete.itertuples():
        exposures[row.symbol] = replace(exposures[row.symbol], market_beta=float(row.beta_126))
    factors = observed_factor_returns(prices,include_size=include_size)
    if factors.index.max().date() != asof:
        raise ValueError('Stale factor proxy series')
    residuals = {}
    for symbol in required:
        if symbol not in stock_returns:
            raise ValueError('Observed factor stock returns unavailable: '+symbol)
        joined = pd.concat([stock_returns[symbol].rename('asset'), factors], axis=1).dropna()
        if len(joined) < 126 or joined.index.max().date() != asof:
            raise ValueError('Insufficient factor residual observations: '+symbol)
        exp = exposures[symbol]
        fitted=exp.market_beta*joined.market+exp.momentum_exposure*joined.momentum
        if include_size:fitted=fitted+exp.size_exposure*joined['size']
        residuals[symbol] = joined.asset-fitted
    covariance = estimate_factor_covariance(factors, lookback_days=cfg.factor_lookback_days,
        ewma_half_life=cfg.factor_ewma_half_life, estimation_date=asof,
        stock_returns=pd.DataFrame(residuals))
    factor_names=['market','size','momentum'] if include_size else ['market','momentum']
    if (covariance is None or covariance.factor_names != factor_names
            or not np.isfinite(covariance.factor_cov).all()
            or (np.diag(covariance.factor_cov) <= 0).any()
            or np.linalg.eigvalsh(covariance.factor_cov).min() < -1e-10
            or any(s not in covariance.specific_variances or not np.isfinite(covariance.specific_variances[s])
                or covariance.specific_variances[s] < 0 for s in required)):
        raise ValueError('Factor covariance/residual variance unqualified')
    fingerprint = hashlib.sha256(json.dumps(dict(protocol=PROTOCOL,asof=str(asof),
        run_ids=sorted(complete.run_id.unique()), required=sorted(required),
        covariance=covariance.factor_cov.tolist(),reconstructed=reconstructed,include_size=include_size),sort_keys=True).encode()).hexdigest()
    return dict(qualified=True, asof_date=asof, captured_at=cutoff.to_pydatetime(),
        observed_at=observed.max().to_pydatetime(), exposures=exposures, covariance=covariance,
        input_available_at=available.max().to_pydatetime(),
        evidence_kind='RECONSTRUCTED_HISTORICAL_INPUTS' if reconstructed else 'ARCHIVED_OBSERVATIONS',
        snapshot_hash=fingerprint, universe_count=len(complete), factor_names=covariance.factor_names,
        market_cap_check_enabled=include_size,disabled_factors=[] if include_size else ['size'],
        value_factor='NOT_MODELED_NO_QUALIFIED_VALUE_INPUTS')


def load_live_factor_context(engine, required, asof, now, cfg):
    frame = refresh_inputs(engine, asof, required=required, cutoff=now)
    # A first computation is published after its initial source cutoff. It is
    # available to this decision only now, never at a fabricated earlier time.
    cutoff = max(now, datetime.now(UTC))
    proxies = pd.concat({s: load_daily_close_series(engine,s,asof) for s in ('SPY','IWM','MTUM')},axis=1).tail(cfg.factor_lookback_days+1)
    from risk_management.db_io import RiskRepository
    returns = RiskRepository(engine).load_return_matrix_asof(required, asof, cfg.factor_lookback_days+1)
    return qualify_factor_context(frame,proxies,returns,required,asof,cutoff,cfg)


def factor_violations(context, weights, cfg, *, candidate, other_sides=None):
    """Apply existing final-size guards, failing closed on missing exposures."""
    if not context or context.get('qualified') is not True:
        raise ValueError('Native factor context unqualified')
    exposures, covariance = context['exposures'], context['covariance']
    required = {s for s,w in weights.items() if w != 0}
    if required-set(exposures) or required-set(covariance.specific_variances):
        raise ValueError('Missing held/pending factor exposure or residual risk')
    violations = check_factor_constraints_on_sized_weights(weights, exposures, covariance,
        max_portfolio_beta=cfg.max_portfolio_beta,
        beta_exposure_basis=cfg.beta_exposure_basis,
        max_factor_concentration=cfg.max_factor_concentration_pct,
        market_factor_concentration_check_enabled=cfg.market_factor_concentration_check_enabled,
        min_factor_diversification=cfg.effective_min_factor_diversification,
        factor_diversification_check_enabled=cfg.factor_diversification_check_enabled)
    if cfg.correlation_check_enabled and cfg.use_factor_correlation_filter:
        for held,side in (other_sides or {}).items():
            if held == candidate:
                continue
            corr = _compute_factor_implied_correlation(exposures[candidate],exposures[held],covariance,
                covariance.specific_variances[candidate],covariance.specific_variances[held])
            corr *= -1 if side in ('sell','short') else 1
            if not np.isfinite(corr) or corr > cfg.factor_correlation_threshold:
                violations.append(f'factor_correlation:{candidate}/{held}:{corr:.4f}>{cfg.factor_correlation_threshold}')
    return violations
