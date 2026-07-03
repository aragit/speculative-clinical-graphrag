import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from api.middleware import APIKeyMiddleware, RateLimitMiddleware, RequestIDMiddleware


@pytest.fixture
def app_with_api_key():
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/protected")
    async def protected():
        return {"data": "secret"}

    app.add_middleware(APIKeyMiddleware, api_key="test-key-123")
    return app


@pytest.fixture
def app_with_rate_limit():
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/data")
    async def data():
        return {"data": "ok"}

    app.add_middleware(RateLimitMiddleware, max_requests=5, window_seconds=60)
    return app


def test_api_key_missing_returns_401(app_with_api_key):
    client = TestClient(app_with_api_key, raise_server_exceptions=False)
    response = client.get("/protected")
    assert response.status_code == 401


def test_api_key_valid_returns_200(app_with_api_key):
    client = TestClient(app_with_api_key)
    response = client.get("/protected", headers={"X-API-Key": "test-key-123"})
    assert response.status_code == 200
    assert response.json()["data"] == "secret"


def test_api_key_health_bypass(app_with_api_key):
    client = TestClient(app_with_api_key)
    response = client.get("/health")
    assert response.status_code == 200


def test_rate_limit_blocks_after_limit(app_with_rate_limit):
    client = TestClient(app_with_rate_limit, raise_server_exceptions=False)
    for _ in range(5):
        resp = client.get("/api/data")
        assert resp.status_code == 200
    response = client.get("/api/data")
    assert response.status_code == 429


def test_rate_limit_health_bypass(app_with_rate_limit):
    client = TestClient(app_with_rate_limit)
    for _ in range(6):
        resp = client.get("/health")
        assert resp.status_code == 200


def test_request_id_header():
    app = FastAPI()

    @app.get("/test")
    async def test():
        return {"ok": True}

    app.add_middleware(RequestIDMiddleware)
    client = TestClient(app)
    response = client.get("/test")
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time" in response.headers
