"""
server.py — CTF Command Center: FastAPI REST + WebSocket hub.

All 23 team members (3 Vegas on-site + 20 Singapore remote) connect here.
Vegas uses the web dashboard. Singapore uses the Telegram bot OR the dashboard.

Endpoints
---------
GET  /                          → web dashboard (serves public/index.html)
GET  /api/challenges            → list all challenges (with optional status/category filter)
POST /api/challenges            → add a new challenge
GET  /api/challenges/{id}       → challenge detail + messages
POST /api/challenges/{id}/solve → trigger agent solve in background
POST /api/challenges/{id}/flag  → manually submit a flag (human found it)
POST /api/challenges/{id}/assign → assign to a team member + profile
DELETE /api/challenges/{id}/solve → cancel a running agent job
GET  /api/scoreboard            → solved/total counts per category
WS   /ws                        → real-time event stream (all clients)

Auth: single shared team token in X-CTF-Token header (set in .env as CTF_TOKEN).
No token check on GET /  and WS /ws to simplify browser access.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import collections
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import challenge_store as store
import worker

# ── Abuse protection ──────────────────────────────────────────────────────────

MAX_CONCURRENT_AGENTS = int(os.getenv("MAX_CONCURRENT_AGENTS", "5"))
RATE_LIMIT_PER_HOUR   = int(os.getenv("RATE_LIMIT_PER_HOUR", "10"))

# ip → deque of timestamps of solve submissions in the last hour
_ip_solve_times: dict[str, collections.deque] = {}

def _check_rate_limit(ip: str) -> None:
    now = time.time()
    dq = _ip_solve_times.setdefault(ip, collections.deque())
    # Drop timestamps older than 1 hour
    while dq and now - dq[0] > 3600:
        dq.popleft()
    if len(dq) >= RATE_LIMIT_PER_HOUR:
        raise HTTPException(429, f"Rate limit: max {RATE_LIMIT_PER_HOUR} solve requests per IP per hour.")
    dq.append(now)

def _check_concurrent_limit() -> None:
    active = len(worker.active_jobs())
    if active >= MAX_CONCURRENT_AGENTS:
        raise HTTPException(429, f"Server busy: {active} agents already running (max {MAX_CONCURRENT_AGENTS}). Try again shortly.")

# ── App setup ─────────────────────────────────────────────────────────────────

store.init_db()
app = FastAPI(title="CTF Command Center", version="1.0")

PUBLIC_DIR = Path(__file__).parent / "public"
PUBLIC_DIR.mkdir(exist_ok=True)

CTF_TOKEN = os.getenv("CTF_TOKEN", "changeme")

PROFILES = ["ctf-vegas", "ctf-singapore", "ctf-solo", "ctf-team", "ctf-practice", "ctf-lite"]


# ── WebSocket broadcast ────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self._clients: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._clients.append(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._clients = [c for c in self._clients if c is not ws]

    async def broadcast(self, data: dict):
        msg = json.dumps(data)
        dead = []
        for client in list(self._clients):
            try:
                await client.send_text(msg)
            except Exception:
                dead.append(client)
        if dead:
            async with self._lock:
                self._clients = [c for c in self._clients if c not in dead]

    @property
    def count(self):
        return len(self._clients)


manager = ConnectionManager()


def _sync_broadcast(event: dict):
    """Called from worker threads — schedule coroutine on the event loop."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(manager.broadcast(event))
            )
    except Exception:
        pass


worker.set_broadcast_callback(_sync_broadcast)


# ── Auth ──────────────────────────────────────────────────────────────────────

def require_token(x_ctf_token: str = Header(default="")):
    if CTF_TOKEN != "changeme" and x_ctf_token != CTF_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid CTF token")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def dashboard():
    index = PUBLIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"message": "CTF Command Center running. Dashboard not found."})


@app.get("/api/challenges")
async def get_challenges(status: str | None = None, category: str | None = None):
    challenges = store.list_challenges(status=status, category=category)
    active = worker.active_jobs()
    for c in challenges:
        c["agent_running"] = c["id"] in active
    return challenges


@app.get("/api/challenges/{challenge_id}")
async def get_challenge(challenge_id: int):
    c = store.get_challenge(challenge_id)
    if not c:
        raise HTTPException(404, "Challenge not found")
    c["messages"] = store.get_messages(challenge_id)
    c["agent_running"] = worker.is_active(challenge_id)
    return c


class NewChallenge(BaseModel):
    title: str
    description: str
    category: str = "unknown"
    points: int = 0
    files: list[str] = []
    profile: str = "ctf-singapore"
    assigned_to: str | None = None


@app.post("/api/challenges", dependencies=[Depends(require_token)])
async def create_challenge(body: NewChallenge):
    if body.category not in store.CATEGORIES:
        raise HTTPException(400, f"category must be one of {store.CATEGORIES}")
    if body.profile not in PROFILES:
        raise HTTPException(400, f"profile must be one of {PROFILES}")
    cid = store.add_challenge(
        title=body.title,
        description=body.description,
        category=body.category,
        points=body.points,
        files=body.files,
        profile=body.profile,
        assigned_to=body.assigned_to,
    )
    await manager.broadcast({"type": "challenge_added", "challenge_id": cid, "title": body.title})
    return {"id": cid, "status": "created"}


class SolveRequest(BaseModel):
    profile: str = "ctf-singapore"
    api_key: str | None = None  # Each user supplies their own key; never stored server-side


@app.post("/api/challenges/{challenge_id}/solve", dependencies=[Depends(require_token)])
async def solve_challenge(challenge_id: int, body: SolveRequest, request: Request):
    _check_concurrent_limit()
    _check_rate_limit(request.client.host)
    c = store.get_challenge(challenge_id)
    if not c:
        raise HTTPException(404, "Challenge not found")
    if c["status"] == "solved":
        return {"status": "already_solved", "flag": c["flag"]}
    if body.profile not in PROFILES:
        raise HTTPException(400, f"profile must be one of {PROFILES}")
    submitted = worker.submit_job(challenge_id, body.profile, api_key=body.api_key or None)
    if not submitted:
        return {"status": "already_running"}
    return {"status": "submitted", "challenge_id": challenge_id, "profile": body.profile}


@app.delete("/api/challenges/{challenge_id}/solve", dependencies=[Depends(require_token)])
async def cancel_solve(challenge_id: int):
    cancelled = worker.cancel_job(challenge_id)
    if cancelled:
        store.update_challenge_status(challenge_id, "unsolved")
    return {"cancelled": cancelled}


class FlagSubmit(BaseModel):
    flag: str
    submitted_by: str = "team"


@app.post("/api/challenges/{challenge_id}/flag", dependencies=[Depends(require_token)])
async def submit_flag(challenge_id: int, body: FlagSubmit):
    c = store.get_challenge(challenge_id)
    if not c:
        raise HTTPException(404, "Challenge not found")
    store.update_challenge_status(challenge_id, "solved", flag=body.flag)
    store.add_message(challenge_id, "system", f"Flag submitted manually by {body.submitted_by}: {body.flag}")
    await manager.broadcast({
        "type": "flag_found",
        "challenge_id": challenge_id,
        "flag": body.flag,
        "title": c["title"],
        "submitted_by": body.submitted_by,
    })
    return {"status": "flag_recorded", "flag": body.flag}


class AssignRequest(BaseModel):
    assigned_to: str
    profile: str = "ctf-singapore"


@app.post("/api/challenges/{challenge_id}/assign", dependencies=[Depends(require_token)])
async def assign(challenge_id: int, body: AssignRequest):
    c = store.get_challenge(challenge_id)
    if not c:
        raise HTTPException(404, "Challenge not found")
    store.assign_challenge(challenge_id, body.assigned_to, body.profile)
    await manager.broadcast({
        "type": "assigned",
        "challenge_id": challenge_id,
        "assigned_to": body.assigned_to,
        "profile": body.profile,
    })
    return {"status": "assigned"}


@app.get("/api/scoreboard")
async def scoreboard():
    return store.scoreboard()


@app.get("/api/status")
async def server_status():
    return {
        "ws_clients": manager.count,
        "active_agents": worker.active_jobs(),
        "db": str(store.DB_PATH),
    }


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    last_event_id = store.latest_event_id()
    try:
        # Replay missed events on connect (up to last 50)
        missed = store.poll_events_since(max(0, last_event_id - 50))
        for ev in missed:
            await ws.send_text(json.dumps({
                "type": ev["type"],
                "challenge_id": ev["challenge_id"],
                **json.loads(ev["payload"]),
                "replayed": True,
            }))

        # Keep connection alive; client sends pings
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=30)
                if data == "ping":
                    await ws.send_text("pong")
            except asyncio.TimeoutError:
                await ws.send_text(json.dumps({"type": "heartbeat"}))
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(ws)
