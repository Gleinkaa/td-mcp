"""Tests for TD client using respx (mocked HTTP)."""

import json

import pytest
import httpx
import respx

from td_mcp.td_client import TDClient, TDResponse


@pytest.fixture
def client():
    return TDClient(host="localhost", port=9981)


# ── Ping ──────────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_ping_success(client):
    respx.get("http://localhost:9981/ping").mock(return_value=httpx.Response(200, text="pong"))
    assert await client.ping() is True
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_ping_connect_error(client):
    respx.get("http://localhost:9981/ping").mock(side_effect=httpx.ConnectError("refused"))
    assert await client.ping() is False
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_ping_timeout(client):
    respx.get("http://localhost:9981/ping").mock(side_effect=httpx.ReadTimeout("timed out"))
    assert await client.ping() is False
    await client.close()


# ── Request error handling ────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_request_http_404(client):
    """HTTP 404 should return error TDResponse, not raise."""
    respx.post("http://localhost:9981/ops/list").mock(
        return_value=httpx.Response(404, text="Not Found")
    )
    resp = await client.list_operators("/project1")
    assert resp.status == "error"
    assert "404" in resp.error
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_request_http_500(client):
    """HTTP 500 should return error TDResponse, not raise."""
    respx.post("http://localhost:9981/ops/list").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )
    resp = await client.list_operators("/project1")
    assert resp.status == "error"
    assert "500" in resp.error
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_request_connect_error(client):
    """ConnectError should return error TDResponse."""
    respx.post("http://localhost:9981/ops/list").mock(side_effect=httpx.ConnectError("refused"))
    resp = await client.list_operators("/project1")
    assert resp.status == "error"
    assert "connect" in resp.error.lower()
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_request_timeout(client):
    """TimeoutException should return error TDResponse."""
    respx.post("http://localhost:9981/ops/list").mock(side_effect=httpx.ReadTimeout("slow"))
    resp = await client.list_operators("/project1")
    assert resp.status == "error"
    assert "timed out" in resp.error.lower()
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_request_non_json_response(client):
    """Non-JSON body should not raise — should wrap as text."""
    respx.post("http://localhost:9981/ops/list").mock(
        return_value=httpx.Response(200, text="<html>Error</html>", headers={"content-type": "text/html"})
    )
    resp = await client.list_operators("/project1")
    assert resp.status == "ok"
    assert "<html>" in resp.data
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_request_response_missing_status_key(client):
    """Dict response without 'status' key should get 'ok' default."""
    respx.post("http://localhost:9981/ops/list").mock(
        return_value=httpx.Response(200, json={"data": [1, 2, 3]})
    )
    resp = await client.list_operators("/project1")
    assert resp.status == "ok"
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_request_response_is_list(client):
    """List body should be wrapped in TDResponse."""
    respx.post("http://localhost:9981/ops/list").mock(
        return_value=httpx.Response(200, json=[{"path": "/a"}])
    )
    resp = await client.list_operators("/project1")
    assert resp.status == "ok"
    assert isinstance(resp.data, list)
    await client.close()


# ── Operator methods ──────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_list_operators(client):
    mock_response = {
        "status": "ok",
        "data": [
            {"path": "/project1/noise1", "name": "noise1", "family": "CHOP", "op_type": "noisechop"}
        ]
    }
    respx.post("http://localhost:9981/ops/list").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    resp = await client.list_operators("/project1")
    assert resp.status == "ok"
    assert len(resp.data) == 1
    assert resp.data[0]["name"] == "noise1"
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_get_operator(client):
    mock_response = {"status": "ok", "data": {"path": "/project1/noise1", "name": "noise1"}}
    respx.post("http://localhost:9981/ops/get").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    resp = await client.get_operator("/project1/noise1")
    assert resp.status == "ok"
    assert resp.data["path"] == "/project1/noise1"
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_get_connections(client):
    mock_response = {"status": "ok", "data": []}
    respx.post("http://localhost:9981/ops/connections").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    resp = await client.get_connections("/project1")
    assert resp.status == "ok"
    await client.close()


# ── Script execution ──────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_run_script(client):
    mock_response = {"status": "ok", "data": "executed"}
    respx.post("http://localhost:9981/script/run").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    resp = await client.run_script("op('/project1').create('noisechop')")
    assert resp.status == "ok"
    await client.close()


# ── Parameter control ─────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_get_par(client):
    mock_response = {"status": "ok", "data": 0.5}
    respx.post("http://localhost:9981/par/get").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    resp = await client.get_par("/project1/noise1", "roughness")
    assert resp.data == 0.5
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_set_par(client):
    mock_response = {"status": "ok", "data": {"set": "roughness", "value": 0.7}}
    respx.post("http://localhost:9981/par/set").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    resp = await client.set_par("/project1/noise1", "roughness", 0.7)
    assert resp.status == "ok"
    await client.close()


# ── CHOP ──────────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_get_chop_channels(client):
    mock_response = {"status": "ok", "data": [{"name": "chan1", "num_samples": 1}]}
    respx.post("http://localhost:9981/chop/channels").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    resp = await client.get_chop_channels("/project1/noise1")
    assert resp.status == "ok"
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_get_chop_values(client):
    mock_response = {"status": "ok", "data": {"chan1": 0.75}}
    respx.post("http://localhost:9981/chop/values").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    resp = await client.get_chop_values("/project1/noise1", channel="chan1")
    assert resp.data["chan1"] == 0.75
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_get_chop_values_all(client):
    mock_response = {"status": "ok", "data": {"chan1": 0.5, "chan2": 0.8}}
    respx.post("http://localhost:9981/chop/values").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    resp = await client.get_chop_values("/project1/noise1")
    assert len(resp.data) == 2
    await client.close()


# ── Network analysis ──────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_analyze_network(client):
    mock_response = {"status": "ok", "data": {"operators": [], "connections": [], "sub_networks": []}}
    respx.post("http://localhost:9981/network/analyze").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    resp = await client.analyze_network("/project1")
    assert resp.status == "ok"
    assert isinstance(resp.data, dict)
    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_get_cooking_stats(client):
    mock_response = {"status": "ok", "data": []}
    respx.get("http://localhost:9981/perf/stats").mock(
        return_value=httpx.Response(200, json=mock_response)
    )
    resp = await client.get_cooking_stats()
    assert resp.status == "ok"
    await client.close()


# ── Client lifecycle ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_close_when_not_opened():
    """close() should not raise if never used."""
    c = TDClient()
    await c.close()  # should not raise


@pytest.mark.asyncio
async def test_double_close():
    """Double close should not raise."""
    c = TDClient()
    await c.close()
    await c.close()
