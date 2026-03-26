"""Tests for the Python script safety validator."""

import pytest
from td_mcp.safety import validate_td_script, validate_td_path


class TestValidScripts:
    def test_simple_op_create(self):
        script = "n = op('/project1')\nop1 = n.create('noisechop')"
        is_safe, reason = validate_td_script(script)
        assert is_safe, reason

    def test_parameter_set(self):
        script = "op('/project1/noise1').par.roughness = 0.5"
        is_safe, reason = validate_td_script(script)
        assert is_safe, reason

    def test_connect_operators(self):
        script = "op('/project1/math1').inputConnectors[0].connect(op('/project1/noise1'))"
        is_safe, reason = validate_td_script(script)
        assert is_safe, reason

    def test_destroy_operator(self):
        script = "op('/project1/null1').destroy()"
        is_safe, reason = validate_td_script(script)
        assert is_safe, reason

    def test_td_globals(self):
        script = "print(me.path)\nprint(absTime.frame)"
        is_safe, reason = validate_td_script(script)
        assert is_safe, reason


class TestBlockedScripts:
    def test_empty(self):
        is_safe, _ = validate_td_script("")
        assert not is_safe

    def test_import_os(self):
        is_safe, reason = validate_td_script("import os")
        assert not is_safe
        assert "os" in reason

    def test_import_subprocess(self):
        is_safe, _ = validate_td_script("import subprocess")
        assert not is_safe

    def test_import_from_os(self):
        is_safe, _ = validate_td_script("from os.path import join")
        assert not is_safe

    def test_import_socket(self):
        is_safe, _ = validate_td_script("import socket")
        assert not is_safe

    def test_import_pickle(self):
        is_safe, _ = validate_td_script("import pickle")
        assert not is_safe

    def test_import_ctypes(self):
        is_safe, _ = validate_td_script("import ctypes")
        assert not is_safe

    def test_import_importlib(self):
        is_safe, _ = validate_td_script("import importlib")
        assert not is_safe

    def test_from_http(self):
        is_safe, _ = validate_td_script("from http.client import HTTPConnection")
        assert not is_safe

    def test_eval_call(self):
        is_safe, _ = validate_td_script("eval('print(1)')")
        assert not is_safe

    def test_exec_call(self):
        is_safe, _ = validate_td_script("exec('import os')")
        assert not is_safe

    def test_compile_call(self):
        is_safe, _ = validate_td_script("compile('print(1)', '<string>', 'exec')")
        assert not is_safe

    def test_open_file(self):
        is_safe, _ = validate_td_script("f = open('/etc/passwd')")
        assert not is_safe

    def test_dunder_class(self):
        is_safe, _ = validate_td_script("x = ''.__class__.__bases__")
        assert not is_safe

    def test_dunder_import(self):
        is_safe, _ = validate_td_script("__import__('os')")
        assert not is_safe

    def test_dunder_dict(self):
        is_safe, _ = validate_td_script("x.__dict__")
        assert not is_safe

    def test_dunder_mro(self):
        is_safe, _ = validate_td_script("x.__mro__")
        assert not is_safe

    def test_too_long(self):
        script = "x = 1\n" * 5001
        is_safe, reason = validate_td_script(script)
        assert not is_safe
        assert "too long" in reason.lower()

    def test_syntax_error(self):
        is_safe, reason = validate_td_script("def (broken")
        assert not is_safe
        assert "syntax" in reason.lower()

    def test_getattr_dunder(self):
        is_safe, _ = validate_td_script("getattr(x, '__globals__')")
        assert not is_safe

    def test_globals_call(self):
        is_safe, _ = validate_td_script("globals()")
        assert not is_safe

    def test_locals_call(self):
        is_safe, _ = validate_td_script("locals()")
        assert not is_safe

    def test_vars_call(self):
        is_safe, _ = validate_td_script("vars()")
        assert not is_safe

    def test_setattr_call(self):
        is_safe, _ = validate_td_script("setattr(x, 'y', 1)")
        assert not is_safe

    def test_delattr_call(self):
        is_safe, _ = validate_td_script("delattr(x, 'y')")
        assert not is_safe

    def test_input_call(self):
        is_safe, _ = validate_td_script("input('hello')")
        assert not is_safe

    def test_breakpoint_call(self):
        is_safe, _ = validate_td_script("breakpoint()")
        assert not is_safe

    # -- run() is now blocked (equivalent to exec in TD) --
    def test_run_call_blocked(self):
        is_safe, reason = validate_td_script("run('print(1)')")
        assert not is_safe
        assert "run" in reason

    def test_run_injection(self):
        """run() with __import__ inside should be blocked."""
        is_safe, _ = validate_td_script("run(\"__import__('os').system('whoami')\")")
        assert not is_safe

    # -- type() blocked to prevent class-building exploits --
    def test_type_call_blocked(self):
        is_safe, _ = validate_td_script("type('X', (), {'__init__': lambda self: None})()")
        assert not is_safe

    # -- Attribute-based blocked calls --
    def test_attribute_eval(self):
        is_safe, _ = validate_td_script("x.eval('code')")
        assert not is_safe

    def test_attribute_exec(self):
        is_safe, _ = validate_td_script("x.exec('code')")
        assert not is_safe


class TestEncodingBypass:
    """Test that encoding-based evasion attempts are caught."""

    def test_hex_escape(self):
        is_safe, reason = validate_td_script(r"x = '\x6f\x73'")
        assert not is_safe
        assert "Hex escape" in reason

    def test_unicode_escape(self):
        is_safe, reason = validate_td_script(r"x = '\u0065val'")
        assert not is_safe
        assert "Unicode escape" in reason

    def test_octal_escape(self):
        is_safe, reason = validate_td_script(r"x = '\157\163'")
        assert not is_safe
        assert "Octal escape" in reason

    def test_chr_call(self):
        is_safe, reason = validate_td_script("x = chr(111) + chr(115)")
        assert not is_safe
        assert "chr()" in reason

    def test_ord_call(self):
        is_safe, reason = validate_td_script("x = ord('a')")
        assert not is_safe
        assert "ord()" in reason


class TestPathValidation:
    """Test validate_td_path for injection prevention."""

    def test_valid_path(self):
        ok, _ = validate_td_path("/project1/noise1")
        assert ok

    def test_valid_nested_path(self):
        ok, _ = validate_td_path("/project1/comp1/noise1")
        assert ok

    def test_valid_with_underscores(self):
        ok, _ = validate_td_path("/project1/my_operator_2")
        assert ok

    def test_empty_path(self):
        ok, _ = validate_td_path("")
        assert not ok

    def test_injection_single_quote(self):
        ok, _ = validate_td_path("'); import os; op('")
        assert not ok

    def test_injection_double_quote(self):
        ok, _ = validate_td_path('"); import os; op("')
        assert not ok

    def test_injection_semicolon(self):
        ok, _ = validate_td_path("/project1; import os")
        assert not ok

    def test_injection_parentheses(self):
        ok, _ = validate_td_path("/project1').destroy(); op('")
        assert not ok

    def test_spaces_rejected(self):
        ok, _ = validate_td_path("/project1/my op")
        assert not ok


class TestTemplateScripts:
    """Test that generated recipe scripts pass validation."""

    def test_recipe_script_passes(self):
        from td_mcp.tools.templates import recipe_to_script
        result = recipe_to_script("audio_reactive_basic")
        assert "error" not in result
        assert "script" in result

    def test_all_recipes_pass(self):
        from td_mcp.tools.templates import BUILTIN_RECIPES, recipe_to_script
        for name in BUILTIN_RECIPES:
            result = recipe_to_script(name)
            assert "error" not in result, f"Recipe {name} failed: {result.get('error')}"

    def test_unknown_recipe(self):
        from td_mcp.tools.templates import recipe_to_script
        result = recipe_to_script("nonexistent_recipe")
        assert "error" in result

    def test_malicious_network_path(self):
        from td_mcp.tools.templates import recipe_to_script
        result = recipe_to_script("audio_reactive_basic", "'); import os; op('")
        assert "error" in result

    def test_list_recipes_all(self):
        from td_mcp.tools.templates import list_recipes
        result = list_recipes()
        assert "recipes" in result
        assert result["count"] > 0

    def test_list_recipes_by_category(self):
        from td_mcp.tools.templates import list_recipes
        result = list_recipes(category="audio_reactive")
        assert all(r["category"] == "audio_reactive" for r in result["recipes"])

    def test_list_recipes_invalid_category(self):
        from td_mcp.tools.templates import list_recipes
        result = list_recipes(category="nonexistent")
        assert result["count"] == 0

    def test_get_recipe_valid(self):
        from td_mcp.tools.templates import get_recipe
        result = get_recipe("lfo_modulator")
        assert "name" in result
        assert result["name"] == "lfo_modulator"

    def test_get_recipe_invalid(self):
        from td_mcp.tools.templates import get_recipe
        result = get_recipe("nonexistent")
        assert "error" in result
        assert "available" in result


class TestDAWMapping:
    """Test DAW mapping script generation."""

    def test_osc_mapping(self):
        from td_mcp.tools.templates import create_daw_mapping_script
        from td_mcp.models import DAWMapping
        mapping = DAWMapping(
            source_type="osc",
            source_channel="/track/1/volume",
            target_op="/project1/geo1",
            target_par="ty",
        )
        result = create_daw_mapping_script(mapping)
        assert "script" in result
        assert "osc" in result["script"].lower()

    def test_midi_cc_mapping(self):
        from td_mcp.tools.templates import create_daw_mapping_script
        from td_mcp.models import DAWMapping
        mapping = DAWMapping(
            source_type="midi_cc",
            source_channel="1",
            target_op="/project1/geo1",
            target_par="ty",
        )
        result = create_daw_mapping_script(mapping)
        assert "script" in result

    def test_invalid_source_type(self):
        from td_mcp.models import DAWMapping
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            DAWMapping(
                source_type="websocket",
                source_channel="ch1",
                target_op="/project1/geo1",
                target_par="ty",
            )

    def test_quote_injection_target_op(self):
        from td_mcp.tools.templates import create_daw_mapping_script
        from td_mcp.models import DAWMapping
        mapping = DAWMapping(
            source_type="osc",
            source_channel="/track/1",
            target_op="/project1'); import os; op('",
            target_par="ty",
        )
        result = create_daw_mapping_script(mapping)
        assert "error" in result

    def test_quote_injection_source_channel(self):
        from td_mcp.tools.templates import create_daw_mapping_script
        from td_mcp.models import DAWMapping
        mapping = DAWMapping(
            source_type="osc",
            source_channel="'; import os; #",
            target_op="/project1/geo1",
            target_par="ty",
        )
        result = create_daw_mapping_script(mapping)
        assert "error" in result

    def test_backslash_injection(self):
        from td_mcp.tools.templates import create_daw_mapping_script
        from td_mcp.models import DAWMapping
        mapping = DAWMapping(
            source_type="osc",
            source_channel="\\x6f\\x73",
            target_op="/project1/geo1",
            target_par="ty",
        )
        result = create_daw_mapping_script(mapping)
        assert "error" in result
