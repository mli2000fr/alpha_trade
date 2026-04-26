from ihm.components import watcher_documentation


def test_build_watcher_documentation_panel_payload_exposes_explicit_workspace_link() -> None:
    payload = watcher_documentation.build_watcher_documentation_panel_payload()

    assert payload["title"] == "📘 Documentation opérateur watcher"
    assert payload["label"] == "📘 Guide watcher complet"
    assert payload["relative_path"] == "doc/watcher.md"
    assert payload["absolute_path"].endswith("doc\\watcher.md")
    assert payload["uri"].startswith("file:///")
    assert "quand le lancer" in payload["quick_summary_markdown"].lower()
    assert "n'est-il pas nécessaire" in payload["quick_summary_markdown"].lower()
    assert "où regarder les logs" in payload["quick_summary_markdown"].lower()
    assert "achat exécuté" in payload["without_watcher_markdown"].lower()
    assert "stop initial exécuté" in payload["without_watcher_markdown"].lower()
    assert "trailing dynamique automatique" in payload["without_watcher_markdown"].lower()
    assert "**oui**" in payload["without_watcher_markdown"].lower()
    assert "**non**" in payload["without_watcher_markdown"].lower()
    assert "doc/watcher.md" in payload["link_markdown"]
    assert "workspace" in payload["fallback_caption"].lower()

