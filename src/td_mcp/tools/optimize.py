"""Performance optimization tools — find hotspots, suggest improvements."""

from __future__ import annotations

from td_mcp.td_client import TDClient


async def get_cooking_stats(client: TDClient) -> dict:
    """Get cook times for all operators — sorted by cost."""
    resp = await client.get_cooking_stats()
    return {"stats": resp.data}


async def find_hotspots(client: TDClient, threshold_ms: float = 1.0) -> dict:
    """Find operators cooking above threshold (default 1ms)."""
    resp = await client.get_cooking_stats()
    stats = resp.data if isinstance(resp.data, list) else []
    hotspots = [op for op in stats if op.get("cook_time", 0) > threshold_ms]
    hotspots.sort(key=lambda x: x.get("cook_time", 0), reverse=True)
    return {
        "threshold_ms": threshold_ms,
        "hotspot_count": len(hotspots),
        "hotspots": hotspots,
    }


async def find_unused_operators(client: TDClient, path: str = "/") -> dict:
    """Find operators with no output connections (potential dead ends)."""
    network = await client.analyze_network(path)
    data = network.data if isinstance(network.data, dict) else {}
    ops = data.get("operators", [])
    connections = data.get("connections", [])

    connected_sources = {c.get("source_op") for c in connections if isinstance(c, dict)}
    connected_targets = {c.get("target_op") for c in connections if isinstance(c, dict)}
    all_ops = {op.get("path") for op in ops if isinstance(op, dict)}

    # Filter out None values that come from missing keys
    connected_sources.discard(None)
    connected_targets.discard(None)
    all_ops.discard(None)

    # Ops that are neither source nor target of any connection
    isolated = all_ops - connected_sources - connected_targets
    # Ops that receive input but output nowhere (dead ends)
    dead_ends = connected_targets - connected_sources

    return {
        "isolated": sorted(isolated),
        "dead_ends": sorted(dead_ends),
        "total_unused": len(isolated) + len(dead_ends),
    }


async def suggest_optimizations(client: TDClient, path: str = "/") -> dict:
    """Analyze network and suggest performance improvements."""
    hotspots = await find_hotspots(client, threshold_ms=0.5)
    unused = await find_unused_operators(client, path)

    suggestions: list[str] = []

    if hotspots["hotspot_count"] > 0:
        for op in hotspots["hotspots"][:5]:
            name = op.get("path", "unknown")
            cook = op.get("cook_time", 0)
            suggestions.append(f"Hotspot: {name} ({cook:.2f}ms) — consider lowering resolution or cook rate")

    if unused["total_unused"] > 0:
        suggestions.append(f"Found {unused['total_unused']} unused/dead-end operators — delete or bypass them")
        for op_path in unused["isolated"][:5]:
            suggestions.append(f"  Isolated: {op_path}")

    if not suggestions:
        suggestions.append("Network looks clean — no obvious bottlenecks found")

    return {"suggestions": suggestions}
