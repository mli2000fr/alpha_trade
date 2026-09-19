"""Offline checks for the exploratory French guidance metadata selector."""

from scripts.research.fr_guidance_feasibility import NUMBER, choose_issuers, choose_pdfs, classify_title


def test_classify_title_rejects_publication_calendar() -> None:
    assert classify_title("Calendrier prévisionnel de communication financière 2023") is None
    assert classify_title("Regroupement des actions et calendrier prévisionnel") is None


def test_classify_title_keeps_real_revision_candidate() -> None:
    assert classify_title("Révision à la hausse de l'objectif annuel du chiffre d'affaires") == "revision_title"


def test_choose_issuers_is_deterministic_and_stratified() -> None:
    counts = [3, 12, 42, 142]
    groups = [{"isin": f"FR{index:010d}", "announcements_2024_25": count}
              for index, count in enumerate(counts)]
    chosen = choose_issuers(groups, size=4, seed="fixed")
    assert chosen == choose_issuers(list(reversed(groups)), size=4, seed="fixed")
    assert {row["activity_bucket"] for row in chosen} == {"2-9", "10-29", "30-99", "100+"}


def test_choose_pdfs_limits_two_per_issuer_and_category() -> None:
    items = [{"url": f"https://example.test/{index}.pdf", "isin": "FR0000000001",
              "kind": "revision_title"} for index in range(5)]
    selected = choose_pdfs(items, seed="fixed", per_kind=4)
    assert len(selected) == 2


def test_numeric_percent_is_detected() -> None:
    assert NUMBER.findall("ancien 12% nouveau 13,5 %") == ["12%", "13,5 %"]
