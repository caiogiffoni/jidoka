import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

import db
import main


@pytest.fixture()
def session():
    """One test = one DB transaction, rolled back at the end.

    Keeps automated runs safe against the dev database (or CI's throwaway
    one) without needing a second database just for tests.
    """
    db.create_db_and_tables()
    connection = db.engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(session):
    main.app.dependency_overrides[db.get_session] = lambda: session
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()
