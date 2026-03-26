"""Template & recipe tools — CHOP chains, DAW mappings, presets."""

from __future__ import annotations

import json

from td_mcp.td_client import TDClient
from td_mcp.models import CHOPRecipe, DAWMapping
from td_mcp.safety import validate_td_script

# Built-in CHOP recipes
BUILTIN_RECIPES: dict[str, CHOPRecipe] = {
    "audio_reactive_basic": CHOPRecipe(
        name="audio_reactive_basic",
        description="Audio input → analyze → filter → output. Basic audio-reactive chain.",
        category="audio_reactive",
        operators=[
            {"type": "audioDeviceIn", "params": {}},
            {"type": "analyzeChop", "params": {"function": "rms"}},
            {"type": "lagChop", "params": {"lag1": 0.2, "lag2": 0.1}},
            {"type": "mathChop", "params": {"gain": 1.0, "range1": 0.0, "range2": 1.0}},
            {"type": "nullChop", "params": {}},
        ],
        connections=[(0, 1), (1, 2), (2, 3), (3, 4)],
    ),
    "audio_fft_bands": CHOPRecipe(
        name="audio_fft_bands",
        description="Audio → FFT → split into low/mid/high bands for reactive visuals.",
        category="audio_reactive",
        operators=[
            {"type": "audioDeviceIn", "params": {}},
            {"type": "audioSpectrumChop", "params": {}},
            {"type": "selectChop", "params": {"channames": "chan1[0-10]"}},   # low
            {"type": "selectChop", "params": {"channames": "chan1[11-50]"}},  # mid
            {"type": "selectChop", "params": {"channames": "chan1[51-]"}},    # high
            {"type": "analyzeChop", "params": {"function": "average"}},       # avg low
            {"type": "analyzeChop", "params": {"function": "average"}},       # avg mid
            {"type": "analyzeChop", "params": {"function": "average"}},       # avg high
            {"type": "mergeChop", "params": {}},
            {"type": "renameChop", "params": {"renameto": "low mid high"}},
        ],
        connections=[(0, 1), (1, 2), (1, 3), (1, 4), (2, 5), (3, 6), (4, 7), (5, 8), (6, 8), (7, 8), (8, 9)],
    ),
    "lfo_modulator": CHOPRecipe(
        name="lfo_modulator",
        description="LFO with controllable speed, shape, and range for parameter modulation.",
        category="lfo",
        operators=[
            {"type": "lfoChop", "params": {"frequency": 1.0, "type": "sin"}},
            {"type": "mathChop", "params": {"fromrange1": -1, "fromrange2": 1, "torange1": 0, "torange2": 1}},
            {"type": "lagChop", "params": {"lag1": 0.05}},
            {"type": "nullChop", "params": {}},
        ],
        connections=[(0, 1), (1, 2), (2, 3)],
    ),
    "midi_cc_mapper": CHOPRecipe(
        name="midi_cc_mapper",
        description="MIDI CC input → smooth → range map → output. For DAW controller mapping.",
        category="mapping",
        operators=[
            {"type": "midiinChop", "params": {}},
            {"type": "selectChop", "params": {"channames": "ch1cc1"}},
            {"type": "lagChop", "params": {"lag1": 0.1}},
            {"type": "mathChop", "params": {"fromrange1": 0, "fromrange2": 127, "torange1": 0, "torange2": 1}},
            {"type": "nullChop", "params": {}},
        ],
        connections=[(0, 1), (1, 2), (2, 3), (3, 4)],
    ),
    "osc_receiver": CHOPRecipe(
        name="osc_receiver",
        description="OSC input for DAW sync — receives from Bitwig/Ableton on configurable port.",
        category="mapping",
        operators=[
            {"type": "oscinChop", "params": {"port": 9000}},
            {"type": "selectChop", "params": {}},
            {"type": "lagChop", "params": {"lag1": 0.05}},
            {"type": "nullChop", "params": {}},
        ],
        connections=[(0, 1), (1, 2), (2, 3)],
    ),
}


def list_recipes(category: str | None = None) -> dict:
    """List available CHOP recipes, optionally filtered by category."""
    recipes = BUILTIN_RECIPES.values()
    if category:
        recipes = [r for r in recipes if r.category == category]
    else:
        recipes = list(recipes)
    return {
        "recipes": [
            {"name": r.name, "description": r.description, "category": r.category}
            for r in recipes
        ],
        "count": len(recipes),
    }


def get_recipe(name: str) -> dict:
    """Get full recipe details including operator chain and connections."""
    recipe = BUILTIN_RECIPES.get(name)
    if not recipe:
        return {"error": f"Recipe '{name}' not found", "available": list(BUILTIN_RECIPES.keys())}
    return recipe.model_dump()


def recipe_to_script(name: str, network_path: str = "/project1") -> dict:
    """Generate a TD Python script that builds the recipe's operator chain."""
    from td_mcp.safety import validate_td_path
    path_ok, path_reason = validate_td_path(network_path)
    if not path_ok:
        return {"error": f"Invalid network path: {path_reason}"}

    recipe = BUILTIN_RECIPES.get(name)
    if not recipe:
        return {"error": f"Recipe '{name}' not found"}

    lines = [
        f"# Auto-generated: {recipe.name}",
        f"# {recipe.description}",
        f"n = op('{network_path}')",
        "",
    ]

    var_names: list[str] = []
    for i, op_def in enumerate(recipe.operators):
        var = f"op{i}"
        var_names.append(var)
        op_type = op_def["type"]
        lines.append(f"{var} = n.create({op_type!r})")
        for par_name, par_val in op_def.get("params", {}).items():
            lines.append(f"{var}.par.{par_name} = {par_val!r}")
        lines.append(f"{var}.nodeY = {i * -150}")
        lines.append("")

    target_input_counts: dict[int, int] = {}
    for src_idx, tgt_idx in recipe.connections:
        if src_idx >= len(var_names) or tgt_idx >= len(var_names):
            return {"error": f"Recipe '{name}' has invalid connection index ({src_idx}->{tgt_idx}), only {len(var_names)} operators"}
        src = var_names[src_idx]
        tgt = var_names[tgt_idx]
        input_idx = target_input_counts.get(tgt_idx, 0)
        lines.append(f"{tgt}.inputConnectors[{input_idx}].connect({src})")
        target_input_counts[tgt_idx] = input_idx + 1

    script = "\n".join(lines)

    is_safe, reason = validate_td_script(script)
    if not is_safe:
        return {"error": f"Generated script failed validation: {reason}"}

    return {"script": script, "recipe": name, "network": network_path}


async def apply_recipe(client: TDClient, name: str, network_path: str = "/project1") -> dict:
    """Generate and execute a recipe's script in TD."""
    result = recipe_to_script(name, network_path)
    if "error" in result:
        return result

    resp = await client.run_script(result["script"])
    return {"applied": True, "recipe": name, "network": network_path, "response": resp.data}


def create_daw_mapping_script(mapping: DAWMapping) -> dict:
    """Generate a TD script that sets up a DAW→TD parameter mapping."""
    for field_name, field_val in [("target_op", mapping.target_op), ("target_par", mapping.target_par),
                                   ("source_channel", mapping.source_channel)]:
        if "'" in field_val or "\\" in field_val:
            return {"error": f"{field_name} contains invalid characters"}

    if mapping.source_type == "osc":
        script = f"""
# DAW Mapping: OSC {mapping.source_channel} -> {mapping.target_op}.{mapping.target_par}
osc = op('{mapping.target_op}').parent().create('oscinChop')
osc.par.port = 9000
sel = op('{mapping.target_op}').parent().create('selectChop')
sel.par.channames = '{mapping.source_channel}'
sel.inputConnectors[0].connect(osc)
math = op('{mapping.target_op}').parent().create('mathChop')
math.par.fromrange1 = {mapping.range_min}
math.par.fromrange2 = {mapping.range_max}
math.par.torange1 = 0
math.par.torange2 = 1
math.inputConnectors[0].connect(sel)
# Bind: op('{mapping.target_op}').par.{mapping.target_par}.expr = "op('{{0}}')[0]".format(math.path)
""".strip()
    elif mapping.source_type == "midi_cc":
        script = f"""
# DAW Mapping: MIDI CC {mapping.source_channel} -> {mapping.target_op}.{mapping.target_par}
midi = op('{mapping.target_op}').parent().create('midiinChop')
sel = op('{mapping.target_op}').parent().create('selectChop')
sel.par.channames = 'ch1cc{mapping.source_channel}'
sel.inputConnectors[0].connect(midi)
math = op('{mapping.target_op}').parent().create('mathChop')
math.par.fromrange1 = 0
math.par.fromrange2 = 127
math.par.torange1 = {mapping.range_min}
math.par.torange2 = {mapping.range_max}
math.inputConnectors[0].connect(sel)
""".strip()
    else:
        return {"error": f"Unsupported source type: {mapping.source_type}"}

    is_safe, reason = validate_td_script(script)
    if not is_safe:
        return {"error": f"Script failed validation: {reason}"}

    return {"script": script, "mapping": mapping.model_dump()}
