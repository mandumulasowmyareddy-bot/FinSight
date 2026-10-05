import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test-finsight.db")

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def signed_in(client):
    result = client.post("/auth/register", json={"name": "Test User", "email": "test@example.local", "password": "StrongPass123"})
    assert result.status_code == 201
    client.headers["Authorization"] = f"Bearer {result.json()['access_token']}"
    return client
