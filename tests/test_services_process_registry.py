from ihm.services import process_registry

def test_services_process_registry_importable():
    assert hasattr(process_registry, "__doc__")

