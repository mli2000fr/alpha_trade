"""Three fixed research selectors; no training, outcome access, SQL or serving."""
import numpy as np
import pandas as pd

POLICIES=('Q051_REFERENCE','GLOBAL_H10','FUSION_50_50')


def select(frame, policy, *, oracle_top_n=179, final_top_n=5):
    if policy not in POLICIES:
        raise ValueError('Politique de classement inconnue')
    needed={'date','symbol','proba_extreme','long_probability','long_auc','long_auc_available_date','global_rank_10'}
    if not needed.issubset(frame):raise ValueError('Scores ou AUC de calibration absents')
    f=frame.copy();f['date']=pd.to_datetime(f.date).dt.normalize()
    if f.duplicated(['date','symbol']).any():raise ValueError('Clés de scores dupliquées')
    for col in ['proba_extreme','long_probability','long_auc','global_rank_10']:
        f[col]=pd.to_numeric(f[col],errors='raise')
        if (f[col].notna()&~f[col].between(0,1)).any():raise ValueError('Score invalide : '+col)
    if f.proba_extreme.isna().any():raise ValueError('Score Oracle absent')
    f=f.sort_values(['date','proba_extreme','symbol'],ascending=[True,False,True])
    f['oracle_rank']=f.groupby('date').cumcount()+1
    pool=f.oracle_rank.le(oracle_top_n)
    f['global_score_present']=f.global_rank_10.notna()
    f['fusion_score']=np.nan
    f['candidate_rank_before_gates']=np.nan
    if policy=='Q051_REFERENCE':
        candidates=f[pool&f.long_probability.notna()].copy();score='long_probability'
    elif policy=='GLOBAL_H10':
        candidates=f[pool&f.global_score_present].copy();score='global_rank_10'
    else:
        candidates=f[pool&f.global_score_present&f.long_probability.notna()].copy()
        for col,label in [('long_probability','symbol_percentile'),('global_rank_10','global_percentile')]:
            candidates[label]=candidates.groupby('date')[col].transform(lambda s:(s.rank(method='average')-.5)/len(s))
        candidates['fusion_score']=.5*candidates.symbol_percentile+.5*candidates.global_percentile
        f.loc[candidates.index,'fusion_score']=candidates.fusion_score
        score='fusion_score'
    candidates=candidates.sort_values(['date',score,'oracle_rank','symbol'],ascending=[True,False,True,True])
    f.loc[candidates.index,'candidate_rank_before_gates']=candidates.groupby('date').cumcount()+1
    available=pd.to_datetime(f.long_auc_available_date,errors='coerce')
    top=f.candidate_rank_before_gates.le(final_top_n)
    f['selected']=top&f.long_probability.gt(.5)&f.long_auc.ge(.5)&available.lt(f.date)
    chosen=f[f.selected].sort_values(['date','candidate_rank_before_gates','oracle_rank','symbol'])
    f['rank']=np.nan;f.loc[chosen.index,'rank']=chosen.groupby('date').cumcount()+1
    f['selection_policy']=policy
    f['reason']=np.where(f.selected,'SELECTED_LONG',np.where(~top,'OUTSIDE_FINAL_TOP5',
        np.where(~f.long_probability.gt(.5),'LONG_SCORE_NOT_ABOVE_THRESHOLD',
        np.where(~available.lt(f.date),'MISSING_OR_FUTURE_CALIBRATION_AUC','LONG_AUC_BELOW_THRESHOLD'))))
    return f
