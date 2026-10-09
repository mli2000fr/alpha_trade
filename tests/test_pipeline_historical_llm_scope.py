import pytest

from ihm.pages import pipeline
from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command


@pytest.mark.parametrize('historical,shadow', [(True, False), (False, True), (True, True)])
def test_research_scope_does_not_wrap_llm_or_mutate_global_options(historical, shadow):
    options = PipelineLaunchOptions(llm_filter_enabled=True, ml_predict_batch_id='oracle-test',
        ml_predict_use_historical_range=historical, ml_oracle_shadow=shadow,
        ml_training_start_date='2025-01-01', ml_training_end_date='2025-12-31')
    scoped = pipeline._ml_prediction_scope_options(options)
    command = build_pipeline_command('ml_predict', scoped)
    assert options.llm_filter_enabled is True
    assert scoped.llm_filter_enabled is False
    assert 'service.llm_directional.pipeline' not in command
    assert scoped.ml_oracle_shadow is shadow
    assert scoped.ml_predict_use_historical_range is historical
    # Runner still rejects unsafe direct calls: no weakening of guard.
    with pytest.raises(ValueError, match='historique ni Oracle shadow'):
        build_pipeline_command('ml_predict', options)


def test_prospective_scope_keeps_llm_filter():
    options = PipelineLaunchOptions(llm_filter_enabled=True, ml_predict_batch_id='oracle-test')
    assert pipeline._ml_prediction_scope_options(options) is options
    assert 'service.llm_directional.pipeline' in build_pipeline_command('ml_predict', options)


def test_historical_panel_preview_and_launch_identical_without_llm(monkeypatch):
    class Container:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
    state = {}
    monkeypatch.setattr(pipeline.st, 'session_state', state)
    captions, previews, launches = [], [], []
    monkeypatch.setattr(pipeline.st, 'caption', lambda x, **kw: captions.append(x))
    for name in ('warning', 'metric', 'code'):
        monkeypatch.setattr(pipeline.st, name, lambda *a, **kw: None)
    monkeypatch.setattr(pipeline.st, 'columns', lambda n, **kw: [Container() for _ in range(n)])
    def selectbox(label, *args, **kwargs):
        state[kwargs['key']] = 'tradable-universe'
        return 'tradable-universe'
    monkeypatch.setattr(pipeline.st, 'selectbox', selectbox)
    monkeypatch.setattr(pipeline, '_resolve_ml_train_scope_preview', lambda *a, **kw: None)
    monkeypatch.setattr(pipeline.st, 'button', lambda *a, **kw: True)
    def preview(step, options):
        previews.append(options)
        return build_pipeline_command(step, options)
    monkeypatch.setattr(pipeline, 'build_pipeline_command', preview)
    monkeypatch.setattr(pipeline, '_launch_pipeline_step',
        lambda step, label, options, db, runs: launches.append(options))
    options = PipelineLaunchOptions(llm_filter_enabled=True, ml_predict_batch_id='oracle-test',
        ml_training_start_date='2025-01-01', ml_training_end_date='2025-12-31')
    pipeline._render_ml_predict_scope_block(options, workflow_active=False,
        active_for_step=[], db_config={}, all_runs=[])
    assert len(previews) == len(launches) == 1
    assert previews[0] is launches[0]
    assert not launches[0].llm_filter_enabled
    assert launches[0].ml_predict_use_historical_range
    assert options.llm_filter_enabled
    assert any('sans LLM' in caption for caption in captions)
