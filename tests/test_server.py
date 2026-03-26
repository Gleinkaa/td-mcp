"""Tests for the MCP server tool handlers.

We monkeypatch the global _client to use a mock TDClient that returns
controlled TDResponse objects, so we test the server-layer logic
(JSON serialization, argument passing, error propagation) without HTTP.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from td_mcp.td_client import TDResponse


# Helper to create a mock client whose methods return TDResponse
def _mock_client(**overrides):
    """Create an AsyncMock TDClient with default return values."""
    defaults = {
        "ping": TDResponse(status="ok", data="pong"),
        "list_operators": TDResponse(status="ok", data=[{"path": "/a", "name": "a", "family": "CHOP", "op_type": "noisechop"}]),
        "get_operator": TDResponse(status="ok", data={"path": "/a", "name": "a"}),
        "get_connections": TDResponse(status="ok", data=[]),
        "analyze_network": TDResponse(status="ok", data={"operators": [], "connections": [], "sub_networks": []}),
        "run_script": TDResponse(status="ok", data="executed"),
        "get_par": TDResponse(status="ok", data=0.5),
        "set_par": TDResponse(status="ok", data={"set": "p", "value": 1}),
        "get_cooking_stats": TDResponse(status="ok", data=[]),
        "get_chop_channels": TDResponse(status="ok", data=[{"name": "chan1"}]),
        "get_chop_values": TDResponse(status="ok", data={"chan1": 0.75}),
        "close": None,
    }
    defaults.update(overrides)

    client = AsyncMock()
    for method_name, return_val in defaults.items():
        getattr(client, method_name).return_value = return_val
    return client


def _patch_client(client):
    """Patch the server module's get_client to return our mock."""
    return patch("td_mcp.server.get_client", return_value=client)


# ── Connection tools ──────────────────────────────────────────────────

class TestServerConnection:
    @pytest.mark.asyncio
    async def test_td_ping(self):
        from td_mcp.server import td_ping
        mc = _mock_client()
        mc.ping.return_value = True
        with _patch_client(mc):
            result = json.loads(await td_ping())
        assert result["reachable"] is True

    @pytest.mark.asyncio
    async def test_td_connect(self):
        from td_mcp.server import td_connect
        with patch("td_mcp.server._client", None):
            with patch("td_mcp.server.TDClient") as MockCls:
                instance = AsyncMock()
                instance.ping.return_value = True
                MockCls.return_value = instance
                result = json.loads(await td_connect("127.0.0.1", 9000))
        assert result["connected"] is True
        assert result["host"] == "127.0.0.1"
        assert result["port"] == 9000


# ── Inspect tools ─────────────────────────────────────────────────────

class TestServerInspect:
    @pytest.mark.asyncio
    async def test_td_list_ops(self):
        from td_mcp.server import td_list_ops
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_list_ops("/project1"))
        assert "operators" in result

    @pytest.mark.asyncio
    async def test_td_get_operator(self):
        from td_mcp.server import td_get_operator
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_get_operator("/project1/noise1"))
        assert "operator" in result

    @pytest.mark.asyncio
    async def test_td_trace_signal_flow(self):
        from td_mcp.server import td_trace_signal_flow
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_trace_signal_flow("/"))
        assert "connections" in result

    @pytest.mark.asyncio
    async def test_td_network_topology(self):
        from td_mcp.server import td_network_topology
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_network_topology("/"))
        assert "network" in result

    @pytest.mark.asyncio
    async def test_td_read_chop(self):
        from td_mcp.server import td_read_chop
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_read_chop("/project1/noise1"))
        assert "chop" in result
        assert "channels" in result
        assert "values" in result

    @pytest.mark.asyncio
    async def test_td_read_par(self):
        from td_mcp.server import td_read_par
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_read_par("/project1/noise1", "roughness"))
        assert result["value"] == 0.5

    @pytest.mark.asyncio
    async def test_td_set_par(self):
        from td_mcp.server import td_set_par
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_set_par("/project1/noise1", "roughness", "0.7"))
        assert result["par"] == "roughness"


# ── Optimize tools ────────────────────────────────────────────────────

class TestServerOptimize:
    @pytest.mark.asyncio
    async def test_td_cooking_stats(self):
        from td_mcp.server import td_cooking_stats
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_cooking_stats())
        assert "stats" in result

    @pytest.mark.asyncio
    async def test_td_find_hotspots(self):
        from td_mcp.server import td_find_hotspots
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_find_hotspots(2.0))
        assert "hotspots" in result
        assert result["threshold_ms"] == 2.0

    @pytest.mark.asyncio
    async def test_td_find_unused(self):
        from td_mcp.server import td_find_unused
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_find_unused("/"))
        assert "isolated" in result

    @pytest.mark.asyncio
    async def test_td_suggest_optimizations(self):
        from td_mcp.server import td_suggest_optimizations
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_suggest_optimizations("/"))
        assert "suggestions" in result


# ── Cleanup tools ─────────────────────────────────────────────────────

class TestServerCleanup:
    @pytest.mark.asyncio
    async def test_td_list_bypassed(self):
        from td_mcp.server import td_list_bypassed
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_list_bypassed("/"))
        assert "bypassed" in result

    @pytest.mark.asyncio
    async def test_td_cleanup_dry_run(self):
        from td_mcp.server import td_cleanup
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_cleanup("/", dry_run=True))
        assert result["dry_run"] is True

    @pytest.mark.asyncio
    async def test_td_validate_network(self):
        from td_mcp.server import td_validate_network
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_validate_network("/"))
        assert "issues" in result


# ── Templates & Recipes ───────────────────────────────────────────────

class TestServerTemplates:
    @pytest.mark.asyncio
    async def test_td_list_recipes(self):
        from td_mcp.server import td_list_recipes
        result = json.loads(await td_list_recipes())
        assert result["count"] > 0

    @pytest.mark.asyncio
    async def test_td_list_recipes_filtered(self):
        from td_mcp.server import td_list_recipes
        result = json.loads(await td_list_recipes(category="audio_reactive"))
        assert all(r["category"] == "audio_reactive" for r in result["recipes"])

    @pytest.mark.asyncio
    async def test_td_get_recipe(self):
        from td_mcp.server import td_get_recipe
        result = json.loads(await td_get_recipe("lfo_modulator"))
        assert result["name"] == "lfo_modulator"

    @pytest.mark.asyncio
    async def test_td_get_recipe_not_found(self):
        from td_mcp.server import td_get_recipe
        result = json.loads(await td_get_recipe("nonexistent"))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_td_recipe_to_script(self):
        from td_mcp.server import td_recipe_to_script
        result = json.loads(await td_recipe_to_script("audio_reactive_basic"))
        assert "script" in result

    @pytest.mark.asyncio
    async def test_td_recipe_to_script_bad_path(self):
        from td_mcp.server import td_recipe_to_script
        result = json.loads(await td_recipe_to_script("audio_reactive_basic", "'; drop table"))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_td_apply_recipe(self):
        from td_mcp.server import td_apply_recipe
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_apply_recipe("audio_reactive_basic"))
        assert result["applied"] is True

    @pytest.mark.asyncio
    async def test_td_apply_recipe_not_found(self):
        from td_mcp.server import td_apply_recipe
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_apply_recipe("nonexistent"))
        assert "error" in result


# ── DAW Bridge ────────────────────────────────────────────────────────

class TestServerDAWBridge:
    @pytest.mark.asyncio
    async def test_td_create_daw_mapping_osc(self):
        from td_mcp.server import td_create_daw_mapping
        result = json.loads(await td_create_daw_mapping(
            source_type="osc",
            source_channel="/track/1/vol",
            target_op="/project1/geo1",
            target_par="ty",
        ))
        assert "script" in result

    @pytest.mark.asyncio
    async def test_td_create_daw_mapping_midi(self):
        from td_mcp.server import td_create_daw_mapping
        result = json.loads(await td_create_daw_mapping(
            source_type="midi_cc",
            source_channel="1",
            target_op="/project1/geo1",
            target_par="ty",
            range_min=0.0,
            range_max=127.0,
        ))
        assert "script" in result

    @pytest.mark.asyncio
    async def test_td_create_daw_mapping_invalid_type(self):
        from td_mcp.server import td_create_daw_mapping
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            await td_create_daw_mapping(
                source_type="invalid",
                source_channel="ch1",
                target_op="/a",
                target_par="p",
            )


# ── Script Execution ──────────────────────────────────────────────────

class TestServerScript:
    @pytest.mark.asyncio
    async def test_td_run_script_valid(self):
        from td_mcp.server import td_run_script
        mc = _mock_client()
        with _patch_client(mc):
            result = json.loads(await td_run_script("op('/project1').create('noisechop')"))
        assert result["executed"] is True

    @pytest.mark.asyncio
    async def test_td_run_script_blocked(self):
        from td_mcp.server import td_run_script
        result = json.loads(await td_run_script("import os"))
        assert result["executed"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_td_validate_script_valid(self):
        from td_mcp.server import td_validate_script
        result = json.loads(await td_validate_script("op('/project1')"))
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_td_validate_script_blocked(self):
        from td_mcp.server import td_validate_script
        result = json.loads(await td_validate_script("eval('bad')"))
        assert result["valid"] is False
