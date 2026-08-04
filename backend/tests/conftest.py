import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

import auth
import db
import main
from models import User

os.environ.setdefault(
    "JWT_SECRET_KEY", "test-secret-for-pytest-must-be-at-least-32-bytes-long"
)


@pytest.fixture()
def session():
    """One test = one DB savepoint, rolled back at the end.

    Keeps automated runs safe against the dev database (or CI's throwaway
    one) without needing a second database just for tests. A nested
    transaction is used so that production code that calls ``session.commit()``
    only commits the savepoint and the outer rollback still discards everything.
    """
    db.create_db_and_tables()
    connection = db.engine.connect()
    transaction = connection.begin_nested()
    session = Session(bind=connection)
    session.begin_nested()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def test_user(session):
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=auth._hash_password("password"),
    )
    session.add(user)
    session.flush()
    return user


@pytest.fixture()
def client(session, test_user):
    main.app.dependency_overrides[db.get_session] = lambda: session
    main.app.dependency_overrides[auth.get_current_user] = lambda: test_user
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()
