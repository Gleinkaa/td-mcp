"""TD-MCP Server — MCP server exposing TouchDesigner tools via WebServer DAT bridge."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from td_mcp.td_client import TDClient
from td_mcp.models import DAWMapping
from td_mcp.tools import inspect, optimize, cleanup, templates
from td_mcp.safety import validate_td_script

mcp = FastMCP(
    "td-mcp",
    description="TouchDesigner MCP server — patch inspection, optimization, CHOP recipes & DAW bridge",
)

# Global client — configured at startup
_client: TDClient | None = None


def get_client() -> TDClient:
    global _client
    if _client is None:
        _client = TDClient()
    return _client


# ── Connection ──────────────────────────────────────────────────────────

@mcp.tool()
async def td_ping() -> str:
    """Check if TouchDesigner is reachable via WebServer DAT."""
    reachable = await get_client().ping()
    return json.dumps({"reachable": reachable})


@mcp.tool()
async def td_connect(host: str = "localhost", port: int = 9981) -> str:
    """Connect to TouchDesigner WebServer DAT at given host:port."""
    global _client
    if _client:
        try:
            await _client.close()
        except Exception:
            pass
    _client = TDClient(host=host, port=port)
    reachable = await _client.ping()
    return json.dumps({"connected": reachable, "host": host, "port": port})


# ── Inspect ─────────────────────────────────────────────────────────────

@mcp.tool()
async def td_list_ops(path: str = "/") -> str:
    """List all operators in a TouchDesigner network path."""
    result = await inspect.list_operators(get_client(), path)
    return json.dumps(result)


@mcp.tool()
async def td_get_operator(path: str) -> str:
    """Get full details of a single operator (params, connections, flags)."""
    result = await inspect.get_operator_detail(get_client(), path)
    return json.dumps(result)


@mcp.tool()
async def td_trace_signal_flow(path: str = "/") -> str:
    """Trace the signal flow graph — which operators feed which."""
    result = await inspect.trace_signal_flow(get_client(), path)
    return json.dumps(result)


@mcp.tool()
async def td_network_topology(path: str = "/") -> str:
    """Get full network topology: operators, connections, sub-networks."""
    result = await inspect.get_network_topology(get_client(), path)
    return json.dumps(result)


@mcp.tool()
async def td_read_chop(chop_path: str) -> str:
    """Read channel names and current values from a CHOP operator."""
    result = await inspect.read_chop_channels(get_client(), chop_path)
    return json.dumps(result)


@mcp.tool()
async def td_read_par(op_path: str, par_name: str) -> str:
    """Read a parameter value from an operator."""
    result = await inspect.read_parameter(get_client(), op_path, par_name)
    return json.dumps(result)


@mcp.tool()
async def td_set_par(op_path: str, par_name: str, value: str) -> str:
    """Set a parameter value on an operator."""
    resp = await get_client().set_par(op_path, par_name, value)
    return json.dumps({"op": op_path, "par": par_name, "value": value, "response": resp.data})


# ── Optimize ────────────────────────────────────────────────────────────

@mcp.tool()
async def td_cooking_stats() -> str:
    """Get cook times for all operators, sorted by cost."""
    result = await optimize.get_cooking_stats(get_client())
    return json.dumps(result)


@mcp.tool()
async def td_find_hotspots(threshold_ms: float = 1.0) -> str:
    """Find operators cooking above threshold (default 1ms)."""
    result = await optimize.find_hotspots(get_client(), threshold_ms)
    return json.dumps(result)


@mcp.tool()
async def td_find_unused(path: str = "/") -> str:
    """Find disconnected/dead-end operators in the network."""
    result = await optimize.find_unused_operators(get_client(), path)
    return json.dumps(result)


@mcp.tool()
async def td_suggest_optimizations(path: str = "/") -> str:
    """Analyze network and suggest performance improvements."""
    result = await optimize.suggest_optimizations(get_client(), path)
    return json.dumps(result)


# ── Cleanup ─────────────────────────────────────────────────────────────

@mcp.tool()
async def td_list_bypassed(path: str = "/") -> str:
    """Find all bypassed operators in a network."""
    result = await cleanup.list_bypassed_operators(get_client(), path)
    return json.dumps(result)


@mcp.tool()
async def td_cleanup(path: str = "/", dry_run: bool = True) -> str:
    """Remove isolated/dead-end operators. Dry-run by default (set dry_run=false to actually delete)."""
    result = await cleanup.cleanup_dead_ops(get_client(), path, dry_run)
    return json.dumps(result)


@mcp.tool()
async def td_validate_network(path: str = "/") -> str:
    """Health check a network — find errors, warnings, and issues."""
    result = await cleanup.validate_network(get_client(), path)
    return json.dumps(result)


# ── Templates & Recipes ─────────────────────────────────────────────────

@mcp.tool()
async def td_list_recipes(category: str | None = None) -> str:
    """List available CHOP chain recipes. Optional filter: audio_reactive, lfo, mapping, filter."""
    result = templates.list_recipes(category)
    return json.dumps(result)


@mcp.tool()
async def td_get_recipe(name: str) -> str:
    """Get full recipe details — operator chain, params, and connections."""
    result = templates.get_recipe(name)
    return json.dumps(result)


@mcp.tool()
async def td_recipe_to_script(name: str, network_path: str = "/project1") -> str:
    """Generate a TD Python script for a recipe (preview before applying)."""
    result = templates.recipe_to_script(name, network_path)
    return json.dumps(result)


@mcp.tool()
async def td_apply_recipe(name: str, network_path: str = "/project1") -> str:
    """Apply a CHOP recipe — creates the operator chain in TD."""
    result = await templates.apply_recipe(get_client(), name, network_path)
    return json.dumps(result)


# ── DAW Bridge ──────────────────────────────────────────────────────────

@mcp.tool()
async def td_create_daw_mapping(
    source_type: str,
    source_channel: str,
    target_op: str,
    target_par: str,
    range_min: float = 0.0,
    range_max: float = 1.0,
) -> str:
    """Create a DAW→TD parameter mapping (OSC or MIDI CC).

    source_type: 'osc' or 'midi_cc'
    source_channel: OSC address (e.g. '/track/1/volume') or MIDI CC number (e.g. '1')
    target_op: TD operator path to control
    target_par: parameter name on that operator
    """
    mapping = DAWMapping(
        source_type=source_type,
        source_channel=source_channel,
        target_op=target_op,
        target_par=target_par,
        range_min=range_min,
        range_max=range_max,
    )
    result = templates.create_daw_mapping_script(mapping)
    return json.dumps(result)


# ── Safe Script Execution ───────────────────────────────────────────────

@mcp.tool()
async def td_run_script(script: str) -> str:
    """Execute a validated Python script inside TouchDesigner.

    The script is safety-checked before execution:
    - No file I/O, network, subprocess, or dangerous imports
    - No eval/exec chains or dunder attribute access
    - Max 10,000 chars
    """
    is_safe, reason = validate_td_script(script)
    if not is_safe:
        return json.dumps({"error": f"Script rejected: {reason}", "executed": False})

    resp = await get_client().run_script(script)
    return json.dumps({"executed": True, "response": resp.data})


@mcp.tool()
async def td_validate_script(script: str) -> str:
    """Validate a Python script without executing it. Returns safety analysis."""
    is_safe, reason = validate_td_script(script)
    return json.dumps({"valid": is_safe, "reason": reason})


# ── Entry point ─────────────────────────────────────────────────────────

def main():
    """Run the TD-MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
