from sqlalchemy import text

from app.db.session import build_engine


def test_sqlite_pragmas_are_enabled(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = build_engine(database_url, busy_timeout_ms=7000)

    with engine.connect() as connection:
        journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()
        foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
        busy_timeout = connection.execute(text("PRAGMA busy_timeout")).scalar_one()

    assert journal_mode.lower() == "wal"
    assert foreign_keys == 1
    assert busy_timeout == 7000

