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
        "alpaca_accounts",
        "corporate_actions",
        "supervision_ops",
        "backtesting",
        "parity",
        "db_admin",
        "settings",
        # Sprint S19.4 / S19.5 — nouvelles pages institutionnelles
        "tax_compliance",
        "compliance_audit",
        "glossary",
    ]


def test_navigation_captions_explain_pipeline_and_support_sections() -> None:
    assert "screening" in navigation.build_primary_navigation_caption().lower()
    assert "comptes alpaca" in navigation.build_primary_navigation_caption().lower()
    assert "corporate actions" in navigation.build_primary_navigation_caption().lower()
    assert "hors workflow quotidien" in navigation.build_support_navigation_caption().lower()
    assert "supervision ops" in navigation.build_support_navigation_caption().lower()


def test_navigation_sections_expose_logical_groups() -> None:
    """Sprint S19.5 + S20.6 — Refonte navigation hiérarchique.

    L'anomalie utilisateur (d) impose de promouvoir Pipeline en section
    propre *Workflow & Orchestration* (utilisée tous les jours), donc
    on passe de 5 à 6 sections."""
    sections = navigation.get_navigation_sections()
    assert [s.key for s in sections] == [
        "home",
        "workflow",
        "trading",
        "research",
        "config",
        "compliance",
    ]
    keys_in_sections = {p.key for s in sections for p in s.pages}
    keys_total = {p.key for p in navigation.get_navigation_pages()}
    assert keys_in_sections == keys_total, (
        f"Pages sans section : {keys_total - keys_in_sections}"
    )


def test_navigation_sections_caption_lists_all_sections() -> None:
    caption = navigation.build_section_navigation_caption()
    for label in (
        "Accueil",
        "Workflow",
        "Trading",
        "Analyse",
        "Configuration",
        "Conformité",
    ):
        assert label in caption


def test_compliance_section_includes_tax_and_audit_pages() -> None:
    sections = {s.key: s for s in navigation.get_navigation_sections()}
    compliance_keys = {p.key for p in sections["compliance"].pages}
    assert {"tax_compliance", "compliance_audit", "glossary"} <= compliance_keys

