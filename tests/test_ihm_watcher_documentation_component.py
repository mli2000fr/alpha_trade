from ihm.components import watcher_documentation


def test_build_watcher_documentation_panel_payload_exposes_explicit_workspace_link() -> None:
    payload = watcher_documentation.build_watcher_documentation_panel_payload()

    assert payload["title"] == "📘 Documentation opérateur watcher"
    assert payload["label"] == "📘 Guide watcher complet"
    assert payload["relative_path"] == "doc/watcher.md"
    assert payload["absolute_path"].endswith("doc\\watcher.md")
    assert payload["uri"].startswith("file:///")
    assert "doc/watcher.md" in payload["link_markdown"]
    assert "workspace" in payload["fallback_caption"].lower()

