#!/usr/bin/env bash
# start-server.sh — Start the CTF Command Center (server + bot)
# Run this on the machine everyone will connect to (VPS or Singapore machine).
set -e

BOLD='\033[1m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info() { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
die()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Load .env ─────────────────────────────────────────────────────────────────
[ -f .env ] || die ".env not found. Copy .env.example and fill in values."
set -a; source .env; set +a

CTF_TOKEN="${CTF_TOKEN:-changeme}"
SERVER_PORT="${SERVER_PORT:-8000}"
SERVER_HOST="${SERVER_HOST:-0.0.0.0}"

if [ "$CTF_TOKEN" = "changeme" ]; then
  warn "CTF_TOKEN is still 'changeme' — set a real token in .env before the competition!"
fi

# ── Check dependencies ────────────────────────────────────────────────────────
python3 -c "import fastapi, uvicorn" 2>/dev/null || {
  info "Installing server dependencies…"
  pip install -r requirements-server.txt -q
}
python3 -c "import langchain, langgraph" 2>/dev/null || {
  info "Installing agent dependencies…"
  pip install -r requirements.txt -q
}

# ── Start API server ──────────────────────────────────────────────────────────
echo -e "\n${BOLD}Starting CTF Command Center${NC}"
info "API server  → http://${SERVER_HOST}:${SERVER_PORT}"
info "Dashboard   → http://<your-ip>:${SERVER_PORT}/"
info "WebSocket   → ws://<your-ip>:${SERVER_PORT}/ws"
info "Team token  → ${CTF_TOKEN}"
echo

# Run server in background
uvicorn server:app \
  --host "$SERVER_HOST" \
  --port "$SERVER_PORT" \
  --workers 1 \
  --log-level info &
SERVER_PID=$!

sleep 2
# Verify server is up
python3 -c "
import httpx, sys
try:
    r = httpx.get('http://localhost:${SERVER_PORT}/api/status', timeout=5)
    r.raise_for_status()
    print('[INFO] Server health check passed.')
except Exception as e:
    print(f'[ERROR] Server not responding: {e}', file=sys.stderr)
    sys.exit(1)
"

# ── Start Telegram bot (optional) ─────────────────────────────────────────────
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
  info "Starting Telegram bot…"
  python3 bot.py &
  BOT_PID=$!
  info "Telegram bot started (PID $BOT_PID)"
else
  warn "TELEGRAM_BOT_TOKEN not set — Telegram bot not started."
  warn "Singapore team can still use the web dashboard."
fi

echo
echo -e "${BOLD}All services running.${NC}"
echo "  Server PID: $SERVER_PID"
[ -n "$BOT_PID" ] && echo "  Bot PID:    $BOT_PID"
echo
echo "Share with your team:"
echo "  Dashboard:  http://$(curl -s ifconfig.me 2>/dev/null || echo '<your-ip>'):${SERVER_PORT}/"
echo "  Token:      ${CTF_TOKEN}"
echo
echo "Press Ctrl+C to stop all services."

# ── Wait & cleanup ────────────────────────────────────────────────────────────
trap 'echo; info "Stopping…"; kill $SERVER_PID 2>/dev/null; [ -n "$BOT_PID" ] && kill $BOT_PID 2>/dev/null; exit 0' INT TERM
wait $SERVER_PID
