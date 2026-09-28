"""Tests for server.py — FastAPI application and 402 middleware."""
import sys

sys.path.insert(0, ".")

import os
import pytest
from httpx import AsyncClient, ASGITransport

# Set env before importing app
os.environ["PAY_TO"] = "0x0000000000000000000000000000000000000000"
os.environ["UPSTREAM_URL"] = "https://api.open-meteo.com"
os.environ["KITE_NETWORK"] = "testnet"
os.environ["PRICE_USD"] = "0.001"

from server import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "network" in data
    assert "asset" in data


@pytest.mark.asyncio
async def test_v1_unpaid_returns_402(client):
    resp = await client.get("/v1/forecast?latitude=52.52&longitude=13.41")
    assert resp.status_code == 402
    assert "payment-required" in resp.headers
    assert resp.headers.get("cache-control") == "no-store"


@pytest.mark.asyncio
async def test_v1_wildcard_returns_402(client):
    resp = await client.get("/v1/some/other/path")
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_v1_post_returns_402(client):
    resp = await client.post("/v1/data", json={"key": "value"})
    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_payment_header_is_base64_json(client):
    resp = await client.get("/v1/forecast?latitude=52.52&longitude=13.41")
    import base64, json

    raw = resp.headers["payment-required"]
    decoded = base64.b64decode(raw)
    body = json.loads(decoded)
    assert body["x402Version"] == 2
    assert body["error"] == "Payment required"
    assert len(body["accepts"]) > 0
    offer = body["accepts"][0]
    assert offer["scheme"] == "exact"
    assert offer["network"] == "eip155:2368"
    assert "amount" in offer
    assert "payTo" in offer
    assert "asset" in offer
    assert "maxTimeoutSeconds" in offer
