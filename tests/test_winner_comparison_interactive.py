"""Archived curves only: selections never launch or alter a backtest."""
import json
import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest
from ihm.components.winner_profile_comparison import (comparison_data,default_curve_labels,
    curve_checkbox_key,closing_drawdowns,comparison_figure)


def traces(app,axis='y'):
    return [t['name'] for t in json.loads(app.get('plotly_chart')[0].proto.spec)['data'] if t['yaxis']==axis]


def test_popup_defaults_top_five_and_checkbox_choices_persist():
    table,_,_=comparison_data();defaults=default_curve_labels(table)
    assert len(defaults)==5 and defaults[0]=='Q051 témoin TOP10 — plafond, attente deux séances'
    app=AppTest.from_string('''
from ihm.components.winner_profile_comparison import show_reference_comparison
show_reference_comparison()
''').run(timeout=30)
    assert not app.exception
    assert {button.proto.id.split('-')[-1] for button in app.get('download_button')} >= {
        'bt_winner_compare_guide_md','bt_winner_compare_guide_zip'}
    assert any('Lire le guide complet' in expander.label for expander in app.expander)
    assert len(app.checkbox)==len(table)==9
    assert {c.key for c in app.checkbox if c.value}=={curve_checkbox_key(s) for s in defaults}
    assert traces(app)==defaults
    assert traces(app,'y2')==defaults
    assert app.dataframe[0].value['Courbe'].tolist()==defaults
    # User choice adds SPY and removes a high-return strategy; reruns must not
    # restore historical winners over the user's selection.
    app.checkbox(key=curve_checkbox_key('SPY')).check()
    app.checkbox(key=curve_checkbox_key(defaults[0])).uncheck().run(timeout=30)
    assert not app.exception
    assert 'SPY' in traces(app) and defaults[0] not in traces(app)
    assert traces(app,'y2')==traces(app)
    app.run(timeout=30)
    assert 'SPY' in traces(app) and defaults[0] not in traces(app)
    # Empty is a deliberate choice, not a request to silently reselect five.
    for checkbox in app.checkbox:checkbox.uncheck()
    app.run(timeout=30)
    assert not app.exception and not app.get('plotly_chart')
    assert any('Cochez au moins une variante' in message.value for message in app.info)
    app.button(key='bt_winner_compare_top5').click().run(timeout=30)
    assert not app.exception and traces(app)==defaults
    assert traces(app,'y2')==defaults


def test_drawdowns_track_the_past_peak_and_match_archived_closing_minima():
    dates=pd.date_range('2021-01-01',periods=5)
    curves=pd.DataFrame({'A':[3600.,4000.,5000.,4500.,6000.]},index=dates)
    dd=closing_drawdowns(curves)
    np.testing.assert_allclose(dd.A,[-10.,0.,0.,-10.,0.],atol=1e-12)
    changed=curves.copy();changed.iloc[-1]=100000.
    pd.testing.assert_frame_equal(closing_drawdowns(changed).iloc[:-1],dd.iloc[:-1])
    table,archives,_=comparison_data()
    minima=closing_drawdowns(archives).min().round(2)
    for row in table.to_dict('records'):
        assert minima[row['Courbe']]==row['DD sur clôtures (%)']
    figure=comparison_figure(archives,['SPY','Q051 témoin — TOP5'])
    assert figure.layout.xaxis.matches=='x2'
    for capital,drawdown in zip(figure.data[:2],figure.data[2:]):
        assert capital.name==drawdown.name
        assert capital.line.color==drawdown.line.color
        assert capital.legendgroup==drawdown.legendgroup
        np.testing.assert_allclose(drawdown.y,closing_drawdowns(archives)[drawdown.name])
