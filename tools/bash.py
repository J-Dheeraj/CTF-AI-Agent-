"""
tools/bash.py – Safe shell execution tool.

Runs arbitrary shell commands in a subprocess with a timeout.
Certain dangerous patterns are blocked via config.BASH_DENY_PATTERNS.
"""

from __future__ import annotations

import subprocess
import shlex
from langchain_core.tools import tool

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import BASH_DENY_PATTERNS, WORKSPACE_DIR

_TIMEOUT = 60  # seconds per command


def _is_dangerous(cmd: str) -> bool:
    return any(pat in cmd for pat in BASH_DENY_PATTERNS)


@tool
def bash_exec(command: str) -> str:
    """
    Execute a shell command and return its stdout + stderr.

    Use this for: running exploit scripts, nmap, netcat, file inspection
    (strings, xxd, file, binwalk), curl, python one-liners, etc.

    Args:
        command: The shell command to run (executed via /bin/bash -c).

    Returns:
        Combined stdout and stderr output (truncated to 8 000 chars).
    """
    if _is_dangerous(command):
        return f"[BLOCKED] Command contains a denied pattern: {command!r}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            cwd=str(WORKSPACE_DIR),
        )
        output = result.stdout + result.stderr
        if len(output) > 8000:
            output = output[:8000] + "\n... [output truncated]"
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] Command exceeded {_TIMEOUT}s: {command!r}"
    except Exception as exc:
        return f"[ERROR] {exc}"
