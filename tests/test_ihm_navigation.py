from ihm.services import navigation


def test_navigation_sidebar_order_matches_pipeline_then_support_pages() -> None:
    pages = navigation.get_navigation_pages()

    assert [page.key for page in pages] == [
        "overview",
        "pipeline",
        "screening",
        "ml",
        "risk",
        "execution",
        "corporate_actions",
        "backtesting",
        "db_admin",
        "settings",
    ]


def test_navigation_captions_explain_pipeline_and_support_sections() -> None:
    assert "screening" in navigation.build_primary_navigation_caption().lower()
    assert "corporate actions" in navigation.build_primary_navigation_caption().lower()
    assert "hors workflow quotidien" in navigation.build_support_navigation_caption().lower()
