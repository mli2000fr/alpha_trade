from ihm.pages import db_admin


def test_pages_db_admin_importable() -> None:
    assert hasattr(db_admin, "__doc__")

