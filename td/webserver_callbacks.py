"""TouchDesigner WebServer DAT Callbacks — drop this into your TD project.

SETUP:
1. Create a WebServer DAT in your project (e.g. /project1/webserver1)
2. Set Port to 9981
3. Set this file as the DAT's callbacks script
4. Toggle the WebServer DAT's Active parameter ON

The MCP server (running outside TD) talks to this via HTTP.
"""

import json
import traceback


def onHTTPRequest(webServerDAT, request, response):
    """Handle incoming HTTP requests from the MCP server."""
    uri = request['uri']
    method = request['method']

    try:
        body = json.loads(request.get('data', '{}')) if request.get('data') else {}
    except json.JSONDecodeError:
        body = {}

    try:
        result = _route(uri, method, body)
        response['statusCode'] = 200
        response['statusReason'] = 'OK'
        response['data'] = json.dumps(result)
    except Exception as e:
        response['statusCode'] = 500
        response['statusReason'] = 'Internal Server Error'
        response['data'] = json.dumps({
            'status': 'error',
            'error': str(e),
            'traceback': traceback.format_exc(),
        })

    response['content-type'] = 'application/json'
    return response


def _route(uri: str, method: str, body: dict) -> dict:
    """Route requests to handler functions."""
    routes = {
        '/ping':              _ping,
        '/ops/list':          _ops_list,
        '/ops/get':           _ops_get,
        '/ops/connections':   _ops_connections,
        '/network/analyze':   _network_analyze,
        '/par/get':           _par_get,
        '/par/set':           _par_set,
        '/script/run':        _script_run,
        '/perf/stats':        _perf_stats,
        '/chop/channels':     _chop_channels,
        '/chop/values':       _chop_values,
    }

    handler = routes.get(uri)
    if handler is None:
        return {'status': 'error', 'error': f'Unknown endpoint: {uri}'}

    return handler(body)


# ── Handlers ────────────────────────────────────────────────────────────

def _ping(body: dict) -> dict:
    return {'status': 'ok', 'data': 'pong', 'version': '1.0.0'}


def _ops_list(body: dict) -> dict:
    path = body.get('path', '/')
    container = op(path)
    if container is None:
        return {'status': 'error', 'error': f'Path not found: {path}'}

    ops_list = []
    for child in container.children:
        ops_list.append({
            'path': child.path,
            'name': child.name,
            'family': child.family,
            'op_type': child.OPType,
        })

    return {'status': 'ok', 'data': ops_list}


def _ops_get(body: dict) -> dict:
    path = body.get('path', '')
    target = op(path)
    if target is None:
        return {'status': 'error', 'error': f'Operator not found: {path}'}

    params = []
    for p in target.pars():
        try:
            params.append({
                'name': p.name,
                'value': p.eval(),
                'default': p.default,
                'mode': str(p.mode),
            })
        except Exception:
            params.append({'name': p.name, 'value': str(p), 'default': None, 'mode': 'unknown'})

    inputs = [c.path for c in target.inputs]
    outputs = [c.path for c in target.outputs]

    flags = {}
    for flag_name in ['display', 'render', 'bypass', 'lock', 'viewer', 'expose']:
        try:
            flags[flag_name] = getattr(target, flag_name, False)
        except Exception:
            pass

    return {
        'status': 'ok',
        'data': {
            'path': target.path,
            'name': target.name,
            'family': target.family,
            'op_type': target.OPType,
            'parameters': params,
            'inputs': inputs,
            'outputs': outputs,
            'flags': flags,
            'cook_time': target.cookTime() if hasattr(target, 'cookTime') else None,
            'error': target.errors() if hasattr(target, 'errors') else None,
        }
    }


def _ops_connections(body: dict) -> dict:
    path = body.get('path', '/')
    container = op(path)
    if container is None:
        return {'status': 'error', 'error': f'Path not found: {path}'}

    connections = []
    for child in container.children:
        for i, inp in enumerate(child.inputs):
            if inp is not None:
                connections.append({
                    'source_op': inp.path,
                    'source_index': 0,
                    'target_op': child.path,
                    'target_index': i,
                })

    return {'status': 'ok', 'data': connections}


def _network_analyze(body: dict) -> dict:
    path = body.get('path', '/')
    container = op(path)
    if container is None:
        return {'status': 'error', 'error': f'Path not found: {path}'}

    operators = []
    connections = []
    sub_networks = []

    for child in container.children:
        op_data = {
            'path': child.path,
            'name': child.name,
            'family': child.family,
            'op_type': child.OPType,
            'flags': {},
            'error': None,
        }

        for flag_name in ['display', 'render', 'bypass', 'lock']:
            try:
                op_data['flags'][flag_name] = getattr(child, flag_name, False)
            except Exception:
                pass

        try:
            op_data['cook_time'] = child.cookTime()
        except Exception:
            op_data['cook_time'] = 0

        try:
            errs = child.errors()
            op_data['error'] = errs if errs else None
        except Exception:
            pass

        operators.append(op_data)

        # Collect connections
        for i, inp in enumerate(child.inputs):
            if inp is not None:
                connections.append({
                    'source_op': inp.path,
                    'target_op': child.path,
                    'source_index': 0,
                    'target_index': i,
                })

        # Track sub-networks (COMPs)
        if child.family == 'COMP' and len(child.children) > 0:
            sub_networks.append(child.path)

    return {
        'status': 'ok',
        'data': {
            'path': path,
            'operators': operators,
            'connections': connections,
            'sub_networks': sub_networks,
        }
    }


def _par_get(body: dict) -> dict:
    op_path = body.get('op', '')
    par_name = body.get('par', '')
    target = op(op_path)
    if target is None:
        return {'status': 'error', 'error': f'Operator not found: {op_path}'}

    try:
        val = getattr(target.par, par_name).eval()
        return {'status': 'ok', 'data': val}
    except AttributeError:
        return {'status': 'error', 'error': f'Parameter not found: {par_name}'}


def _par_set(body: dict) -> dict:
    op_path = body.get('op', '')
    par_name = body.get('par', '')
    value = body.get('value')
    target = op(op_path)
    if target is None:
        return {'status': 'error', 'error': f'Operator not found: {op_path}'}

    try:
        setattr(target.par, par_name, value)
        return {'status': 'ok', 'data': {'set': par_name, 'value': value}}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def _script_run(body: dict) -> dict:
    script = body.get('script', '')
    if not script:
        return {'status': 'error', 'error': 'No script provided'}

    try:
        result = run(script)
        output = str(result) if result else 'executed'
        # Truncate to prevent blowing up HTTP responses
        if len(output) > 65536:
            output = output[:65536] + '\n... [truncated]'
        return {'status': 'ok', 'data': output}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def _perf_stats(body: dict) -> dict:
    """Collect cook time stats for all operators in /project1."""
    container = op('/project1')
    if container is None:
        container = op('/')

    stats = []
    for child in _all_ops_recursive(container):
        try:
            cook = child.cookTime()
        except Exception:
            cook = 0

        stats.append({
            'path': child.path,
            'name': child.name,
            'family': child.family,
            'op_type': child.OPType,
            'cook_time': cook,
        })

    stats.sort(key=lambda x: x['cook_time'], reverse=True)
    return {'status': 'ok', 'data': stats}


def _chop_channels(body: dict) -> dict:
    path = body.get('path', '')
    target = op(path)
    if target is None:
        return {'status': 'error', 'error': f'CHOP not found: {path}'}
    if target.family != 'CHOP':
        return {'status': 'error', 'error': f'{path} is not a CHOP (family: {target.family})'}

    channels = []
    for chan in target.chans():
        channels.append({
            'name': chan.name,
            'num_samples': chan.numSamples,
        })

    return {'status': 'ok', 'data': channels}


def _chop_values(body: dict) -> dict:
    path = body.get('path', '')
    channel = body.get('channel', None)
    target = op(path)
    if target is None:
        return {'status': 'error', 'error': f'CHOP not found: {path}'}

    if channel:
        chan = target[channel]
        if chan is None:
            return {'status': 'error', 'error': f'Channel not found: {channel}'}
        return {'status': 'ok', 'data': {channel: chan.eval()}}

    values = {}
    for chan in target.chans():
        values[chan.name] = chan.eval()

    return {'status': 'ok', 'data': values}


# ── Helpers ─────────────────────────────────────────────────────────────

def _all_ops_recursive(container, depth=0, max_depth=5):
    """Recursively collect all operators up to max_depth."""
    if depth > max_depth:
        return
    for child in container.children:
        yield child
        if child.family == 'COMP' and len(child.children) > 0:
            yield from _all_ops_recursive(child, depth + 1, max_depth)
