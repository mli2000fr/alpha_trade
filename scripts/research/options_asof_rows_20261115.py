"""Research-only receipt/session separation; never change native timestamps.

The compiled native feature arithmetic is reused with an isolated globals dict.
Only row qualification changes. The production module is never monkey-patched.
"""
from types import FunctionType
import pandas as pd
from service.options_directional.features import build_features
from common.options_directional_contract import DTE_MIN,DTE_MAX


def rows_asof(frame,day,cutoff,*,volume=False):
    f=frame.copy()
    if f.empty:return f
    for key in ['observed_at','available_at']:f[key]=pd.to_datetime(f[key],utc=True,errors='coerce')
    f=f[f[['observed_at','available_at']].notna().all(axis=1)&f.payload_hash.notna()&f.contract_symbol.notna()].copy()
    f['received_at']=f[['observed_at','available_at']].max(axis=1)
    f=f[f.received_at.le(cutoff)&f.received_at.ge(cutoff-pd.Timedelta(hours=72))].copy()
    if 'provider_timestamp' in f:
        t=pd.to_datetime(f.provider_timestamp,utc=True,errors='coerce');f=f[t.isna()|t.le(cutoff)].copy()
    f['day']=f.received_at.dt.tz_convert('America/New_York').dt.date
    if volume:
        t=pd.to_datetime(f.bar_timestamp,utc=True,errors='coerce')
        f=f[t.le(cutoff)&t.dt.tz_convert('America/New_York').dt.date.eq(day)].copy()
    f['expiration_date']=pd.to_datetime(f.expiration_date,errors='coerce')
    f['option_type']=f.option_type.str.upper().replace({'C':'CALL','P':'PUT'})
    roots=f.contract_symbol.str.replace(r'\d{6}[CP]\d{8}$','',regex=True)
    f=f[roots.eq(f.symbol.str.replace('.','',regex=False))].copy()
    f['dte']=(f.expiration_date-pd.Timestamp(day)).dt.days
    return f[f.dte.between(DTE_MIN,DTE_MAX)].copy()


build_features_asof=FunctionType(build_features.__code__,{**build_features.__globals__,'_rows':rows_asof},
    name='build_features_asof',argdefs=build_features.__defaults__,closure=build_features.__closure__)
