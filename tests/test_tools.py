"""Tests for tool modules (inspect, optimize, cleanup) using mocked TDClient."""

import pytest
import httpx
import respx

from td_mcp.td_client import TDClient


@pytest.fixture
def client():
    return TDClient(host="localhost", port=9981)


# ── Inspect tools ─────────────────────────────────────────────────────

class TestInspect:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_operators(self, client):
        from td_mcp.tools.inspect import list_operators
        mock = {"status": "ok", "data": [{"path": "/project1/noise1", "name": "noise1"}]}
        respx.post("http://localhost:9981/ops/list").mock(return_value=httpx.Response(200, json=mock))
        result = await list_operators(client, "/project1")
        assert result["path"] == "/project1"
        assert len(result["operators"]) == 1
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_operator_detail(self, client):
        from td_mcp.tools.inspect import get_operator_detail
        mock = {"status": "ok", "data": {"path": "/project1/noise1", "name": "noise1"}}
        respx.post("http://localhost:9981/ops/get").mock(return_value=httpx.Response(200, json=mock))
        result = await get_operator_detail(client, "/project1/noise1")
        assert "operator" in result
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_trace_signal_flow(self, client):
        from td_mcp.tools.inspect import trace_signal_flow
        mock = {"status": "ok", "data": []}
        respx.post("http://localhost:9981/ops/connections").mock(return_value=httpx.Response(200, json=mock))
        result = await trace_signal_flow(client, "/project1")
        assert "connections" in result
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_network_topology(self, client):
        from td_mcp.tools.inspect import get_network_topology
        mock = {"status": "ok", "data": {"operators": [], "connections": []}}
        respx.post("http://localhost:9981/network/analyze").mock(return_value=httpx.Response(200, json=mock))
        result = await get_network_topology(client, "/")
        assert "network" in result
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_read_chop_channels(self, client):
        from td_mcp.tools.inspect import read_chop_channels
        respx.post("http://localhost:9981/chop/channels").mock(
            return_value=httpx.Response(200, json={"status": "ok", "data": [{"name": "chan1"}]})
        )
        respx.post("http://localhost:9981/chop/values").mock(
            return_value=httpx.Response(200, json={"status": "ok", "data": {"chan1": 0.5}})
        )
        result = await read_chop_channels(client, "/project1/noise1")
        assert result["chop"] == "/project1/noise1"
        assert "channels" in result
        assert "values" in result
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_read_parameter(self, client):
        from td_mcp.tools.inspect import read_parameter
        mock = {"status": "ok", "data": 0.5}
        respx.post("http://localhost:9981/par/get").mock(return_value=httpx.Response(200, json=mock))
        result = await read_parameter(client, "/project1/noise1", "roughness")
        assert result["value"] == 0.5
        await client.close()


# ── Optimize tools ────────────────────────────────────────────────────

class TestOptimize:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_cooking_stats(self, client):
        from td_mcp.tools.optimize import get_cooking_stats
        mock = {"status": "ok", "data": [{"path": "/a", "cook_time": 2.0}]}
        respx.get("http://localhost:9981/perf/stats").mock(return_value=httpx.Response(200, json=mock))
        result = await get_cooking_stats(client)
        assert "stats" in result
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_hotspots(self, client):
        from td_mcp.tools.optimize import find_hotspots
        mock = {"status": "ok", "data": [
            {"path": "/a", "cook_time": 5.0},
            {"path": "/b", "cook_time": 0.1},
        ]}
        respx.get("http://localhost:9981/perf/stats").mock(return_value=httpx.Response(200, json=mock))
        result = await find_hotspots(client, threshold_ms=1.0)
        assert result["hotspot_count"] == 1
        assert result["hotspots"][0]["path"] == "/a"
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_hotspots_none(self, client):
        from td_mcp.tools.optimize import find_hotspots
        mock = {"status": "ok", "data": [{"path": "/a", "cook_time": 0.1}]}
        respx.get("http://localhost:9981/perf/stats").mock(return_value=httpx.Response(200, json=mock))
        result = await find_hotspots(client, threshold_ms=1.0)
        assert result["hotspot_count"] == 0
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_hotspots_non_list_data(self, client):
        """If TD returns a dict instead of list for stats, handle gracefully."""
        from td_mcp.tools.optimize import find_hotspots
        mock = {"status": "ok", "data": "unexpected"}
        respx.get("http://localhost:9981/perf/stats").mock(return_value=httpx.Response(200, json=mock))
        result = await find_hotspots(client, threshold_ms=1.0)
        assert result["hotspot_count"] == 0
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_unused_operators(self, client):
        from td_mcp.tools.optimize import find_unused_operators
        mock = {"status": "ok", "data": {
            "operators": [
                {"path": "/a"}, {"path": "/b"}, {"path": "/c"},
            ],
            "connections": [
                {"source_op": "/a", "target_op": "/b"},
            ],
        }}
        respx.post("http://localhost:9981/network/analyze").mock(return_value=httpx.Response(200, json=mock))
        result = await find_unused_operators(client, "/")
        assert "/c" in result["isolated"]
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_unused_with_none_paths(self, client):
        """None values in path/source/target should not crash sorted()."""
        from td_mcp.tools.optimize import find_unused_operators
        mock = {"status": "ok", "data": {
            "operators": [{"path": "/a"}, {"path": None}, {}],
            "connections": [{"source_op": None, "target_op": "/a"}],
        }}
        respx.post("http://localhost:9981/network/analyze").mock(return_value=httpx.Response(200, json=mock))
        result = await find_unused_operators(client, "/")
        # Should not raise TypeError
        assert isinstance(result["isolated"], list)
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_suggest_optimizations(self, client):
        from td_mcp.tools.optimize import suggest_optimizations
        respx.get("http://localhost:9981/perf/stats").mock(
            return_value=httpx.Response(200, json={"status": "ok", "data": []})
        )
        respx.post("http://localhost:9981/network/analyze").mock(
            return_value=httpx.Response(200, json={"status": "ok", "data": {"operators": [], "connections": []}})
        )
        result = await suggest_optimizations(client, "/")
        assert "suggestions" in result
        await client.close()


# ── Cleanup tools ─────────────────────────────────────────────────────

class TestCleanup:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_bypassed(self, client):
        from td_mcp.tools.cleanup import list_bypassed_operators
        mock = {"status": "ok", "data": {
            "operators": [
                {"path": "/a", "flags": {"bypass": True}},
                {"path": "/b", "flags": {"bypass": False}},
            ],
            "connections": [],
        }}
        respx.post("http://localhost:9981/network/analyze").mock(return_value=httpx.Response(200, json=mock))
        result = await list_bypassed_operators(client, "/")
        assert result["count"] == 1
        assert "/a" in result["bypassed"]
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_operator_valid_path(self, client):
        from td_mcp.tools.cleanup import delete_operator
        mock = {"status": "ok", "data": "executed"}
        respx.post("http://localhost:9981/script/run").mock(return_value=httpx.Response(200, json=mock))
        result = await delete_operator(client, "/project1/noise1")
        assert result["deleted"] is True
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_operator_injection(self, client):
        from td_mcp.tools.cleanup import delete_operator
        result = await delete_operator(client, "'); import os; op('")
        assert result["deleted"] is False
        assert "error" in result
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_cleanup_dry_run(self, client):
        from td_mcp.tools.cleanup import cleanup_dead_ops
        mock = {"status": "ok", "data": {
            "operators": [{"path": "/a"}, {"path": "/b"}],
            "connections": [],
        }}
        respx.post("http://localhost:9981/network/analyze").mock(return_value=httpx.Response(200, json=mock))
        result = await cleanup_dead_ops(client, "/", dry_run=True)
        assert result["dry_run"] is True
        assert result["count"] == 2
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_validate_network(self, client):
        from td_mcp.tools.cleanup import validate_network
        mock = {"status": "ok", "data": {
            "operators": [
                {"path": "/a", "op_type": "noisechop", "error": None},
                {"path": "/b", "op_type": "mathchop", "error": "Cook error"},
            ],
            "connections": [{"source_op": "/a", "target_op": "/b"}],
        }}
        respx.post("http://localhost:9981/network/analyze").mock(return_value=httpx.Response(200, json=mock))
        result = await validate_network(client, "/")
        assert result["total_ops"] == 2
        assert result["issue_count"] >= 1  # at least the error on /b
        await client.close()
