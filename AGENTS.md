# AGENTS.md — td-mcp

## What this repo is

An MCP server plus a web dashboard for **TouchDesigner**. Claude Code (or any MCP client)
talks stdio to this server, which talks HTTP to a **WebServer DAT** inside a running TD project
on port `9981`; a FastAPI dashboard on `:8080` exposes the same tooling in a browser. 22 MCP
tools across four groups — inspect (list ops, trace signal flow, read CHOPs, read/set params),
optimize (cook-time stats, hotspots, unused ops), cleanup (find bypassed/dead ops, delete with
dry-run default, validate network) and templates (5 built-in CHOP recipes plus a DAW mapping
generator for OSC/MIDI CC). Every script that reaches TD goes through `src/td_mcp/safety.py` first.

## Layout (real paths)

```
pyproject.toml                    Hatchling package; scripts td-mcp and td-mcp-web; pytest config
src/td_mcp/server.py              FastMCP stdio server — the 22 tools
src/td_mcp/web.py                 FastAPI + htmx dashboard (main() runs uvicorn on :8080)
src/td_mcp/td_client.py           Async httpx client to the TD WebServer DAT; never raises
src/td_mcp/safety.py              The script validator (blocks imports, eval/exec, dunders, obfuscation)
src/td_mcp/models.py              Pydantic models
src/td_mcp/tools/inspect.py       List ops, trace signal flow, read CHOPs and params
src/td_mcp/tools/optimize.py      Cook-time hotspots, unused/dead-end ops, suggestions
src/td_mcp/tools/cleanup.py       Dead/bypassed ops, delete_operator, cleanup_dead_ops, validation
src/td_mcp/tools/templates.py     5 CHOP recipes + the DAW mapping generator
td/webserver_callbacks.py         Drop-in for TD's WebServer DAT onHTTPRequest callback
tests/test_models.py, test_safety.py, test_server.py, test_td_client.py, test_tools.py
```

## How to build / run / test

Requires Python 3.10+.

```bash
pip install -e ".[dev]"
pytest                                    # asyncio_mode=auto, testpaths=["tests"] (26 tests)

td-mcp                                    # MCP server over stdio
td-mcp-web                                # dashboard at http://localhost:8080
uvicorn td_mcp.web:app --port 8080 --app-dir src   # same dashboard, run directly
```

Client config for the stdio server:

```json
{
  "mcpServers": { "td-mcp": { "command": "td-mcp", "args": [] } }
}
```

On the TouchDesigner machine: create a **WebServer DAT**, set its **Port** to `9981`, paste
`td/webserver_callbacks.py` into the DAT's callbacks, toggle **Active** on. Nothing else
connects until that DAT is live. There is no CI in this repo.

## Conventions observed in the code

- **`src/td_mcp/safety.py` is the only thing between an LLM and code execution inside TD.** Every script
  is parsed with `ast` against `BLOCKED_IMPORTS`, `BLOCKED_CALLS` and `BLOCKED_ATTRS`, plus a
  regex pass for obfuscation (`\xNN`, `\uNNNN`, `\NNN`, `chr`, `ord`, string-built
  `__import__`), and a 10,000-character cap. `run` is blocked because it is exec in TD.
- **TD operator paths are validated** with `TD_PATH_RE` before being interpolated anywhere.
- `TDClient.request` **never raises**: connection errors and timeouts come back as
  `TDResponse(status="error", ...)`. Keep that contract — the tools rely on it.
- The web dashboard is hand-rolled htmx against FastAPI, with the markup built in `web.py`;
  there is no template directory or JS build step.
- Tests are pytest with `asyncio_mode = "auto"`, restricted to `tests/`. No `__init__.py`
  packages involved beyond the `td_mcp` ones.

## Gotchas and do-not-touch

- **Do not weaken the validator.** Loosening the blocked sets, raising the length cap, or dropping
  the regex fallback turns an "inspect my patch" tool into arbitrary code execution on the TD
  machine. New legitimate needs get an allowlist entry, not a removed block.
- **The dashboard binds `0.0.0.0:8080`.** `main()` in `src/td_mcp/web.py` runs
  `uvicorn.run(app, host="0.0.0.0", port=8080)`, so the dashboard is reachable from the whole
  LAN. `src/td_mcp/web.py` has no authentication — do not widen the bind, and do not put
  anything sensitive behind it.
- **Live-system risk.** Everything here drives a running TouchDesigner project that someone may
  be performing with. `delete_operator` and `cleanup_dead_ops` destroy ops: `cleanup_dead_ops`
  defaults to `dry_run=True` — never flip that default, and always run the dry run before
  deleting. It is a DAW/visual rig on the other side, not a sandbox.
- The TD-side half of the contract is `td/webserver_callbacks.py`, which is **copied by hand**
  into the DAT. Editing it in the repo does nothing until it is re-pasted into the project —
  say so when changing the routes.
- The MCP server's connection target is the WebServer DAT on port `9981`; the dashboard's own
  port is `8080`. Do not conflate them.
- `.env` is gitignored and there are no secrets in the repo. Keep it that way; tokens for any
  future provider belong in the environment, not in `td/webserver_callbacks.py`.
- The README's tool count (22) and test count are user-facing claims; update them when the
  counts change.

## Definition of done

- Code change: `pytest` passes, and the affected tool was exercised against a live TD WebServer
  DAT if the change touches the HTTP contract, the routes or an op mutation.
- Safety change: `tests/test_safety.py` covers the new case, both in the block direction and —
  where relevant — in the allow direction.
- Template or recipe change: the recipe still appears in the dashboard's recipe browser and its
  preview renders.
- No secrets, no weakened blocklist, no `dry_run` default flipped, no new port exposure.
- If TouchDesigner was not running, say the live step is untested rather than implying the
  tools were exercised — the unit tests mock the HTTP layer and prove nothing about TD.
