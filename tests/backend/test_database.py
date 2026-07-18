from sqlalchemy import text

from services.api.app.db.session import engine


def test_sqlite_safety_pragmas_are_enabled() -> None:
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == 5000
        assert connection.execute(text("PRAGMA journal_mode")).scalar_one().lower() == "wal"


def test_migration_created_metadata_table() -> None:
    with engine.connect() as connection:
        value = connection.execute(
            text("SELECT value FROM app_metadata WHERE key = 'schema_version'")
        ).scalar_one()
    assert value == "20260718_0001"
