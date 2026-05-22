"""
tools/python_exec.py – In-process Python execution sandbox.

Runs arbitrary Python code and captures its stdout. Useful for writing
quick exploit scripts, math computations, crypto attacks, parsing binary
data, etc., without having to write to a file first.
"""

from __future__ import annotations

import sys
import io
import traceback
import contextlib
from langchain_core.tools import tool


@tool
def python_exec(code: str) -> str:
    """
    Execute a block of Python code and return its printed output.

    Use this to:
    - Write and run pwntools exploits
    - Perform crypto math (RSA, modular arithmetic, discrete log)
    - Parse binary formats, file formats, or network captures
    - Brute-force small key spaces
    - Decode/encode data with complex transformations

    Args:
        code: Valid Python 3 source code. Use print() to produce output.

    Returns:
        Captured stdout, or a traceback on error.

    Example:
        code = "import base64; print(base64.b64decode('aGVsbG8='))"
    """
    stdout_capture = io.StringIO()
    exec_globals: dict = {"__builtins__": __builtins__}

    try:
        with contextlib.redirect_stdout(stdout_capture):
            exec(compile(code, "<ctf_agent>", "exec"), exec_globals)  # noqa: S102
        output = stdout_capture.getvalue()
        return output[:8000] if output else "(no output – did you forget to print?)"
    except Exception:
        tb = traceback.format_exc()
        return f"[PYTHON ERROR]\n{tb}"
