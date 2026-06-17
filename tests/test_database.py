from core.database import Database


def test_database_creation():

    db = Database()

    assert db is not None

    db.close()