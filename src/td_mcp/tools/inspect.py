"""Inspection tools — list ops, trace signal flow, read CHOP channels."""

from __future__ import annotations

from td_mcp.td_client import TDClient


async def list_operators(client: TDClient, path: str = "/") -> dict:
    """List all operators in a network path with their types and families."""
    resp = await client.list_operators(path)
    return {"path": path, "operators": resp.data}


async def get_operator_detail(client: TDClient, path: str) -> dict:
    """Get full details of a single operator (params, connections, flags)."""
    resp = await client.get_operator(path)
    return {"operator": resp.data}


async def trace_signal_flow(client: TDClient, path: str = "/") -> dict:
    """Trace the full signal flow graph — who feeds whom."""
    resp = await client.get_connections(path)
    return {"path": path, "connections": resp.data}


async def get_network_topology(client: TDClient, path: str = "/") -> dict:
    """Full network analysis: ops, connections, sub-networks."""
    resp = await client.analyze_network(path)
    return {"network": resp.data}


async def read_chop_channels(client: TDClient, chop_path: str) -> dict:
    """Read channel names and current values from a CHOP."""
    channels = await client.get_chop_channels(chop_path)
    values = await client.get_chop_values(chop_path)
    return {
        "chop": chop_path,
        "channels": channels.data,
        "values": values.data,
    }


async def read_parameter(client: TDClient, op_path: str, par_name: str) -> dict:
    """Read a single parameter value from an operator."""
    resp = await client.get_par(op_path, par_name)
    return {"op": op_path, "parameter": par_name, "value": resp.data}
