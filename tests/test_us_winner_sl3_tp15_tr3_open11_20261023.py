from dataclasses import asdict
import pandas as pd
import pytest
from scripts.research import us_winner_sl3_tp15_tr3_open11_20261023 as s


def test_only_tp_changes_and_context_is_restored():
    p=s.base.source.read(s.base.PARENT/'protocol.json')
    before=s.base.variant_config(p,2026)
    rule=s.base.RULE;scalar=s.auditor.scalar_exit
    with s.tp15_adapter():
        after=s.base.variant_config(p,2026)
        a,b=asdict(before.exec_config.winner_pyramiding),asdict(after.exec_config.winner_pyramiding)
        assert {k for k in a if a[k]!=b[k]}=={'take_profit_pct'}
        assert b['take_profit_pct']==.15 and b['horizon_sessions']==10
        assert after.risk_config==before.risk_config and after.exec_config.leverage==before.exec_config.leverage
    assert s.base.RULE is rule and s.auditor.scalar_exit is scalar


def test_context_restored_on_error():
    arm=s.base.ARM;save=s.base.source.save_new
    with pytest.raises(RuntimeError):
        with s.tp15_adapter():raise RuntimeError('intentional')
    assert s.base.ARM==arm and s.base.source.save_new is save


def frame(open=100,high=116,low=98):
    return pd.DataFrame(dict(open=[open],high=[high],low=[low],close=[open],
        bar_timestamp=[pd.Timestamp('2026-01-02 15:00Z')],bar_end_timestamp=[pd.Timestamp('2026-01-02 15:05Z')]))


def test_scalar_target_is_15_not_7():
    f=frame();t=f.bar_timestamp.iloc[0];due=t+pd.Timedelta(days=20)
    assert s.scalar_tp15(f,t,100,due)[1]==pytest.approx(115)
    assert s.ORIGINAL_SCALAR(f,t,100,due)[1]==107


def test_collision_and_gap_keep_original_conventions():
    f=frame(low=96);t=f.bar_timestamp.iloc[0];due=t+pd.Timedelta(days=20)
    assert s.scalar_tp15(f,t,100,due)[1:]==(97.,'STOP')
    f=frame(open=120,high=125,low=119)
    price,reason=s.scalar_tp15(f,t,100,due)[1:]
    assert price==pytest.approx(115) and reason=='TP_GAP_CAPPED'


def test_cannot_silently_override_frozen_tp():
    f=frame();t=f.bar_timestamp.iloc[0]
    with pytest.raises(ValueError,match='TP15'):s.scalar_tp15(f,t,100,t+pd.Timedelta(days=20),tp=.07)
