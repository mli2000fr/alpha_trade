from ihm.pages import supervision_ops


def test_pages_supervision_ops_importable():
    assert hasattr(supervision_ops, "__doc__")


def test_restart_button_label_reflects_local_service_state() -> None:
    assert supervision_ops._restart_button_label({"local_service_active": False}) == "▶️ Démarrer service local IHM"
    assert supervision_ops._restart_button_label({"local_service_active": True}) == "♻️ Restart service local IHM"


def test_tail_text_limits_output_to_last_lines() -> None:
    content = "\n".join(str(index) for index in range(250))

    tailed = supervision_ops._tail_text(content, max_lines=5)

    assert tailed == "245\n246\n247\n248\n249"


