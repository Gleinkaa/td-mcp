"""Python script safety validator for TouchDesigner execution.

Validates generated scripts before sending to TD's run_script endpoint.
Rejects dangerous patterns: file I/O, network calls, imports, eval/exec chains.
"""

from __future__ import annotations

import ast
import re

# Regex for validating TD operator paths (alphanumeric, slashes, underscores, dots, hyphens)
TD_PATH_RE = re.compile(r"^[/a-zA-Z0-9_.\-]+$")

# Forbidden module imports
BLOCKED_IMPORTS = {
    "os", "sys", "subprocess", "shutil", "pathlib",
    "socket", "http", "urllib", "requests", "ftplib",
    "pickle", "shelve", "marshal",
    "ctypes", "importlib",
    "__builtin__", "builtins",
}

# Forbidden function calls — includes `run` (equivalent to exec in TD)
BLOCKED_CALLS = {
    "eval", "exec", "compile", "__import__", "run",
    "open", "input", "breakpoint",
    "globals", "locals", "vars",
    "getattr", "setattr", "delattr",
    "type",
}

# Forbidden attribute access patterns
BLOCKED_ATTRS = {
    "__class__", "__bases__", "__subclasses__",
    "__globals__", "__builtins__",
    "__code__", "__func__", "__dict__",
    "__mro__", "__qualname__",
}

# Allowed TD-specific globals (run removed — it's equivalent to exec)
ALLOWED_TD_GLOBALS = {
    "op", "ops", "me", "parent", "ipar", "ext",
    "tdu", "td", "absTime", "mod",
    "project", "ui", "sop", "top", "chop", "dat", "comp", "mat",
}


def validate_td_path(path: str) -> tuple[bool, str]:
    """Validate that a TD operator path is safe for interpolation.

    Returns (is_safe, reason).
    """
    if not path:
        return False, "Empty path"
    if not TD_PATH_RE.match(path):
        return False, f"Invalid path characters: {path!r}"
    return True, "OK"


def validate_td_script(script: str) -> tuple[bool, str]:
    """Validate a Python script is safe to execute in TouchDesigner.

    Returns (is_safe, reason). If is_safe is False, reason explains why.
    """
    if not script or not script.strip():
        return False, "Empty script"

    # Length limit — no mega-scripts
    if len(script) > 10_000:
        return False, f"Script too long ({len(script)} chars, max 10000)"

    # Try to parse as valid Python
    try:
        tree = ast.parse(script)
    except SyntaxError as e:
        return False, f"Syntax error: {e}"

    for node in ast.walk(tree):
        # Block imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split(".")[0]
                if root_module in BLOCKED_IMPORTS:
                    return False, f"Blocked import: {alias.name}"

        if isinstance(node, ast.ImportFrom):
            if node.module:
                root_module = node.module.split(".")[0]
                if root_module in BLOCKED_IMPORTS:
                    return False, f"Blocked import: {node.module}"

        # Block dangerous function calls
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BLOCKED_CALLS:
                return False, f"Blocked call: {func.id}()"
            if isinstance(func, ast.Attribute) and func.attr in BLOCKED_CALLS:
                return False, f"Blocked call: .{func.attr}()"

        # Block dangerous attribute access
        if isinstance(node, ast.Attribute):
            if node.attr in BLOCKED_ATTRS:
                return False, f"Blocked attribute access: .{node.attr}"

    # Regex fallback for string-based evasion
    dangerous_patterns = [
        (r'__import__\s*\(', "String-based __import__"),
        (r'getattr\s*\(.*,\s*["\']__', "getattr with dunder"),
        (r'\\x[0-9a-fA-F]{2}', "Hex escape (potential obfuscation)"),
        (r'\\u[0-9a-fA-F]{4}', "Unicode escape (potential obfuscation)"),
        (r'\\[0-7]{3}', "Octal escape (potential obfuscation)"),
        (r'chr\s*\(', "chr() call (potential obfuscation)"),
        (r'ord\s*\(', "ord() call (potential obfuscation)"),
    ]
    for pattern, desc in dangerous_patterns:
        if re.search(pattern, script):
            return False, f"Suspicious pattern: {desc}"

    return True, "OK"
