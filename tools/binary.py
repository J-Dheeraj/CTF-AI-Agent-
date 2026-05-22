"""
tools/binary.py – Binary analysis helpers for pwn/rev challenges.

Wraps common static-analysis tasks that don't require pwntools interactivity.
For interactive exploits (remote/process), use python_exec with pwntools directly.

NOTE: Uses subprocess directly (not the bash_exec tool) to avoid circular imports.
"""

from __future__ import annotations

import math
import collections
import io
import os
import subprocess
import contextlib
from pathlib import Path
from langchain_core.tools import tool

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import WORKSPACE_DIR, BASH_DENY_PATTERNS

_TIMEOUT = 60


def _run(cmd: str) -> str:
    """Run a shell command and return combined stdout+stderr (up to 8 000 chars)."""
    if any(pat in cmd for pat in BASH_DENY_PATTERNS):
        return f"[BLOCKED] {cmd!r}"
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=_TIMEOUT, cwd=str(WORKSPACE_DIR))
        out = (r.stdout + r.stderr)[:8000]
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] {cmd!r}"
    except Exception as exc:
        return f"[ERROR] {exc}"


def _py(code: str) -> str:
    """Run Python code inline and capture stdout."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(code, "<binary_tool>", "exec"), {"__builtins__": __builtins__})  # noqa: S102
        return buf.getvalue()[:8000] or "(no output)"
    except Exception as exc:
        import traceback
        return traceback.format_exc()


@tool
def binary_analyze(path: str, action: str = "info") -> str:
    """
    Perform static analysis on a binary file in the workspace.

    Actions:
      info        – file type, architecture, protections (uses `file`, `checksec`)
      strings     – printable strings of length >= 6 (grep for flag patterns)
      disasm      – disassemble with objdump (first 100 instructions of main)
      sections    – list ELF sections (readelf -S)
      symbols     – list exported symbols (nm -D)
      entropy     – byte entropy per section (detect packed/encrypted regions)
      hexdump     – first 256 bytes as hex

    Args:
        path: Relative path to binary inside the workspace directory.
        action: One of the actions listed above (default: "info").

    Returns:
        Analysis output as text.
    """
    full_path = WORKSPACE_DIR / path
    if not full_path.exists():
        return f"[ERROR] File not found in workspace: {path}"

    abs_path = str(full_path.resolve())
    act = action.strip().lower()

    if act == "info":
        result = _run(f'file "{abs_path}"')
        result += "\n" + _run(f'checksec --file="{abs_path}" 2>/dev/null || echo "checksec not available"')
        result += "\n" + _run(f'readelf -h "{abs_path}" 2>/dev/null | head -20')
        return result

    if act == "strings":
        return _run(
            f'strings -n 6 "{abs_path}" | '
            r'grep -iE "(flag|ctf|key|\{|\}|pass|secret|admin|root|token)" | head -50 ; '
            f'echo "---ALL STRINGS (first 200)---" ; '
            f'strings -n 6 "{abs_path}" | head -200'
        )

    if act == "disasm":
        return _run(
            f'objdump -d -M intel "{abs_path}" 2>/dev/null | '
            'grep -A 200 "<main>:" | head -120'
        )

    if act == "sections":
        return _run(f'readelf -S "{abs_path}" 2>/dev/null')

    if act == "symbols":
        return _run(f'nm -D "{abs_path}" 2>/dev/null || nm "{abs_path}" 2>/dev/null | head -80')

    if act == "hexdump":
        return _run(f'xxd "{abs_path}" | head -16')

    if act == "entropy":
        code = f"""
import math, collections
data = open(r'{abs_path}', 'rb').read()
counts = collections.Counter(data)
total = len(data)
entropy = -sum((c/total)*math.log2(c/total) for c in counts.values())
print(f"Total bytes: {{total}}")
print(f"Byte entropy: {{entropy:.4f}} bits/byte  (8.0 = fully random / encrypted)")
for offset in range(0, min(len(data), 256*20), 256):
    chunk = data[offset:offset+256]
    if not chunk: continue
    ct = collections.Counter(chunk)
    e = -sum((v/len(chunk))*math.log2(v/len(chunk)) for v in ct.values())
    print(f"  0x{{offset:06x}}: entropy={{e:.2f}}")
"""
        return _py(code)

    return f"[ERROR] Unknown action: {action!r}. Valid: info, strings, disasm, sections, symbols, hexdump, entropy"
