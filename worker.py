"""
worker.py — Concurrent agent session runner.

Each challenge gets its own thread so all 23 team members can run the agent
on different challenges simultaneously without blocking each other.

Architecture:
  submit_job(challenge_id, profile) → enqueued immediately, returns job_id
  A background thread picks it up, calls solve_challenge(), streams
  messages back to challenge_store and triggers WebSocket events.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import challenge_store as store
from agent import solve_challenge

# One thread per active challenge. DEFCON typically has 50-100 challenges;
# most teams work 5-10 at a time.
_POOL = ThreadPoolExecutor(max_workers=20, thread_name_prefix="ctf-worker")

# Map challenge_id → Future so we can cancel or check status
_active: dict[int, object] = {}
_active_lock = threading.Lock()

# Optional callback invoked on every WebSocket-worthy event
_broadcast_cb: Callable[[dict], None] | None = None


def set_broadcast_callback(cb: Callable[[dict], None]) -> None:
    global _broadcast_cb
    _broadcast_cb = cb


def _notify(event: dict) -> None:
    if _broadcast_cb:
        try:
            _broadcast_cb(event)
        except Exception:
            pass


def _run_challenge(challenge_id: int, profile: str, api_key: str | None = None) -> None:
    """Worker body — runs in a thread-pool thread."""
    challenge = store.get_challenge(challenge_id)
    if not challenge:
        return

    store.update_challenge_status(challenge_id, "in_progress")
    _notify({"type": "status_changed", "challenge_id": challenge_id, "status": "in_progress"})

    description = challenge["description"]
    files_ctx   = ""
    if challenge.get("files"):
        files_ctx = "Files available in workspace/: " + ", ".join(challenge["files"])

    try:
        result = solve_challenge(
            description=description,
            extra_context=files_ctx,
            profile=profile,
            api_key=api_key,
        )
    except Exception as exc:
        store.add_message(challenge_id, "system", f"[Agent error]: {exc}")
        store.update_challenge_status(challenge_id, "unsolved")
        _notify({"type": "error", "challenge_id": challenge_id, "error": str(exc)})
        return
    finally:
        with _active_lock:
            _active.pop(challenge_id, None)

    # Persist conversation to store
    for msg in result["messages"]:
        if isinstance(msg, HumanMessage):
            store.add_message(challenge_id, "human", str(msg.content))
        elif isinstance(msg, AIMessage):
            content = str(msg.content) if msg.content else ""
            if content:
                store.add_message(challenge_id, "ai", content)
        elif isinstance(msg, ToolMessage):
            store.add_message(challenge_id, "tool", str(msg.content)[:4000], tool_name=getattr(msg, "name", None))

    flag = result.get("flag")
    iterations = result.get("iterations", 0)

    if flag:
        store.update_challenge_status(
            challenge_id,
            "solved",
            flag=flag,
            iterations=iterations,
        )
        _notify({
            "type": "flag_found",
            "challenge_id": challenge_id,
            "flag": flag,
            "title": challenge["title"],
            "iterations": iterations,
        })
    else:
        store.update_challenge_status(challenge_id, "unsolved", iterations=iterations)
        _notify({
            "type": "agent_done_no_flag",
            "challenge_id": challenge_id,
            "iterations": iterations,
        })


def submit_job(challenge_id: int, profile: str, api_key: str | None = None) -> bool:
    """
    Submit a challenge to the worker pool.

    Returns True if submitted, False if already running.
    """
    with _active_lock:
        if challenge_id in _active:
            return False
        future = _POOL.submit(_run_challenge, challenge_id, profile, api_key)
        _active[challenge_id] = future
    return True


def cancel_job(challenge_id: int) -> bool:
    """Cancel a running or queued job. Returns True if cancelled."""
    with _active_lock:
        future = _active.pop(challenge_id, None)
    if future and hasattr(future, "cancel"):
        return future.cancel()
    return False


def active_jobs() -> list[int]:
    """Return list of challenge IDs currently being solved."""
    with _active_lock:
        return list(_active.keys())


def is_active(challenge_id: int) -> bool:
    with _active_lock:
        return challenge_id in _active
