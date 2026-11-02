"""Tests for the shared HTTP/SSE app: API key auth and /health (GM-90)"""

import pytest
from starlette.testclient import TestClient

KEY = "test-key-0123456789"


@pytest.fixture
def client(monkeypatch):
    from main import build_http_app

    monkeypatch.setenv("MCP_API_KEY", KEY)
    # No lifespan: MCP requests that pass auth may fail inside the handler, which is fine -
    # these tests only check what the middleware lets through
    return TestClient(build_http_app("http"), raise_server_exceptions=False)


def test_missing_key_refuses_to_start(monkeypatch):
    from main import build_http_app

    monkeypatch.delenv("MCP_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="MCP_API_KEY is required"):
        build_http_app("http")


def test_blank_key_refuses_to_start(monkeypatch):
    from main import build_http_app

    monkeypatch.setenv("MCP_API_KEY", "   ")
    with pytest.raises(SystemExit):
        build_http_app("http")


def test_health_needs_no_key(client):
    from main import VERSION

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": VERSION}


def test_mcp_without_key_is_401(client):
    assert client.post("/mcp/", json={}).status_code == 401


def test_mcp_with_wrong_key_is_401(client):
    assert client.post("/mcp/", json={}, headers={"MCP_API_KEY": "nope"}).status_code == 401


def test_mcp_with_key_passes_auth(client):
    # Header names are case-insensitive
    response = client.post("/mcp/", json={}, headers={"mcp_api_key": KEY})
    assert response.status_code != 401


def test_sse_app_is_protected_too(monkeypatch):
    from main import build_http_app

    monkeypatch.setenv("MCP_API_KEY", KEY)
    sse = TestClient(build_http_app("sse"), raise_server_exceptions=False)
    assert sse.get("/sse").status_code == 401
    assert sse.get("/health").status_code == 200
