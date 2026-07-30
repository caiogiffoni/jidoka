import pytest
from fastapi.testclient import TestClient

import db
import main


@pytest.fixture()
def anon_client(session):
    """A client with no authenticated user (but still using the test session).

    Mirrors the pattern in tests/test_auth.py: only get_session is overridden,
    so requests exercise the real JWT auth flow with real tokens.
    """
    main.app.dependency_overrides[db.get_session] = lambda: session
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()
