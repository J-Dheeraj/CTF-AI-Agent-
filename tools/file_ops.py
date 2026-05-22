"""
tools/file_ops.py – File system tools scoped to the agent workspace.

All paths are sandboxed to WORKSPACE_DIR to avoid escaping.
"""

from __future__ import annotations

import os
from pathlib import Path
from langchain_core.tools import tool

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import WORKSPACE_DIR


def _safe_path(relative: str) -> Path:
    """Resolve a relative path inside WORKSPACE_DIR. Raises if it escapes."""
    target = (WORKSPACE_DIR / relative).resolve()
    if not str(target).startswith(str(WORKSPACE_DIR.resolve())):
        raise ValueError(f"Path escapes workspace: {relative!r}")
    return target


@tool
def file_read(path: str, as_hex: bool = False) -> str:
    """
    Read a file from the agent workspace directory.

    Use this to inspect challenge files: binaries (as hex), text files,
    pcap dumps, images, etc.

    Args:
        path: Relative path inside the workspace (e.g. "challenge/flag.txt").
        as_hex: If True, return file bytes as a hex dump (for binary files).

    Returns:
        File contents as text, or hex dump if as_hex=True.
    """
    try:
        target = _safe_path(path)
        raw = target.read_bytes()
        if as_hex:
            hex_lines = []
            for i in range(0, min(len(raw), 4096), 16):
                chunk = raw[i : i + 16]
                hex_part = " ".join(f"{b:02x}" for b in chunk)
                ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                hex_lines.append(f"{i:08x}  {hex_part:<47}  |{ascii_part}|")
            return "\n".join(hex_lines)
        return raw.decode("utf-8", errors="replace")[:8000]
    except Exception as exc:
        return f"[FILE READ ERROR] {exc}"


@tool
def file_write(path: str, content: str) -> str:
    """
    Write content to a file in the agent workspace directory.

    Use this to save exploit scripts, extracted data, decoded payloads, etc.

    Args:
        path: Relative path inside the workspace.
        content: Text content to write.

    Returns:
        Confirmation message with absolute path.
    """
    try:
        target = _safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Written {len(content)} bytes → {target}"
    except Exception as exc:
        return f"[FILE WRITE ERROR] {exc}"


@tool
def file_list(directory: str = ".") -> str:
    """
    List files in a workspace directory.

    Args:
        directory: Relative path to list (default: workspace root).

    Returns:
        Newline-separated list of files with sizes.
    """
    try:
        target = _safe_path(directory)
        entries = []
        for item in sorted(target.iterdir()):
            size = item.stat().st_size if item.is_file() else 0
            kind = "DIR" if item.is_dir() else f"{size:>8} B"
            entries.append(f"  {kind}  {item.relative_to(WORKSPACE_DIR)}")
        return "\n".join(entries) or "(empty directory)"
    except Exception as exc:
        return f"[LIST ERROR] {exc}"
