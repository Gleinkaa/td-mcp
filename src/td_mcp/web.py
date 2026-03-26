"""TD-MCP Web Dashboard — FastAPI + htmx live monitoring UI."""

from __future__ import annotations

import html as _html
import json
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from td_mcp.td_client import TDClient
from td_mcp.tools import inspect, optimize, cleanup, templates
from td_mcp.safety import validate_td_script
from td_mcp.models import DAWMapping


def _esc(value: object) -> str:
    """HTML-escape a value for safe interpolation into templates."""
    return _html.escape(str(value))


app = FastAPI(title="TD-MCP Dashboard", docs_url="/api/docs")

# Global client — same pattern as MCP server
_client: TDClient | None = None


def get_client() -> TDClient:
    global _client
    if _client is None:
        _client = TDClient()
    return _client


@app.on_event("shutdown")
async def _shutdown_client() -> None:
    global _client
    if _client:
        await _client.close()
        _client = None


# ── HTML Shell ──────────────────────────────────────────────────────────

LAYOUT_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TD-MCP Dashboard</title>
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<style>
:root {
  --bg: #0d0d0d; --bg2: #1a1a1a; --bg3: #252525; --bg4: #333;
  --fg: #e0e0e0; --fg2: #888; --accent: #00e5ff; --accent2: #76ff03;
  --warn: #ffab00; --err: #ff1744; --border: #333;
  --font: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--bg); color: var(--fg); font-family: var(--font); font-size: 13px; line-height: 1.5; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

.shell { display: grid; grid-template-columns: 200px 1fr; grid-template-rows: 48px 1fr; min-height: 100vh; }
header { grid-column: 1/-1; background: var(--bg2); border-bottom: 1px solid var(--border);
  display: flex; align-items: center; padding: 0 20px; gap: 16px; }
header h1 { font-size: 15px; font-weight: 600; letter-spacing: 1px; }
header h1 span { color: var(--accent); }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--fg2); display: inline-block; }
.status-dot.ok { background: var(--accent2); box-shadow: 0 0 6px var(--accent2); }
.status-dot.err { background: var(--err); box-shadow: 0 0 6px var(--err); }

nav { background: var(--bg2); border-right: 1px solid var(--border); padding: 12px 0; }
nav a { display: block; padding: 8px 20px; color: var(--fg2); font-size: 12px; transition: all .15s; }
nav a:hover, nav a.active { color: var(--fg); background: var(--bg3); text-decoration: none; }
nav a.active { border-left: 2px solid var(--accent); color: var(--accent); }
nav .section { padding: 12px 20px 4px; font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px; color: var(--fg2); }

main { padding: 20px; overflow-y: auto; }
.card { background: var(--bg2); border: 1px solid var(--border); border-radius: 6px; padding: 16px; margin-bottom: 16px; }
.card h2 { font-size: 13px; font-weight: 600; margin-bottom: 12px; color: var(--accent); text-transform: uppercase; letter-spacing: 1px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }

.stat { text-align: center; padding: 12px; }
.stat .val { font-size: 28px; font-weight: 700; color: var(--accent); }
.stat .label { font-size: 10px; color: var(--fg2); text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

table { width: 100%; border-collapse: collapse; }
th { text-align: left; padding: 8px 12px; font-size: 10px; text-transform: uppercase; letter-spacing: 1px;
  color: var(--fg2); border-bottom: 1px solid var(--border); }
td { padding: 8px 12px; border-bottom: 1px solid var(--bg3); font-size: 12px; }
tr:hover td { background: var(--bg3); }

.badge { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 10px; font-weight: 600; }
.badge-chop { background: #1a3a2a; color: #4caf50; }
.badge-top { background: #3a2a1a; color: #ff9800; }
.badge-sop { background: #1a2a3a; color: #2196f3; }
.badge-dat { background: #3a1a3a; color: #9c27b0; }
.badge-comp { background: #2a2a2a; color: #9e9e9e; }
.badge-mat { background: #3a3a1a; color: #cddc39; }
.badge-warn { background: #3a2a00; color: var(--warn); }
.badge-err { background: #3a0000; color: var(--err); }
.badge-ok { background: #003a1a; color: var(--accent2); }

.bar { height: 6px; border-radius: 3px; background: var(--bg3); overflow: hidden; }
.bar-fill { height: 100%; border-radius: 3px; background: var(--accent); transition: width .3s; }
.bar-fill.hot { background: var(--err); }
.bar-fill.warm { background: var(--warn); }

btn, .btn { display: inline-block; padding: 6px 14px; border-radius: 4px; border: 1px solid var(--border);
  background: var(--bg3); color: var(--fg); font-family: var(--font); font-size: 12px; cursor: pointer; transition: all .15s; }
.btn:hover { background: var(--bg4); border-color: var(--accent); color: var(--accent); }
.btn-accent { background: rgba(0,229,255,.1); border-color: var(--accent); color: var(--accent); }
.btn-danger { border-color: var(--err); color: var(--err); }
.btn-danger:hover { background: rgba(255,23,68,.1); }

.code { background: var(--bg); border: 1px solid var(--border); border-radius: 4px; padding: 12px; overflow-x: auto; white-space: pre; font-size: 12px; }
.loading { color: var(--fg2); font-style: italic; }
.htmx-indicator { display: none; }
.htmx-request .htmx-indicator { display: inline; }
.htmx-request .htmx-hide { display: none; }

.recipe-card { background: var(--bg3); border: 1px solid var(--border); border-radius: 6px; padding: 14px; cursor: pointer; transition: all .15s; }
.recipe-card:hover { border-color: var(--accent); }
.recipe-card h3 { font-size: 13px; margin-bottom: 4px; }
.recipe-card p { font-size: 11px; color: var(--fg2); }
.recipe-card .cat { font-size: 10px; color: var(--accent); text-transform: uppercase; letter-spacing: 1px; }

input, select, textarea { background: var(--bg); border: 1px solid var(--border); border-radius: 4px;
  padding: 6px 10px; color: var(--fg); font-family: var(--font); font-size: 12px; }
input:focus, textarea:focus { outline: none; border-color: var(--accent); }
textarea { resize: vertical; width: 100%; }

.flash { padding: 10px 14px; border-radius: 4px; margin-bottom: 12px; font-size: 12px; }
.flash-ok { background: rgba(118,255,3,.1); border: 1px solid var(--accent2); color: var(--accent2); }
.flash-err { background: rgba(255,23,68,.1); border: 1px solid var(--err); color: var(--err); }

.tab-bar { display: flex; gap: 0; border-bottom: 1px solid var(--border); margin-bottom: 16px; }
.tab-bar a { padding: 8px 16px; color: var(--fg2); font-size: 12px; border-bottom: 2px solid transparent; }
.tab-bar a:hover { color: var(--fg); text-decoration: none; }
.tab-bar a.active { color: var(--accent); border-bottom-color: var(--accent); }
</style>
</head>
<body>
<div class="shell">
<header>
  <h1><span>TD</span>-MCP</h1>
  <div id="conn-status" hx-get="/api/ping" hx-trigger="load, every 5s" hx-swap="innerHTML">
    <span class="status-dot"></span> checking...
  </div>
</header>
<nav>
  <div class="section">Monitor</div>
  <a href="/" class="{nav_dashboard}">Dashboard</a>
  <a href="/ops" class="{nav_ops}">Operators</a>
  <a href="/perf" class="{nav_perf}">Performance</a>
  <div class="section">Tools</div>
  <a href="/recipes" class="{nav_recipes}">Recipes</a>
  <a href="/cleanup" class="{nav_cleanup}">Cleanup</a>
  <a href="/script" class="{nav_script}">Script Runner</a>
  <div class="section">Config</div>
  <a href="/connect" class="{nav_connect}">Connection</a>
</nav>
<main>
"""

LAYOUT_FOOT = """
</main>
</div>
</body>
</html>"""


def page(content: str, active: str = "") -> HTMLResponse:
    nav_map = {
        "dashboard": "nav_dashboard", "ops": "nav_ops", "perf": "nav_perf",
        "recipes": "nav_recipes", "cleanup": "nav_cleanup", "script": "nav_script",
        "connect": "nav_connect",
    }
    replacements = {v: "active" if k == active else "" for k, v in nav_map.items()}
    head = LAYOUT_HEAD
    for key, val in replacements.items():
        head = head.replace("{" + key + "}", val)
    return HTMLResponse(head + content + LAYOUT_FOOT)


# ── API Endpoints (htmx partials) ──────────────────────────────────────

@app.get("/api/ping")
async def api_ping():
    try:
        ok = await get_client().ping()
    except Exception:
        ok = False
    if ok:
        return HTMLResponse('<span class="status-dot ok"></span> connected')
    return HTMLResponse('<span class="status-dot err"></span> offline')


@app.get("/api/ops")
async def api_ops(path: str = "/"):
    try:
        result = await inspect.list_operators(get_client(), path)
        ops = result.get("operators", [])
        if not ops:
            return HTMLResponse('<p class="loading">No operators found</p>')
        rows = ""
        for o in (ops if isinstance(ops, list) else []):
            family = o.get("family", "?").upper()
            badge_cls = f"badge-{family.lower()}" if family.lower() in ("chop", "top", "sop", "dat", "comp", "mat") else ""
            rows += f"""<tr>
                <td><a href="/ops?path={_esc(o.get('path',''))}">{_esc(o.get('path','?'))}</a></td>
                <td>{_esc(o.get('name','?'))}</td>
                <td><span class="badge {badge_cls}">{_esc(family)}</span></td>
                <td>{_esc(o.get('op_type','?'))}</td>
            </tr>"""
        return HTMLResponse(f"""<table>
            <tr><th>Path</th><th>Name</th><th>Family</th><th>Type</th></tr>
            {rows}</table>""")
    except Exception as e:
        return HTMLResponse(f'<p class="flash flash-err">{_esc(e)}</p>')


@app.get("/api/hotspots")
async def api_hotspots(threshold: float = 1.0):
    try:
        result = await optimize.find_hotspots(get_client(), threshold)
        hotspots = result.get("hotspots", [])
        if not hotspots:
            return HTMLResponse('<p style="color:var(--accent2)">No hotspots above threshold</p>')
        max_cook = max(h.get("cook_time", 1) for h in hotspots)
        rows = ""
        for h in hotspots[:20]:
            cook = h.get("cook_time", 0)
            pct = min(cook / max_cook * 100, 100) if max_cook > 0 else 0
            bar_cls = "hot" if cook > 5 else "warm" if cook > 2 else ""
            rows += f"""<tr>
                <td>{_esc(h.get('path','?'))}</td>
                <td>{_esc(h.get('op_type','?'))}</td>
                <td style="width:40%"><div class="bar"><div class="bar-fill {bar_cls}" style="width:{pct}%"></div></div></td>
                <td style="text-align:right">{cook:.2f}ms</td>
            </tr>"""
        return HTMLResponse(f"""<table>
            <tr><th>Operator</th><th>Type</th><th>Cook Time</th><th></th></tr>
            {rows}</table>""")
    except Exception as e:
        return HTMLResponse(f'<p class="flash flash-err">{_esc(e)}</p>')


@app.get("/api/unused")
async def api_unused(path: str = "/"):
    try:
        result = await optimize.find_unused_operators(get_client(), path)
        isolated = result.get("isolated", [])
        dead_ends = result.get("dead_ends", [])
        html = ""
        if isolated:
            items = "".join(f"<li>{_esc(p)}</li>" for p in isolated)
            html += f'<h3 style="color:var(--warn);margin-bottom:8px">Isolated ({len(isolated)})</h3><ul style="list-style:none;padding:0">{items}</ul>'
        if dead_ends:
            items = "".join(f"<li>{_esc(p)}</li>" for p in dead_ends)
            html += f'<h3 style="color:var(--fg2);margin:12px 0 8px">Dead Ends ({len(dead_ends)})</h3><ul style="list-style:none;padding:0">{items}</ul>'
        if not html:
            html = '<p style="color:var(--accent2)">All operators connected</p>'
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f'<p class="flash flash-err">{_esc(e)}</p>')


@app.get("/api/validate")
async def api_validate(path: str = "/"):
    try:
        result = await cleanup.validate_network(get_client(), path)
        issues = result.get("issues", [])
        total = result.get("total_ops", 0)
        conns = result.get("total_connections", 0)
        html = f'<p style="margin-bottom:8px"><strong>{total}</strong> ops, <strong>{conns}</strong> connections</p>'
        if not issues:
            html += '<p class="flash flash-ok">Network healthy — no issues found</p>'
        else:
            for issue in issues:
                level = issue.get("level", "info")
                badge = "badge-err" if level == "error" else "badge-warn"
                html += f'<p style="margin:4px 0"><span class="badge {badge}">{_esc(level)}</span> <strong>{_esc(issue.get("op",""))}</strong> — {_esc(issue.get("message",""))}</p>'
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f'<p class="flash flash-err">{_esc(e)}</p>')


@app.get("/api/recipe-preview")
async def api_recipe_preview(name: str, network: str = "/project1"):
    result = templates.recipe_to_script(name, network)
    if "error" in result:
        return HTMLResponse(f'<p class="flash flash-err">{_esc(result["error"])}</p>')
    return HTMLResponse(f'<div class="code">{_esc(result["script"])}</div>')


@app.post("/api/recipe-apply")
async def api_recipe_apply(name: str = Form(...), network: str = Form("/project1")):
    try:
        result = await templates.apply_recipe(get_client(), name, network)
        if "error" in result:
            return HTMLResponse(f'<p class="flash flash-err">{_esc(result["error"])}</p>')
        return HTMLResponse(f'<p class="flash flash-ok">Applied recipe <strong>{_esc(name)}</strong> to {_esc(network)}</p>')
    except Exception as e:
        return HTMLResponse(f'<p class="flash flash-err">{_esc(e)}</p>')


@app.post("/api/cleanup-run")
async def api_cleanup_run(path: str = Form("/"), dry_run: bool = Form(True)):
    try:
        result = await cleanup.cleanup_dead_ops(get_client(), path, dry_run)
        if dry_run:
            targets = result.get("would_delete", [])
            if not targets:
                return HTMLResponse('<p class="flash flash-ok">Nothing to clean up</p>')
            items = "".join(f"<li>{_esc(p)}</li>" for p in targets)
            return HTMLResponse(f"""<p style="margin-bottom:8px">Would delete <strong>{len(targets)}</strong> isolated operators:</p>
                <ul style="list-style:none;padding:0">{items}</ul>
                <form hx-post="/api/cleanup-run" hx-target="#cleanup-result" style="margin-top:12px">
                    <input type="hidden" name="path" value="{_esc(path)}">
                    <input type="hidden" name="dry_run" value="false">
                    <button class="btn btn-danger" type="submit">Delete for real</button>
                </form>""")
        deleted = result.get("deleted", [])
        errors = result.get("errors", [])
        html = f'<p class="flash flash-ok">Deleted {len(deleted)} operators</p>'
        if errors:
            html += '<p class="flash flash-err">Errors: ' + ", ".join(errors) + "</p>"
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f'<p class="flash flash-err">{_esc(e)}</p>')


@app.post("/api/script-validate")
async def api_script_validate(script: str = Form(...)):
    is_safe, reason = validate_td_script(script)
    if is_safe:
        return HTMLResponse('<span class="badge badge-ok">SAFE</span> Script passed validation')
    return HTMLResponse(f'<span class="badge badge-err">BLOCKED</span> {_esc(reason)}')


@app.post("/api/script-run")
async def api_script_run(script: str = Form(...)):
    is_safe, reason = validate_td_script(script)
    if not is_safe:
        return HTMLResponse(f'<p class="flash flash-err">Rejected: {_esc(reason)}</p>')
    try:
        resp = await get_client().run_script(script)
        return HTMLResponse(f'<p class="flash flash-ok">Executed</p><div class="code">{_esc(json.dumps(resp.data, indent=2))}</div>')
    except Exception as e:
        return HTMLResponse(f'<p class="flash flash-err">{_esc(e)}</p>')


@app.post("/api/connect")
async def api_connect(host: str = Form("localhost"), port: int = Form(9981)):
    global _client
    if _client:
        try:
            await _client.close()
        except Exception:
            pass
    _client = TDClient(host=host, port=port)
    ok = await _client.ping()
    if ok:
        return HTMLResponse(f'<p class="flash flash-ok">Connected to {_esc(host)}:{port}</p>')
    return HTMLResponse(f'<p class="flash flash-err">Cannot reach {_esc(host)}:{port}</p>')


# ── Pages ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def page_dashboard():
    return page("""
    <h2 style="margin-bottom:16px">Dashboard</h2>
    <div class="grid2">
      <div class="card">
        <h2>Network Health</h2>
        <div hx-get="/api/validate?path=/" hx-trigger="load" hx-swap="innerHTML">
          <span class="loading">Loading...</span>
        </div>
      </div>
      <div class="card">
        <h2>Hotspots (>1ms)</h2>
        <div hx-get="/api/hotspots?threshold=1.0" hx-trigger="load" hx-swap="innerHTML">
          <span class="loading">Loading...</span>
        </div>
      </div>
    </div>
    <div class="card">
      <h2>Unused Operators</h2>
      <div hx-get="/api/unused?path=/" hx-trigger="load" hx-swap="innerHTML">
        <span class="loading">Loading...</span>
      </div>
    </div>
    """, active="dashboard")


@app.get("/ops", response_class=HTMLResponse)
async def page_ops(path: str = "/"):
    return page(f"""
    <h2 style="margin-bottom:16px">Operators</h2>
    <div class="card">
      <div style="display:flex;gap:8px;margin-bottom:12px">
        <input type="text" id="ops-path" value="{_esc(path)}" placeholder="Network path" style="flex:1">
        <button class="btn btn-accent" hx-get="/api/ops" hx-include="#ops-path" hx-vals='{{"path":""}}' hx-target="#ops-table"
          onclick="this.setAttribute('hx-vals', JSON.stringify({{path:document.getElementById('ops-path').value}})); htmx.trigger(this, 'click')">
          Browse
        </button>
      </div>
      <div id="ops-table" hx-get="/api/ops?path={_esc(path)}" hx-trigger="load" hx-swap="innerHTML">
        <span class="loading">Loading...</span>
      </div>
    </div>
    """, active="ops")


@app.get("/perf", response_class=HTMLResponse)
async def page_perf():
    return page("""
    <h2 style="margin-bottom:16px">Performance</h2>
    <div class="card">
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:12px">
        <label>Threshold (ms):</label>
        <input type="number" id="threshold" value="0.5" step="0.1" min="0" style="width:80px">
        <button class="btn btn-accent" hx-get="/api/hotspots" hx-include="#threshold"
          hx-vals='js:{"threshold": document.getElementById("threshold").value}'
          hx-target="#hotspot-list">Refresh</button>
        <span class="htmx-indicator loading">loading...</span>
      </div>
      <div id="hotspot-list" hx-get="/api/hotspots?threshold=0.5" hx-trigger="load" hx-swap="innerHTML">
        <span class="loading">Loading...</span>
      </div>
    </div>
    <div class="card">
      <h2>Optimization Suggestions</h2>
      <div id="suggestions" hx-get="/api/unused?path=/" hx-trigger="load" hx-swap="innerHTML">
        <span class="loading">Loading...</span>
      </div>
    </div>
    """, active="perf")


@app.get("/recipes", response_class=HTMLResponse)
async def page_recipes():
    recipe_list = templates.list_recipes()
    cards = ""
    for r in recipe_list.get("recipes", []):
        name = r["name"]
        cards += f"""<div class="recipe-card" hx-get="/api/recipe-preview?name={name}" hx-target="#recipe-preview" hx-swap="innerHTML">
            <div class="cat">{r['category']}</div>
            <h3>{name.replace('_',' ').title()}</h3>
            <p>{r['description']}</p>
        </div>"""

    return page(f"""
    <h2 style="margin-bottom:16px">CHOP Recipes</h2>
    <div class="grid2">
      <div>
        <div style="display:grid;gap:10px">
          {cards}
        </div>
      </div>
      <div>
        <div class="card">
          <h2>Preview</h2>
          <div id="recipe-preview">
            <p class="loading">Click a recipe to preview its script</p>
          </div>
        </div>
        <div class="card">
          <h2>Apply</h2>
          <form hx-post="/api/recipe-apply" hx-target="#apply-result">
            <div style="display:flex;gap:8px;margin-bottom:8px">
              <select name="name" style="flex:1">
                {"".join(f'<option value="{r["name"]}">{r["name"]}</option>' for r in recipe_list.get("recipes", []))}
              </select>
              <input name="network" value="/project1" style="width:120px">
              <button class="btn btn-accent" type="submit">Apply</button>
            </div>
          </form>
          <div id="apply-result"></div>
        </div>
      </div>
    </div>
    """, active="recipes")


@app.get("/cleanup", response_class=HTMLResponse)
async def page_cleanup():
    return page("""
    <h2 style="margin-bottom:16px">Network Cleanup</h2>
    <div class="grid2">
      <div class="card">
        <h2>Validate Network</h2>
        <div style="display:flex;gap:8px;margin-bottom:12px">
          <input type="text" id="val-path" value="/" style="flex:1" placeholder="Network path">
          <button class="btn btn-accent" hx-get="/api/validate" hx-include="#val-path"
            hx-vals='js:{"path": document.getElementById("val-path").value}'
            hx-target="#val-result">Check</button>
        </div>
        <div id="val-result" hx-get="/api/validate?path=/" hx-trigger="load" hx-swap="innerHTML">
          <span class="loading">Loading...</span>
        </div>
      </div>
      <div class="card">
        <h2>Cleanup Dead Operators</h2>
        <form hx-post="/api/cleanup-run" hx-target="#cleanup-result">
          <div style="display:flex;gap:8px;margin-bottom:12px">
            <input name="path" value="/" style="flex:1" placeholder="Network path">
            <input type="hidden" name="dry_run" value="true">
            <button class="btn btn-accent" type="submit">Dry Run</button>
          </div>
        </form>
        <div id="cleanup-result"></div>
      </div>
    </div>
    """, active="cleanup")


@app.get("/script", response_class=HTMLResponse)
async def page_script():
    return page("""
    <h2 style="margin-bottom:16px">Script Runner</h2>
    <div class="card">
      <h2>Execute TD Python</h2>
      <textarea id="script-input" name="script" rows="10" placeholder="# Write TD Python here&#10;n = op('/project1')&#10;print(n.children)"></textarea>
      <div style="display:flex;gap:8px;margin-top:10px">
        <button class="btn" hx-post="/api/script-validate" hx-include="#script-input"
          hx-vals='js:{"script": document.getElementById("script-input").value}'
          hx-target="#script-validation">Validate</button>
        <button class="btn btn-accent" hx-post="/api/script-run" hx-include="#script-input"
          hx-vals='js:{"script": document.getElementById("script-input").value}'
          hx-target="#script-result">Run</button>
        <span id="script-validation" style="line-height:32px;margin-left:8px"></span>
      </div>
      <div id="script-result" style="margin-top:12px"></div>
    </div>
    """, active="script")


@app.get("/connect", response_class=HTMLResponse)
async def page_connect():
    c = get_client()
    return page(f"""
    <h2 style="margin-bottom:16px">Connection Settings</h2>
    <div class="card" style="max-width:400px">
      <h2>TouchDesigner WebServer DAT</h2>
      <form hx-post="/api/connect" hx-target="#conn-result">
        <div style="margin-bottom:10px">
          <label style="display:block;margin-bottom:4px;color:var(--fg2)">Host</label>
          <input name="host" value="localhost" style="width:100%">
        </div>
        <div style="margin-bottom:12px">
          <label style="display:block;margin-bottom:4px;color:var(--fg2)">Port</label>
          <input name="port" type="number" value="9981" style="width:100%">
        </div>
        <button class="btn btn-accent" type="submit">Connect</button>
      </form>
      <div id="conn-result" style="margin-top:12px"></div>
    </div>
    <div class="card" style="max-width:400px;margin-top:16px">
      <h2>Current</h2>
      <p>Base URL: <code>{c.base_url}</code></p>
      <p>Timeout: <code>{c.timeout}s</code></p>
    </div>
    """, active="connect")


# ── Entry point ────────────────────────────────────────────────────────

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")


if __name__ == "__main__":
    main()
