# TD-MCP

MCP server + web dashboard for TouchDesigner. Inspect, optimize, and control TD patches from Claude Code or the browser.

```
Claude Code <--MCP(stdio)--> td-mcp server <--HTTP--> TD WebServer DAT (port 9981)
                                  |
                          Web Dashboard (:8080)
```

## Features

**22 MCP tools** across 4 groups:

| Group | Tools |
|-------|-------|
| **Inspect** | List ops, trace signal flow, read CHOP channels, read/set params |
| **Optimize** | Cook time stats, find hotspots, find unused ops, suggest fixes |
| **Cleanup** | Find bypassed ops, delete dead ops (dry-run default), validate network |
| **Templates** | 5 CHOP recipes, DAW mapping generator (OSC + MIDI CC) |

**Web dashboard** (FastAPI + htmx):
- Live connection status
- Network health overview
- Cook time hotspot visualization
- Recipe browser with script preview
- Cleanup tool with dry-run
- Script runner with safety validation

**Built-in CHOP recipes:**
- `audio_reactive_basic` -- audio in > RMS > lag > math > null
- `audio_fft_bands` -- FFT > split low/mid/high bands
- `lfo_modulator` -- LFO with range mapping
- `midi_cc_mapper` -- MIDI CC > smooth > range > output
- `osc_receiver` -- OSC input for Bitwig/Ableton sync

## Install

```bash
pip install -e ".[dev]"
```

Requires Python 3.10+.

## Usage

### MCP Server (for Claude Code)

```bash
td-mcp
```

Add to your Claude Code MCP config:

```json
{
  "mcpServers": {
    "td-mcp": {
      "command": "td-mcp",
      "args": []
    }
  }
}
```

### Web Dashboard

```bash
td-mcp-web
```

Opens at http://localhost:8080. Dark-themed, auto-polls TD status every 5s.

Or run directly:

```bash
uvicorn td_mcp.web:app --port 8080 --app-dir src
```

### Tests

```bash
pytest
```

26 tests covering client, server, tools, safety, models.

## TouchDesigner Setup

On the TD machine (Luci's side):

1. Create a **WebServer DAT** in your project
2. Set **Port** to `9981`
3. Paste the contents of `td/webserver_callbacks.py` into the DAT's callbacks
4. Toggle **Active** ON

That's it. The MCP server and web dashboard connect to this endpoint.

## Safety

All scripts executed in TD go through `safety.py` which blocks:
- File I/O, network, subprocess imports
- `eval`/`exec`/`compile`/`__import__`/`run`
- Dunder attribute access (`__class__`, `__globals__`, etc.)
- Encoding bypass attempts (hex/unicode/octal escapes, `chr`/`ord`)
- Max 10,000 chars per script

## Project Structure

```
td-mcp/
  src/td_mcp/
    server.py          # FastMCP server -- 22 tools via stdio
    web.py             # FastAPI web dashboard
    td_client.py       # Async HTTP client to TD WebServer DAT
    safety.py          # Script validator
    models.py          # Pydantic models
    tools/
      inspect.py       # List ops, trace signal flow, read CHOPs
      optimize.py      # Cook time hotspots, find unused/dead-end ops
      cleanup.py       # Delete dead ops (dry-run default), validate network
      templates.py     # 5 built-in CHOP recipes + DAW mapping generator
  td/
    webserver_callbacks.py  # Drop-in for TD's WebServer DAT
  tests/
    test_models.py
    test_safety.py
    test_server.py
    test_td_client.py
    test_tools.py
  pyproject.toml
```

## License

MIT
