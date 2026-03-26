"""Cleanup tools — remove dead ops, fix bypassed nodes, validate network."""

from __future__ import annotations

from td_mcp.td_client import TDClient
from td_mcp.tools.optimize import find_unused_operators
from td_mcp.safety import validate_td_script


async def list_bypassed_operators(client: TDClient, path: str = "/") -> dict:
    """Find all bypassed operators in a network."""
    network = await client.analyze_network(path)
    data = network.data if isinstance(network.data, dict) else {}
    ops = data.get("operators", [])

    bypassed = [
        op.get("path")
        for op in ops
        if op.get("flags", {}).get("bypass", False)
    ]
    return {"bypassed": bypassed, "count": len(bypassed)}


async def delete_operator(client: TDClient, op_path: str) -> dict:
    """Delete a single operator (generates validated script)."""
    from td_mcp.safety import validate_td_path
    path_ok, path_reason = validate_td_path(op_path)
    if not path_ok:
        return {"error": f"Invalid operator path: {path_reason}", "deleted": False}

    script = f"op('{op_path}').destroy()"
    is_safe, reason = validate_td_script(script)
    if not is_safe:
        return {"error": f"Script rejected: {reason}", "deleted": False}

    resp = await client.run_script(script)
    return {"deleted": True, "path": op_path, "response": resp.data}


async def cleanup_dead_ops(client: TDClient, path: str = "/", dry_run: bool = True) -> dict:
    """Remove isolated/dead-end operators. Dry-run by default."""
    unused = await find_unused_operators(client, path)
    targets = unused["isolated"]

    if dry_run:
        return {
            "dry_run": True,
            "would_delete": targets,
            "count": len(targets),
        }

    deleted: list[str] = []
    errors: list[str] = []
    for op_path in targets:
        result = await delete_operator(client, op_path)
        if result.get("deleted"):
            deleted.append(op_path)
        else:
            errors.append(f"{op_path}: {result.get('error', 'unknown')}")

    return {"deleted": deleted, "errors": errors, "count": len(deleted)}


async def validate_network(client: TDClient, path: str = "/") -> dict:
    """Run a health check on a network — errors, warnings, suggestions."""
    network = await client.analyze_network(path)
    data = network.data if isinstance(network.data, dict) else {}
    ops = data.get("operators", [])
    connections = data.get("connections", [])

    issues: list[dict] = []

    # Check for operators with errors
    for op in ops:
        if op.get("error"):
            issues.append({
                "level": "error",
                "op": op.get("path"),
                "message": op.get("error"),
            })

    # Check for unconnected inputs on non-generator ops
    generators = {"noisechop", "lfochop", "constantchop", "patternchop",
                  "audiodevin", "audiofilein", "moviefilein", "noisetop"}
    target_ops = {c.get("target_op") for c in connections}
    for op in ops:
        op_path = op.get("path", "")
        op_type = op.get("op_type", "")
        if op_path not in target_ops and op_type not in generators:
            issues.append({
                "level": "warning",
                "op": op_path,
                "message": f"No input connections (type: {op_type})",
            })

    return {
        "path": path,
        "total_ops": len(ops),
        "total_connections": len(connections),
        "issues": issues,
        "issue_count": len(issues),
    }
