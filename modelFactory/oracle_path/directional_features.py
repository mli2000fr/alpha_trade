"""Versioned per-symbol inputs; Oracle ranks always use its full population."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

VOLATILITY_INPUTS = ['rolling_volatility_60','rolling_volatility_120',
    'rolling_volatility_20_zscore','rolling_volatility_60_zscore','rolling_volatility_120_zscore']
# Input-only qualification shared by the controlled T0/A/B study. These four
# columns qualify the historical context; they are not fitted inputs in B.
VOLATILITY_CONTEXT = ['beta_252','r_squared_252','alpha_252','momentum_252_vs_market']


def compact_columns(mode='compact'):
    from .directional import INPUTS
    if mode not in ('compact','compact_volatility'):
        raise ValueError('Unknown compact directional feature mode')
    return [*INPUTS,*(VOLATILITY_INPUTS if mode=='compact_volatility' else [])]


def input_columns(root,protocol=None):
    root=Path(root)
    protocol=protocol or json.loads((root/'protocol.json').read_text(encoding='utf-8'))
    mode=protocol.get('directional_contract',{}).get('feature_mode','compact')
    if mode in ('compact','compact_volatility'):
        return compact_columns(mode)
    if mode!='oracle':raise ValueError('Unknown directional feature mode')
    profile=json.loads((root/'feature_profile.json').read_text(encoding='utf-8'))
    columns=profile['feature_columns']
    if (not isinstance(columns,list) or not columns or len(set(columns))!=len(columns)
            or any(not isinstance(c,str) or not c or c in ('date','symbol','long','short','available')
                   or c.startswith(('oracle_path_extreme','oracle_extreme','future_')) for c in columns)):
        raise ValueError('Invalid or leaking Oracle feature profile')
    return list(columns)


def training_matrix(root):
    from .train import digest,restore_ranks
    root=Path(root);p=json.loads((root/'protocol.json').read_text(encoding='utf-8'))
    columns=input_columns(root,p);parts=[]
    for path in sorted((root/'chunks').glob('*/features.parquet')):
        marker=json.loads((path.parent/'done.json').read_text(encoding='utf-8'))
        if digest(path)!=marker['files']['features.parquet']:raise ValueError('Corrupt Oracle feature chunk')
        parts.append(pd.read_parquet(path))
    if not parts:raise ValueError('Oracle feature chunks absent')
    frame=restore_ranks(pd.concat(parts,ignore_index=True),p['generator_options'])
    if frame.duplicated(['date','symbol']).any():raise ValueError('Duplicate Oracle feature key')
    if set(frame.symbol)-set(p['universe']):raise ValueError('Oracle feature population outside contract')
    return frame[['date','symbol',*columns]]


def oracle_panels(bars,calendar,features,columns):
    """Retain the same past-only 60-bar guard; never inspect future labels."""
    from common.daily_bar_sources import select_daily_bars
    bars=select_daily_bars(bars.copy()).sort_values('date')
    symbol=str(bars.symbol.iloc[0]);a=bars.set_index('date').reindex(calendar)
    raw=a[['open','high','low','close','adj_close','volume','is_filled']].apply(pd.to_numeric,errors='coerce')
    good=(raw[['open','high','low','close']].notna().all(axis=1)
        &raw[['open','high','low','close']].gt(0).all(axis=1)&raw.volume.gt(0)
        &raw.is_filled.eq(0)&a.instrument_id.notna())
    f=features.loc[features.symbol.eq(symbol),['date',*columns]].copy()
    if f.date.duplicated().any():raise ValueError('Duplicate per-symbol Oracle feature date')
    f=f.set_index('date').reindex(calendar)
    for c in columns:f[c]=pd.to_numeric(f[c],errors='coerce').replace([np.inf,-np.inf],np.nan)
    eligible=good.rolling(60,min_periods=60).sum().eq(60)&f.notna().mean(axis=1).ge(.8)
    f=f.loc[eligible].rename_axis('date').reset_index();f['symbol']=symbol
    return f
