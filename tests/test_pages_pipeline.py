from ihm.pages import pipeline

def test_pages_pipeline_importable():
    assert hasattr(pipeline, "__doc__")


def test_alpha_scanner_strict_preset_defaults_to_false_and_uses_default_bucket() -> None:
    session_state: dict[str, object] = {}

    value = pipeline._sync_alpha_scanner_strict_preset_preference(None, session_state)

    assert value is False
    assert session_state[pipeline.ALPHA_SCANNER_PRESET_WIDGET_KEY] is False
    assert session_state[pipeline.ALPHA_SCANNER_PRESET_LAST_ACCOUNT_KEY] == "default"
    assert session_state[pipeline.ALPHA_SCANNER_PRESET_PREFS_KEY] == {"default": False}


def test_alpha_scanner_strict_preset_is_memorized_per_account() -> None:
    session_state: dict[str, object] = {}

    assert pipeline._sync_alpha_scanner_strict_preset_preference("acct-a", session_state) is False
    session_state[pipeline.ALPHA_SCANNER_PRESET_WIDGET_KEY] = True
    assert pipeline._sync_alpha_scanner_strict_preset_preference("acct-a", session_state) is True

    assert pipeline._sync_alpha_scanner_strict_preset_preference("acct-b", session_state) is False
    assert session_state[pipeline.ALPHA_SCANNER_PRESET_WIDGET_KEY] is False

    assert pipeline._sync_alpha_scanner_strict_preset_preference("acct-a", session_state) is True
    assert session_state[pipeline.ALPHA_SCANNER_PRESET_WIDGET_KEY] is True


