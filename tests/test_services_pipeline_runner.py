from ihm.services import pipeline_runner

def test_services_pipeline_runner_importable():
    assert hasattr(pipeline_runner, "__doc__")

