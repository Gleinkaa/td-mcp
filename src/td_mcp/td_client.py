"""HTTP client for TouchDesigner WebServer DAT communication."""

from __future__ import annotations

import json as _json

import httpx
from pydantic import BaseModel


class TDResponse(BaseModel):
    """Response from TD WebServer DAT."""
    status: str
    data: dict | list | str | int | float | bool | None = None
    error: str | None = None


class TDClient:
    """Async HTTP client that talks to TD's WebServer DAT."""

    def __init__(self, host: str = "localhost", port: int = 9981, timeout: float = 10.0):
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def ping(self) -> bool:
        """Check if TD is reachable."""
        try:
            client = await self._get_client()
            resp = await client.get("/ping")
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def request(self, endpoint: str, method: str = "POST", **kwargs) -> TDResponse:
        """Send request to TD WebServer DAT. Never raises — returns error TDResponse on failure."""
        try:
            client = await self._get_client()
            resp = await client.request(method, endpoint, **kwargs)
            resp.raise_for_status()
        except httpx.ConnectError:
            return TDResponse(status="error", error="Cannot connect to TouchDesigner")
        except httpx.TimeoutException:
            return TDResponse(status="error", error="Request to TouchDesigner timed out")
        except httpx.HTTPStatusError as exc:
            return TDResponse(
                status="error",
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:500]}",
            )

        try:
            body = resp.json()
        except (_json.JSONDecodeError, ValueError):
            # TD returned non-JSON — wrap the raw text
            return TDResponse(status="ok", data=resp.text[:65536])

        if isinstance(body, dict):
            # Ensure the dict has a 'status' key before unpacking
            if "status" not in body:
                body["status"] = "ok"
            return TDResponse(**body)
        return TDResponse(status="ok", data=body)

    # -- Operator queries --

    async def list_operators(self, path: str = "/") -> TDResponse:
        """List all operators under a network path."""
        return await self.request("/ops/list", json={"path": path})

    async def get_operator(self, path: str) -> TDResponse:
        """Get operator details (type, parameters, connections)."""
        return await self.request("/ops/get", json={"path": path})

    async def get_connections(self, path: str = "/") -> TDResponse:
        """Get all wire connections in a network."""
        return await self.request("/ops/connections", json={"path": path})

    # -- Script execution --

    async def run_script(self, script: str) -> TDResponse:
        """Execute a Python script inside TD (use with caution — validate first)."""
        return await self.request("/script/run", json={"script": script})

    # -- Parameter control --

    async def get_par(self, op_path: str, par_name: str) -> TDResponse:
        """Get a parameter value."""
        return await self.request("/par/get", json={"op": op_path, "par": par_name})

    async def set_par(self, op_path: str, par_name: str, value: str | float | int) -> TDResponse:
        """Set a parameter value."""
        return await self.request("/par/set", json={"op": op_path, "par": par_name, "value": value})

    # -- Network analysis --

    async def analyze_network(self, path: str = "/") -> TDResponse:
        """Get full network topology for analysis."""
        return await self.request("/network/analyze", json={"path": path})

    async def get_cooking_stats(self) -> TDResponse:
        """Get performance/cooking stats for all operators."""
        return await self.request("/perf/stats", method="GET")

    # -- CHOP specifics --

    async def get_chop_channels(self, path: str) -> TDResponse:
        """Get channel names and sample counts from a CHOP."""
        return await self.request("/chop/channels", json={"path": path})

    async def get_chop_values(self, path: str, channel: str | None = None) -> TDResponse:
        """Get current values from a CHOP (optionally specific channel)."""
        payload: dict = {"path": path}
        if channel:
            payload["channel"] = channel
        return await self.request("/chop/values", json=payload)
