from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from scripts.research import us_winner_continuous_h20_20261108 as h20
from tests.test_winner_continuous_q051_q088 import reference


def test_four_h20_cases_preserve_profiles_and_exit_at_official_open21():
    from common.winner_pyramiding import due_open
    ref=reference();ref['winner_policy']['horizon_sessions']=20
    assert len(h20.CASES)==4 and set(h20.MODEL_IDS)==set(range(2021,2027))
    for name,case in h20.CASES.items():
        cfg=h20.shared.configuration(ref,case);p=cfg.exec_config.winner_pyramiding
        selection=h20.shared.settings(case,1790)
        assert p.horizon_sessions==20 and p.stop_loss_pct==.05
        assert p.initial_position_fraction==1. and p.confirmation_bars==0
        assert p.take_profit_pct is None and p.trailing_stop_pct is None
        assert cfg.exec_config.simulated_margin_buying_power_multiplier==2.
        assert cfg.winner_drawdown_controller_enabled==(case['profile']=='Q088')
        assert cfg.risk_config.max_gross_exposure==(2. if case['profile']=='Q088' else 1.)
        assert selection.oracle_top_n==(358 if case['profile']=='Q088' else 179)
        assert selection.long_top_n==(10 if case['profile']=='Q088' else 5)
        assert selection.min_long_probability==selection.min_long_auc==(.6 if name.endswith('060') else .5)
        assert pd.Timestamp(due_open(pd.Timestamp('2021-01-04T14:30Z'),p))==pd.Timestamp('2021-02-02T14:30Z')


def test_h20_price_inventory_reaches_open21_not_just_open11():
    sessions=[date(2021,1,4)+pd.Timedelta(days=i) for i in range(24)]
    signals=pd.DataFrame([dict(symbol='NEW',trade_date=date(2020,12,31))])
    windows=h20.shared.supplemental_windows([signals],sessions,set(),horizon=20)
    assert all('NEW' in windows[d] for d in sessions[:21])
    assert all(not windows[d] for d in sessions[21:])


def test_prediction_readiness_requires_both_oracle_and_directional_coverage(monkeypatch):
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def begin(self):return self
        def execute(self,*args,**kwargs):pass
    engine=SimpleNamespace(connect=lambda:Connection())
    days=[date(2024,1,2)]
    frames=iter([pd.DataFrame({'prediction_date':days,'n':[1790]}),pd.DataFrame({'prediction_date':days,'n':[1664]})])
    monkeypatch.setattr(h20.pd,'read_sql',lambda *args,**kwargs:next(frames))
    assert h20.coverage(engine,'batch',days)['complete'] is False
    frames=iter([pd.DataFrame({'prediction_date':days,'n':[1665]})]*2)
    monkeypatch.setattr(h20.pd,'read_sql',lambda *args,**kwargs:next(frames))
    assert h20.coverage(engine,'batch',days)['complete'] is True


def test_reference_archive_survives_removal_of_old_ihm_exports(tmp_path,monkeypatch):
    source=tmp_path/'ihm';source.mkdir();root=tmp_path/'research';root.mkdir()
    for name in ('protocol.json','report.json','signals.csv'):(source/name).write_text('saved',encoding='utf-8')
    monkeypatch.setattr(h20,'ANNUAL_REFERENCE',source)
    h20.freeze_annual_reference(root)
    for name in ('protocol.json','report.json','signals.csv'):(source/name).unlink()
    h20.freeze_annual_reference(root)
    assert (root/'reference-H20-2021/report.json').read_text(encoding='utf-8')=='saved'
